#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威尔新资讯 · 选题候选生成

读 assets/topics.json（领域池）+ 扫项目目录里的历史 *_content.json，
算出每个领域「最近一次被用过是哪期」，据此给出本期的候选领域，
目的是让每期选题轮换起来，不再固定那三条线。

用法：
    # 本期候选（默认 4 个）
    python scripts/topic_menu.py --project-dir "C:/Users/Yang/Pictures/威尔新资讯"

    # 指定刊期日期（不给我按今天算）
    python scripts/topic_menu.py --project-dir "..." --date 2026-09-25

    # 看完整领域池
    python scripts/topic_menu.py --list-all

    # 机读输出（给 Agent 拼 AskUserQuestion 用）
    python scripts/topic_menu.py --project-dir "..." --json

退出码：0 正常；2 参数/数据有问题。
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POOL = SKILL_ROOT / "assets" / "topics.json"

# 上期刚用过的领域扣多少分（足以把它挤出推荐，但仍列在「上期已用」里供回选）
STREAK_PENALTY = 80
# 从未被用过的领域加多少分
FRESH_BONUS = 60
# 当季加分
SEASON_BONUS = 25
# 距上次使用的间隔加分：gap 期 × 系数，封顶
GAP_STEP = 15
GAP_CAP = 50

_CONTENT_RE = re.compile(r"^(?P<issue>\d+)_content\.json$", re.IGNORECASE)


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


# ---------------------------------------------------------------- 数据读取

