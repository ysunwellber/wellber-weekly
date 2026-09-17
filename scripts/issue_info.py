#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威尔新资讯 · 刊期确认（期号 + 发布日期）

每期开工前的第一步。推出：

    上期期号  →  本期期号（= 上期 + 1）  →  发布日期（默认本周五）  →  目标文件名

并检查这个日期是否已经有成品（提前做过的情况），供孙哥确认后再往下走。

期号怎么定（v1.5.1 起，两条硬规则）：

    规则一 · 时间锚点：期号 = 锚点期号 + 周差
        锚点写在 assets/issues.json 的 baseline —— 当前是 38 期 = 2026-09-18（周五）。
        发布日期落在哪一周，期号就是那一周的数；差几周就加几期，不再靠"上期 +1"累加。

    规则二 · 时间没到，就不能 +1（孙哥 2026-09-15 定）
        目录里有没有成品、这一期做没做过，统统不算数。只有发布日期真的推进了一周，
        期号才 +1。所以目录里就算躺着一个误建的 39 期（0925），本期该是 38 还是 38。

    覆盖顺序：--last-issue（手动指定）> 时间锚点推算 > 扫项目目录（兜底，仅当没锚点）
    目录扫描的结果只用来告警，不参与期号推算。

为什么改：纯扫目录会被"误建的期"带偏。2026-09-15 出过一次——目录里有个误建的
39 期（0925），扫描直接把本期算成 40 期，配的日期却是 0918。锚点就是为了根治这个。

用法：
    # 默认：台账优先 + 扫目录兜底 + 本周五
    python scripts/issue_info.py --project-dir "C:/Users/Yang/Pictures/威尔新资讯"

    # 指定发布日期（不是周五发就传这个）
    python scripts/issue_info.py --project-dir "..." --date 2026-10-02

    # 孙哥说上期是多少，就用手动指定（优先级最高）
    python scripts/issue_info.py --project-dir "..." --last-issue 39

    # 往台账里记一条（已存在则覆盖日期）
    python scripts/issue_info.py --add 38=2026-09-18

    # 不用台账，纯扫目录（排查台账写错时用）
    python scripts/issue_info.py --project-dir "..." --no-ledger

    # 机读（Agent 拼 AskUserQuestion 用）
    python scripts/issue_info.py --project-dir "..." --json

退出码：0 正常；2 参数/数据有问题。
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# 刊期台账（v1.5.1）：期号的权威来源，扫目录只是兜底
LEDGER_PATH = SKILL_ROOT / "assets" / "issues.json"

# 成品命名约定：<期号>_<月日>.<png|jpg|pdf>
_ARTIFACT_RE = re.compile(r"^(?P<issue>\d{1,3})_(?P<mmdd>\d{4})\.(?P<ext>png|jpg|jpeg|pdf)$", re.I)
# 内容存档：<期号>_content.json
_CONTENT_RE = re.compile(r"^(?P<issue>\d{1,3})_content\.json$", re.I)


# ---------------------------------------------------------------- 输出工具

def _safe(s: str) -> str:
    """控制台可能是 GBK，遇到编不出的字符就地降级，别让脚本崩。"""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        s.encode(enc)
    except (UnicodeEncodeError, LookupError):
        s = s.encode(enc, "replace").decode(enc, "replace")
    return s


def out(s: str = "") -> None:
    print(_safe(s))


# ---------------------------------------------------------------- 日期

def friday_of(d: datetime.date) -> datetime.date:
    """本周的周五（今天就是周五则返回今天）。"""
    return d + datetime.timedelta(days=(4 - d.weekday()) % 7)


