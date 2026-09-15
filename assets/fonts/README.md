# 自带字体（可选）

放这里的字体文件会被 `build.py` 自动接管：生成 `@font-face` 并优先于系统字体使用，
从而实现**跨机器像素完全一致**（不同电脑的大标题/导航词不会再有几个像素的差别）。

不放也能用 —— 会走三平台通用字体栈，观感一致，只是 ink 宽高可能差几像素（在容差内）。

## 怎么放

按文件名放进来即可，`build.py` 按文件名关键词判断角色：

| 文件名包含 | 角色 | 对应元素 |
|---|---|---|
| `serif` / `song` / `宋` / `ming` / `明` | 宋体 | 大标题「威尔新资讯」 |
| `sans` / （其他默认） | 黑体 | 正文、小标题、日期 |
| `kai` / `楷` | 楷体 | 页眉导航词 |

例：

```
assets/fonts/
├─ NotoSerifSC-VF.ttf      → 大标题
├─ NotoSansSC-VF.ttf       → 正文
└─ KaiTi.ttf               → 导航词
```

支持 `.ttf` / `.otf` / `.woff2` / `.woff`。放好后跑 `python scripts/check_env.py`，
会看到一行 `[OK] 技能自带字体: ...`。

## Windows 上从哪拿

系统字体在 `C:\Windows\Fonts\`。本期版式基准用的就是这三个：

- `NotoSerifSC-VF.ttf`（思源宋体 / Noto Serif SC，OFL 许可，可自由分发）
- `NotoSansSC-VF.ttf`（Noto Sans SC，OFL 许可，可自由分发）
- `KaiTi`（`simkai.ttf`，**微软随系统授权，不要对外分发**）

> 建议：能自由分发的用 Noto / 思源系列。楷体若不便分发，就让队友那边走系统楷体
> （macOS 有 `STKaiti`、Linux 可装 `AR PL UKai`），文件里放一个即可。

## macOS / Linux 对应字体

- macOS：`/System/Library/Fonts/`、`/Library/Fonts/` → `Songti.ttc`、`STKaiti.ttf`、`PingFang.ttc`
- Linux：`/usr/share/fonts/` → `fonts-noto-cjk`（Debian/Ubuntu 下 `apt install fonts-noto-cjk`）、
  `fonts-arphic-ukai`（楷体）
