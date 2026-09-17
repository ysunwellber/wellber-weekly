---
name: wellber-weekly
description: 制作「威尔新资讯」公司周报竖版长图（童装/母婴/电商行业资讯，每周五发公司群）。当用户要求"做本周/本期威尔新资讯""公司简报周报""按往期模板出一期长图""每周五发群里的简报""这期写什么方向""只要排版不要内容""按模板出图给人审"时使用。流程定死为四关：先确认刊期（问上期期号推本期期号 + 发布日期）、再问公司头条（固定第一条，AI 不自编）、再选领域（14 个领域轮换，自动避开上期用过的）、最后定向搜新闻。内容边界写死：业务为国内电商 / 本地线下母婴集合店 / 欧美跨境亚马逊三条线，品类限婴童纺织用品与童装，每条正文 ≤250 字、每期最多 5 条。顶部自动加「未来一周天气」banner（北上广、发布日次日周六起 7 天、7 源交叉验证后取中位数与众数，任一源挂掉自动跳过）。内含已逆向还原的完整版式参数（尺寸/配色/字体/字号，含日期期号与图片框架）、一键构建脚本（内容 JSON 进，整版长图/微信分片/PDF 出）、版式回归校验，跨 Windows/macOS/Linux。
agent_created: true
---

# 威尔新资讯 · 公司周报长图

孙哥团队每周五发到群里的内部简报，竖版长图，1744px 宽。往期样例在
`C:\Users\Yang\Pictures\威尔新资讯\`：`34_0821.png` / `35_0828.png` / `36_0904.png` / `37_0911.jpg`。

**排版和内容是解耦的**：排版只认一个 `content.json`（期号、日期、2–4 个板块的标题/正文/配图），
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

**顺序定死，四道关不要并步、不要跳步**：

0. **刊期确认**：跑 `scripts/issue_info.py --project-dir "<项目目录>"`，拿到
   「本期期号 → 发布日期（默认本周五）→ 目标文件名」。
   **期号只看时间、不看目录**（孙哥 2026-09-15 定的硬规则）：
   `assets/issues.json` 的 `baseline` 是锚点（**38 期 = 2026-09-18**），
   发布日期落在哪一周就取哪一周的期号，**差几周加几期；时间没到就绝不 +1**。
   目录里就算躺着一个误建的 39 期（0925），本期该 38 还是 38 —— 脚本只会告警，不会顶号。
   然后**一次** `AskUserQuestion` 让孙哥确认期号与日期。脚本若报
   `[!] 该日期已有别的期号成品`，**必须原样转达**，不许自己拍板。详见 `references/topic-menu.md` 第一节。
1. **公司头条（每期必问）**：第一条固定是「公司头条」，报公司自己的事（新品/活动/渠道/数据/团队）。
   **AI 搜不到、也不许编，只能问孙哥**；他说这期没有，就跳过头条、从行业新闻排起。
   头条配图**优先用孙哥给的公司实拍/设计图**，别一上来就 AI 生成。
   头条**定稿之后**才往下走 —— 它占一条配额，会影响后面还能收几条。
2. **选题**：跑 `scripts/topic_menu.py` 生成候选领域（会扫历史、自动避开上期用过的）
   → **一次** `AskUserQuestion` 问清：本期覆盖哪些领域（多选）/ **头条之外再收几条** /
   有没有特别想跟的方向。领域池 14 个与提问细则见 `references/topic-menu.md`。
   **不要默认退回「电商大促 + 平台动向 + 跨境电商」那三件套。**
3. **定向检索**：只按选定领域的 `keywords` 跑 `WebSearch`（`freshness: d10`），每个领域 2–3 条查询。
   关键词要冠上品类限定词（`母婴` / `童装` / `婴童`），否则会搜出一堆无关大盘。
   整理成候选新闻清单（含来源与关键数字）。
4. **列清单确认**：把清单给孙哥过目 → `AskUserQuestion` 确认收录哪几条 / 配图方式。
   **不能跳过这一步**。配图若用 AI 生成，要先告知额度消耗。
5. **写 `content.json`**：**头条放第一条**，其余按选定领域排；**总数 ≤5 条**。
   跑 `count_chars.py` 核字数（每条 ≤250 字）。
6. **生成配图**：`ImageGen`，`size:1536x1024`、`quality:high`，提示词末尾加 `no text, no watermark`。
7. **跑 `build.py`** 出成品（顶部天气 banner 会自动拉 7 源合成，不用管），看版式校验是否全 PASS。
8. **`present_files`** 交付；提醒孙哥微信发图勾**原图**。

> 定时任务（每周五 09:00）无人可问：**刊期按时间锚点自算**（不会算错号，可以放心跑）、
> **跳过头条**（交付时提示"头条位留空，需要补请告诉我"）、领域按 `topic_menu.py` 推荐 top 4 走。
> 详见 `references/topic-menu.md` 第六节。

---

## 二、文件地图

```
wellber-weekly/
├─ SKILL.md                      ← 本文件（总入口）
├─ README.md                     ← 给团队成员看的独立说明书（可单独转发）
├─ references/
│  ├─ layout-spec.md             ← 版式规格 + 图片框架 + 日期期号 + 校验基准 + WARN 排查
│  ├─ content-guide.md           ← 【写死的口径】250字/最多5条/头条必问/业务三线+品类边界/文风
│  └─ topic-menu.md              ← 每期四关：刊期确认 → 公司头条 → 选题领域 → 定向检索
├─ assets/
│  ├─ layout.json                ← 【版式参数唯一来源】尺寸/配色/字号/字体栈/输出规格/校验基准
│  ├─ template.html              ← HTML 模板（全部用 CSS 变量，不写死数值）
│  ├─ topics.json                ← 【选题领域池唯一来源】14 个领域 + `_business` 业务边界
│  └─ issues.json                ← 【刊期台账】baseline 是时间锚点（38 期=2026-09-18）+ 历史刊期 + 作废记录
│  ├─ content.example.json       ← 内容文件模板（含逐字段说明）
│  ├─ logo.png                   ← 页尾品牌落款（wellber 威尔贝鲁，透明 PNG；换 logo 直接覆盖它）
│  └─ fonts/                     ← 可选：放字体文件实现跨机器像素一致（见目录内 README）
└─ scripts/
   ├─ build.py                   ← 一键构建：天气取数 → 配图裁切 → HTML → 渲染 → 整版/分片/PDF → 校验
   ├─ weather_banner.py           ← 顶部天气 banner：7 源取数 + 多源合成 + 出 HTML 片段/预览图
   ├─ issue_info.py              ← 刊期确认：按时间锚点推期号 + 发布日期，并查该日期是否已被占用
   ├─ topic_menu.py              ← 选题候选生成（读领域池 + 扫历史，避免与上期重复）
   ├─ split_long_image.py        ← 长图整版/空白行分片（纯 Pillow，无 numpy）
   ├─ count_chars.py             ← 正文段落字数核验（≤250 字）
   └─ check_env.py               ← 环境自检（依赖/浏览器/中文字体）
