# -*- coding: utf-8 -*-
"""威尔新资讯 · 一键构建。

输入：content.json（内容）+ 配图原图
输出：<name>.png（整版长图）、<name>_分片/N.png（微信分片）、<name>.pdf、第N期.html

一条命令跑完全程：
  配图裁切去水印 → 套版式生成 HTML → 本地 HTTP 渲染长图 → 缩放整版 → 空白行分片 → PDF → 版式回归校验

跨平台：Windows / macOS / Linux 通用（Python 3.8+，依赖 Pillow + Playwright）。
路径一律用 pathlib，编码一律 UTF-8，字体走三平台通用字体栈。

用法：
  python build.py --content content.json
  python build.py --content content.json --out-dir ~/Desktop/输出 --date 2026.9.25 --issue 39
"""
import argparse
import datetime
import functools
import html as html_mod
import http.server
import json
import re
import shutil
import sys
import threading
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DEFAULT_LAYOUT = SKILL_ROOT / "assets" / "layout.json"
DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "template.html"
BUNDLED_FONTS = SKILL_ROOT / "assets" / "fonts"
DEFAULT_LOGO = SKILL_ROOT / "assets" / "logo.png"

WHITE = 248


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def deep_get(d: dict, path: str, default=None):
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def parse_date(spec: str) -> datetime.date:
    """支持 '2026.9.18' / '2026-9-18' / '2026/9/18' / 'auto'（下一个周五，若今天是周五则今天）。"""
    if not spec or spec == "auto":
        today = datetime.date.today()
        return today + datetime.timedelta(days=(4 - today.weekday()) % 7)
    parts = [int(x) for x in re.split(r"[.\-/]", spec.strip())]
    if len(parts) != 3:
        raise SystemExit(f"日期格式无法识别：{spec}（应为 2026.9.18 这样）")
    return datetime.date(*parts)


def build_name(issue, date_str: str) -> str:
    """38 + 2026.9.18 -> 38_0918"""
    d = parse_date(date_str)
    return f"{issue}_{d.month:02d}{d.day:02d}"


# --------------------------------------------------------------------------- #
# 版式参数 -> CSS
# --------------------------------------------------------------------------- #
def _align_to_flex(value: str) -> str:
    return {"left": "flex-start", "center": "center", "right": "flex-end"}.get(
        str(value).lower(), "center")


