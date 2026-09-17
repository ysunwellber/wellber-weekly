#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威尔新资讯 · 未来一周天气 banner（v1.5.0，多源合成版）
=========================================================

窗口：发布日（周五）之后的周六 → 下周五，共 7 天。
城市：北京 / 上海 / 广州（默认）。

数据源（全部免密钥，任一源挂掉自动跳过，不影响出图）
------------------------------------------------------
  openmeteo_best   Open-Meteo best_match（混合，主源）
  openmeteo_ecmwf  ECMWF IFS 0.25°（欧洲中心，中期最稳）
  openmeteo_gfs    GFS（美国）
  openmeteo_gem    GEM（加拿大）—— 实测稳定离群，合成时默认剔除
  nmc              中国气象局 nmc.cn 官方（只发 7 天，末段会缺）
  cw               中国天气网 weather.com.cn（sojson 转发）
  metno            挪威气象局 met.no

合成规则（2026-09-17 孙哥拍板：B 方案）
---------------------------------------
  · 温度 = 各源**中位数**（剔除 GEM 后）
  · 天气 = 各源**众数**，平票时取「更轻」的那个
  · 雷雨保守降级：占比 < 60% 一律写成「雨」
    （7 源实测没有一天天气完全一致，强词容易夸大；
      详见 _work/天气预报多渠道验证报告_2026-09-19至25.html）

三种用法
--------
1. 数据（build.py 用）：
     from weather_banner import fetch_multi
     data = fetch_multi("2026-09-19", "2026-09-25")

2. HTML 片段：
     from weather_banner import fetch_multi, render_html
     html = render_html(data, {"marginX": 90, "paddingX": 26})

3. 命令行：
     python weather_banner.py --out-dir <目录> --publish-date 2026-09-18 --preview
     python weather_banner.py --out-dir <目录> --publish-date 2026-09-18 --json-only