def load_pool(path=None) -> list:
    p = Path(path) if path else DEFAULT_POOL
    if not p.exists():
        raise SystemExit(f"找不到领域池文件：{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    pool = data.get("pool") or []
    if not pool:
        raise SystemExit(f"领域池是空的：{p}")
    for e in pool:
        e.setdefault("name", "")
        e.setdefault("desc", "")
        e.setdefault("keywords", [])
        e.setdefault("sources", [])
        e.setdefault("months", [])
        e.setdefault("weight", 0)
        e.setdefault("aliases", [])
    return pool


def parse_date(s, default=None):
    """吃 '2026-09-18' / '2026.9.18' / '2026/9/18' / '9.18'，吐 (year, month, day)。"""
    import datetime
    if not s:
        return default
    s = str(s).strip()
    if s.lower() == "auto":
        return default
    m = re.match(r"^(?:(\d{4})[-./])?(\d{1,2})[-./](\d{1,2})$", s)
    if not m:
        return default
    y = int(m.group(1)) if m.group(1) else (default[0] if default else datetime.date.today().year)
    return (y, int(m.group(2)), int(m.group(3)))


def scan_history(project_dir: Path) -> list:
    """扫出历史内容文件里的 issue / date / topics。目录不存在或无文件时返回 []。"""
    if not project_dir or not project_dir.is_dir():
        return []
    hist = []
    for f in sorted(project_dir.glob("*_content.json")):
        # 跳过 _top_test.json 这类临时文件
        if f.name.startswith("_"):
            continue
        m = _CONTENT_RE.match(f.name)
        if not m:
            continue
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        topics = [str(s.get("topic", "")).strip()
                  for s in (c.get("sections") or []) if isinstance(s, dict)]
        topics = [t for t in topics if t]
        if not topics:
            continue
        hist.append({
            "issue": int(m.group("issue")),
            "date": str(c.get("date", "")),
            "file": f.name,
            "topics": topics,
        })
    hist.sort(key=lambda h: h["issue"], reverse=True)
    return hist


def build_seen(hist: list, pool: list) -> dict:
    """领域名 -> 最近一次出现的期号。历史主题词经 aliases 归一到领域名。"""
    alias = {}
    for e in pool:
        alias[e["name"]] = e["name"]
        for a in e["aliases"]:
            alias[a] = e["name"]
    seen = {}
    for h in hist:
        for t in h["topics"]:
            name = alias.get(t)
            if not name:
                continue  # 池子里没有的旧主题词，忽略
            prev = seen.get(name)
            if prev is None or h["issue"] > prev:
                seen[name] = h["issue"]
    return seen


# ---------------------------------------------------------------- 评分

def score_entry(entry: dict, month: int, max_issue: int, seen: dict):
    name = entry["name"]
    last = seen.get(name)
    s = entry.get("weight", 0)
    tags = []

    if last is None:
        s += FRESH_BONUS
        tags.append("从未覆盖")
    else:
        gap = max_issue - last
        s += min(GAP_CAP, max(0, gap) * GAP_STEP)
        if gap == 0:
            s -= STREAK_PENALTY
            tags.append("上期刚用")
        elif gap >= 2:
            tags.append(f"距上次{gap}期")
        else:
            tags.append("上期用过")

    if month and month in (entry.get("months") or []):
        s += SEASON_BONUS
        tags.append("当季")

    return s, tags


def rank(pool: list, hist: list, month: int, count: int):
    max_issue = max((h["issue"] for h in hist), default=0)
    seen = build_seen(hist, pool)

    # 主题词别名反查，用于展示「上期用过哪些」
    alias = {}
    for e in pool:
        for a in e["aliases"]:
            alias[a] = e["name"]

    scored = []
    for e in pool:
        s, tags = score_entry(e, month, max_issue, seen)
        scored.append((e, s, tags, seen.get(e["name"])))

    # 推荐：排除上期刚用过的
    fresh = [x for x in scored if "上期刚用" not in x[2]]
    fresh.sort(key=lambda x: (-x[1], pool.index(x[0])))
    recommended = fresh[:count]

    # 上期用过的（含别名归一后的原名）
    last_issue = max_issue
    last_topics = []
    for h in hist:
        if h["issue"] == last_issue:
            for t in h["topics"]:
                last_topics.append(t)
    return {
        "max_issue": last_issue,
        "seen": seen,
        "scored": scored,
        "recommended": recommended,
        "last_topics": last_topics,
    }


# ---------------------------------------------------------------- 渲染

def render_text(pool, hist, res, month, project_dir, count):
    line = "=" * 62
    out()
    out(line)
    out(f"  威尔新资讯 · 选题候选" + (f"（{month} 月）" if month else ""))
    out(line)

    if not hist:
        out("  历史覆盖：没找到历史内容文件（*_content.json）")
        out("           按「从未覆盖 + 当季」直接给候选，无法做轮换判断。")
        if project_dir:
            out(f"           扫过的目录：{project_dir}")
    else:
        out(f"  历史覆盖（扫到 {len(hist)} 份内容文件）")
        for h in hist[:6]:
            d = h["date"] or "?"
            mark = " " if h["issue"] != res["max_issue"] else "*"
            out(f"   {mark}{h['issue']:>3}期({d})  " + " / ".join(h["topics"]))
        if len(hist) > 6:
            out(f"        ...（更早的 {len(hist) - 6} 份省略）")

        rep = [t for t in res["last_topics"]]
        if rep:
            out()
            out(f"  [!] 上期（{res['max_issue']}期）已用：{' / '.join(rep)}")
            out("      这期换一换，读者才不会觉得期期一个模子。")

    out()
    out(f"  本期推荐候选（{len(res['recommended'])} 个）")
    if not res["recommended"]:
        out("     （领域池太小，没有可推荐的了）")
    for i, (e, s, tags, last) in enumerate(res["recommended"], 1):
        # 没有历史时「从未覆盖」这类轮换标签不可信，只留当季
        shown = tags if hist else [t for t in tags if t == "当季"]
        tag = " ".join(f"[{t}]" for t in shown) if shown else ""
        out(f"   [{i}] {e['name']}")
        out(f"       {e['desc']}   {tag}")
    out()
    out(f"  领域池共 {len(pool)} 个，看全部：python scripts/topic_menu.py --list-all")
    out(line)


def render_list_all(pool, month):
    out()
    out("=" * 62)
    out(f"  威尔新资讯 · 选题领域池（共 {len(pool)} 个）")
    out("=" * 62)
    for i, e in enumerate(pool, 1):
        seasons = "/".join(str(m) for m in e["months"]) if e["months"] else "全年"
        star = " *当季" if (month and month in e["months"]) else ""
        out(f"  {i:>2}. {e['name']}（{seasons}）{star}")
        out(f"      {e['desc']}")
        out(f"      关键词：{'、'.join(e['keywords'][:4])}")
    out("=" * 62)


def render_json(pool, hist, res, month, project_dir):
    payload = {
        "month": month,
        "history": [{"issue": h["issue"], "date": h["date"], "topics": h["topics"]} for h in hist],
        "last_issue": res["max_issue"],
        "last_topics": res["last_topics"],
        "recommended": [
            {
                "rank": i,
                "name": e["name"],
                "desc": e["desc"],
                "keywords": e["keywords"],
                "sources": e["sources"],
                "score": s,
                "tags": tags,
                "last_used_issue": last,
            }
            for i, (e, s, tags, last) in enumerate(res["recommended"], 1)
        ],
        "pool_size": len(pool),
        "pool": [{"name": e["name"], "desc": e["desc"], "months": e["months"]} for e in pool],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="威尔新资讯 · 选题候选生成")
    ap.add_argument("--project-dir", default="", help="项目目录，用于扫历史 *_content.json")
    ap.add_argument("--date", default="", help="刊期日期，如 2026-09-25；不给按今天算")
    ap.add_argument("--count", type=int, default=4, help="推荐候选个数（默认 4）")
    ap.add_argument("--pool", default="", help="领域池 json 路径（默认 assets/topics.json）")
    ap.add_argument("--list-all", action="store_true", help="列出完整领域池")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    import datetime
    today = datetime.date.today()
    d = parse_date(args.date, (today.year, today.month, today.day))
    month = d[1] if d else today.month

    pool = load_pool(args.pool or None)

    if args.list_all:
        render_list_all(pool, month)
        return 0

    project_dir = Path(args.project_dir).expanduser() if args.project_dir else None
    hist = scan_history(project_dir)
    res = rank(pool, hist, month, max(1, args.count))

    if args.json:
        render_json(pool, hist, res, month, project_dir)
    else:
        render_text(pool, hist, res, month, project_dir, args.count)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(_safe(f"出错了：{e}"), file=sys.stderr)
        sys.exit(2)
