---
name: wellber-weekly
description: 制作「威尔新资讯」公司周报竖版长图（童装/母婴/电商行业资讯，每周五发公司群）。当用户要求"做本周/本期威尔新资讯""公司简报周报""按往期模板出一期长图""每周五发群里的简报""这期写什么方向""只要排版不要内容""按模板出图给人审"时使用。流程定死为四关：先确认刊期（问上期期号推本期期号 + 发布日期）、再问公司头条（固定第一条，AI 不自编）、再选领域（14 个领域轮换，自动避开上期用过的）、最后定向搜新闻。内容边界写死：业务为国内电商 / 本地线下母婴集合店 / 欧美跨境亚马逊三条线，品类限婴童纺织用品与童装，每条正文 ≤250 字、每期最多 5 条。内含已逆向还原的完整版式参数（尺寸/配色/字体/字号，含日期期号与图片框架）、一键构建脚本（内容 JSON 进，整版长图/微信分片/PDF 出）、版式回归校验，跨 Windows/macOS/Linux。
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
   「上期期号 → 本期期号（+1）→ 发布日期（默认本周五）→ 目标文件名」。
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
7. **跑 `build.py`** 出成品，看版式校验是否全 PASS。
8. **`present_files`** 交付；提醒孙哥微信发图勾**原图**。

> 定时任务（每周五 09:00）无人可问：**刊期自己算**（遇日期冲突则停手报告）、
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
│  ├─ content.example.json       ← 内容文件模板（含逐字段说明）
│  ├─ logo.png                   ← 页尾品牌落款（wellber 威尔贝鲁，透明 PNG；换 logo 直接覆盖它）
│  └─ fonts/                     ← 可选：放字体文件实现跨机器像素一致（见目录内 README）
└─ scripts/
   ├─ build.py                   ← 一键构建：配图裁切 → HTML → 渲染 → 整版/分片/PDF → 校验
   ├─ issue_info.py              ← 刊期确认：上期期号 → 本期期号 + 发布日期，并查该日期是否已被占用
   ├─ topic_menu.py              ← 选题候选生成（读领域池 + 扫历史，避免与上期重复）
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

出图后 `build.py` 会自动做版式回归校验（报头是否铺满顶部与左右 / 标题 ink / 导航带 / 日期），
有偏差会打印 WARN 与排查提示。

---

## 四、坑位清单（踩过的）

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
- **微信发图要勾「原图」**，否则长图会被压糊 —— 交付时要提醒。

## 五、相关文件位置（孙哥这台机器）

- 项目目录：`C:\Users\Yang\Pictures\威尔新资讯\`
- 历史内容存档：`38_content.json` / `39_content.json`（下一期为 `40_content.json`）。
  `topic_menu.py` 靠扫这些文件判断领域轮换，**别改名、别删**。
  注：`39_content.json` 的报头曾是错的（写成 38 期 / 9.18，实际 39 期 / 9.25），已修正，
  原文件备份在 `_work/39_content.json.bak`。
- Python：`C:\Users\Yang\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
- 每周五 09:00 有定时任务「威尔新资讯 · 每周五电商新闻简报」自动跑路径 B
  （四关：刊期自算 → 跳过头条并提示 → 按 `topic_menu.py` 推荐 top 4 选题 → 检索成稿）
- **本技能目录本身是一个 git 仓库**（分支 `main`，已打标签 `v1.4.0`），远程 `origin` 为
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
