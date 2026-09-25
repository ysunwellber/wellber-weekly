# -*- coding: utf-8 -*-
"""正文/段落字数核验（威尔新资讯）。

孙哥的硬约束：每条正文 ≤250 字（含标点）。初稿经常写到 300+，交稿前必须跑一遍。

用法：
  python count_chars.py <文本文件或 .html 或 content.json>  [--limit 250]
  直接把文字从 stdin 管道进来也可以：  echo "..." | python count_chars.py --stdin

.html 会提取所有 <p>...</p> 段落；.txt/.md 按空行分段；
content.json 会逐条取 sections[].paragraphs（按条汇总，标签为「主题词｜正标题」）。
统计口径：len(去空白后的字符串)，即含中文标点，与孙哥口径一致。
"""
import argparse
import html as html_mod
import json
import re
import sys


def texts_from_html(raw: str):
    body = re.sub(r"<style[\s\S]*?</style>", "", raw, flags=re.I)
    body = re.sub(r"<script[\s\S]*?</script>", "", body, flags=re.I)
    out = []
    for m in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", body, flags=re.I):
        t = re.sub(r"<[^>]+>", "", m.group(1))
        t = html_mod.unescape(t).replace("&nbsp;", " ")
        out.append(t)
    return out


def texts_from_plain(raw: str):
    return [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]


def texts_from_content_json(raw: str):
    """content.json：一个板块算一条（该板块所有段落合并计字），标签 = 主题词｜正标题。"""
    data = json.loads(raw)
    out = []
    for sec in data.get("sections", []) or []:
        paras = sec.get("paragraphs") or []
        body = "".join(p for p in paras if isinstance(p, str))
        if not body.strip():
            continue
        topic = sec.get("topic") or ""
        title = sec.get("title") or ""
        label = f"{topic}｜{title}" if topic or title else "(未命名板块)"
        out.append((label, body))
    return out


def count(t: str) -> int:
    return len(re.sub(r"\s+", "", t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--stdin", action="store_true")
    a = ap.parse_args()

    if a.stdin or not a.path:
        raw = sys.stdin.read()
        blocks = [(f"第{i}段", t) for i, t in enumerate(texts_from_plain(raw), 1)]
    else:
        with open(a.path, encoding="utf-8") as f:
            raw = f.read()
        low = a.path.lower()
        if low.endswith(".json"):
            try:
                blocks = texts_from_content_json(raw)   # [(标签, 正文)]
            except Exception as e:
                print(f"content.json 解析失败：{e}")
                return 1
        elif low.endswith((".html", ".htm")):
            blocks = [(f"第{i}段", t) for i, t in enumerate(texts_from_html(raw), 1)]
        else:
            blocks = [(f"第{i}段", t) for i, t in enumerate(texts_from_plain(raw), 1)]

    if not blocks:
        print("没有解析到正文段落")
        return 1

    over = 0
    total = 0
    is_json = bool(a.path) and a.path.lower().endswith(".json")
    for i, (lab, b) in enumerate(blocks, 1):
        n = count(b)
        total += n
        flag = "OK  " if n <= a.limit else "OVER"
        if n > a.limit:
            over += 1
        head = lab if is_json else f"第{i}段"
        print(f"{flag} {head} {n} 字  (上限 {a.limit}, 超 {max(0, n - a.limit)})")
        if n > a.limit:
            print(f"      {b[:60]}...")
    print(f"\n合计 {len(blocks)} 段 / {total} 字；超限 {over} 段")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
