# 更新记录

## v1.3.0 — 2026-09-15

**内容不再框死：新增「选题」环节，先定领域再定向搜新闻**

孙哥反馈：内容框得有点死，希望由技能主动问几个相关领域、再去搜，而不是一上来就往
固定框架里填。问题出在三处 —— `content-guide.md` 写着 5 条固定检索线、立意举例写死、
`content.example.json` 里三条 topic 直接就是「电商大促/平台动向/跨境电商」，
结果期期都长一个样。

- **新增 `assets/topics.json`**：14 个领域的选题池（主题词 / 说明 / 检索关键词 / 来源 / 当季月份 / 权重）
- **新增 `scripts/topic_menu.py`**：扫项目目录里的历史 `*_content.json`，算出每个领域最近一次被用的期号，
  把「上期刚用过的」剔出推荐，输出本期候选（默认 4 个）。支持 `--list-all` / `--json` / `--count`
- **新增 `references/topic-menu.md`**：选题流程、AskUserQuestion 问法、无人值守策略、轮换规则、评分逻辑
- `content-guide.md` 第六节的 5 条固定检索线**撤掉**，改为「按当期选定领域的 keywords 搜」；
  第四节立意举例标注为「仅风格参考，不是固定模板」；条数由「3 条」放宽为 **2–4 条**
- `SKILL.md` 路径 B 由 6 步变 7 步，开头插入「选题」；文件地图、坑位清单、frontmatter description 同步更新
- `README.md` 加入「内容从哪来」说明；`content.example.json` 注明 topic 必须用领域池原词
  （换成别的说法，轮换统计就认不出来，下期会被当成「没用过」重复推荐）
- 每周五定时任务 prompt 同步：无人值守时按脚本推荐 top 4 走，交付时须说明选取理由并留回退口

轮换评分：`weight +（从未用过 60，或 min(50, 间隔期数×15)）+（当季 25）-（上期刚用 80）`，
按分降序取前 N。五个常量都在 `topic_menu.py` 顶部，想调手感改那里。

想回到固定选题：把 `topic-menu.md` 第一步跳过，直接按 `content-guide.md` 第五节的主题词硬写即可，
其余流程不变。

**顺带修掉**：`39_content.json` 的 `issue` / `date` 写成了 `38` / `2026.9.18`（成品实为第 39 期 / 9.25），
已改正 —— 这两个字段错了会让轮换统计把两期当成同一期，也会影响日后拿它重出图时的报头。

## v1.2.0 — 2026-09-15

**报头铺满顶部与左右到边（苔藓绿 banner 占满整个顶部）**

孙哥反馈：钉钉文档时代的版式里绿块四周留白，绿色没有占满顶部。现在改成整条铺满。

- `layout.json` 新增 `strip.enabled`（**false**）：顶部粉蓝渐变细条整条不再渲染
- `brandBar.marginX`：`60` → **`0`**，绿块左右铺满到边
- `nav.paddingX`：`30` → **`90`**。旧版的导航词对齐是「绿块留白 60 + paddingX 30」叠出来的 90px，
  铺满后那 60 没了，得直接写 90，导航词才能继续跟日期、正文左对齐成一条竖线
- `template.html`：新增 `{{STRIP_HTML}}` 占位符，细条那条 div 由 `build.py` 决定输不输出
- `build.py` 的 `verify()` 重写：行号改为**相对报头绿块顶部**计算，并新增 4 项报头几何断言
  （绿块顶部行 / 高 / 左边缘 / 右边缘）。以后切换报头版式都不用再改校验基准
- `baseline` 同步改版：`brandBarRows` → `barHeight`，新增 `titleWindow` / `navWindow` / `datelineWindow`
- 报头**内部**比例未动：白字距绿块顶 30px、距底 13~17px，与原版一致，观感不会变紧

想回到旧版报头：`strip.enabled` → `true`、`brandBar.marginX` → `60`、`nav.paddingX` → `30`。

## v1.1.1 — 2026-09-15

**技能改名为 `wellber-weekly`**

- 目录 `weili-weekly-briefing` → `wellber-weekly`，`SKILL.md` 的 frontmatter `name` 同步更新
  （两者必须一致，否则技能无法被正确识别）
- 更新所有引用：`SKILL.md` 文件地图、`README.md` 的 clone 示例、项目记忆、每周五定时任务
- 脚本无需改动：`build.py` / `check_env.py` 均用 `Path(__file__).parent.parent` 定位技能根目录，不依赖目录名
- 克隆目录名随之变为 `wellber-weekly`：`git clone https://github.com/ysunwellber/wellber-weekly.git wellber-weekly`

## v1.1 — 2026-09-15

**页尾改造：品牌落款取代二维码**

- 页尾从「170px 留白」改为品牌 logo 落款（`assets/logo.png`，wellber 威尔贝鲁，透明 PNG 已裁掉四周透明边）
- 新增 logo 两侧的浅橄榄分割线，与页眉绿块 `#b2b382` 同色系呼应（`footer.rule.mode = sides`）
- logo 尺寸定为 240px 稿宽（占版宽 18.8%），居中；高度按原图比例自适应，不写死
- 页脚全部参数化：`footer.logo`（src / width / opacity / marginTop / alt）+ `footer.rule`（mode / length / thickness / gap / color）+ `footer.bottomGap`
- `build.py` 新增 logo 素材自动接管：技能自带 logo，使用者无需自备素材

**修掉的坑**

- `footer.bottomGap` 语义修正为「logo 下方留白」。v1.0 版本曾把它误当容器总高，导致 logo 下方只剩一半留白

**文档**

- `references/layout-spec.md` 第六节整节重写，含换 logo / 调大小 / 改线型的操作说明
- `README.md` 版式示例与 Q&A 同步为 footer 结构

## v1.0 — 2026-09-15

**首版：版式与内容解耦**

- 逆向还原「威尔新资讯」周报长图版式（1744px 宽），所有参数抽到 `assets/layout.json` 单一来源
- `assets/template.html` 全部改用 CSS 变量，不写死数值
- `scripts/build.py`：内容 JSON 进，整版长图 / 微信分片 / PDF 出，一条命令完成
- 内置版式回归校验（绿块行范围、大标题 ink 高宽、导航词行带、日期行带）5 项自动比对基准值
- `scripts/split_long_image.py`：在真·空白行切分微信分片，避免切断文字行
- `scripts/count_chars.py`：正文段落字数核验（硬约束：每条 ≤250 字含标点）
- `scripts/check_env.py`：环境自检
- 跨平台：Windows / macOS / Linux 三套中文字体栈；弃用 `file://` 改本地 HTTP 渲染以绕开字体 CORS；浏览器回退链 chromium → Chrome → Edge；仅依赖 Pillow + Playwright（已去 numpy 依赖）
