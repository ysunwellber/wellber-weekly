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

> **内容从哪来**：每期走定死的四关 —— ① 确认刊期（按时间锚点推本期期号 + 发布日期）
> ② 问公司头条（固定第一条）③ 选领域（14 个领域轮换，自动避开上期用过的）④ 定向搜新闻。
> 细则见 `references/topic-menu.md`。**内容边界写死**：业务只写国内电商 / 本地线下母婴集合店 /
> 欧美跨境亚马逊三条线，品类限婴童纺织用品与童装，每条 ≤250 字、每期最多 5 条（含头条）。
> 本节只管把拿到手的文案变成图。

### 1. 准备内容文件

复制 `assets/content.example.json` 为 `content.json`（可以放在任何目录），改这几处：

```jsonc
{
  "issue": 38,                          // 期号（按时间锚点推，先确认再填）
  "date": "auto",                       // "auto" = 本周五；也可写死 "2026.9.18"
  "output": { "dir": "输出目录", "name": "" },   // name 留空则自动生成 38_0918

  "sections": [
    {
      "topic": "公司头条",                // 第一条固定是头条（孙哥没给要点就整条删掉）
      "title": "本期头条的题",
      "paragraphs": ["头条正文，≤250 字。这一条必须来自孙哥，AI 不自己编。"],
      "image": { "src": "公司实拍图.png" }  // 头条配图优先用公司自己的图
    },
    {
      "topic": "电商大促",                // 其余取自当期选定的领域（可选清单 assets/topics.json）
      "title": "正标题",                  // 最终呈现：主题词｜正标题
      "paragraphs": ["正文，每条不超过 250 字（含标点）"],
      "image": { "src": "配图路径.png" }   // 可选 crop 覆盖裁切，prep:false 表示不再裁
    }
    // …含头条最多 5 条，常用 3–4 条
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

跑完顶部会自动带一条**未来一周天气**（北上广，发布日次日周六起 7 天），
数据由 7 个气象源合成，不用手工准备。不想要就加 `--no-weather`，
`--weather-refresh` 可强制重新拉数（默认有缓存就复用）。

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
  --no-pdf \                    # 不生成 PDF
  --no-weather \                # 本期不加顶部天气 banner
  --weather-refresh             # 忽略缓存重新拉天气
```

单独调试天气 banner：

```bash
python scripts/weather_banner.py --out-dir ./天气预览 --publish-date 2026-09-18 --preview
```

会输出 `weather_banner.png`（正式版式）+ A 通栏 / B 留白 / C 整页效果 三张对比图。

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
"output":  { "width": 1744, "maxSegmentHeight": 3400 },
"weather": {                                    // 顶部未来一周天气（v1.5.0）
  "enabled": true,
  "position": "after_dateline",  // 日期下面、头条上面；after_brandbar = 挪到报头下面
  "cities": ["beijing", "shanghai", "guangzhou"],
  "marginX": 90,                 // 左右留白，与正文对齐；0 = 通栏铺满
  "background": "#f6f7ee"
}
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
注意**含头条最多 5 条**。

**Q：这期该写第几期？头条写什么？**
A：先跑 `python scripts/issue_info.py --project-dir "<项目目录>"`，它会给出
「本期期号 → 发布日期（默认本周五）→ 目标文件名」。

期号**只跟时间走、不看目录**：`assets/issues.json` 的 `baseline` 是锚点（**38 期 = 2026-09-18**），
发布日期落在哪一周就取哪一周的期号，**差几周加几期；时间没到就绝不 +1**。
所以目录里就算躺着一个误建的 39 期成品，本期该 38 还是 38（脚本只告警，不顶号）。
查某天发是第几期：`--date 2026-10-02`；换锚点：`--add 38=2026-09-18`。

**期号仍要跟孙哥确认**；头条报的是公司自己的事，AI 搜不到，也得问孙哥
（他这期没有就跳过，第一条放行业新闻）。

**Q：搜新闻老是搜到无关品类怎么办？**
A：口径写死在 `references/content-guide.md` 第二节：业务只写国内电商 / 本地线下母婴集合店 /
欧美跨境亚马逊三条线，品类只写婴童纺织用品与童装。检索关键词记得冠上
`母婴` / `童装` / `婴童` 限定词。`python scripts/topic_menu.py` 每次运行也会把这段边界打印出来。

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
│  ├─ content-guide.md      内容口径（字数/品类/平台白名单/文风/流程）
│  └─ topic-menu.md         选题环节（领域池用法、提问方式、轮换规则）
├─ assets/
│  ├─ layout.json           版式参数（唯一来源）
│  ├─ template.html         HTML 模板
│  ├─ topics.json           选题领域池（14 个领域，唯一来源）
│  ├─ content.example.json  内容模板
│  ├─ logo.png              页尾品牌落款素材
│  ├─ issues.json           刊期台账（baseline = 时间锚点 38期/2026-09-18）
│  └─ fonts/                可选字体（跨机器一致用）
└─ scripts/
   ├─ build.py              一键构建
   ├─ issue_info.py         刊期确认（按时间锚点推期号）
   ├─ topic_menu.py         选题候选生成（扫历史避免与上期重复）
   ├─ split_long_image.py   整版/分片
   ├─ count_chars.py        字数核验
   └─ check_env.py          环境自检
```

---

## 八、版本与更新

工具包用 git 管理，打标签发版（当前 `v1.5.1`），改动记录见 `CHANGELOG.md`。

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