```

**要改版式，一律改 `assets/layout.json`**，不要去改 template.html 里的数值。
**要改文案，一律改 `content.json`**，不要手工去改生成的 HTML。

---

## 三、顶部天气 banner（v1.5.0）

「未来一周天气」自动加在**日期下面、头条上面**（`layout.json` → `weather.position`，
改成 `after_brandbar` 就挪到报头绿块下面、日期上面）。1280 稿宽下高 565px，
左右各留 90，与正文左右对齐。

- **窗口**：发布日（周五）**次日的周六 → 下周五**，共 7 天。城市北上广，改 `weather.cities`。
- **7 个数据源，全部免密钥**：Open-Meteo 四个模式（best_match / ECMWF / GFS / GEM）、
  中国气象局、中国天气网、挪威 met.no。
  **任一源挂掉自动跳过，全挂才降级到单源，再挂就整块不渲染 —— 天气永远不会拖垮整期。**
- **合成规则**（孙哥 2026-09-17 拍板 B 方案）：
  温度 = 各源**中位数**；天气 = 各源**众数**，平票时取「更轻」的那个；
  **雷雨占比 <60% 一律降级成「雨」**。GEM（加拿大模式）实测稳定离群，默认剔除。
- **为什么这么麻烦**：2026-09-17 做过 7 源交叉验证，结论是「温度可用、天气词要保守」——
  多源中位数跟单源只差 ±1~2°C，但**没有任何一天 7 个源天气完全一致**，
  第 6、7 天各源温差能到 5~10°C，而且中国气象局只发 7 天、最后两天根本没有官方数据。
  验证报告见 `_work/天气预报多渠道验证报告_2026-09-19至25.html`。
- **缓存**：数据存 `_work/weather_<起始日>.json`，重跑直接复用。
  强制刷新 `--weather-refresh`，本期不要天气 `--no-weather`。
- 单独调试看效果：
  `python scripts/weather_banner.py --out-dir <目录> --publish-date 2026-09-18 --preview`
  （出 `weather_banner.png` 与 A 通栏 / B 留白 / C 整页 三张对比图）。

---

## 四、跨平台

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

出图后 `build.py` 会自动做版式回归校验（报头是否铺满顶部与左右 / 标题 ink / 导航带 / 日期），
有偏差会打印 WARN 与排查提示。

---

## 五、坑位清单（踩过的）

- **分片不要按高度等分**：会把文字行切断，也会整段切在配图中间。
  `split_long_image.py` 现在是「理想切点 ±300 内找**真·空白行**（非白像素 <1%），找不到就放宽到 ±600 / ±1200，最后才退化成取最小值」。
- **别用 canvas 测中文宽度去判断字体**：中文字宽恒等于 1em，测不出差别，**必须渲染截图目视比对**。
- **导航词是楷体、35px**：原来估成 38px，实测行带偏高 5px，校到 35px 才对得上原版（距绿块顶 299–329）。
- **报头是铺满的**（孙哥 2026-09-15 改）：苔藓绿块从 **y=0** 开始、左右**到边**，顶部那根粉蓝渐变细条已关掉。
  开关就是 `layout.json` 里两个值：`strip.enabled`（false=不画细条）+ `brandBar.marginX`（0=铺满 / 60=旧版留白）。
  `nav.paddingX` 必须跟着等于 `body.marginX`(90)，导航词才能跟日期、正文对齐成一条竖线
  （旧版这个对齐是「绿块留白 60 + paddingX 30」叠出来的，铺满后要直接写 90）。
  报头内部比例没动，白字距绿块顶仍是 30px，和原版一致。
- **AI 配图必裁**：右下角有水印（y≈865–905），顶部 0–145 常有模型臆造的假英文 logo。
  统一裁 `(0,145,1536,843)` 得 1536×698（2.2:1，正好等于画框比例，不再二次裁切）。
- **页尾不放二维码**（孙哥 2026-09-15 明确删除），改为**品牌 logo 落款**：`assets/logo.png`
  显示宽 240px（稿宽）、居中、不透明度 0.92，两侧各一条 140×2px 浅橄榄 `#c9cbaa` 分割线
  （呼应页眉绿块）。参数全在 `layout.json` → `footer`，换 logo 直接覆盖 `assets/logo.png` 即可。
  注意 `footer.bottomGap` 是 **logo 下方留白**，不是容器总高（曾把语义写错，导致下方只剩一半）。
