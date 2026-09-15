# -*- coding: utf-8 -*-
"""正文/段落字数核验（威尔新资讯）。

孙哥的硬约束：每条正文 ≤250 字（含标点）。初稿经常写到 300+，交稿前必须跑一遍。

用法：
  python count_chars.py <文本文件或 .html>  [--limit 250]
  直接把文字从 stdin 管道进来也可以：  echo "..." | python count_chars.py --stdin

.html 会提取所有 <p>...</p> 段落；.txt/.md 按空行分段。
统计口径：len(去空白后的字符串)，即含中文标点，与孙哥口径一致。
"""
import argparse
import html as html_mod
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
        blocks = texts_from_plain(raw)
    else:
        with open(a.path, encoding="utf-8") as f:
            raw = f.read()
        blocks = texts_from_html(raw) if a.path.lower().endswith((".html", ".htm")) else texts_from_plain(raw)

    if not blocks:
        print("没有解析到正文段落")
        return 1

    over = 0
    total = 0
    for i, b in enumerate(blocks, 1):
        n = count(b)
        total += n
        flag = "OK  " if n <= a.limit else "OVER"
        if n > a.limit:
            over += 1
        print(f"{flag} 第{i}段 {n} 字  (上限 {a.limit}, 超 {max(0, n - a.limit)})")
        if n > a.limit:
            print(f"      {b[:60]}...")
    print(f"\n合计 {len(blocks)} 段 / {total} 字；超限 {over} 段")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
