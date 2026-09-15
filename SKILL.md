---
name: weili-weekly-briefing
description: 制作「威尔新资讯」公司周报竖版长图（童装/母婴/电商行业资讯，每周五发公司群）。当用户要求"做本周/本期威尔新资讯""公司简报周报""按往期模板出一期长图""每周五发群里的简报""只要排版不要内容""按模板出图给人审"时使用。内含已逆向还原的完整版式参数（尺寸/配色/字体/字号，含日期期号与图片框架）、一键构建脚本（内容 JSON 进，整版长图/微信分片/PDF 出）、版式回归校验，跨 Windows/macOS/Linux。
agent_created: true
---

# 威尔新资讯 · 公司周报长图

孙哥团队每周五发到群里的内部简报，竖版长图，1744px 宽。往期样例在
`C:\Users\Yang\Pictures\威尔新资讯\`：`34_0821.png` / `35_0828.png` / `36_0904.png` / `37_0911.jpg`。

**排版和内容是解耦的**：排版只认一个 `content.json`（期号、日期、三个板块的标题/正文/配图），
所以文案可以人工审核后随便改，改完重跑一次命令即可，版式不会跑偏。

---

## 一、两条使用路径

### 路径 A · 只要排版（做图的人 / 审核的人）

```bash
# 0) 新机器第一次：自检环境
python scripts/check_env.py

# 1) 拿内容模板改文案
cp <技能目录>/assets/content.example.json ./content.json

# 2) 一条命令出全套
python scripts/build.py --content content.json
```

产出（默认落在 `content.json` 里 `output.dir` 指定的目录，或 content.json 同目录）：

| 文件 | 说明 |
|---|---|
| `<name>.png` | 整版长图 1744px 宽，直接发群 |
| `<name>_分片/N.png` | 微信分片，在空白行处切，不切断文字 |
| `<name>.pdf` | 可缩放版 |
| `第<期号>期.html` | 源文件（图片走相对路径，可直接在浏览器打开） |
| `_work/` | 中间产物：裁好的配图 `final/`、渲染原始图 `out/` |

`<name>` 默认按 `期号_月日` 生成（第38期 + 2026.9.18 → `38_0918`）。

### 路径 B · 内容 + 排版（孙哥的完整流程）

1. **检索新闻**：按 `references/content-guide.md` 的 5 条线跑 `WebSearch`（`freshness: d10`）。
2. **先列清单**（含来源与关键数字）→ `AskUserQuestion` 一次问清：收录哪几条 / 配图方式 / 刊期日期。
   **不能跳过这一步**。配图若用 AI 生成，要先告知额度消耗。
3. **写 `content.json`**，跑 `count_chars.py` 核字数（每条 ≤250 字）。
4. **生成配图**：`ImageGen`，`size:1536x1024`、`quality:high`，提示词末尾加 `no text, no watermark`。
5. **跑 `build.py`** 出成品，看版式校验是否全 PASS。
6. **`present_files`** 交付；提醒孙哥微信发图勾**原图**。

---

## 二、文件地图

```
weili-weekly-briefing/
├─ SKILL.md                      ← 本文件（总入口）
├─ README.md                     ← 给团队成员看的独立说明书（可单独转发）
├─ references/
│  ├─ layout-spec.md             ← 版式规格 + 图片框架 + 日期期号 + 校验基准 + WARN 排查
│  └─ content-guide.md           ← 内容口径（250字/品类相关性/平台白名单/文风/检索方向）
├─ assets/
│  ├─ layout.json                ← 【版式参数唯一来源】尺寸/配色/字号/字体栈/输出规格/校验基准
│  ├─ template.html              ← HTML 模板（全部用 CSS 变量，不写死数值）
│  ├─ content.example.json       ← 内容文件模板（含逐字段说明）
│  ├─ logo.png                   ← 页尾品牌落款（wellber 威尔贝鲁，透明 PNG；换 logo 直接覆盖它）
│  └─ fonts/                     ← 可选：放字体文件实现跨机器像素一致（见目录内 README）
└─ scripts/
   ├─ build.py                   ← 一键构建：配图裁切 → HTML → 渲染 → 整版/分片/PDF → 校验
   ├─ split_long_image.py        ← 长图整版/空白行分片（纯 Pillow，无 numpy）
   ├─ count_chars.py             ← 正文段落字数核验（≤250 字）
   └─ check_env.py               ← 环境自检（依赖/浏览器/中文字体）