- **Chromium 截图有高度上限**（约 16384px）。成品 5000~7300px，安全；若正文异常长要留意。
- **内容不要框死**（孙哥 2026-09-15 提）：早期 `content-guide.md` 里写死了 5 条检索线和立意举例，
  结果期期都是「电商大促 / 平台动向 / 跨境电商」那三件套。现在改成**先选题、再定向搜**：
  `scripts/topic_menu.py` 扫历史内容文件、给候选并自动避开上期用过的领域，14 个领域轮换着来，
  领域池在 `assets/topics.json`。细则见 `references/topic-menu.md`。
- **期号不能靠扫目录推**（2026-09-15 踩过）：目录里有个误建的 39 期（0925），
  "取最大期号 +1" 直接把本期算成 40 期，配的日期却是 0918，期号日期对不上。
  现在改成**时间锚点**：`assets/issues.json → baseline` 定死 38 期 = 2026-09-18，
  `issue_info.py` 按周差推算，**目录里有什么都不影响期号**（只会告警）。
  锚点不用每期更新 —— 日期推进一周，期号自动 +1。
- **微信发图要勾「原图」**，否则长图会被压糊 —— 交付时要提醒。
- **天气别把「雷阵雨」当默认写法**：7 源交叉验证显示强词最容易夸大，
  `weather_banner.py` 里的 `THUNDER_MIN_RATIO = 0.6` 会把占比不足六成的雷雨自动降级成「雨」。
- **中国气象局的 stationid 不是区站号**：是它自己内部的城市码
  （北京 `Wqsps` / 上海 `WwcJd` / 广州 `DwzZf`），要从 `/rest/province/{ABJ,ASH,AGD}` 拿；
  填 54511 这类区站号会返回 `data:""`（空），不报错但没数据。另外它**只发 7 天**。