def css_vars(L: dict, font_prefix: dict) -> str:
    strip, bar, brand = L["strip"], L["brandBar"], L["brand"]
    n, dl, bd = L["nav"], L["dateline"], L["body"]
    h2, fg, f = L["heading"], L["figure"], L["fonts"]
    ft = L.get("footer", {})
    lg = ft.get("logo", {})
    ru = ft.get("rule", {})

    def font(key):
        head = font_prefix.get(key, "")
        return head + f[key]

    lines = [
        ":root{",
        f"  --page-w:{L['page']['pageWidth']}px;",
        f"  --page-bg:{L['page']['background']};",
        f"  --strip-h:{strip['height']}px;",
        f"  --strip-margin-x:{strip['marginX']}px;",
        f"  --strip-gradient:{strip['gradient']};",
        f"  --bar-bg:{bar['background']};",
        f"  --bar-margin-x:{bar['marginX']}px;",
        f"  --bar-padding:{bar['padding']};",
        f"  --brand-size:{brand['size']}px;",
        f"  --brand-weight:{brand['weight']};",
        f"  --brand-line-height:{brand['lineHeight']};",
        f"  --brand-letter-spacing:{brand['letterSpacing']};",
        f"  --brand-color:{brand['color']};",
        f"  --nav-size:{n['size']}px;",
        f"  --nav-margin-top:{n['marginTop']}px;",
        f"  --nav-padding-x:{n['paddingX']}px;",
        f"  --nav-line-height:{n['lineHeight']};",
        f"  --nav-opacity:{n['opacity']};",
        f"  --nav-color:{n['color']};",
        f"  --dateline-size:{dl['size']}px;",
        f"  --dateline-weight:{dl['weight']};",
        f"  --dateline-line-height:{dl['lineHeight']};",
        f"  --dateline-letter-spacing:{dl['letterSpacing']};",
        f"  --dateline-color:{dl['color']};",
        f"  --dateline-margin:{dl['margin']};",
        f"  --body-size:{bd['size']}px;",
        f"  --body-line-height:{bd['lineHeight']}px;",
        f"  --body-color:{bd['color']};",
        f"  --body-margin-x:{bd['marginX']}px;",
        f"  --body-para-gap:{bd['paraGap']}px;",
        f"  --body-align:{bd['align']};",
        f"  --h2-size:{h2['size']}px;",
        f"  --h2-weight:{h2['weight']};",
        f"  --h2-line-height:{h2['lineHeight']};",
        f"  --h2-letter-spacing:{h2['letterSpacing']};",
        f"  --h2-color:{h2['color']};",
        f"  --h2-margin:{h2['margin']};",
        f"  --fig-w:{fg['width']}px;",
        f"  --fig-h:{fg['height']}px;",
        f"  --fig-margin-top:{fg['marginTop']}px;",
        f"  --fig-margin-bottom:{fg['marginBottom']}px;",
        f"  --fig-object-fit:{fg['objectFit']};",
        f"  --fig-radius:{fg['radius']}px;",
        f"  --footer-margin-top:{lg.get('marginTop', 130)}px;",
        f"  --footer-gap:{ft.get('bottomGap', ft.get('height', 150))}px;",
        f"  --footer-justify:{_align_to_flex(lg.get('align', 'center'))};",
        f"  --footer-logo-w:{lg.get('width', 240)}px;",
        f"  --footer-logo-opacity:{lg.get('opacity', 1)};",
        f"  --footer-rule-len:{ru.get('length', 140)}px;",
        f"  --footer-rule-t:{ru.get('thickness', 2)}px;",
        f"  --footer-rule-gap:{ru.get('gap', 44)}px;",
        f"  --footer-rule-color:{ru.get('color', '#c9cbaa')};",
        f"  --font-serif:{font('serif')};",
        f"  --font-sans:{font('sans')};",
        f"  --font-kai:{font('kai')};",
        "}",
    ]
    return "\n".join(lines)


def bundled_font_face(out_dir: Path, work_dir: Path, L: dict):
    """若 assets/fonts/ 放了字体文件，就用 @font-face 接管，实现跨机器像素一致。

    返回 (fontface_css, font_prefix)。字体文件会被复制到 <work>/fonts/ 下，
    与 HTML 同源（走本地 HTTP），不存在 file:// 的 CORS 问题。
    """
    if not BUNDLED_FONTS.is_dir():
        return "", {}

    files = [p for p in sorted(BUNDLED_FONTS.iterdir())
             if p.suffix.lower() in (".ttf", ".otf", ".woff2", ".woff")]
    if not files:
        return "", {}

    dst_dir = work_dir / "fonts"
    dst_dir.mkdir(parents=True, exist_ok=True)

    roles = {"serif": [], "sans": [], "kai": []}
    for p in files:
        low = p.name.lower()
        if any(k in low for k in ("kai", "楷")):
            roles["kai"].append(p)
        elif any(k in low for k in ("serif", "song", "宋", "ming", "明")):
            roles["serif"].append(p)
        else:
            roles["sans"].append(p)

    css, prefix = [], {}
    for role, paths in roles.items():
        if not paths:
            continue
        family = f"WB Bundled {role}"
        prefix[role] = f"'{family}',"
        for p in paths:
            target = dst_dir / p.name
            shutil.copy2(p, target)
            rel = target.relative_to(out_dir).as_posix()
            css.append(
                f"@font-face{{font-family:'{family}';"
                f"src:url('{rel}');font-weight:100 900;font-style:normal;font-display:block;}}"
            )
    return "\n".join(css), prefix


