#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""威尔新资讯 · 新闻事实核查（v1.5.3）

出稿之后、交付之前，把 content.json 里所有**可核查断言**机械抽出来，
逐条要求用**更多信源**复核；对 AI 判断不了的，输出「判断指令」给作者（孙哥）。

天气模块（v1.5.0）做的是「同一份数据多源取中位数」；
这里做的是另一件事：**同一句话，去哪儿找第二个独立来源来证实**。

------------------------------------------------------------------ 两步走

1) 抽取（默认）
   python scripts/fact_check.py --content 39_content.json
   → factcheck_39_0925.json   待核清单（Agent 逐条回填 status / sources / note / action）
   → 核查清单_39_0925.md      人读版，带每条的建议核查查询

2) 出报告 + 交付前卡口
   python scripts/fact_check.py --content 39_content.json --report
   → 事实核查报告_39_0925.html 逐条结论 + 给作者的判断指令
   退出码 0 = 可以推；2 = 还有未决 / 无法判断的断言（详见 references/fact-check.md）

------------------------------------------------------------------ 判据

信源分级、多源独立判据、口径陷阱、查询模板、判断指令模板全在
`assets/sources.json`；工作流规范见 `references/fact-check.md`。
"""

import argparse
import datetime
import html as _html
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_SOURCES = SKILL_DIR / "assets" / "sources.json"
DEFAULT_TOPICS = SKILL_DIR / "assets" / "topics.json"

RISK_ORDER = {"高": 0, "中": 1, "低": 2}
RISK_BADGE = {"高": "#c0392b", "中": "#b7791f", "低": "#5b7a52"}
STATUS_LABEL = {
    "pending": "待核",
    "confirmed": "已确证",
    "softened": "已弱化",
    "dropped": "已删除",
    "unjudgeable": "无法判断（需作者定夺）",
}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_date(spec):
    """同 build.py：'2026.9.18' / '2026-9-18' / 'auto'（下一个周五）"""
    if not spec or spec == "auto":
        today = datetime.date.today()
        return today + datetime.timedelta(days=(4 - today.weekday()) % 7)
    parts = [int(x) for x in re.split(r"[.\-/]", str(spec).strip())]
    if len(parts) != 3:
        raise SystemExit(f"日期格式无法识别：{spec}（应为 2026.9.18 这样）")
    return datetime.date(*parts)


def build_name(issue, date_str: str) -> str:
    """39 + 2026.9.25 -> 39_0925（与 build.py 完全一致）"""
    d = parse_date(date_str)
    return f"{issue}_{d.month:02d}{d.day:02d}"


# --------------------------------------------------------------------------- #
# 断言识别规则
#   原则：只抓「可以被证实/证伪」的硬事实，纯修辞不抓。
# --------------------------------------------------------------------------- #
_NUM = r"\d+(?:[.,]\d+)*"
_U = r"(?:%|％|个百分点|亿元|万元|亿美元|万美元|亿|万|美元|元|点|倍|成|家|款|个|件|吨|万人|亿人|人次|人|天|周|个月|年|场|次|台|辆|小时|分钟)"

RE_UNITNUM = re.compile(_NUM + r"\s*" + _U)
RE_PCT = re.compile(
    r"(?:同比|环比|较|比|与[^，。；]{1,10}相比)?\s*"
    r"(?:增长|上涨|上升|回升|下滑|下降|下跌|回落|提升|提高|减少|降低|增至|降至|扩大|收窄|翻)\s*"
    + _NUM + r"\s*(?:个?百分点|%|％|倍|成)"
)
RE_TREND = re.compile(
    r"增长|上涨|上升|回升|下滑|下降|下跌|回落|提升|提高|减少|降低|扩大|收窄|"
    r"回暖|降温|走高|承压|反弹|遇冷|爆发|井喷|萎缩|见顶|领跑|发力|提速|放缓|"
    r"拉升|低迷|火热|爆单|滞销|提价|降价|涨价|跌价|翻倍|新高|新低|"
    r"上调|下调|高于|低于|多于|少于|优于|不及|跑赢|跑输|增超|增至|突破"
)
RE_ABS = re.compile(
    r"首个|首款|首家|首条|首例|首次|唯一|最大|最小|最强|最高|最低|"
    r"全部|所有|无一|绝无|历史新高|创新高|创纪录|第一|领先|超过|突破|满额|清零|"
    r"超(?=\d)"
)
RE_DATE = re.compile(
    r"20\d{2}\s*年|20\d{2}\s*[-/.]\s*\d{1,2}|\d{1,2}\s*月\d{1,2}\s*日|\d{1,2}\s*月|"
    r"Q[1-4]|第[一二三四五六]季度|上旬|中旬|下旬"
)
RE_DEADLINE = re.compile(
    r"截至|截止|生效|施行|实施|落地|执行|最后期限|之前|前完成|锁仓|入仓|报名截止|提报|开征"
)
RE_ATTR = re.compile(
    r"数据显示|报告显示|报告称|据[^，。；]{0,12}?(?:显示|统计|发布|介绍|公告|通知|报道)|"
    r"业内(?:认为|观察|普遍|人士|预计)|官方(?:称|表示|公告|发布|宣布)|"
    r"宣布|透露|预计|预测|有望|或将|拟|计划|指出|认为|估算"
)
RE_MONEY = re.compile(
    r"份额|占比|渗透率|规模|均价|客单价|营收|GMV|销售额|销量|订单量|产值|"
    r"市场规模|出口额|增速|毛利|利润|亏损|补贴金额|券"
)
RE_STD = re.compile(r"(?:CFR|EN|ASTM|ISO|GB/T|GB|OEKO-TEX)\s*[\d][\d\.\-]*", re.I)
RE_EVENT = re.compile(
    r"召回|通报|抽检|不合格|处罚|罚款|禁令|新规|下架|封店|侵权|诉讼|"
    r"涨价|降价|停运|关停|裁员|收购|合并|上市|融资|发布|上线|开卖|首发|招商|签约"
)


def detect(text: str, section_topic: str):
    """返回 (flags, kinds, evidence)"""
    flags = {
        "num": bool(RE_UNITNUM.search(text)),
        "pct": bool(RE_PCT.search(text)),
        "trend": bool(RE_TREND.search(text)),
        "abs": bool(RE_ABS.search(text)),
        "date": bool(RE_DATE.search(text)),
        "deadline": bool(RE_DEADLINE.search(text)),
        "attr": bool(RE_ATTR.search(text)),
        "money": bool(RE_MONEY.search(text)),
        "std": bool(RE_STD.search(text)),
        "event": bool(RE_EVENT.search(text)),
        "headline": section_topic == "公司头条",
    }
    kinds, evidence = [], []
    for key, pat, label in (
        ("pct", RE_PCT, "百分比/幅度"),
        ("num", RE_UNITNUM, "数字+单位"),
        ("std", RE_STD, "标准/法规编号"),
        ("date", RE_DATE, "时间"),
        ("trend", RE_TREND, "趋势"),
        ("abs", RE_ABS, "绝对化"),
        ("money", RE_MONEY, "金额/规模"),
        ("event", RE_EVENT, "事实性事件"),
        ("attr", RE_ATTR, "引用/预测"),
    ):
        if flags.get(key):
            kinds.append(label)
            for m in list(pat.finditer(text))[:3]:
                s = m.group(0).strip()
                if s and s not in evidence:
                    evidence.append(s)
    return flags, kinds, evidence


def grade(flags) -> tuple:
    """机械分级：高 = 写错会误导判断；中 = 常规复核；低 = 定性，可放过。"""
    lv = "低"
    why = []

    if flags["num"] or flags["trend"] or flags["attr"] or flags["date"] or flags["event"] or flags["std"]:
        lv = "中"

    if flags["pct"]:
        lv = "高"
        why.append("带百分比 / 幅度，最容易被放大")
    if flags["num"] and flags["trend"]:
        lv = "高"
        why.append("数据 + 趋势词，典型「数据趋势类」新闻")
    if flags["num"] and flags["abs"]:
        lv = "高"
        why.append("数据 + 绝对化表述（首个/最大/唯一…）")
    if flags["money"] and flags["num"]:
        lv = "高"
        why.append("金额 / 规模 / 份额类数据，口径差一点结果就反")
    if flags["std"]:
        lv = "高"
        why.append("标准 / 法规编号：必须核原文与生效日")
    if flags["date"] and flags["deadline"]:
        lv = "高"
        why.append("期限 / 生效日：写错会让人提前或错过动作")
    if flags["headline"] and flags["num"]:
        lv = "高"
        why.append("公司经营数据：外部查不到，只能作者确认")

    if flags["abs"] and lv == "中":
        why.append("绝对化表述")
    if flags["trend"] and lv == "中":
        why.append("趋势表述")
    if not why:
        why.append("常规复核")
    return lv, why


def split_sentences(text: str):
    parts = re.split(r"(?<=[。；！？!?])", text)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------- #
# 从 content.json 抽断言
# --------------------------------------------------------------------------- #
def load_orgs(sources_cfg: dict, topics_cfg: dict):
    orgs = set(sources_cfg.get("knownOrgs", []))
    for d in topics_cfg.get("pool", []):
        orgs.update(d.get("sources", []))
    # 长的优先匹配，免得「中国天气网」被「天气网」截胡
    return sorted(orgs, key=len, reverse=True)


def make_queries(claim, sources_cfg, domain_sources):
    ents = claim.get("orgs") or []
    num = claim.get("number") or ""
    base = " ".join(ents[:2]) if ents else claim["title"][:12]
    topic = claim.get("topic", "")
    qs = []
    for t in sources_cfg.get("queryTemplates", []):
        q = t.replace("{ent}", base).replace("{num}", num).replace("{topic}", topic)
        q = re.sub(r"\s+", " ", q).strip()
        if q and q not in qs:
            qs.append(q)
    if domain_sources:
        qs.append("优先查这些来源：" + " / ".join(domain_sources[:4]))
    return qs[:5]


def extract(content: dict, sources_cfg: dict, topics_cfg: dict, min_risk="低"):
    orgs = load_orgs(sources_cfg, topics_cfg)
    domain_sources = {}
    for d in topics_cfg.get("pool", []):
        domain_sources[d["name"]] = d.get("sources", [])

    claims = []
    for si, sec in enumerate(content.get("sections", []), 1):
        topic = sec.get("topic", "")
        title = sec.get("title", "")
        seen = set()
        n = 0
        for pi, para in enumerate(sec.get("paragraphs", []), 1):
            for sent in split_sentences(para):
                flags, kinds, evidence = detect(sent, topic)
                if not kinds:
                    continue
                lv, why = grade(flags)
                if RISK_ORDER[lv] > RISK_ORDER.get(min_risk, 2):
                    continue
                key = re.sub(r"\s+", "", sent)
                if key in seen:
                    continue
                seen.add(key)
                n += 1
                hit_orgs = [o for o in orgs if o in sent]
                nums = [e for e in evidence if re.search(r"\d", e)]
                claim = {
                    "id": f"S{si}-{n}",
                    "section": si,
                    "topic": topic,
                    "title": title,
                    "paragraph": pi,
                    "quote": sent,
                    "evidence": evidence,
                    "kinds": kinds,
                    "risk": lv,
                    "risk_reasons": why,
                    "orgs": hit_orgs,
                    "number": nums[0] if nums else "",
                    "domain_sources": domain_sources.get(topic, []),
                    "status": "pending",
                    "verdict": "",
                    "sources": [],
                    "note": "",
                    "action": "",
                }
                claim["suggested_queries"] = make_queries(claim, sources_cfg, claim["domain_sources"])
                claims.append(claim)

    # 高危在前，方便优先处理
    claims.sort(key=lambda c: (RISK_ORDER[c["risk"]], c["section"]))
    # 重排 id：保持稳定（按原始顺序给号更利于引用，所以这里不改 id）
    return claims


# --------------------------------------------------------------------------- #
# 卡口
# --------------------------------------------------------------------------- #
def gate(claims, sources_cfg):
    r = sources_cfg.get("rules", {}).get("gate", {})
    block_high = set(r.get("blockHigh", ["pending", "unjudgeable"]))
    block_mid = set(r.get("blockMid", ["pending"]))
    blocking, warns = [], []
    for c in claims:
        st = c.get("status", "pending")
        if c["risk"] == "高" and st in block_high:
            blocking.append(c)
        elif c["risk"] == "中" and st in block_mid:
            warns.append(c)
    unjudgeable = [c for c in claims if c.get("status") == "unjudgeable"]
    return blocking, warns, unjudgeable


# --------------------------------------------------------------------------- #
# 人读清单（Markdown）
# --------------------------------------------------------------------------- #
def write_checklist(path: Path, meta, claims):
    lines = [
        f"# 事实核查待办 · 第{meta['issue']}期 {meta['date']}（{meta['name']}）",
        "",
        f"共 **{meta['total']}** 条待核断言："
        + " / ".join(f"{k} {v} 条" for k, v in meta["by_risk"].items() if v),
        "",
        "> 逐条去查，把结论写回 `" + meta["json"] + "` 的 `status` 字段：",
        "> `confirmed` 已确证 · `softened` 已弱化 · `dropped` 已删除 · "
        "`unjudgeable` 无法判断（要写 `action` 判断指令给作者）",
        "> 每条都要在 `sources` 里留下你查到的来源（含链接），**同一篇被多家转载不算多源**。",
        "",
    ]
    cur = None
    for c in claims:
        if c["section"] != cur:
            cur = c["section"]
            lines += ["", f"## S{c['section']} · {c['topic']}｜{c['title']}", ""]
        lines.append(f"- [ ] **{c['id']}**  `{c['risk']}`  {c['id']}｜{'、'.join(c['kinds'])}")
        lines.append(f"      - 原因：{'；'.join(c['risk_reasons'])}")
        lines.append(f"      - 原文：{c['quote']}")
        if c.get("evidence"):
            lines.append(f"      - 抽取：{' / '.join(c['evidence'])}")
        for q in c.get("suggested_queries", []):
            lines.append(f"      - 建议查：`{q}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# HTML 报告
# --------------------------------------------------------------------------- #
CSS = """
:root{--ink:#22231f;--ink2:#5c5f56;--line:#e3e2d9;--bg:#f7f6f0;--card:#fff;--green:#7d8a5c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 60px;}
h1{font-size:24px;margin:0 0 6px;}
h2{font-size:18px;margin:34px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line);}
.sub{color:var(--ink2);font-size:13.5px;margin-bottom:20px;}
.banner{border-radius:12px;padding:16px 18px;margin:18px 0;font-size:15px;font-weight:600;line-height:1.6}
.ok{background:#eaf1e2;border:1px solid #cfdcbe;color:#3f5230}
.bad{background:#fdeceb;border:1px solid #f3c8c4;color:#8f2b21}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:104px}
.stat b{display:block;font-size:20px;line-height:1.2}
.stat span{font-size:12.5px;color:var(--ink2)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;margin:12px 0;}
.card h3{font-size:15.5px;margin:0 0 8px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.badge{font-size:11.5px;font-weight:700;color:#fff;border-radius:999px;padding:2px 9px;white-space:nowrap}
.state{font-size:11.5px;border-radius:999px;padding:2px 9px;background:#efeee6;color:var(--ink2);white-space:nowrap}
.quote{background:#faf9f4;border-left:3px solid var(--green);padding:8px 12px;border-radius:0 8px 8px 0;
  margin:8px 0;font-size:14.5px;}
.meta{font-size:13px;color:var(--ink2);margin:6px 0 0}
.meta b{color:var(--ink)}
ul.tight{margin:6px 0 0;padding-left:20px;font-size:13.5px}
ul.tight li{margin:3px 0}
.judge{background:#fff8e6;border:1px solid #e8d7a8;border-radius:12px;padding:14px 16px;margin:12px 0}
.judge h3{color:#7a5a12}
a{color:#3f6b45;word-break:break-all}
@media (max-width:560px){
  .wrap{padding:18px 13px 44px}
  h1{font-size:20px}
  .stat{flex:1 1 44%;min-width:0}
  .quote{font-size:14px}
}
"""


def esc(s):
    return _html.escape(str(s or ""))


def rich(s):
    """转义后再把 **粗体** 变成 <b>，免得报告里露出 markdown 星号；换行转 <br>。"""
    t = esc(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")


def render_report(path: Path, meta, claims, sources_cfg):
    blocking, warns, unjudgeable = gate(claims, sources_cfg)
    ok = not blocking
    head = "可以推：高危断言全部已处置" if ok else f"先别推：还有 {len(blocking)} 条高危断言未处置"

    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>事实核查报告 · 第{meta['issue']}期</title>",
        f"<style>{CSS}</style></head><body><div class='wrap'>",
        f"<h1>事实核查报告 · 第{meta['issue']}期</h1>",
        f"<div class='sub'>{meta['date']} · {meta['name']} · "
        f"生成于 {meta['generated']} · 信源分级表 <code>assets/sources.json</code></div>",
        f"<div class='banner {'ok' if ok else 'bad'}'>{esc(head)}</div>",
        "<div class='stats'>",
        f"<div class='stat'><b>{meta['total']}</b><span>可核查断言</span></div>",
    ]
    for k in ("高", "中", "低"):
        v = meta["by_risk"].get(k, 0)
        parts.append(f"<div class='stat'><b style='color:{RISK_BADGE[k]}'>{v}</b><span>{k}风险</span></div>")
    for k, lab in (("confirmed", "已确证"), ("softened", "已弱化"), ("dropped", "已删除"),
                   ("unjudgeable", "无法判断"), ("pending", "仍待核")):
        parts.append(f"<div class='stat'><b>{meta['by_status'].get(k, 0)}</b><span>{lab}</span></div>")
    parts.append("</div>")

    if unjudgeable:
        parts.append("<h2>给作者的判断指令</h2>")
        parts.append("<div class='sub'>这几条 AI 判断不了（要么是你公司内部的事，要么公开渠道找不到第二来源）。"
                     "请逐条给一句话结论，我据此定稿。</div>")
        for c in unjudgeable:
            parts.append("<div class='judge'>")
            parts.append(f"<h3>{esc(c['id'])} · {esc(c['topic'])}｜{esc(c['title'])}</h3>")
            parts.append(f"<div class='quote'>{rich(c['quote'])}</div>")
            if c.get("action"):
                parts.append(f"<div class='meta'><b>要你定夺：</b>{rich(c['action'])}</div>")
            else:
                parts.append("<div class='meta'><b>要你定夺：</b>（未填写 action，请补）</div>")
            if c.get("note"):
                parts.append(f"<div class='meta'><b>核查过程：</b>{rich(c['note'])}</div>")
            parts.append("</div>")

    if blocking:
        parts.append("<h2>未处置 · 高危</h2>")
        for c in blocking:
            parts.append(f"<div class='card'><h3><span class='badge' style='background:{RISK_BADGE['高']}'>高</span>"
                         f"<span>{esc(c['id'])}｜{esc(c['topic'])}</span>"
                         f"<span class='state'>{STATUS_LABEL.get(c['status'], c['status'])}</span></h3>"
                         f"<div class='quote'>{rich(c['quote'])}</div></div>")
    if warns:
        parts.append("<h2>建议复核 · 中危</h2>")
        for c in warns[:30]:
            parts.append(f"<div class='card'><h3><span class='badge' style='background:{RISK_BADGE['中']}'>中</span>"
                         f"<span>{esc(c['id'])}｜{esc(c['topic'])}</span></h3>"
                         f"<div class='quote'>{rich(c['quote'])}</div></div>")

    parts.append("<h2>逐条明细</h2>")
    cur = None
    for c in claims:
        if c["section"] != cur:
            cur = c["section"]
            parts.append(f"<h2 style='font-size:16px;border:0;margin:26px 0 6px'>"
                         f"S{c['section']} · {esc(c['topic'])}｜{esc(c['title'])}</h2>")
        parts.append("<div class='card'>")
        parts.append(f"<h3><span class='badge' style='background:{RISK_BADGE[c['risk']]}'>{c['risk']}</span>"
                     f"<span>{esc(c['id'])}</span><span class='state'>{esc(STATUS_LABEL.get(c['status'], c['status']))}</span></h3>")
        parts.append(f"<div class='quote'>{rich(c['quote'])}</div>")
        parts.append(f"<div class='meta'><b>抽到：</b>{esc('、'.join(c['kinds']))}"
                     f"　<b>理由：</b>{esc('；'.join(c['risk_reasons']))}</div>")
        if c.get("verdict"):
            parts.append(f"<div class='meta'><b>结论：</b>{rich(c['verdict'])}</div>")
        if c.get("note"):
            parts.append(f"<div class='meta'><b>备注：</b>{rich(c['note'])}</div>")
        if c.get("action"):
            parts.append(f"<div class='meta'><b>判断指令：</b>{rich(c['action'])}</div>")
        if c.get("sources"):
            parts.append("<ul class='tight'>")
            for s in c["sources"]:
                if isinstance(s, dict):
                    t = esc(s.get("title") or s.get("url") or "来源")
                    u = s.get("url") or ""
                    tier = s.get("tier") or ""
                    lk = f" <a href='{esc(u)}' target='_blank'>{esc(u)}</a>" if u else ""
                    parts.append(f"<li>[{esc(tier)}] {t}{lk}</li>")
                else:
                    parts.append(f"<li>{esc(s)}</li>")
            parts.append("</ul>")
        parts.append("</div>")

    parts.append("</div></body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="威尔新资讯 · 新闻事实核查")
    ap.add_argument("--content", required=True, help="content.json 路径")
    ap.add_argument("--report", action="store_true",
                    help="出报告 + 交付前卡口（不跑这一步只算抽取）")
    ap.add_argument("--out-dir", help="产物目录（默认 content.json 所在目录）")
    ap.add_argument("--name", help="产物前缀，如 39_0925（默认按期号+日期）")
    ap.add_argument("--sources", default=str(DEFAULT_SOURCES), help="信源分级表")
    ap.add_argument("--min-risk", choices=["高", "中", "低"], default="低",
                    help="抽取的最低风险级（默认全抽）")
    ap.add_argument("--no-html", action="store_true", help="只出 JSON/MD，不出 HTML 报告")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    content_path = Path(args.content).expanduser().resolve()
    if not content_path.exists():
        raise SystemExit(f"找不到内容文件：{content_path}")
    content = load_json(content_path)
    sources_cfg = load_json(Path(args.sources).expanduser().resolve())
    topics_cfg = load_json(DEFAULT_TOPICS)
    verbose = not args.quiet

    issue = content.get("issue")
    if not issue:
        raise SystemExit("content.json 里缺少 issue（期号）")
    date_str = content.get("date") or "auto"
    d = parse_date(date_str)
    date_str = f"{d.year}.{d.month}.{d.day}"
    name = args.name or (content.get("output", {}) or {}).get("name") or build_name(issue, date_str)
    out_dir = Path(args.out_dir or (content.get("output", {}) or {}).get("dir")
                   or content_path.parent).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"factcheck_{name}.json"
    md_path = out_dir / f"核查清单_{name}.md"
    html_path = out_dir / f"事实核查报告_{name}.html"

    if args.report:
        if not json_path.exists():
            raise SystemExit(f"还没有核查文件：{json_path}\n先跑一次不带 --report 的抽取。")
        data = load_json(json_path)
        claims = data.get("claims", [])
        meta = data.get("meta", {})
        meta["total"] = len(claims)
        meta["by_risk"] = {k: sum(1 for c in claims if c["risk"] == k) for k in ("高", "中", "低")}
        meta["by_status"] = {}
        for c in claims:
            meta["by_status"][c.get("status", "pending")] = \
                meta["by_status"].get(c.get("status", "pending"), 0) + 1
        data["meta"] = meta
        dump_json(json_path, data)

        blocking, warns, unjudgeable = gate(claims, sources_cfg)
        if not args.no_html:
            render_report(html_path, meta, claims, sources_cfg)

        if verbose:
            print(f"\n事实核查 · 报告（第{issue}期 {date_str} · {name}）")
            print(f"  可核查断言 {meta['total']} 条 "
                  f"（高 {meta['by_risk']['高']} / 中 {meta['by_risk']['中']} / 低 {meta['by_risk']['低']}）")
            for k, lab in (("confirmed", "已确证"), ("softened", "已弱化"), ("dropped", "已删除"),
                           ("unjudgeable", "无法判断"), ("pending", "仍待核")):
                if meta["by_status"].get(k):
                    print(f"  {lab:<8} {meta['by_status'][k]}")
            if unjudgeable:
                print(f"\n  【给作者的判断指令】{len(unjudgeable)} 条：")
                for c in unjudgeable:
                    print(f"    · {c['id']} {c['topic']}｜{c['title']}")
                    print(f"      {c.get('action') or '（未填 action，请补判断指令）'}")
            if blocking:
                print(f"\n  [X] 高危未处置 {len(blocking)} 条 —— 先别推：")
                for c in blocking:
                    print(f"    · {c['id']} [{c['risk']}] {c['topic']}：{c['quote'][:40]}…")
            else:
                print("\n  [ok] 高危断言全部已处置，可以交付")
            if warns:
                print(f"  [!] 中危仍待核 {len(warns)} 条（不拦，但建议看一眼）")
            if not args.no_html:
                print(f"\n报告：{html_path}")
        return 2 if blocking else 0

    # ---- 抽取 ----
    claims = extract(content, sources_cfg, topics_cfg, min_risk=args.min_risk)
    by_risk = {k: sum(1 for c in claims if c["risk"] == k) for k in ("高", "中", "低")}
    meta = {
        "issue": issue, "date": date_str, "name": name,
        "content": str(content_path), "json": json_path.name,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(claims), "by_risk": by_risk,
        "by_status": {"pending": len(claims)},
    }
    data = {
        "meta": meta,
        "_howto": [
            "逐条核查并把结果填回本文件：status = confirmed | softened | dropped | unjudgeable",
            "每条都要在 sources 里留下查到的来源（{tier,title,url}），同一篇被多家转载不算多源。",
            "status=unjudgeable 的必须在 action 里写一句『判断指令』，作者一句话就能答。",
            "verdict 写最终结论（一句话）；note 写核查过程（查了什么、各家怎么说）。",
            "填完跑：python scripts/fact_check.py --content <content.json> --report",
            "判据与要求见 references/fact-check.md，信源分级表见 assets/sources.json。",
        ],
        "claims": claims,
    }
    dump_json(json_path, data)
    write_checklist(md_path, meta, claims)

    if verbose:
        print(f"\n事实核查 · 抽取（第{issue}期 {date_str} · {name}）")
        print(f"  待核断言 {len(claims)} 条：" +
              " / ".join(f"{k} {v}" for k, v in by_risk.items() if v))
        cur = None
        for c in claims:
            if c["section"] != cur:
                cur = c["section"]
                print(f"\n  S{c['section']} · {c['topic']}｜{c['title']}")
            print(f"    [{c['risk']}] {c['id']} {'、'.join(c['kinds'])}")
            print(f"          {c['quote'][:64]}{'…' if len(c['quote']) > 64 else ''}")
        print(f"\n待核清单：{json_path}")
        print(f"人读清单：{md_path}")
        print("下一步：逐条核查后跑 --report（高危未处置会返回退出码 2，拦住交付）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