```

**要改版式，一律改 `assets/layout.json`**，不要去改 template.html 里的数值。
**要改文案，一律改 `content.json`**，不要手工去改生成的 HTML。

---

## 三、跨平台

技能设计上就是跨平台的（Windows / macOS / Linux），已经处理掉这几件事：

| 平台差异 | 处理方式 |
|---|---|
| 中文字体不同 | 三个字体栈覆盖三平台（Noto / 思源 / 苹方 / 冬青 / 微软雅黑 / 文泉驿 / 楷体系）。详见 `references/layout-spec.md` 第七节 |
| 路径分隔符与盘符 | 全部 `pathlib`，`--content` / `--out-dir` 支持相对路径与 `~` |
| 编码 | 所有读写显式 UTF-8，不受 Windows 默认 GBK 影响 |
| file:// 页面的 CORS / 图片加载 | **不再用 file://**，`build.py` 起本地 HTTP 服务渲染，`@font-face` 与相对路径图片都可靠 |
| 浏览器来源 | chromium 自带内核 → 系统 Chrome → 系统 Edge 依次回退（Playwright 里后两者是 channel） |
| 依赖 | 只要 Pillow + Playwright，**已去掉 numpy** |

**唯一会有差异的是字体渲染**：没有 `Noto Serif SC` 的机器会回退到系统宋体，大标题的 ink 宽高可能差几像素
（实测容差内；macOS 的 Songti SC 字面略窄）。需要**跨机器像素完全一致**，把字体文件放进 `assets/fonts/`，
`build.py` 会自动生成 `@font-face` 并优先使用。详见 `assets/fonts/README.md`。

出图后 `build.py` 会自动做版式回归校验（绿块行范围 / 标题 ink / 导航带 / 日期），有偏差会打印 WARN 与排查提示。

---

## 四、坑位清单（踩过的）

- **分片不要按高度等分**：会把文字行切断，也会整段切在配图中间。
  `split_long_image.py` 现在是「理想切点 ±300 内找**真·空白行**（非白像素 <1%），找不到就放宽到 ±600 / ±1200，最后才退化成取最小值」。
- **别用 canvas 测中文宽度去判断字体**：中文字宽恒等于 1em，测不出差别，**必须渲染截图目视比对**。
- **导航词是楷体、35px**：原来估成 38px，实测行带偏高 5px，校到 35px 才对得上原版（y 360–390）。
- **AI 配图必裁**：右下角有水印（y≈865–905），顶部 0–145 常有模型臆造的假英文 logo。
  统一裁 `(0,145,1536,843)` 得 1536×698（2.2:1，正好等于画框比例，不再二次裁切）。
- **页尾不放二维码**（孙哥 2026-09-15 明确删除），改为**品牌 logo 落款**：`assets/logo.png`
  显示宽 240px（稿宽）、居中、不透明度 0.92，两侧各一条 140×2px 浅橄榄 `#c9cbaa` 分割线
  （呼应页眉绿块）。参数全在 `layout.json` → `footer`，换 logo 直接覆盖 `assets/logo.png` 即可。
  注意 `footer.bottomGap` 是 **logo 下方留白**，不是容器总高（曾把语义写错，导致下方只剩一半）。
- **Chromium 截图有高度上限**（约 16384px）。成品 5000~7300px，安全；若正文异常长要留意。
- **微信发图要勾「原图」**，否则长图会被压糊 —— 交付时要提醒。

## 五、相关文件位置（孙哥这台机器）

- 项目目录：`C:\Users\Yang\Pictures\威尔新资讯\`
- 本期内容存档：`C:\Users\Yang\Pictures\威尔新资讯\38_content.json`
- Python：`C:\Users\Yang\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
- 每周五 09:00 有定时任务「威尔新资讯 · 每周五电商新闻简报」自动跑路径 B
- **本技能目录本身是一个 git 仓库**（分支 `main`，已打标签 `v1.1.0`），用于版本管理和分发给团队。
  改完版式后建议：`git add -A && git commit -m "..." && git tag v1.x.0 && git push --follow-tags`，
  同事侧 `git pull` 即可拿到更新（比传 zip 省事）。
  `.gitignore` 已排除 `_work/`、`*_content.json`、`out/`、`*.zip`、`*.pdf`，个人文案不会误提交。
  注意：仓库是**私有**的，包内含 wellber 品牌 logo 与刊名，不要改成公开。
