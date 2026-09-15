# 版式规格（逆向自往期原图）

所有数值都是 **1280px 稿宽**（CSS 像素）下的值。成品长图 1744px 宽 = 1280 × 1.3625。
参数唯一存放处：`assets/layout.json`。**要改版式只改那个文件**，`template.html` 通过 CSS 变量取用。

> 数值怎么来的：对第 37 期原图（1748×… 的成图缩回 1280）做逐行/逐列墨迹投影量出来的，不是目测估的。
> 偏差基准见 `assets/layout.json` 的 `baseline`，`build.py` 每次出图后会自动复核。

## 一、整体

| 元素 | 规格 | JSON 键 |
|---|---|---|
| 稿宽 | 1280px，白底 | `page.pageWidth` |
| 成品宽 | 1744px（往期一致） | `output.width` |
| 渲染倍率 | 2x（截出 2560px 宽的原始图） | `output.scale` |
| PDF 页宽 | 1280px（与 CSS 稿宽 1:1，不留白边） | `output.pdfWidth` |
| 成品高度 | 往期 5758~7276px；三条精简稿约 4850px | — |

## 二、页眉（报头）

**2026-09-15 改版：苔藓绿报头铺满顶部与左右到边。**
原本是「顶部渐变细条 + 左右各留白 60px 的绿块」（钉钉文档时代的做法，绿块不占满顶部）；
现在 `strip.enabled:false`、`brandBar.marginX:0`，绿块从页面 **y=0** 开始、横向占满整个 1280px。

| 元素 | 规格 | 实测基准（行号相对绿块顶） |
|---|---|---|
| 报头色块 | 背景 `#b2b382`，**左右留白 0（铺满到边）**，`padding:12px 22px 6px` | 行 **0–344**（高 345px）、列 **0–1279** |
| 大标题 | `威尔新资讯`，Noto Serif SC 900，**212px**，`line-height:1`，白色，字距 2px | ink 高 **202px**、宽 **1059px** |
| 导航词 | `合作 · 奋斗 · 靠谱 · 专业 · 学习 · 应变`，**楷体**，**35px**，`margin-top:66px`，`padding:0 90px` | 白字行带 **299–329**（高 31px） |
| 顶部渐变细条 | **已关闭**（粉蓝色 `linear-gradient`，原本高 61px、左右留 60px） | — |

铺满后报头的**内部**比例和原版一致：白字距绿块顶 30px（原版 30px）、距底 13~17px，
所以观感不会因为贴到页面边缘而变紧。

**导航词的 90px 是有讲究的**：`nav.paddingX` 要等于 `body.marginX`(90)，导航词才能跟日期、正文
左对齐成一条竖线。旧版这个对齐是「绿块留白 60 + `paddingX` 30」叠出来的；绿块铺满后 60 没了，
所以 `paddingX` 直接写 90。

**想回到旧版报头**：`strip.enabled` → `true`、`brandBar.marginX` → `60`、`nav.paddingX` → `30`。

**导航词必须是楷体**。这是原版的一个细节，用普通黑体复刻不出来 —— 字体栈里优先 `KaiTi`（Win）/ `STKaiti`（macOS）。
字号也踩过坑：早期用 38px，实测行带偏高 5px，校到 **35px** 才完全对齐。

## 三、日期期号

- 文案：`2026.9.18第38期`，由 `layout.json` 的 `dateline.template` 拼：`{date}第{issue}期`
- 规格：56px / 700 / `line-height:1.2` / 字距 1px / `margin:34px 90px 0`
- 实测 ink 高 ≈ 49px
- `content.json` 里 `"date": "auto"` 会自动取**本周五**；也可写死 `"2026.9.25"`，或命令行 `--date` 覆盖

## 四、正文

| 元素 | 规格 |
|---|---|
| 正文 | 29px / 行高 41px / 两端对齐（`text-justify:inter-ideograph`）/ 段间距 20px / 左右内边距 90px（内容宽 1100px） |
| 小标题 | 34px / 700 / 行高 1.5 / `margin:80px 0 22px` |
| 小标题格式 | `主题词｜正标题`（全角竖线，由 `heading.separator` 拼） |

## 五、图片框架（重点）

- **通栏**：宽 1100px（= 页宽 − 左右各 90px），与正文同宽，不缩进
- **画框高度 500px**，`object-fit:cover` —— 图片会被居中裁切填充，不会变形、不会留白边
- 上边距 36px，无圆角、无边框
- 每块正文 1 张图，放在该块正文之后、下一块小标题之前

配图**原始素材**与画框的关系：

| 项 | 值 |
|---|---|
| 素材裁切基准 | `(0, 145, 1536, 843)` → 1536×698（约 2.2:1） |
| 为什么这么裁 | AI 生成图右下角 y≈865–905 有「AI生成 WORKBUDDY」水印；顶部 0–145 区间常出现模型臆造的假英文 logo。一刀切掉两端最省事 |
| 画框比例 | 1100:500 = 2.2:1，与素材比例一致 → 实际不裁切，整幅呈现 |
| 单图可覆盖 | 在 `content.json` 该板块的 `image.crop` 里写 `[x0,y0,x1,y1]`；`"prep": false` 表示原图已是成品、不要再裁 |

## 六、页尾（品牌落款）