def parse_date(s):
    """吃 '2026-09-18' / '2026.9.18' / '9.18'，吐 datetime.date；无效吐 None。"""
    if not s:
        return None
    s = str(s).strip()
    if s.lower() == "auto":
        return None
    m = re.match(r"^(?:(\d{4})[-./])?(\d{1,2})[-./](\d{1,2})$", s)
    if not m:
        return None
    y = int(m.group(1)) if m.group(1) else datetime.date.today().year
    try:
        return datetime.date(y, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def mmdd(d: datetime.date) -> str:
    return f"{d.month:02d}{d.day:02d}"


def date_label(d: datetime.date) -> str:
    return f"{d.year}.{d.month}.{d.day}"


def issue_for_date(pub, anchor_issue, anchor_date):
    """按周差推期号：锚点那一周 = anchor_issue，往后每过一周 +1，往前就 -1。

    发布日期按各自所在周的周五对齐（固定周五发布），所以 0918 和 0925 差 7 天 = 差 1 期。
    锚点不全时返回 None，交给调用方退化。
    """
    if not anchor_issue or not anchor_date:
        return None
    weeks = (friday_of(pub) - friday_of(anchor_date)).days // 7
    return anchor_issue + weeks


# ---------------------------------------------------------------- 刊期台账

def load_ledger(path=None):
    """读台账。文件不存在 / 坏了 → 返回空台账（不抛，退化成扫目录）。"""
    p = Path(path).expanduser() if path else LEDGER_PATH
    empty = {"path": str(p), "ok": False, "records": [], "baseline": {}, "max_issue": 0}
    try:
        if not p.is_file():
            return empty
        d = json.loads(p.read_text(encoding="utf-8"))
        recs = [r for r in (d.get("records") or [])
                if isinstance(r, dict) and isinstance(r.get("issue"), int)]
        recs.sort(key=lambda r: r["issue"])
        empty.update({
            "ok": True, "records": recs,
            "baseline": d.get("baseline") or {},
            "max_issue": max([r["issue"] for r in recs], default=0),
        })
        return empty
    except Exception:
        return empty


def add_record(issue, date_iso, status="draft", note="", path=None):
    """往台账里记一条（同 issue 覆盖）。返回 (台账dict, 是否新增)。"""
    p = Path(path).expanduser() if path else LEDGER_PATH
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except Exception:
        d = {}
    recs = d.setdefault("records", [])
    for r in recs:
        if isinstance(r, dict) and r.get("issue") == issue:
            r["date"] = date_iso
            if status:
                r["status"] = status
            if note:
                r["note"] = note
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return load_ledger(path), False
    recs.append({"issue": issue, "date": date_iso, "status": status,
                 **({"note": note} if note else {})})
    recs.sort(key=lambda r: r["issue"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_ledger(path), True


# ---------------------------------------------------------------- 扫描

def scan_project(project_dir):
    """扫项目目录，返回 issues / max_issue / by_mmdd。目录不存在时优雅降级。"""
    issues, by_mmdd = {}, {}
    if not project_dir or not project_dir.is_dir():
        return {"issues": issues, "max_issue": 0, "by_mmdd": by_mmdd, "scanned": False}

    for f in sorted(project_dir.iterdir()):
        if not f.is_file():
            continue
        name = f.name

        m = _ARTIFACT_RE.match(name)
        if m:
            iss, md = int(m.group("issue")), m.group("mmdd")
            rec = issues.setdefault(iss, {"issue": iss, "date": "", "artifacts": [],
                                          "has_content": False})
            rec["artifacts"].append(name)
            if not rec["date"]:
                rec["date"] = f"{int(md[:2])}.{int(md[2:])}"
            by_mmdd.setdefault(md, []).append(name)
            continue

        m = _CONTENT_RE.match(name)
        if m:
            iss = int(m.group("issue"))
            rec = issues.setdefault(iss, {"issue": iss, "date": "", "artifacts": [],
                                          "has_content": False})
            rec["has_content"] = True
            if not rec["date"]:
                try:
                    c = json.loads(f.read_text(encoding="utf-8"))
                    rec["date"] = str(c.get("date", "") or "")
                except Exception:
                    pass

    return {"issues": issues, "max_issue": max(issues) if issues else 0,
            "by_mmdd": by_mmdd, "scanned": True}


# ---------------------------------------------------------------- 结果

def compute(project_dir, last_issue=None, publish_date=None, today=None,
            use_ledger=True, ledger_path=None):
    today = today or datetime.date.today()
    scan = scan_project(project_dir)
    ledger = load_ledger(ledger_path) if use_ledger else \
        {"path": "", "ok": False, "records": [], "baseline": {}, "max_issue": 0}

    scan_max = scan["max_issue"]

    # ---------- 锚点：台账 baseline 优先，没有就从目录里最晚的一期临时借一个
    base = (ledger.get("baseline") or {}) if use_ledger else {}
    anchor_issue = base.get("issue") if isinstance(base.get("issue"), int) else None
    anchor_date = parse_date(str(base.get("date") or "")) if base.get("date") else None
    anchor_src = f"刊期台账 baseline（{Path(ledger['path']).name}）"

    if not (anchor_issue and anchor_date) and scan_max:
        dated = []
        for rec in scan["issues"].values():
            d = parse_date(str(rec.get("date") or ""))
            if d:
                dated.append((rec["issue"], d))
        if dated:
            dated.sort()
            anchor_issue, anchor_date = dated[-1]
            anchor_src = "扫项目目录（无台账，临时锚点）"
    if not (anchor_issue and anchor_date):
        anchor_src = ""

    # ---------- 发布日期
    pub = publish_date or friday_of(today)
    md = mmdd(pub)

    # ---------- 期号：只跟日期走（时间没到就不 +1）
    time_issue = issue_for_date(pub, anchor_issue, anchor_date)
    if last_issue:
        source = "手动指定"
        nxt = int(last_issue) + 1
    elif time_issue is not None:
        source = f"时间锚点推算（{anchor_src}）"
        nxt = time_issue
    else:
        source = "扫项目目录" if scan_max else "无历史"
        nxt = (scan_max or 0) + 1
    last = nxt - 1
    auto_last = last

    # ---------- 告警：目录里比本期更新的期号（误建 / 提前做），仅供参考，不改期号
    future_in_dir = [rec for rec in sorted(scan["issues"].values(), key=lambda x: x["issue"])
                     if rec["issue"] > nxt]

    taken = scan["by_mmdd"].get(md, [])
    # 该日期已被"别的期号"占用才算冲突（同名期号不算，那是同一期重出）
    conflicts = []
    for name in taken:
        m = _ARTIFACT_RE.match(name)
        if m and int(m.group("issue")) != nxt:
            conflicts.append(name)

    return {
        "today": today.isoformat(),
        "auto_last_issue": auto_last,
        "last_issue": last,
        "last_issue_source": source,
        "scan_max_issue": scan_max,
        "this_issue": nxt,
        "time_issue": time_issue,
        "anchor": {
            "issue": anchor_issue, "date": anchor_date.isoformat() if anchor_date else "",
            "source": anchor_src,
        },
        "future_in_dir": [
            {"issue": r_["issue"], "date": r_["date"], "artifacts": r_["artifacts"]}
            for r_ in future_in_dir
        ],
        "ledger": {
            "path": ledger["path"],
            "ok": ledger["ok"],
            "max_issue": ledger["max_issue"],
            "records": ledger["records"][-8:],
            "baseline": ledger["baseline"],
        },
        "next_issue": nxt,
        "publish_date": pub.isoformat(),
        "publish_date_label": date_label(pub),
        "is_friday": pub.weekday() == 4,
        "name": f"{nxt}_{md}",
        "date_taken": taken,
        "conflicts": conflicts,
        "issues": [
            {"issue": r["issue"], "date": r["date"], "artifacts": r["artifacts"],
             "has_content": r["has_content"]}
            for r in sorted(scan["issues"].values(), key=lambda x: x["issue"])
        ],
        "scanned": scan["scanned"],
        "project_dir": str(project_dir) if project_dir else "",
    }


# ---------------------------------------------------------------- 渲染

def render_text(r):
    line = "=" * 62
    out()
    out(line)
    out("  威尔新资讯 · 刊期确认")
    out(line)

    if not r["scanned"]:
        out("  没扫到项目目录，期号只能靠孙哥报。")
        out(f"    （项目目录：{r['project_dir'] or '未指定'}）")
    else:
        hist = r["issues"][-8:]
        if hist:
            txt = "  ".join(f"{h['issue']}({h['date'] or '?'})" for h in hist)
            more = f"  …共 {len(r['issues'])} 期" if len(r["issues"]) > 8 else ""
            out(f"  历史：{txt}{more}")
        else:
            out("  历史：目录里还没有成品/内容文件")

    out()
    out(f"  上期期号：{r['last_issue']}        （{r['last_issue_source']}）")

    anc = r["anchor"]
    if anc["issue"]:
        ad = date_label(datetime.date.fromisoformat(anc["date"]))
        out(f"  时间锚点：{anc['issue']} 期 = {ad}    往后每过一周 +1")
        out(f"            来源：{anc['source']}")
    else:
        out("  时间锚点：无 → 退化成扫项目目录（不推荐，会被误建的期带偏）")

    lg = r["ledger"]
    if lg["ok"]:
        tail = lg["records"][-5:]
        txt = "  ".join(f"{h['issue']}({h.get('date', '?')})" for h in tail)
        more = "  …" if len(lg["records"]) > 5 else ""
        out(f"  台账记录：{txt}{more}   最大 {lg['max_issue']}")
    elif lg["path"]:
        out(f"  台账记录：没读到（{lg['path']}）")
    else:
        out("  台账记录：未启用（--no-ledger）")

    out(f"  本期期号：{r['next_issue']}        ← 时间推算（日期定死，不看目录）")
    fri = "本周五" if r["is_friday"] else "非周五 ⚠"
    out(f"  发布日期：{r['publish_date_label']}（{fri}）")
    out(f"  目标文件名：{r['name']}.png")

    if r["future_in_dir"]:
        out()
        out("  [!] 目录里有比本期更新的成品："
            + " / ".join(f"{x['issue']}期({x['date'] or '?'})" for x in r["future_in_dir"]))
        out(f"      时间没到就不算数 —— 本期仍是 {r['next_issue']} 期，不会 +1。")
        out("      确认是误建的就清掉，别让它一直挂着碍眼。")

    if r["conflicts"]:
        out()
        out(f"  [!] {r['publish_date_label']} 这个日期已有成品：{' / '.join(r['conflicts'])}")
        out("      说明这一期是提前做的，和现在算出的期号会对不上。")
        out("      务必先跟孙哥确认：本期到底算第几期、哪天发。")
    elif r["date_taken"]:
        out()
        out(f"  （同日期已有同名文件：{' / '.join(r['date_taken'])}，属同一期重出，正常）")

    out()
    out("  → 下一步：拿这两个数跟孙哥确认（期号 / 发布日期），确认后再选题。")
    out(line)


def render_json(r):
    print(json.dumps(r, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="威尔新资讯 · 刊期确认")
    ap.add_argument("--project-dir", default="", help="项目目录，用于扫描历史成品")
    ap.add_argument("--last-issue", type=int, default=0, help="手动指定上期期号（覆盖台账与扫描）")
    ap.add_argument("--date", default="", help="发布日期，如 2026-10-02；不给按本周五")
    ap.add_argument("--add", default="", help="往刊期台账记一条，如 38=2026-09-18")
    ap.add_argument("--status", default="draft", help="配合 --add 用的状态，默认 draft")
    ap.add_argument("--note", default="", help="配合 --add 用的备注")
    ap.add_argument("--no-ledger", action="store_true", help="不用刊期台账，纯扫项目目录")
    ap.add_argument("--ledger", default="", help="指定台账文件路径（默认技能 assets/issues.json）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    # 记台账：--add 38=2026-09-18
    if args.add:
        m = re.match(r"^\s*(\d{1,3})\s*=\s*(.+?)\s*$", args.add)
        if not m:
            print(_safe(f"--add 格式不对：{args.add}（示例：38=2026-09-18）"), file=sys.stderr)
            return 2
        iss = int(m.group(1))
        d = parse_date(m.group(2))
        if d is None:
            print(_safe(f"日期看不懂：{m.group(2)}（示例：2026-09-18）"), file=sys.stderr)
            return 2
        led, created = add_record(iss, d.isoformat(), status=args.status,
                                  note=args.note, path=args.ledger or None)
        verb = "新增" if created else "更新"
        out(f"  已{verb}台账：{iss} 期 = {date_label(d)}"
            f"  （{Path(led['path']).name}，现共 {len(led['records'])} 条，最大 {led['max_issue']}）")
        return 0

    project_dir = Path(args.project_dir).expanduser() if args.project_dir else None
    pub = parse_date(args.date)

    if args.date and pub is None:
        print(_safe(f"日期看不懂：{args.date}（示例：2026-10-02 / 2026.10.2 / 10.2）"),
              file=sys.stderr)
        return 2

    r = compute(project_dir, last_issue=args.last_issue or None, publish_date=pub,
                use_ledger=not args.no_ledger, ledger_path=args.ledger or None)

    if args.json:
        render_json(r)
    else:
        render_text(r)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(_safe(f"出错了：{e}"), file=sys.stderr)
        sys.exit(2)
