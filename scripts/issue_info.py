#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威尔新资讯 · 刊期确认（期号 + 发布日期）

每期开工前的第一步。扫项目目录，推出：

    上期期号  →  本期期号（= 上期 + 1）  →  发布日期（默认本周五）  →  目标文件名

并检查这个日期是否已经有成品（提前做过的情况），供孙哥确认后再往下走。

用法：
    # 默认：扫项目目录 + 本周五
    python scripts/issue_info.py --project-dir "C:/Users/Yang/Pictures/威尔新资讯"

    # 指定发布日期（不是周五发就传这个）
    python scripts/issue_info.py --project-dir "..." --date 2026-10-02

    # 孙哥说上期是多少，就用手动指定（覆盖自动扫描）
    python scripts/issue_info.py --project-dir "..." --last-issue 39

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

def compute(project_dir, last_issue=None, publish_date=None, today=None):
    today = today or datetime.date.today()
    scan = scan_project(project_dir)

    auto_last = scan["max_issue"]
    last = int(last_issue) if last_issue else auto_last
    nxt = last + 1

    pub = publish_date or friday_of(today)
    md = mmdd(pub)

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
        "last_issue_source": "手动指定" if last_issue else ("扫项目目录" if auto_last else "无历史"),
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
    out(f"  本期期号：{r['next_issue']}        ← 上期 + 1")
    fri = "本周五" if r["is_friday"] else "非周五 ⚠"
    out(f"  发布日期：{r['publish_date_label']}（{fri}）")
    out(f"  目标文件名：{r['name']}.png")

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
    ap.add_argument("--last-issue", type=int, default=0, help="手动指定上期期号（覆盖自动扫描）")
    ap.add_argument("--date", default="", help="发布日期，如 2026-10-02；不给按本周五")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser() if args.project_dir else None
    pub = parse_date(args.date)

    if args.date and pub is None:
        print(_safe(f"日期看不懂：{args.date}（示例：2026-10-02 / 2026.10.2 / 10.2）"),
              file=sys.stderr)
        return 2

    r = compute(project_dir, last_issue=args.last_issue or None, publish_date=pub)

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