跨平台：标准库 + Pillow(可选) + playwright，无 numpy、无 shell 管道。
"""

import argparse
import datetime as dt
import functools
import http.server
import json
import socketserver
import statistics
import ssl
import sys
import threading
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

OPENMETEO = "https://api.open-meteo.com/v1/forecast"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
NMC_REF = "http://www.nmc.cn/publish/forecast/ABJ/beijing.html"
SSL_CTX = ssl._create_unverified_context()  # met.no 在本机证书链验证不过

# 城市表。nmc 是中国气象局内部城市码（不是区站号！），cw 是中国天气网城市码。
CITIES = [
    {"key": "beijing", "name": "北京", "lat": 39.9042, "lon": 116.4074,
     "nmc": "Wqsps", "cw": "101010100"},
    {"key": "shanghai", "name": "上海", "lat": 31.2304, "lon": 121.4737,
     "nmc": "WwcJd", "cw": "101020100"},
    {"key": "guangzhou", "name": "广州", "lat": 23.1291, "lon": 113.2644,
     "nmc": "DwzZf", "cw": "101280101"},
]

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# WMO weather_code → (中文, 图标)。措辞按中文天气习惯，不直译 drizzle。
WMO = {
    0: ("晴", "sun"),
    1: ("晴", "sun"),
    2: ("多云", "partly"),
    3: ("阴", "cloud"),
    45: ("雾", "fog"),
    48: ("雾", "fog"),
    51: ("小雨", "drizzle"),
    53: ("小雨", "drizzle"),
    55: ("小雨", "drizzle"),
    56: ("雨", "drizzle"),
    57: ("雨", "drizzle"),
    61: ("小雨", "rain"),
    63: ("中雨", "rain"),
    65: ("大雨", "rain"),
    66: ("雨", "rain"),
    67: ("雨", "rain"),
    71: ("小雪", "snow"),
    73: ("中雪", "snow"),
    75: ("大雪", "snow"),
    77: ("小雪", "snow"),
    80: ("阵雨", "rain"),
    81: ("中雨", "rain"),
    82: ("大雨", "rain"),
    85: ("阵雪", "snow"),
    86: ("阵雪", "snow"),
    95: ("雷阵雨", "thunder"),
    96: ("雷阵雨", "thunder"),
    99: ("雷阵雨", "thunder"),
}

# 归一化后的天气等级：数字越大越「坏」。平票时取小的（保守，不夸大）。
SEV = {"晴": 0, "多云": 1, "阴": 2, "雾": 3, "雨": 4, "雷雨": 5, "雪": 5}
ALIAS = {"霾": "雾", "雾凇": "雾", "阵雨": "雨", "中雨": "雨", "大雨": "雨",
         "小雨": "雨", "毛毛雨": "雨", "雷阵雨": "雷雨", "阵雪": "雪"}

METNO_MAP = {"clearsky": "晴", "fair": "晴", "partlycloudy": "多云", "cloudy": "阴",
             "fog": "雾", "lightrain": "雨", "rain": "雨", "heavyrain": "雨",
             "lightrainshowers": "雨", "rainshowers": "雨", "heavyrainshowers": "雨",
             "lightssnowshowers": "雪", "snowshowers": "雪", "snow": "雪",
             "lightrainandthunder": "雷雨", "rainandthunder": "雷雨",
             "heavyrainandthunder": "雷雨", "sleet": "雨"}

ICON_COLOR = {
    "sun": "#e0a33c", "partly": "#93a24f", "cloud": "#8d949a",
    "drizzle": "#6f93a8", "rain": "#5b86a3", "thunder": "#6b7fa8",
    "fog": "#9aa0a4", "snow": "#7fa3b8",
}
ICON_BY_WX = {"晴": "sun", "多云": "partly", "阴": "cloud", "雾": "fog",
              "雨": "rain", "雷雨": "thunder", "雪": "snow"}

# 合成时默认剔除（GEM 加拿大模式实测稳定离群：北京夜间比别家低 8~10°C）
DEFAULT_EXCLUDE = ("openmeteo_gem",)
THUNDER_MIN_RATIO = 0.6   # 雷雨占比低于这个值就降级成「雨」


def norm_wx(s):
    """把各家中文/英文天气词归一化到 SEV 的键。"""
    if not s:
        return "多云"
    s = str(s).strip()
    if s in METNO_MAP:
        return METNO_MAP[s]
    for k, v in METNO_MAP.items():
        if s.startswith(k):
            return v
    if s in SEV:
        return s
    if s in ALIAS:
        return ALIAS[s]
    for k, v in ALIAS.items():
        if k in s:
            return v
    for ch in ("雷", "雨", "雪", "雾", "霾", "阴", "云", "晴"):
        if ch in s:
            return {"雷": "雷雨", "雨": "雨", "雪": "雪", "雾": "雾",
                    "霾": "雾", "阴": "阴", "云": "多云", "晴": "晴"}[ch]
    return "多云"


# --------------------------------------------------------------------------
# 一、日期
# --------------------------------------------------------------------------
def friday_of(d):
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def window_for(publish_date):
    """周五发布 → 次日（周六）起 7 天，到下一个周五。"""
    p = (dt.date.fromisoformat(publish_date) if isinstance(publish_date, str)
         else publish_date)
    return (p + dt.timedelta(days=1)).isoformat(), (p + dt.timedelta(days=7)).isoformat()


# --------------------------------------------------------------------------
# 二、各源取数（统一返回 {date: [tmax, tmin, 天气]}）
# --------------------------------------------------------------------------
def _http(url, headers=None, timeout=15, ctx=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    kw = {"timeout": timeout}
    if ctx:
        kw["context"] = ctx
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), **kw) as r:
        return r.read().decode("utf-8", "ignore")


def _src_openmeteo(city, start, end, model, timeout=15):
    q = urllib.parse.urlencode({
        "latitude": city["lat"], "longitude": city["lon"],
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Shanghai", "start_date": start, "end_date": end,
        "models": model})
    j = json.loads(_http(f"{OPENMETEO}?{q}", timeout=timeout))
    d = j["daily"]
    return {d["time"][i]: [round(d["temperature_2m_max"][i]),
                           round(d["temperature_2m_min"][i]),
                           norm_wx(WMO.get(int(d["weather_code"][i]), ("多云",))[0])]
            for i in range(len(d["time"]))}


def _src_nmc(city, start, end, timeout=15):
    j = json.loads(_http(
        f"http://www.nmc.cn/rest/weather?stationid={city['nmc']}",
        headers={"Referer": NMC_REF}, timeout=timeout))
    out = {}
    for day in j["data"]["predict"]["detail"]:
        d = day["date"][:10]
        if start <= d <= end:
            out[d] = [int(day["day"]["weather"]["temperature"]),
                      int(day["night"]["weather"]["temperature"]),
                      norm_wx(day["day"]["weather"]["info"])]
    return out


def _src_cw(city, start, end, timeout=15):
    j = json.loads(_http(
        f"http://t.weather.sojson.com/api/weather/city/{city['cw']}", timeout=timeout))
    out = {}
    for f in j["data"]["forecast"]:
        d = f["ymd"]
        if start <= d <= end:
            hi = int(str(f["high"]).replace("高温", "").replace("℃", "").strip())
            lo = int(str(f["low"]).replace("低温", "").replace("℃", "").strip())
            out[d] = [hi, lo, norm_wx(f["type"])]
    return out


def _src_metno(city, start, end, timeout=20):
    q = urllib.parse.urlencode({"lat": city["lat"], "lon": city["lon"]})
    j = json.loads(_http(
        f"https://api.met.no/weatherapi/locationforecast/2.0/compact?{q}",
        headers={"User-Agent": "wellber-weekly/1.5"}, ctx=SSL_CTX, timeout=timeout))
    agg = {}
    for it in j["properties"]["timeseries"]:
        d = it["time"][:10]
        t = it["data"]["instant"]["details"].get("air_temperature")
        if t is None or not (start <= d <= end):
            continue
        a = agg.setdefault(d, {"mx": -99, "mn": 99, "sym": {}})
        a["mx"], a["mn"] = max(a["mx"], t), min(a["mn"], t)
        blk = it["data"].get("next_6_hours") or it["data"].get("next_1_hours") or {}
        sym = (blk.get("summary") or {}).get("symbol_code")
        if sym:
            a["sym"][sym] = a["sym"].get(sym, 0) + 1
    return {d: [round(a["mx"]), round(a["mn"]),
                norm_wx(max(a["sym"], key=a["sym"].get) if a["sym"] else "partlycloudy")]
            for d, a in agg.items()}


SOURCES = {
    "openmeteo_best": lambda c, s, e: _src_openmeteo(c, s, e, "best_match"),
    "openmeteo_ecmwf": lambda c, s, e: _src_openmeteo(c, s, e, "ecmwf_ifs025"),
    "openmeteo_gfs": lambda c, s, e: _src_openmeteo(c, s, e, "gfs_seamless"),
    "openmeteo_gem": lambda c, s, e: _src_openmeteo(c, s, e, "gem_seamless"),
    "nmc": _src_nmc,
    "cw": _src_cw,
    "metno": _src_metno,
}
SOURCE_LABEL = {
    "openmeteo_best": "Open-Meteo best_match",
    "openmeteo_ecmwf": "ECMWF 欧洲中心",
    "openmeteo_gfs": "GFS 美国",
    "openmeteo_gem": "GEM 加拿大（离群，默认剔除）",
    "nmc": "中国气象局",
    "cw": "中国天气网",
    "metno": "met.no 挪威",
}


# --------------------------------------------------------------------------
# 三、合成
# --------------------------------------------------------------------------
def pick_wx(votes):
    """众数 → 平票取轻 → 雷雨占比不足则降级成雨。"""
    if not votes:
        return "多云", 0.0, {}
    n = len(votes)
    cnt = Counter(votes)
    top = max(cnt.values())
    cand = [w for w, k in cnt.items() if k == top]
    w = min(cand, key=lambda x: SEV.get(x, 9))
    if w == "雷雨" and cnt["雷雨"] / n < THUNDER_MIN_RATIO:
        w = "雨"
    return w, cnt[w] / n, dict(cnt)


def fetch_multi(start, end, cities=None, sources=None, exclude=DEFAULT_EXCLUDE,
                timeout=15, verbose=False):
    """拉所有源并合成为一份数据。任一源失败只记录，不影响整体。"""
    cities = cities or CITIES
    names = list(sources or SOURCES.keys())
    n_days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1
    days = [(dt.date.fromisoformat(start) + dt.timedelta(days=i)).isoformat()
            for i in range(n_days)]

    out_cities, used, failed = [], set(), []
    for c in cities:
        per_src = {}
        for s in names:
            if s not in SOURCES:
                continue
            try:
                r = SOURCES[s](c, start, end)
                if r:
                    per_src[s] = r
                    used.add(s)
            except Exception as e:
                failed.append(f"{c['name']}/{s}: {type(e).__name__}")
        eff = {k: v for k, v in per_src.items() if k not in (exclude or ())} or per_src
        day_list = []
        for d in days:
            his = [v[d][0] for v in eff.values() if d in v]
            los = [v[d][1] for v in eff.values() if d in v]
            wxs = [v[d][2] for v in eff.values() if d in v]
            if not his:
                continue
            wx, agree, votes = pick_wx(wxs)
            dd = dt.date.fromisoformat(d)
            sp_h, sp_l = max(his) - min(his), max(los) - min(los)
            if agree >= 0.6 and sp_h <= 3 and sp_l <= 3:
                conf = "高"
            elif agree >= 0.4 and sp_h <= 5:
                conf = "中"
            else:
                conf = "低"
            hi, lo = round(statistics.median(his)), round(statistics.median(los))
            if lo > hi:
                lo = hi
            day_list.append({
                "date": d, "md": f"{dd.month}.{dd.day}",
                "weekday": WEEKDAY_CN[dd.weekday()], "weekend": dd.weekday() >= 5,
                "text": wx, "icon": ICON_BY_WX.get(wx, "cloud"),
                "tmax": hi, "tmin": lo, "conf": conf, "agree": round(agree, 2),
                "spreadHi": sp_h, "spreadLo": sp_l, "votes": votes, "n": len(his),
            })
        out_cities.append({"name": c["name"], "days": day_list})

    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    data = {
        "start": start, "end": end,
        "range": f"{s.month}.{s.day} - {e.month}.{e.day}",
        "source": "多源合成",
        "sourcesUsed": sorted(used),
        "sourcesFailed": failed,
        "excluded": list(exclude or []),
        "cities": out_cities,
    }
    if verbose:
        print(f"天气窗口：{data['range']}（{start} → {end}）")
        print(f"  成功源（{len(used)}）：{'、'.join(SOURCE_LABEL.get(x, x) for x in sorted(used))}")
        if failed:
            print(f"  失败源：{failed}")
    return data


def fetch(start, end, cities=None, timeout=15):
    """单源（Open-Meteo best_match）—— 兼容旧调用 & 断网兜底。"""
    cities = cities or CITIES
    out = []
    for c in cities:
        r = _src_openmeteo(c, start, end, "best_match", timeout=timeout)
        days = []
        for d in sorted(r):
            dd = dt.date.fromisoformat(d)
            hi, lo, wx = r[d]
            days.append({"date": d, "md": f"{dd.month}.{dd.day}",
                         "weekday": WEEKDAY_CN[dd.weekday()], "weekend": dd.weekday() >= 5,
                         "text": wx, "icon": ICON_BY_WX.get(wx, "cloud"),
                         "tmax": hi, "tmin": lo, "conf": "—", "agree": 1.0,
                         "spreadHi": 0, "spreadLo": 0, "votes": {}, "n": 1})
        out.append({"name": c["name"], "days": days})
    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return {"start": start, "end": end, "range": f"{s.month}.{s.day} - {e.month}.{e.day}",
            "source": "Open-Meteo", "sourcesUsed": ["openmeteo_best"],
            "sourcesFailed": [], "excluded": [], "cities": out}


# --------------------------------------------------------------------------
# 四、图标（内联 SVG 线描，不依赖 emoji 字体）
# --------------------------------------------------------------------------
_CLOUD = "M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"


def icon_svg(kind, color=None, size=34):
    color = color or ICON_COLOR.get(kind, "#8d949a")
    body = {
        "sun": (
            f'<circle cx="12" cy="12" r="4.6" fill="{color}" stroke="none"/>'
            '<g stroke="%s"><line x1="12" y1="1.6" x2="12" y2="4"/>'
            '<line x1="12" y1="20" x2="12" y2="22.4"/>'
            '<line x1="1.6" y1="12" x2="4" y2="12"/>'
            '<line x1="20" y1="12" x2="22.4" y2="12"/>'
            '<line x1="4.6" y1="4.6" x2="6.3" y2="6.3"/>'
            '<line x1="17.7" y1="17.7" x2="19.4" y2="19.4"/>'
            '<line x1="4.6" y1="19.4" x2="6.3" y2="17.7"/>'
            '<line x1="17.7" y1="6.3" x2="19.4" y2="4.6"/></g>' % color
        ),
        "partly": (
            f'<circle cx="8.2" cy="8.2" r="3.4" fill="{color}" stroke="none"/>'
            '<g stroke="%s"><line x1="8.2" y1="1.4" x2="8.2" y2="3.2"/>'
            '<line x1="1.4" y1="8.2" x2="3.2" y2="8.2"/>'
            '<line x1="3.4" y1="3.4" x2="4.7" y2="4.7"/>'
            '<line x1="12.9" y1="3.4" x2="11.6" y2="4.7"/>'
            '<line x1="3.4" y1="12.9" x2="4.7" y2="11.6"/></g>'
            '<path d="M19.5 19.4h-7a3.9 3.9 0 0 1 .3-7.8 5.4 5.4 0 0 1 5.4 4.1'
            'A3.9 3.9 0 0 1 19.5 19.4z" fill="none"/>' % color
        ),
        "cloud": f'<path d="{_CLOUD}" fill="none"/>',
        "drizzle": (
            f'<path d="{_CLOUD}" fill="none"/>'
            '<g stroke="%s"><line x1="8" y1="21.2" x2="8" y2="23"/>'
            '<line x1="12" y1="20.4" x2="12" y2="22.6"/>'
            '<line x1="16" y1="21.2" x2="16" y2="23"/></g>' % color
        ),
        "rain": (
            f'<path d="{_CLOUD}" fill="none"/>'
            '<g stroke="%s"><line x1="8.4" y1="19.6" x2="7.2" y2="23"/>'
            '<line x1="12" y1="19.6" x2="10.8" y2="23"/>'
            '<line x1="15.6" y1="19.6" x2="14.4" y2="23"/></g>' % color
        ),
        "thunder": (
            f'<path d="{_CLOUD}" fill="none"/>'
            f'<path d="M13.4 13.6 9.6 19.4h3.2l-1 4.2 4.4-6.2h-3.2z" '
            f'fill="{color}" stroke="none"/>'
        ),
        "fog": (
            f'<path d="{_CLOUD}" fill="none"/>'
            '<g stroke="%s"><line x1="5" y1="22" x2="19" y2="22"/></g>' % color
        ),
        "snow": (
            f'<path d="{_CLOUD}" fill="none"/>'
            '<g stroke="%s"><line x1="8" y1="21.4" x2="8" y2="23"/>'
            '<line x1="12" y1="21.4" x2="12" y2="23"/>'
            '<line x1="16" y1="21.4" x2="16" y2="23"/></g>' % color
        ),
    }.get(kind, f'<path d="{_CLOUD}" fill="none"/>')

    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" '
        f'style="display:block">{body}</svg>'
    )


# --------------------------------------------------------------------------
# 五、默认版式参数（正式值写在 layout.json 的 weather 段，这里只兜底）
# --------------------------------------------------------------------------
DEFAULT_CFG = {
    "marginX": 90,          # 左右留白；0 = 通栏铺满
    "marginTop": 30,
    "marginBottom": 0,
    "paddingX": 26,         # 内容距卡片左右边缘
    "paddingY": 24,
    "background": "#f6f7ee",
    "rule": "#e2e5d2",
    "accent": "#b2b382",
    "weekendTint": "rgba(178,179,130,0.18)",
    "title": "未来一周天气",
    "titleSize": 30,
    "titleColor": "#3d4a2e",
    "metaSize": 21,
    "metaColor": "#8b9080",
    "metaSuffix": " · 多源合成",
    "citySize": 26,
    "cityWidth": 88,
    "cityPill": "rgba(178,179,130,0.30)",
    "gap": 8,
    "daySize": 22,
    "dayColor": "#3a3a3a",
    "dateSize": 18,
    "dateColor": "#9a9a90",
    "iconSize": 34,
    "textSize": 21,
    "textColor": "#5a5f52",
    "hiSize": 25,
    "hiColor": "#c0613d",
    "loSize": 22,
    "loColor": "#78909c",
    "fontSans": "'Noto Sans SC','Source Han Sans SC','PingFang SC','Microsoft YaHei',sans-serif",
}


def render_html(data, cfg=None, cities_label=None):
    """输出天气 banner 的 HTML 片段（不含 <html>/<body>，可直接塞进 template）。"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update({k: v for k, v in cfg.items() if v is not None})

    n = max((len(x["days"]) for x in data["cities"]), default=7)
    label = cities_label or " · ".join(x["name"] for x in data["cities"])

    rows = []
    for ci, city in enumerate(data["cities"]):
        cells = []
        for d in city["days"]:
            tint = f"background:{c['weekendTint']};" if d.get("weekend") else ""
            cells.append(
                f'<div class="wx-cell" style="{tint}" data-conf="{d.get("conf", "")}">'
                f'<div class="wx-dt"><span class="wx-wd">{d["weekday"]}</span>'
                f'<span class="wx-md">{d["md"]}</span></div>'
                f'<div class="wx-ic">{icon_svg(d["icon"], size=c["iconSize"])}</div>'
                f'<div class="wx-tx">{d["text"]}</div>'
                f'<div class="wx-tp"><span class="hi">{d["tmax"]}°</span>'
                f'<span class="sl">/</span><span class="lo">{d["tmin"]}°</span></div>'
                f"</div>"
            )
        border = "" if ci == len(data["cities"]) - 1 else f'border-bottom:1px solid {c["rule"]};'
        rows.append(
            f'<div class="wx-row" style="{border}">'
            f'<div class="wx-city"><span>{city["name"]}</span></div>'
            f'<div class="wx-days">{"".join(cells)}</div>'
            f"</div>"
        )

    return f"""<section class="wx" style="
  margin:{c['marginTop']}px {c['marginX']}px {c['marginBottom']}px;
  padding:{c['paddingY']}px {c['paddingX']}px;
  background:{c['background']};
  font-family:{c['fontSans']};
  -webkit-font-smoothing:antialiased;
">
  <div class="wx-head">
    <div class="wx-title">
      <span class="wx-tic">{icon_svg('partly', color=c['accent'], size=26)}</span>
      <span>{c['title']}</span>
    </div>
    <div class="wx-meta">{data['range']} · {label}{c['metaSuffix']}</div>
  </div>
  {"".join(rows)}
</section>
<style>
.wx-head{{display:flex;justify-content:space-between;align-items:flex-end;
  padding-bottom:14px;border-bottom:1px solid {c['rule']};}}
.wx-title{{display:flex;align-items:center;gap:10px;
  font-size:{c['titleSize']}px;font-weight:800;color:{c['titleColor']};letter-spacing:1px;}}
.wx-tic{{display:flex;}}
.wx-meta{{font-size:{c['metaSize']}px;color:{c['metaColor']};letter-spacing:.5px;}}
/* 行：城市列定宽 + 日期区占满剩余；日期区自己再分 n 列。
   别用「父网格直接分 8 列」—— 日期区会只落到第 2 列，单元格被压成 13px（踩过）。 */
.wx-row{{display:flex;gap:{c['gap']}px;align-items:center;}}
.wx-city{{flex:none;width:{c['cityWidth']}px;display:flex;align-items:center;justify-content:center;}}
.wx-city span{{display:block;width:{c['cityWidth'] - 14}px;text-align:center;
  background:{c['cityPill']};border-radius:5px;padding:5px 0;
  font-size:{c['citySize']}px;font-weight:800;color:{c['titleColor']};letter-spacing:1px;}}
.wx-days{{flex:1;min-width:0;display:grid;
  grid-template-columns:repeat({n}, minmax(0,1fr));gap:{c['gap']}px;}}
.wx-cell{{text-align:center;padding:11px 0 10px;border-radius:5px;}}
.wx-dt{{display:flex;justify-content:center;align-items:baseline;gap:5px;line-height:1.25;}}
.wx-wd{{font-size:{c['daySize']}px;color:{c['dayColor']};font-weight:700;}}
.wx-md{{font-size:{c['dateSize']}px;color:{c['dateColor']};}}
.wx-ic{{display:flex;justify-content:center;padding:6px 0 3px;}}
.wx-tx{{font-size:{c['textSize']}px;color:{c['textColor']};line-height:1.3;white-space:nowrap;}}
.wx-tp{{margin-top:2px;font-weight:700;line-height:1.25;}}
.wx-tp .hi{{font-size:{c['hiSize']}px;color:{c['hiColor']};}}
.wx-tp .lo{{font-size:{c['loSize']}px;color:{c['loColor']};}}
.wx-tp .sl{{font-size:{c['loSize'] - 2}px;color:#c3c7bc;margin:0 3px;font-weight:400;}}
</style>"""


