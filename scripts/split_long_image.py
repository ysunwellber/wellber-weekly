# -*- coding: utf-8 -*-
"""把渲染出的超长 PNG 转成微信友好的产物。

产出：
  1) <name>.png          整版长图（默认缩到 1744px 宽，与往期一致）
  2) <name>_分片/N.png   竖切分片，每片 <= max-height，且在「空白行」处切，不切断文字
  3) <name>.pdf          若同目录已有同名 PDF 则一并保留（PDF 由 build.py 生成）

依赖：只用 Pillow，不需要 numpy（跨平台省事）。
用法：
  python split_long_image.py <长图.png> --out-dir <目录> --name 38_0918 --width 1744 --max-height 3400
"""
import argparse
import math
from pathlib import Path

from PIL import Image

WHITE_THRESHOLD = 248
SEGMENT_DIR_SUFFIX = "分片"


def row_density(im: Image.Image):
    """返回每行「非白像素占比」列表（0~255 的整数，越大=这一行内容越多）。

    用 Pillow 的 BOX 缩放到 1px 宽得到逐行平均值，避免引入 numpy。
    """
    gray = im.convert("L")
    binary = gray.point(lambda v: 255 if v < WHITE_THRESHOLD else 0)
    col = binary.resize((1, im.height), Image.BOX)
    return list(col.getdata())


def compute_cuts(height: int, density, max_height: int, snap: int = 300):
    """在尽量均分的前提下，把切点吸附到「真正的空白行」。

    策略（层层放宽，避免切在配图中间）：
      1) 理想切点 ±snap 内找密度 <= blank_ratio 的空白行，取最靠近理想点的；
      2) 没有就放宽到 ±2*snap 再找；
      3) 仍然没有，才退回该窗口内密度最小的一行。
    返回 cut 坐标列表（含 0 和 height）。
    """
    n = max(1, int(round(height / max_height)))
    while math.ceil(height / n) > max_height:
        n += 1

    blank_threshold = 1.0  # 行内非白像素占比 <1% 视为空白行
    cuts = [0]
    for i in range(1, n):
        target = int(i * height / n)
        best = None
        for radius in (snap, snap * 2, snap * 4):
            lo = max(1, target - radius)
            hi = min(height - 2, target + radius)
            blanks = [y for y in range(lo, hi) if density[y] <= blank_threshold]
            if blanks:
                best = min(blanks, key=lambda y: abs(y - target))
                break
        if best is None:
            lo = max(1, target - snap)
            hi = min(height - 2, target + snap)
            window = density[lo:hi]
            best = lo + min(range(len(window)), key=lambda k: window[k])
        cuts.append(best)
    cuts.append(height)
    return cuts


def split_long_image(im: Image.Image, out_dir: Path, name: str, max_height: int = 3400,
                     snap: int = 300, verbose: bool = True):
    """把长图切成 <name>_分片/N.png，返回 [(路径, 起始y, 结束y), ...]。"""
    density = row_density(im)
    cuts = compute_cuts(im.height, density, max_height, snap)

    seg_dir = Path(out_dir) / f"{name}_{SEGMENT_DIR_SUFFIX}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    for old in seg_dir.glob("*.png"):
        old.unlink()

    result = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        path = seg_dir / f"{i + 1}.png"
        im.crop((0, a, im.width, b)).save(path, "PNG")
        if verbose:
            print(f"分片 : {path}  y={a}~{b}  高={b - a}  起始行非白占比={density[a]}/255"
                  f"（下一片切点行 {density[b] if b < len(density) else 0}/255）")
        result.append((path, a, b))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="渲染得到的长图 PNG")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--name", required=True, help="输出文件名前缀，如 38_0918")
    ap.add_argument("--width", type=int, default=1744, help="成品整版宽度")
    ap.add_argument("--max-height", type=int, default=3400, help="单片最大高度")
    ap.add_argument("--snap", type=int, default=300, help="切点两侧搜索空白行的半径")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    im = Image.open(src).convert("RGB")
    if im.width != args.width:
        im = im.resize((args.width, round(im.height * args.width / im.width)), Image.LANCZOS)
    full = out / f"{args.name}.png"
    im.save(full, "PNG")
    print(f"整版 : {full}  {im.width}x{im.height}")

    split_long_image(im, out, args.name, args.max_height, args.snap)


if __name__ == "__main__":
    main()
