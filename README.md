# 威尔新资讯 · 排版工具包

把一份内容（`content.json`）+ 几张配图，一条命令出成「威尔新资讯」周报长图。
版式与公司往期完全一致（1744px 宽竖版长图，含报头、导航词、日期期号、通栏配图、微信分片）。
**内容和排版是分开的**：文案可以人工审核后随便改，改完重跑一次，版式不会跑偏。

支持 Windows / macOS / Linux。

---

## 一、安装（每台电脑只需一次）

需要 Python 3.8 以上：

```bash
pip install pillow playwright
python -m playwright install chromium
```

> Windows 若 `pip` 不认，用 `py -m pip install ...`。
> 本机已有 Chrome 或 Edge 的话，最后一步可以跳过（脚本会自动回退到系统浏览器）。

装完自检一下：

```bash
python scripts/check_env.py
```

看到「结论：可以出图」就成了。

---

## 二、三步出图

### 1. 准备内容文件

复制 `assets/content.example.json` 为 `content.json`（可以放在任何目录），改这三处：

```jsonc
{
  "issue": 39,                          // 期号
  "date": "auto",                       // "auto" = 本周五；也可写死 "2026.9.25"
  "output": { "dir": "输出目录", "name": "" },   // name 留空则自动生成 39_0925

  "sections": [
    {
      "topic": "电商大促",               // 主题词
      "title": "正标题",                 // 最终呈现：电商大促｜正标题
      "paragraphs": ["正文，每条不超过 250 字（含标点）"],
      "image": { "src": "配图路径.png" }  // 可选 crop 覆盖裁切，prep:false 表示不再裁
    }
    // …建议 3 条
  ]
}
```

配图放哪都行，`src` 写绝对路径或相对 content.json 的路径都可以。

### 2. 核字数（硬规矩：每条 ≤250 字）

```bash
python scripts/count_chars.py content.json --limit 250
```

### 3. 出图

```bash
python scripts/build.py --content content.json
```

跑完会打印成品路径和一段**版式校验**（跟往期的基准比对了绿块位置、大标题、导航词、日期）：

```
整版 : .../38_0918.png  1744x4856
版式校验（1x 稿宽 1280px，容差 ±6px）
  PASS  绿块行范围: 实测 (61, 405)  基准 (61, 405)
  PASS  标题 ink 高: 实测 200  基准 202
  …
```

全 PASS 就可以发了。出现 WARN 见下面的常见问题。

---

## 三、产出物

| 文件 | 用途 |
|---|---|
| `<name>.png` | **整版长图**，直接发群（微信里记得勾「原图」） |
| `<name>_分片/1.png …` | 微信分片，怕长图被压糊时逐张发；切点落在空白行，不会切断文字 |
| `<name>.pdf` | 可缩放版 |
| `第<期号>期.html` | 源文件，浏览器可直接打开看 |
| `_work/` | 中间产物（裁好的配图、渲染原图），删掉不影响 |

---

## 四、常用参数

```bash
python scripts/build.py --content content.json \
  --out-dir ~/Desktop/输出 \    # 改输出目录
  --issue 40 --date 2026.10.2 \ # 临时改期号/日期
  --only-html \                 # 只生成 HTML 不出图（想先在浏览器里看效果）
  --no-pdf                      # 不生成 PDF
```

一次性工具：

```bash
# 只把渲染好的长图切整版+分片（不重新渲染）
python scripts/split_long_image.py 长图.png --out-dir . --name 39_0925 --width 1744
```

---

## 五、想改版式

所有尺寸、配色、字号、字体、输出规格都在 **`assets/layout.json`** 里，改完直接重跑 `build.py`：

```jsonc
"brand":   { "size": 212 },            // 大标题字号
"nav":     { "size": 35, "marginTop": 66 },
"figure":  { "width": 1100, "height": 500 },   // 图片框架
"footer":  {                                    // 页尾品牌落款
  "logo": { "width": 240, "opacity": 0.92, "marginTop": 130 },
  "rule": { "mode": "sides", "length": 140, "thickness": 2,
            "gap": 44, "color": "#c9cbaa" },     // logo 两侧的分割线
  "bottomGap": 150
},
"output":  { "width": 1744, "maxSegmentHeight": 3400 }
```

改完记得同步更新同文件里的 `baseline`（校验基准），或临时接受 WARN。
`template.html` 里全是 CSS 变量，正常**不需要**动它。

---

## 六、常见问题

**Q：字号/间距跟往期差几个像素？**
A：多半是这台电脑缺 `Noto Serif SC`（大标题用的宋体），回退到了系统宋体，字面宽窄略有差别。
不影响观感。要跨机器完全一致，把字体文件放进 `assets/fonts/`（见该目录里的 README）。

**Q：提示找不到浏览器？**
A：跑 `python -m playwright install chromium`；或本机装 Chrome / Edge，脚本会自动回退。

**Q：配图上还有 AI 水印？**
A：默认裁切 `(0,145,1536,843)` 已能去掉右下角水印和顶部假 logo。个别图残留的话，
在该板块的 `image.crop` 里写 `[x0, y0, x1, y1]` 手动多裁一点。

**Q：想加一条 / 减一条？**
A：`sections` 数组里增删一项即可，版式会自动适配（每增一条版面约多 800–900px 高）。

**Q：二维码呢？**
A：2026-09-15 起页尾不再放二维码，改为**品牌 logo 落款**。要换 logo，直接覆盖 `assets/logo.png`
（透明 PNG 最好，先把四周透明边裁掉）；要调大小改 `layout.json` → `footer.logo.width`；
logo 两侧那条线的颜色/长度/粗细在 `footer.rule` 里；不想要 logo 就设 `footer.logo.enabled: false`。
详见 `references/layout-spec.md` 第六节。

---

## 七、目录结构

```
├─ SKILL.md                 技能主文档（含完整流程与踩坑记录）
├─ README.md                本文件
├─ CHANGELOG.md             版本更新记录
├─ references/
│  ├─ layout-spec.md        版式规格（逐像素参数、图片框架、校验基准）
│  └─ content-guide.md      内容口径（字数/品类/平台白名单/文风/检索方向）
├─ assets/
│  ├─ layout.json           版式参数（唯一来源）
│  ├─ template.html         HTML 模板
│  ├─ content.example.json  内容模板
│  ├─ logo.png              页尾品牌落款素材
│  └─ fonts/                可选字体（跨机器一致用）
└─ scripts/
   ├─ build.py              一键构建
   ├─ split_long_image.py   整版/分片
   ├─ count_chars.py        字数核验
   └─ check_env.py          环境自检
```

---

## 八、版本与更新

工具包用 git 管理，打标签发版（当前 `v1.1.1`），改动记录见 `CHANGELOG.md`。

**第一次拿到（推荐克隆，而不是下载 zip）**：

```bash
git clone https://github.com/ysunwellber/wellber-weekly.git wellber-weekly
cd wellber-weekly
pip install pillow playwright && python -m playwright install chromium
python scripts/check_env.py
```

**以后拿最新版**：

```bash
git pull
```

> 你自己的文案和配图不要提交进仓库（`.gitignore` 已排除 `_work/`、`*_content.json`、
> `out/`、`*.zip`、`*.pdf`），所以 `git pull` 不会覆盖你的内容文件。