- **met.no 在本机证书链验证不过**（SSL: CERTIFICATE_VERIFY_FAILED），要 `ssl._create_unverified_context()`。
- **天气网格别用「父网格直接分 8 列」**：城市列 + 7 个日期列写在一个 grid 里，
  日期区会只落到第 2 列，单元格被压成 13px。正确写法是
  `.wx-row` 用 flex（城市列 `flex:none` 定宽 + 日期区 `flex:1`），日期区自己再 grid 分 7 列。
- **Playwright 截图前本地 http 服务必须绑目录**：
  `functools.partial(SimpleHTTPRequestHandler, directory=...)`，否则截到 404 页（白图）还报 ok。

## 六、相关文件位置（孙哥这台机器）

- 项目目录：`C:\Users\Yang\Pictures\威尔新资讯\`
- 历史内容存档：`38_content.json`（当前，头条还有【待补】占位）。下一期应存为 `39_content.json`。
  `topic_menu.py` 靠扫这些文件判断领域轮换，**别改名、别删**。
  注：曾经误建过一个 39 期（0925，内容已写好、图也出了），2026-09-15 按孙哥口径作废，
  成品与内容已移入回收站，`assets/issues.json` 的 `invalidated` 段留了记录。
  **教训：不要靠"目录里有没有成品"来推期号 —— 一律按时间锚点算。**
- 刊期台账：`assets/issues.json`。锚点 `baseline` = 38 期 / 2026-09-18，一般不用动；
  换锚点或补记走 `python scripts/issue_info.py --add <期号>=<日期>`。
- Python：`C:\Users\Yang\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
- 每周五 09:00 有定时任务「威尔新资讯 · 每周五电商新闻简报」自动跑路径 B
  （四关：刊期自算 → 跳过头条并提示 → 按 `topic_menu.py` 推荐 top 4 选题 → 检索成稿）
- **本技能目录本身是一个 git 仓库**（分支 `main`，已打标签 `v1.5.1`），远程 `origin` 为
  `https://github.com/ysunwellber/wellber-weekly.git`（私有仓库），用于版本管理和分发给团队。
  改完版式后建议：`git add -A && git commit -m "..." && git tag v1.x.0 && git push --follow-tags`，
  同事侧 `git pull` 即可拿到更新（比传 zip 省事）。
  `.gitignore` 已排除 `_work/`、`*_content.json`、`out/`、`*.zip`、`*.pdf`，个人文案不会误提交。
  注意：仓库是**私有**的，包内含 wellber 品牌 logo 与刊名，不要改成公开。

### 推送（本机有网络特殊性，务必先看）

**本机（孙哥电脑）访问不到 `github.com`**：直连 20s+ 超时，本机常见代理端口也连不通；
只有 `api.github.com` 通。所以**推送前必须先开代理/VPN**（系统代理或 TUN 模式均可）。

- **推荐做法**：开代理 → **双击桌面 `push-wellber-to-github.cmd`**。
  脚本会自动探测代理端口（7897 / 7890 / 10809 / 10808 / 8889 / 1080 / 7891 / 7892），
  调便携版 Git 执行 `push -u origin main --follow-tags`（标签一并推送）。
  首次会弹浏览器让你登录 GitHub，之后凭据由 GCM 缓存，不会再弹。
- 脚本探测不到端口时：记事本打开，把第 12 行 `set "PROXY=..."` 的 `REM` 去掉并改成实际端口。
- 被拒（non-fast-forward，同事也推过）时按脚本提示：先 `git pull --rebase origin main` 再重推。
- 手动等价命令（在 cmd 里，git 不在 PATH，要写全路径）：

  ```
  cd /d C:\Users\Yang\.workbuddy\skills\wellber-weekly
  "C:\Users\Yang\.workbuddy\binaries\PortableGit\versions\1.2.0\mingw64\bin\git.exe" push -u origin main --follow-tags
  ```

- 本机**没装 Git**，一直用 WorkBuddy 自带的便携版（上面那个路径），cmd 里直接敲 `git` 会报
  "不是内部或外部命令"。全局配置已设好：`credential.helper=manager`、`user.name=ysunwellber`。
- 写 `.cmd` 脚本的两个坑（踩过）：**必须存成 GBK**（系统代码页 936，存 UTF-8 会让 cmd 按字节
  偏移错位、命令被截断）；**不要在脚本内部写 `chcp`**（会让 cmd 丢失文件读取位置）。
