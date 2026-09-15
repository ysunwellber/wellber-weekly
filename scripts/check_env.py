# -*- coding: utf-8 -*-
"""威尔新资讯排版技能 · 环境自检。

新机器上第一件事就跑这个：确认 Python/依赖/浏览器/中文字体齐不齐。
用法：
  python check_env.py
"""
import importlib
import os
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent

OK, BAD, WARN = "[OK]  ", "[缺失]", "[注意]"


def check_python():
    v = sys.version_info
    good = v >= (3, 8)
    print(f"{OK if good else BAD} Python {platform.python_version()}  ({platform.system()} {platform.machine()})")
    return good


def check_module(name, hint):
    try:
        m = importlib.import_module(name)
        ver = getattr(m, "__version__", "")
        print(f"{OK} {name} {ver}")
        return True
    except ImportError:
        print(f"{BAD} {name} 未安装 —— {hint}")
        return False


def check_browsers():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"{BAD} 无法检查浏览器（playwright 未安装）")
        return False

    ok = False
    with sync_playwright() as p:
        for channel, label in ((None, "chromium 自带内核"), ("chrome", "系统 Chrome"), ("msedge", "系统 Edge")):
            try:
                b = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
                b.close()
                print(f"{OK} 浏览器可用: {label}")
                ok = True
            except Exception as e:  # noqa: BLE001
                print(f"{WARN} 浏览器不可用: {label}  （非必需，有其一即可）")
    if not ok:
        print("       请执行：python -m playwright install chromium")
    return ok


def font_dirs():
    system = platform.system()
    if system == "Windows":
        dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
    elif system == "Darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
    else:
        dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                Path.home() / ".local/share/fonts", Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


ROLE_KEYWORDS = {
    "serif（大标题宋体）": ("notoserifsc", "notoserifcjk", "sourcehanserif", "songti", "stsong",
                          "simsun", "fzshusong", "fzsong", "sun-ext"),
    "sans（正文本黑）": ("notosanssc", "notosanscjk", "sourcehansans", "pingfang", "hiraginosansgb",
                       "msyh", "simhei", "yahei", "wqy", "wenquanyi", "droidsansfallback"),
    "kai（导航词楷体）": ("kaiti", "stkaiti", "kaiti sc", "tw-kai", "ukai", "simkai", "fzkai"),
}


def check_fonts():
    dirs = font_dirs()
    names = []
    for d in dirs:
        try:
            names += [p.name for p in d.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc", ".otc")]
        except OSError:
            pass
    low = [n.lower() for n in names]
    print(f"       扫描字体目录 {len(dirs)} 个，字体文件 {len(names)} 个")

    all_ok = True
    for role, keys in ROLE_KEYWORDS.items():
        hit = sorted({n for n, l in zip(names, low) if any(k in l for k in keys)})
        if hit:
            print(f"{OK} {role}: {', '.join(hit[:3])}{' …' if len(hit) > 3 else ''}")
        else:
            all_ok = False
            print(f"{BAD} {role}: 未找到（会用系统兜底字体，版式可能有几像素偏差）")

    bundled = SKILL_ROOT / "assets" / "fonts"
    files = [p.name for p in bundled.iterdir()] if bundled.is_dir() else []
    files = [f for f in files if Path(f).suffix.lower() in (".ttf", ".otf", ".woff2")]
    if files:
        print(f"{OK} 技能自带字体: {', '.join(files)}（跨机器像素一致）")
    else:
        print(f"{WARN} 未放自带字体。本机使用没问题；想让别的电脑输出完全一致，"
              f"可把字体文件放进 assets/fonts/（见该目录 README）")
    return all_ok


def main():
    print("=" * 62)
    print("威尔新资讯 · 排版环境自检")
    print("=" * 62)
    a = check_python()
    b = check_module("PIL", "pip install pillow")
    c = check_module("playwright", "pip install playwright")
    d = check_browsers() if c else False
    e = check_fonts()
    print("=" * 62)
    if a and b and c and d:
        print("结论：可以出图。直接跑：")
        print("  python scripts/build.py --content <你的 content.json>")
    else:
        print("结论：先按上面的提示补齐依赖，再跑 build.py")
    if not e:
        print("（字体缺失不阻塞出图，只是版式可能与基准差几像素）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