# --------------------------------------------------------------------------- #
# 页尾 logo
# --------------------------------------------------------------------------- #
def prepare_logo(L: dict, out_dir: Path, work_dir: Path, content_dir: Path,
                 verbose=True) -> str:
    """把页尾 logo 复制到产物目录（与 HTML 同源，便于本地 HTTP 访问），返回相对路径。

    素材查找顺序：layout.footer.logo.src（先按技能根、再按 content.json 所在目录）
    → 技能自带 assets/logo.png。enabled=false 或缺素材时返回空串，页尾退化为纯留白。
    """
    cfg = (L.get("footer") or {}).get("logo") or {}
    if cfg.get("enabled") is False:
        if verbose:
            print("页脚 : 已禁用 logo，页尾按纯留白输出")
        return ""

    raw = (cfg.get("src") or "").strip()
    candidates = []
    if raw:
        p = Path(raw).expanduser()
        candidates.append(p if p.is_absolute() else SKILL_ROOT / p)
        candidates.append((content_dir / raw).resolve())
    candidates.append(DEFAULT_LOGO)

    src = next((c for c in candidates if c.exists()), None)
    if src is None:
        if verbose:
            print("页脚 : 未找到 logo 素材，页尾按纯留白输出"
                  f"（可放入 {DEFAULT_LOGO}）")
        return ""

    dst_dir = work_dir / "assets"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    rel = dst.relative_to(out_dir).as_posix()
    if verbose:
        print(f"页脚 : {src.name} -> {rel}")
    return rel


def build_footer(L: dict, logo_rel: str):
    """按 layout.footer 组装页尾 HTML，返回 (inner_html, footer_class)。

    rule.mode: sides 两侧夹线 / top logo 上方一条 / none 不画线。
    """
    if not logo_rel:
        return "", ""

    ft = L.get("footer") or {}
    lg, ru = ft.get("logo") or {}, ft.get("rule") or {}
    alt = html_mod.escape(lg.get("alt", ""), quote=True)
    img = f'<img class="footer-logo" src="{logo_rel}" alt="{alt}">'

    mode = str(ru.get("mode", "sides")).lower()
    if ru.get("enabled") is False or mode == "none" or ru.get("thickness") in (0, "0"):
        return img, ""

    if mode == "top":
        return f'<span class="footer-rule top"></span>{img}', "is-top"
    return (f'<span class="footer-rule sides left"></span>{img}'
            f'<span class="footer-rule sides right"></span>', "")


# --------------------------------------------------------------------------- #
# 配图预处理
# --------------------------------------------------------------------------- #
def prep_image(entry: dict, idx: int, content_dir: Path, final_dir: Path,
               out_dir: Path, L: dict, verbose=True) -> str:
    """按 layout.image 规则裁掉 AI 水印/假 logo，返回 HTML 里可用的相对路径。"""
    from PIL import Image

    cfg = L["image"]
    src = Path(entry["src"])
    if not src.is_absolute():
        src = (content_dir / src).resolve()
    if not src.exists():
        raise SystemExit(f"配图不存在：{src}")

    prep = entry.get("prep", True)
    final_dir.mkdir(parents=True, exist_ok=True)

    if not prep:
        dst = final_dir / f"asset_{idx}{src.suffix.lower()}"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return dst.relative_to(out_dir).as_posix()

    crop = entry.get("crop", cfg["defaultCrop"])
    im = Image.open(src).convert("RGB")
    before = im.size
    if crop:
        im = im.crop(tuple(crop))
    dst = final_dir / f"asset_{idx}.jpg"
    im.save(dst, format="JPEG", quality=cfg["quality"], subsampling=cfg["subsampling"])
    if verbose:
        print(f"配图 : {src.name}  {before[0]}x{before[1]} -> {im.width}x{im.height}  ->  {dst.name}")
    return dst.relative_to(out_dir).as_posix()


