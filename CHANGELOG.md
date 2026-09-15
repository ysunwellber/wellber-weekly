# 更新记录

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