# --------------------------------------------------------------------------
# 六、渲染（本地 http 服务 + Playwright，跟 build.py 同套路）
# --------------------------------------------------------------------------
def _render(html_path, png_path, width=1280, scale=2, browser=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("缺少 playwright：pip install playwright && python -m playwright install chromium")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    html_path = Path(html_path)
    # 必须把服务根目录绑到 html 所在目录，否则截到 404 页（踩过）。
    handler = functools.partial(Quiet, directory=str(html_path.parent))
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    cands = [(None, "chromium"), ("chrome", "chrome"), ("msedge", "msedge")]
    if browser:
        tgt = None if browser == "chromium" else browser
        cands = [(tgt, browser)] + [x for x in cands if x[0] != tgt]

    try:
        with sync_playwright() as p:
            b = None
            for ch, name in cands:
                try:
                    b = p.chromium.launch(channel=ch) if ch else p.chromium.launch()
                    break
                except Exception:
                    continue
            if b is None:
                raise SystemExit("起不了浏览器，请先：python -m playwright install chromium")
            ctx = b.new_context(viewport={"width": width, "height": 900},
                                device_scale_factor=scale)
            pg = ctx.new_page()
            pg.goto(f"http://127.0.0.1:{port}/{html_path.name}", wait_until="load")
            pg.wait_for_timeout(500)
            pg.query_selector("body").screenshot(path=str(png_path))
            b.close()
    finally:
        srv.shutdown()
    return png_path


def page_doc(fragment, title="天气 banner 预览", width=1280):
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>html,body{{margin:0;padding:0;background:#fff}}"
            f".wrap{{width:{width}px;background:#fff}}</style></head>"
            f"<body><div class='wrap'>{fragment}</div></body></html>")


def mock_top(weather_fragment, date_text="2026.9.18第40期",
             heading="公司头条｜秋季新品启动会定档"):
    """把 banner 塞进真实报头里看整体效果（预览用，不是最终版式）。"""
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#fff}}
body{{width:1280px;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif}}
.bar{{background:#b2b382;padding:12px 22px 6px;text-align:center}}
.brand{{font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-weight:900;font-size:212px;
  line-height:1;letter-spacing:2px;color:#fff;white-space:nowrap}}
.nav{{display:flex;justify-content:space-between;padding:0 90px;margin-top:66px;
  font-family:'KaiTi','STKaiti',serif;font-size:35px;line-height:1.4;color:#fff}}
.dateline{{margin:34px 90px 0;font-size:56px;font-weight:700;color:#111;letter-spacing:1px}}
main{{padding:0 90px}}
h2{{font-size:34px;font-weight:700;line-height:1.5;margin:60px 0 22px;color:#111}}
p{{font-size:29px;line-height:41px;color:#1a1a1a;margin:0 0 20px;text-align:justify}}
</style></head><body>
<div class="bar"><div class="brand">威尔新资讯</div>
  <div class="nav"><span>合作</span><span>奋斗</span><span>靠谱</span><span>专业</span><span>学习</span><span>应变</span></div>
</div>
<div class="dateline">{date_text}</div>
{weather_fragment}
<main><h2>{heading}</h2>
<p>本周公司秋季婴童睡袋系列完成首轮内部评审，设计、生产、电商三条线对齐了上新节奏，
首批备货量与主推渠道已确认，详细排期见各线周计划。</p></main>
</body></html>"""


# --------------------------------------------------------------------------
# 七、命令行
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="威尔新资讯 · 未来一周天气 banner（多源合成）")
    ap.add_argument("--publish-date", help="发布日（默认本周五），窗口自动取 周六→下周五")
    ap.add_argument("--start"), ap.add_argument("--end")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cities", help="城市 key 逗号分隔（beijing,shanghai,guangzhou）")
    ap.add_argument("--single-source", action="store_true", help="只用 Open-Meteo（不做多源合成）")
    ap.add_argument("--json-only", action="store_true", help="只取数据不出图")
    ap.add_argument("--preview", action="store_true", help="出预览图")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--browser")
    a = ap.parse_args(argv)

    if a.start and a.end:
        start, end = a.start, a.end
    else:
        pub = a.publish_date or friday_of(dt.date.today()).isoformat()
        start, end = window_for(pub)

    cities = CITIES
    if a.cities:
        keys = [k.strip() for k in a.cities.split(",")]
        cities = [c for k in keys for c in CITIES if c["key"] == k]

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    data = (fetch(start, end, cities) if a.single_source
            else fetch_multi(start, end, cities, verbose=True))
    (out / "weather_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n合成结果（温度=中位数，天气=众数；剔除 {data['excluded'] or '无'}）：")
    for c in data["cities"]:
        seg = "  ".join(f"{d['weekday']}{d['text']}{d['tmax']}/{d['tmin']}[{d['conf']}]"
                        for d in c["days"])
        print(f"  {c['name']}：{seg}")
    print(f"\n[ok] 数据 → {out / 'weather_data.json'}")

    if a.json_only:
        return 0

    frag = render_html(data, {"marginX": 90, "paddingX": 26})
    hp = out / "weather_banner.html"
    hp.write_text(page_doc(frag), encoding="utf-8")
    _render(hp, out / "weather_banner.png", scale=a.scale, browser=a.browser)
    print("[ok] weather_banner.png")

    if a.preview:
        for name, m in (("A_通栏.png", {"marginX": 0, "paddingX": 90}),
                        ("B_留白.png", {"marginX": 90, "paddingX": 26})):
            h = out / (name.replace(".png", ".html"))
            h.write_text(page_doc(render_html(data, m), title=name), encoding="utf-8")
            _render(h, out / name, scale=a.scale, browser=a.browser)
            print(f"[ok] {name}")
        h = out / "C_整页效果.html"
        h.write_text(mock_top(frag), encoding="utf-8")
        _render(h, out / "C_整页效果.png", scale=a.scale, browser=a.browser)
        print("[ok] C_整页效果.png")
    print(f"\n输出目录：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