# --------------------------------------------------------------------------- #
# HTML 组装
# --------------------------------------------------------------------------- #
def render_html(content: dict, L: dict, out_dir: Path, work_dir: Path,
                issue, date_str: str, template: Path, verbose=True) -> Path:
    from PIL import Image  # noqa: F401  (确保依赖缺失时报错位置清晰)

    tpl = template.read_text(encoding="utf-8")
    fontface, font_prefix = bundled_font_face(out_dir, work_dir, L)

    # 配图
    final_dir = work_dir / "final"
    html_imgs = []
    for i, sec in enumerate(content.get("sections", []), 1):
        img = sec.get("image")
        if not img or not img.get("src"):
            html_imgs.append(None)
            continue
        html_imgs.append(prep_image(img, i, Path(content["_base"]), final_dir,
                                    out_dir, L, verbose))

    # 正文
    sep = L["heading"]["separator"]
    blocks = []
    for i, sec in enumerate(content.get("sections", []), 1):
        topic = (sec.get("topic") or "").strip()
        title = (sec.get("title") or "").strip()
        head = f"{topic}{sep}{title}" if topic else title
        blocks.append(f"  <h2>{html_mod.escape(head, quote=False)}</h2>")

        paras = sec.get("paragraphs") or sec.get("text") or []
        if isinstance(paras, str):
            paras = [paras]
        for p in paras:
            blocks.append(f"  <p>{html_mod.escape(p.strip(), quote=False)}</p>")

        if html_imgs[i - 1]:
            alt = html_mod.escape(sec.get("image", {}).get("alt", ""), quote=False)
            blocks.append(f'  <figure><img src="{html_imgs[i - 1]}" alt="{alt}"></figure>')

    # 导航词
    nav_html = "".join(
        f"<span>{html_mod.escape(w, quote=False)}</span>"
        + (f"<span>{html_mod.escape(L['nav']['separator'], quote=False)}</span>"
           if i < len(L["nav"]["words"]) - 1 else "")
        for i, w in enumerate(L["nav"]["words"])
    )

    dateline = L["dateline"]["template"].format(date=date_str, issue=issue)

    # 页尾 logo + 分割线
    logo_rel = prepare_logo(L, out_dir, work_dir, Path(content["_base"]), verbose)
    logo_html, footer_class = build_footer(L, logo_rel)

    out = (tpl
           .replace("{{PAGE_TITLE}}", html_mod.escape(f"{L['brand']['text']} 第{issue}期", quote=False))
           .replace("{{CSS_VARS}}", css_vars(L, font_prefix))
           .replace("{{FONTFACE}}", fontface)
           .replace("{{BRAND}}", html_mod.escape(L["brand"]["text"], quote=False))
           .replace("{{NAV_HTML}}", nav_html)
           .replace("{{LOGO_HTML}}", logo_html)
           .replace("{{FOOTER_CLASS}}", footer_class)
           .replace("{{DATELINE}}", html_mod.escape(dateline, quote=False))
           .replace("{{SECTIONS_HTML}}", "\n".join(blocks)))

    html_path = out_dir / f"第{issue}期.html"
    html_path.write_text(out, encoding="utf-8")
    if verbose:
        print(f"HTML : {html_path}")
    return html_path


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(root: Path):
    handler = functools.partial(_QuietHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


BROWSER_CANDIDATES = [
    (None, "chromium 自带内核"),
    ("chrome", "系统 Chrome"),
    ("msedge", "系统 Edge"),
]


def launch_browser(p, prefer=None):
    """按 chromium → Chrome → Edge 依次尝试，任何一个能起就行（Playwright 里后两者是 channel）。"""
    order = [(None, "chromium 自带内核")]
    if prefer:
        target = None if prefer in ("chromium", "chromium-bundled") else prefer
        order = [(target, prefer)] + [c for c in BROWSER_CANDIDATES if c[0] != target]
    else:
        order = BROWSER_CANDIDATES

    errs = []
    for channel, label in order:
        try:
            b = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
            return b, label
        except Exception as e:  # noqa: BLE001
            errs.append(f"  - {label}: {str(e).splitlines()[0][:90]}")
    raise SystemExit("无法启动任何浏览器，请先安装：\n"
                     "  python -m playwright install chromium\n"
                     "（或本机装 Chrome / Edge 任一即可）\n尝试记录：\n" + "\n".join(errs))


def render(html_path: Path, out_dir: Path, work_dir: Path, L: dict, name: str,
           browser=None, verbose=True):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("缺少 playwright，请先安装：\n"
                         "  pip install pillow playwright\n"
                         "  python -m playwright install chromium")

    out_cfg = L["output"]
    page_w = L["page"]["pageWidth"]

    httpd, port = serve(out_dir)
    url = f"http://127.0.0.1:{port}/{urllib.parse.quote(html_path.name)}"
    raw_png = work_dir / "out" / f"{name}-raw.png"
    raw_png.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{name}.pdf"

    try:
        with sync_playwright() as p:
            b, used = launch_browser(p, browser)
            if verbose:
                print(f"浏览器: {used}")
            ctx = b.new_context(viewport={"width": page_w, "height": 1200},
                                device_scale_factor=out_cfg["scale"])
            page = ctx.new_page()
            page.goto(url, wait_until="load")
            page.wait_for_function("() => Array.from(document.images).every(i => i.complete)")
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(400)
            page.screenshot(path=str(raw_png), full_page=True)
            if verbose:
                print(f"渲染 : {raw_png}")

            page.pdf(path=str(pdf_path), width=f"{out_cfg['pdfWidth']}px",
                     print_background=True)
            if verbose:
                print(f"PDF  : {pdf_path}")
            b.close()
    finally:
        httpd.shutdown()

    return raw_png, pdf_path


# --------------------------------------------------------------------------- #
# 导出与校验
# --------------------------------------------------------------------------- #
def export(raw_png: Path, out_dir: Path, name: str, L: dict, verbose=True):
    from PIL import Image
    sys.path.insert(0, str(HERE))
    from split_long_image import split_long_image

    out_cfg = L["output"]
    im = Image.open(raw_png).convert("RGB")
    if im.width != out_cfg["width"]:
        im = im.resize((out_cfg["width"], round(im.height * out_cfg["width"] / im.width)),
                       Image.LANCZOS)
    full = out_dir / f"{name}.png"
    im.save(full, "PNG")
    if verbose:
        print(f"整版 : {full}  {im.width}x{im.height}")

    segs = split_long_image(im, out_dir, name, out_cfg["maxSegmentHeight"], verbose=verbose)
    return full, segs


# ---------- 版式回归校验（纯 Pillow，不依赖 numpy） ---------- #
def _mask(image_l, box, mode, thresh):
    region = image_l.crop(box) if box else image_l
    if mode == "light":
        return region.point(lambda v: 255 if v > thresh else 0)
    return region.point(lambda v: 255 if v < thresh else 0)


def _extent(mask, min_ratio=0.02):
    """量出 mask 里墨迹的行范围与列范围。列投影只在检测到的行带内做，否则会被大片空白稀释。"""
    from PIL import Image

    dens_y = list(mask.resize((1, mask.height), Image.BOX).getdata())
    ys = [i for i, v in enumerate(dens_y) if v >= 255 * min_ratio]
    if not ys:
        return None
    band = mask.crop((0, ys[0], mask.width, ys[-1] + 1))
    trans = band.transpose(Image.TRANSPOSE)
    dens_x = list(trans.resize((1, trans.height), Image.BOX).getdata())
    xs = [i for i, v in enumerate(dens_x) if v >= 255 * min_ratio]
    if not xs:
        return None
    return ys[0], ys[-1], xs[0], xs[-1]


def _green_mask(im):
    from PIL import Image, ImageChops
    solid = Image.new("RGB", im.size, (178, 179, 130))
    diff = ImageChops.difference(im, solid)
    r, g, b = diff.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return mx.point(lambda v: 255 if v <= 25 else 0)


def verify(full_png: Path, L: dict, verbose=True) -> bool:
    from PIL import Image

    base = L["baseline"]
    tol = base["tolerance"]
    im = Image.open(full_png).convert("RGB")
    if im.width != L["page"]["pageWidth"]:
        im = im.resize((L["page"]["pageWidth"], round(im.height * L["page"]["pageWidth"] / im.width)),
                       Image.LANCZOS)
    gray = im.convert("L")

    checks = []

    green = _green_mask(im)
    e = _extent(green, 0.5)
    if e:
        checks.append(("绿块行范围", (e[0], e[1]), tuple(base["brandBarRows"])))

    e = _extent(_mask(gray, (100, 70, 1180, 330), "light", 225))
    if e:
        checks.append(("标题 ink 高", e[1] - e[0] + 1, base["titleInkHeight"]))
        checks.append(("标题 ink 宽", e[3] - e[2] + 1, base["titleInkWidth"]))

    # 导航词：取样下限要留在绿块内，否则会把它下面的白色页边当成「白字」
    e = _extent(_mask(gray, (70, 336, 1210, 400), "light", 215))
    if e:
        checks.append(("导航词行带", (e[0] + 336, e[1] + 336), tuple(base["navBandRows"])))

    e = _extent(_mask(gray, (0, 415, im.width, 565), "dark", 140))
    if e:
        checks.append(("日期 ink 高", e[1] - e[0] + 1, base["datelineInkHeight"]))

    def near(a, b):
        if isinstance(a, tuple):
            return all(abs(x - y) <= tol for x, y in zip(a, b))
        return abs(a - b) <= tol

    ok = True
    if verbose:
        print("\n版式校验（1x 稿宽 %dpx，容差 ±%dpx）" % (L["page"]["pageWidth"], tol))
        for label, got, want in checks:
            good = near(got, want)
            ok = ok and good
            print(f"  {'PASS' if good else 'WARN'}  {label}: 实测 {got}  基准 {want}")
        if not ok:
            print("  提示：偏差通常是字体不同导致（本机没装 Noto Serif SC 会回退到系统宋体）。"
                  "\n        需要跨机器完全一致，请把字体文件放进 assets/fonts/。")
    return ok


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="威尔新资讯 · 一键构建长图")
    ap.add_argument("--content", required=True, help="content.json 路径")
    ap.add_argument("--layout", default=str(DEFAULT_LAYOUT), help="版式参数（默认技能自带）")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="HTML 模板")
    ap.add_argument("--out-dir", help="成品输出目录（默认取 content.json 的 output.dir）")
    ap.add_argument("--name", help="成品文件名前缀，如 38_0918（默认按 期号+日期 生成）")
    ap.add_argument("--issue", help="覆盖期号")
    ap.add_argument("--date", help="覆盖日期，如 2026.9.25")
    ap.add_argument("--browser", help="指定浏览器：chromium / chrome / msedge")
    ap.add_argument("--only-html", action="store_true", help="只生成 HTML，不渲染")
    ap.add_argument("--no-pdf", action="store_true", help="不生成 PDF")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    verbose = not args.quiet

    content_path = Path(args.content).expanduser().resolve()
    if not content_path.exists():
        raise SystemExit(f"找不到内容文件：{content_path}")
    content = load_json(content_path)
    content["_base"] = str(content_path.parent)
    L = load_json(Path(args.layout).expanduser().resolve())

    issue = args.issue or content.get("issue")
    if not issue:
        raise SystemExit("content.json 里缺少 issue（期号），也没有 --issue")
    date_str = args.date or content.get("date") or "auto"
    d = parse_date(date_str)
    date_str = f"{d.year}.{d.month}.{d.day}"

    out_dir = Path(args.out_dir or deep_get(content, "output.dir") or content_path.parent
                   ).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_work"
    name = args.name or deep_get(content, "output.name") or build_name(issue, date_str)

    if verbose:
        print(f"刊期 : 第{issue}期 · {date_str}   成品前缀 {name}")
        print(f"输出 : {out_dir}")

    html_path = render_html(content, L, out_dir, work_dir, issue, date_str,
                            Path(args.template).expanduser().resolve(), verbose)
    if args.only_html:
        return 0

    raw_png, pdf_path = render(html_path, out_dir, work_dir, L, name, args.browser, verbose)
    if args.no_pdf and pdf_path.exists():
        pdf_path.unlink()
    full_png, segs = export(raw_png, out_dir, name, L, verbose)
    verify(full_png, L, verbose)

    if verbose:
        print("\n交付：")
        print(f"  {full_png}")
        for p, a, b in segs:
            print(f"  {p}")
        if pdf_path.exists():
            print(f"  {pdf_path}")
        print(f"  {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