**不要二维码**（2026-09-15 孙哥明确要求删除），改为**品牌 logo 落款**（同日追加）。

| 项 | 值 | 参数位置 |
|---|---|---|
| 素材 | `assets/logo.png`（wellber 威尔贝鲁，1353×154 透明 PNG，主体色 `#272729`） | 技能自带 |
| 显示宽 | 240px（稿宽），占版宽 18.8%；高按原图比例自适应 ≈27.3px | `footer.logo.width` |
| 不透明度 | 0.92（略降，让落款含蓄不抢戏） | `footer.logo.opacity` |
| 两侧分割线 | 长 140px、粗 2px、浅橄榄 `#c9cbaa`（呼应页眉绿块），与 logo 间距 44px | `footer.rule.*` |
| logo 上方留白 | 130px | `footer.logo.marginTop` |
| logo 下方留白 | 150px | `footer.bottomGap` |
| 对齐 | 居中 | `footer.logo.align` |

第38期成品（1744 宽）实测：logo 327×38px，水平居中偏差 <2px；距上方配图 130 CSS px、距底 150 CSS px；
线长实测 191px（=140×1.3625），与 logo 间距 60px（=44×1.3625）。

### 换 logo / 调大小 / 改线型

- **换 logo**：把新文件覆盖到 `assets/logo.png`（推荐透明 PNG，先裁掉四周透明边），
  或放一份到 `content.json` 同目录、在 `layout.json` 的 `footer.logo.src` 里写相对路径。
  查找顺序：`footer.logo.src`（先技能根、再 content.json 所在目录）→ 技能自带 `assets/logo.png`。
- **调大小**：改 `footer.logo.width`（稿宽 CSS px）。**只写宽度**，高度自动按比例，别写死 height 会压扁。
- **线型**：`footer.rule.mode` 支持 `sides`（两侧夹线，当前）/ `top`（logo 上方一条）/ `none`（不画线）；
  `enabled: false` 或 `thickness: 0` 同样不画线。线长 `length`、粗细 `thickness`、间距 `gap`、颜色 `color` 都可调。
  线色可参考页眉橄榄绿 `#b2b382` 做同色系浅色（当前用 `#c9cbaa`）或中性灰 `#d5d5d5`。
- **完全不落款**：`footer.logo.enabled: false` → 页尾退化为纯留白。

## 七、字体与跨平台

字体栈按优先级排列，浏览器取第一个装了的：

| 角色 | 字体栈 |
|---|---|
| 大标题（serif） | `Noto Serif SC` → `Source Han Serif SC/CN` → `Songti SC` → `STSong` → `SimSun` |
| 正文（sans） | `Noto Sans SC` → `Source Han Sans SC/CN` → `PingFang SC` → `Hiragino Sans GB` → `Microsoft YaHei` → `WenQuanYi Micro Hei` |
| 导航（kai） | `KaiTi` → `STKaiti` → `Kaiti SC` → `TW-Kai` → `AR PL UKai CN` |

- **不要**在模板里用 `@font-face` 直接引系统目录的 ttf：file:// 页面会被 CORS 拦掉，字体会静默回退。
  本技能改成**本地 HTTP 起服务再渲染**（见 `build.py`），`@font-face` 才可靠。
- 想要**跨机器像素完全一致**：把字体文件丢进 `assets/fonts/`，`build.py` 会自动生成 `@font-face` 并优先使用（见该目录 README）。

## 八、出图后的自动校验

`build.py` 每次出图都会在 1x 图上量这几项，与 `layout.json` 的 `baseline` 比（容差 ±6px）。
**行号一律相对报头绿块顶部计算**，所以切换报头版式（铺满 / 留白 / 有没有细条）都不用改基准。

```
版式校验（1x 稿宽 1280px，容差 ±6px）
  PASS  绿块顶部行: 实测 0  基准 0
  PASS  绿块高: 实测 345  基准 345
  PASS  绿块左边缘: 实测 0  基准 0
  PASS  绿块右边缘: 实测 1279  基准 1279
  PASS  标题 ink 高: 实测 200  基准 202
  PASS  标题 ink 宽: 实测 1057  基准 1059
  PASS  导航词行带: 实测 (300, 328)  基准 (299, 329)
  PASS  日期 ink 高: 实测 48  基准 49
```

前四项就是「报头有没有铺满顶部和左右」的断言：`绿块顶部行` 期望等于 0（开着渐变细条时期望等于细条高度），
`绿块左/右边缘` 期望等于 `brandBar.marginX` 与 `pageWidth-1-marginX`。改版式后这四项会自动跟着变。

出现 `WARN` 的排查顺序：

1. **只有导航词偏** → 楷体缺失，回退到了宋体/黑体。装楷体或放自带字体。
2. **标题宽高偏** → 宋体家族不同（macOS 的 Songti SC 与 Noto Serif SC 字面宽度有差）。属正常字体差异，不影响观感；要一致就放自带字体。
3. **绿块顶部行 / 左右边缘偏** → `strip.enabled`、`brandBar.marginX` 改了但 `baseline` 没同步。
4. **绿块高偏** → 改过 `brandBar.padding` 或 `nav.marginTop`。
5. 全部偏差很大 → 拿错版式文件了（`--layout` 指到了别的 json）。
