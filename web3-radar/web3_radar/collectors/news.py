from __future__ import annotations

import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

from web3_radar.fallback import load_fallback, merge_items
from web3_radar.http_util import client

BJ = timezone(timedelta(hours=8))
NEWS_MAX_AGE_SEC = 24 * 3600

RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
    ("美联储", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
]

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
BINANCE_CMS = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"

# Only keep headlines that can actually open a directional tape.
BULL_HINTS = (
    ("etf approv", "ETF/机构", 22),
    ("spot bitcoin etf", "ETF/机构", 18),
    ("etf inflow", "ETF/机构", 16),
    ("etf 批准", "ETF/机构", 22),
    ("净流入", "ETF/机构", 14),
    ("rate cut", "宏观利率", 22),
    ("cuts rates", "宏观利率", 22),
    ("降息", "宏观利率", 22),
    ("dovish", "宏观利率", 16),
    ("鸽派", "宏观利率", 16),
    ("strategic bitcoin reserve", "监管政策", 24),
    ("strategic reserve", "监管政策", 20),
    ("战略储备", "监管政策", 22),
    ("legal tender", "监管政策", 18),
    ("pause hikes", "宏观利率", 14),
    ("blackrock buy", "ETF/机构", 12),
)
BEAR_HINTS = (
    ("rate hike", "宏观利率", 22),
    ("hikes rates", "宏观利率", 22),
    ("加息", "宏观利率", 22),
    ("hawkish", "宏观利率", 16),
    ("鹰派", "宏观利率", 16),
    ("etf outflow", "ETF/机构", 16),
    ("净流出", "ETF/机构", 14),
    ("sec charges", "监管政策", 16),
    ("sec sues", "监管政策", 16),
    ("lawsuit", "监管政策", 10),
    ("ban bitcoin", "监管政策", 18),
    ("bans crypto", "监管政策", 18),
    ("禁止加密", "监管政策", 18),
    ("全面禁止", "监管政策", 16),
    ("hacked", "安全事件", 20),
    ("bridge hack", "安全事件", 20),
    ("exploit", "安全事件", 16),
    ("被盗", "安全事件", 18),
    ("depeg", "稳定币", 24),
    ("脱锚", "稳定币", 24),
    ("losing peg", "稳定币", 22),
    ("paused withdrawals", "交易所", 18),
    ("suspends withdrawals", "交易所", 18),
    ("暂停提现", "交易所", 18),
    ("bankruptcy", "交易所", 18),
    ("insolvency", "交易所", 16),
    ("破产", "交易所", 18),
    ("network outage", "网络故障", 14),
    ("chain halt", "网络故障", 16),
    ("宕机", "网络故障", 14),
    ("halted blocks", "网络故障", 14),
    ("liquidation cascade", "杠杆清算", 18),
    ("大规模清算", "杠杆清算", 18),
)
EITHER_HINTS = (
    ("fomc", "宏观利率", 20),
    ("federal open market", "宏观利率", 20),
    ("federal reserve", "宏观利率", 12),
    ("美联储", "宏观利率", 14),
    ("鲍威尔", "宏观利率", 16),
    ("powell", "宏观利率", 16),
    ("interest rate decision", "宏观利率", 20),
    ("利率决议", "宏观利率", 20),
    ("cpi", "宏观利率", 18),
    ("consumer price", "宏观利率", 16),
    ("pce", "宏观利率", 16),
    ("nfp", "宏观利率", 18),
    ("non-farm", "宏观利率", 18),
    ("nonfarm", "宏观利率", 18),
    ("非农", "宏观利率", 18),
    ("unemployment rate", "宏观利率", 12),
    ("gdp", "宏观利率", 10),
    ("tariff", "地缘", 12),
    ("关税", "地缘", 12),
    ("war ", "地缘", 12),
    ("missile", "地缘", 10),
    ("emergency meeting", "宏观利率", 14),
    ("circuit breaker", "杠杆清算", 12),
)

CALENDAR_KEEP = (
    "fomc",
    "interest rate",
    "rate decision",
    "cpi",
    "pce",
    "nfp",
    "non-farm",
    "nonfarm",
    "unemployment",
    "powell",
    "gdp",
    "ppi",
    "core inflation",
    "retail sales",
)
CALENDAR_COUNTRIES = {"USD", "CNY", "EUR", "JPY", "GBP"}

NOISE = (
    "hackathon",
    "price prediction",
    "how to buy",
    "giveaway",
    "airdrop guide",
    "best crypto",
    "opinion:",
    "sponsored",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _blob(*parts: str) -> str:
    return " ".join(_norm(p).lower() for p in parts if p)


def _hit(blob: str, phrase: str) -> bool:
    p = phrase.lower()
    if p.endswith(" "):
        return p in f" {blob} "
    return p in blob


def classify_headline(title: str, summary: str = "") -> dict[str, Any] | None:
    """Return None when the item is ordinary noise, not a 单边 catalyst."""
    title_n = _norm(title)
    blob = _blob(title_n, summary)
    if not title_n or any(n in blob for n in NOISE):
        return None
    bull = 0
    bear = 0
    category = ""
    reasons: list[str] = []
    for phrase, cat, pts in BULL_HINTS:
        if _hit(blob, phrase):
            bull += pts
            category = category or cat
            reasons.append(phrase.strip())
    for phrase, cat, pts in BEAR_HINTS:
        if _hit(blob, phrase):
            bear += pts
            category = category or cat
            reasons.append(phrase.strip())
    either = 0
    for phrase, cat, pts in EITHER_HINTS:
        if _hit(blob, phrase):
            either += pts
            category = category or cat
            reasons.append(phrase.strip())
    score = bull + bear + either
    if score < 12:
        return None
    if bull - bear >= 8:
        bias = "偏多"
    elif bear - bull >= 8:
        bias = "偏空"
    else:
        bias = "方向未定"
    if score >= 28:
        impact = "高"
    elif score >= 16:
        impact = "中"
    else:
        impact = "低"
    why = "、".join(dict.fromkeys(reasons[:4])) or "宏观/监管事件"
    if bias == "方向未定":
        playbook = "公布前后波动容易突然打开，先看是否从震荡切到单边，不要提前追突破。"
    elif bias == "偏多":
        playbook = "消息偏多，若K线确认单边再跟涨；震荡里当噪音。"
    else:
        playbook = "消息偏空，若K线确认单边再跟跌；震荡里当噪音。"
    return {
        "category": category or "宏观利率",
        "bias": bias,
        "impact": impact,
        "score": min(99, 50 + score),
        "why": why,
        "playbook": playbook,
    }


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 1e12:
            raw /= 1000.0
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    text = str(value).strip()
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        iso = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def beijing_label(dt: datetime | None) -> str:
    if not dt:
        return "时间待确认"
    return dt.astimezone(BJ).strftime("%m-%d %H:%M 北京时间")


def timing_fields(dt: datetime | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    if not dt:
        return {
            "when_utc": "",
            "when_label": "时间待确认",
            "when_status": "未知",
            "seconds_to": None,
            "alert": False,
        }
    delta = (dt - now).total_seconds()
    if delta > 3600:
        status = f"{delta / 3600:.1f} 小时后"
    elif delta > 0:
        status = f"{int(delta / 60)} 分钟后公布"
    elif delta > -3600:
        status = f"{int(-delta / 60)} 分钟前"
    elif delta > -86400:
        status = f"{-delta / 3600:.1f} 小时前"
    else:
        status = f"{int(-delta / 86400)} 天前"
    upcoming = 0 <= delta <= 24 * 3600
    recent = -24 * 3600 <= delta < 0
    return {
        "when_utc": dt.isoformat(),
        "when_label": f"{beijing_label(dt)} · {status}",
        "when_status": status,
        "seconds_to": int(delta),
        "alert": upcoming or recent,
    }


def _key(*parts: str) -> str:
    raw = "|".join(p.strip().lower() for p in parts if p)
    return "news:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _item(
    title: str,
    url: str,
    source: str,
    kind: str,
    summary: str = "",
    when: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    classified = classify_headline(title, summary)
    if not classified:
        return None
    when = when or _now()
    timed = timing_fields(when)
    impact = classified["impact"]
    alert = bool(timed["alert"] and impact in {"高", "中"} and classified["score"] >= 66)
    if impact == "高" and timed["seconds_to"] is not None and abs(timed["seconds_to"]) <= NEWS_MAX_AGE_SEC:
        alert = True
    row = {
        "key": _key(url or title, source),
        "title": _norm(title)[:180],
        "text": _norm(summary)[:400],
        "url": url,
        "source": source,
        "source_kind": "live",
        "kind": kind,
        "category": classified["category"],
        "bias": classified["bias"],
        "impact": impact,
        "score": classified["score"],
        "why": classified["why"],
        "playbook": classified["playbook"],
        "alert": alert,
        "alert_level": "紧急" if alert and impact == "高" else ("关注" if alert else ""),
        **timed,
    }
    if extra:
        row.update(extra)
    return row


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_feed_xml(xml_text: str, source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    nodes = list(root.iter())
    entries = [n for n in nodes if _local(n.tag) in {"item", "entry"}]
    for node in entries[:40]:
        title = ""
        link = ""
        summary = ""
        when = None
        for child in list(node):
            name = _local(child.tag)
            if name == "title":
                title = child.text or ""
            elif name == "link":
                link = (child.get("href") or child.text or link or "").strip()
            elif name in {"description", "summary", "content"}:
                summary = re.sub(r"<[^>]+>", " ", child.text or "")
            elif name in {"pubDate", "published", "updated", "date"}:
                when = _parse_time(child.text)
        row = _item(title, link, source, "新闻", summary, when)
        if row:
            items.append(row)
    return items


async def _fetch_rss(name: str, url: str) -> list[dict[str, Any]]:
    async with client(timeout=10.0) as c:
        resp = await c.get(url)
        resp.raise_for_status()
        return parse_feed_xml(resp.text, name)


def _calendar_title(row: dict[str, Any]) -> str:
    title = _norm(str(row.get("title") or row.get("event") or ""))
    country = str(row.get("country") or row.get("currency") or "").upper()
    return f"{country} {title}".strip()


def parse_calendar_rows(rows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or _now()
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        country = str(raw.get("country") or raw.get("currency") or "").upper()
        if country and country not in CALENDAR_COUNTRIES:
            continue
        impact = str(raw.get("impact") or raw.get("importance") or "").lower()
        title = _calendar_title(raw)
        blob = _blob(title)
        if not any(k in blob for k in CALENDAR_KEEP) and impact not in {"high", "3", "red"}:
            continue
        if not any(k in blob for k in CALENDAR_KEEP):
            continue
        when = _parse_time(raw.get("date") or raw.get("datetime") or raw.get("time"))
        extra = {
            "forecast": raw.get("forecast") or "",
            "previous": raw.get("previous") or "",
            "actual": raw.get("actual") or "",
            "country": country,
        }
        summary = f"预测 {extra['forecast'] or '-'} · 前值 {extra['previous'] or '-'}"
        classified = classify_headline(title, "FOMC interest rate CPI NFP PCE")
        if not classified:
            classified = {
                "category": "宏观利率",
                "bias": "方向未定",
                "impact": "中",
                "score": 70,
                "why": title,
                "playbook": "公布前后波动容易突然打开，先看是否从震荡切到单边，不要提前追突破。",
            }
        timed = timing_fields(when, now)
        high = impact in {"high", "3", "red"}
        item = {
            "key": _key(title, str(when), "calendar"),
            "title": title[:180],
            "text": summary,
            "url": "https://www.forexfactory.com/calendar",
            "source": "宏观日历",
            "source_kind": "live",
            "kind": "日历",
            "category": classified["category"],
            "bias": "方向未定",
            "impact": "高" if high else classified["impact"],
            "score": max(int(classified["score"]), 82 if high else 70),
            "why": classified["why"],
            "playbook": classified["playbook"],
            **timed,
            **extra,
        }
        if timed.get("seconds_to") is not None and abs(int(timed["seconds_to"])) <= NEWS_MAX_AGE_SEC:
            item["alert"] = True
            item["alert_level"] = "紧急" if item["impact"] == "高" else "关注"
        else:
            item["alert"] = False
            item["alert_level"] = ""
        out.append(item)
    return out


async def _fetch_calendar() -> list[dict[str, Any]]:
    async with client(timeout=10.0) as c:
        resp = await c.get(CALENDAR_URL)
        resp.raise_for_status()
        data = resp.json()
    rows = data if isinstance(data, list) else (data.get("events") or data.get("data") or [])
    return parse_calendar_rows(rows if isinstance(rows, list) else [])


async def _fetch_binance() -> list[dict[str, Any]]:
    async with client(timeout=10.0) as c:
        resp = await c.get(BINANCE_CMS, params={"type": 1, "pageNo": 1, "pageSize": 20})
        resp.raise_for_status()
        payload = resp.json()
    catalogs = ((payload.get("data") or {}).get("catalogs")) or []
    out: list[dict[str, Any]] = []
    for cat in catalogs:
        for art in cat.get("articles") or []:
            title = str(art.get("title") or "")
            code = str(art.get("code") or art.get("id") or "")
            url = f"https://www.binance.com/en/support/announcement/{quote(code)}" if code else "https://www.binance.com/en/support/announcement"
            when = _parse_time(art.get("releaseDate") or art.get("publishDate"))
            row = _item(title, url, "币安公告", "公告", title, when)
            if row:
                out.append(row)
    return out


def cluster_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in items:
        key = f"{row.get('category') or '其他'}|{row.get('bias') or ''}"
        buckets.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for rows in buckets.values():
        rows = sorted(rows, key=lambda x: (-int(x.get("score") or 0), not x.get("alert")))
        head = dict(rows[0])
        head["cluster_size"] = len(rows)
        head["cluster"] = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "source": r.get("source"),
                "when_label": r.get("when_label"),
            }
            for r in rows[:8]
        ]
        if len(rows) > 1:
            head["headline"] = f"{head.get('category')}（{len(rows)}条同向）"
            head["text"] = "依据：" + "；".join(str(r.get("title") or "") for r in rows[:4])
        else:
            head["headline"] = head.get("title")
        out.append(head)
    out.sort(key=lambda x: (not x.get("alert"), -(x.get("score") or 0)))
    return out


def synthesize_stance(items: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    """Turn headlines into one 做多 / 做空 / 观望 call with grouped evidence."""
    now = now or _now()
    long_items: list[dict[str, Any]] = []
    short_items: list[dict[str, Any]] = []
    wait_items: list[dict[str, Any]] = []
    long_pts = short_pts = wait_pts = 0.0
    for row in items:
        if row.get("source_kind") == "seed" or row.get("source") == "观察池":
            continue
        weight = float(row.get("score") or 0)
        if row.get("impact") == "高":
            weight *= 1.35
        if row.get("alert"):
            weight *= 1.15
        secs = row.get("seconds_to")
        bias = str(row.get("bias") or "")
        upcoming = row.get("kind") == "日历" and secs is not None and float(secs) > 0
        if upcoming or bias == "方向未定":
            wait_items.append(row)
            wait_pts += weight
            continue
        if bias == "偏多":
            long_items.append(row)
            long_pts += weight
        elif bias == "偏空":
            short_items.append(row)
            short_pts += weight
        else:
            wait_items.append(row)
            wait_pts += weight

    def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda x: (-int(x.get("score") or 0), not x.get("alert")))

    long_items, short_items, wait_items = _rank(long_items), _rank(short_items), _rank(wait_items)
    imminent = [
        row
        for row in wait_items
        if row.get("kind") == "日历"
        and row.get("impact") == "高"
        and row.get("seconds_to") is not None
        and 0 < float(row["seconds_to"]) <= 8 * 3600
    ]
    gap = long_pts - short_pts
    if long_pts >= 80 and gap >= 28 and not (imminent and abs(gap) < 50):
        stance = "做多"
    elif short_pts >= 80 and -gap >= 28 and not (imminent and abs(gap) < 50):
        stance = "做空"
    else:
        stance = "观望"
    if imminent and stance != "观望" and abs(gap) < 50:
        stance = "观望"

    strength = max(long_pts, short_pts)
    if stance == "观望":
        confidence = "中" if imminent or (long_items and short_items) else "低"
    elif abs(gap) >= 60 and strength >= 120:
        confidence = "高"
    else:
        confidence = "中"

    def _titles(rows: list[dict[str, Any]], n: int = 3) -> str:
        return "；".join(str(r.get("title") or "") for r in rows[:n] if r.get("title"))

    if stance == "做多":
        summary = "消息面整理后偏多：" + (_titles(long_items) or "利多催化剂占优") + "。"
        playbook = "结论是偏多，不是马上追涨。先看合约页有没有从震荡切到单边，切了再跟。"
    elif stance == "做空":
        summary = "消息面整理后偏空：" + (_titles(short_items) or "利空催化剂占优") + "。"
        playbook = "结论是偏空，不是马上追跌。先看合约页有没有从震荡切到单边，切了再跟。"
    else:
        bits: list[str] = []
        if imminent:
            bits.append("临近 " + "、".join(str(x.get("title") or "") for x in imminent[:2]) + "，公布前方向未定")
        if long_items and short_items:
            bits.append("利多与利空同时存在，净方向不够清楚")
        if not bits:
            bits.append("还没有足够强的单边催化剂")
        summary = "消息面结论：观望。" + "；".join(bits) + "。"
        playbook = "先看合约页是震荡还是单边。没切单边，不要因为标题下手。"

    return {
        "stance": stance,
        "stance_tag": "涨" if stance == "做多" else ("跌" if stance == "做空" else "观望"),
        "confidence": confidence,
        "summary": summary,
        "playbook": playbook,
        "long_score": round(long_pts, 1),
        "short_score": round(short_pts, 1),
        "wait_score": round(wait_pts, 1),
        "long_count": len(long_items),
        "short_count": len(short_items),
        "wait_count": len(wait_items),
        "groups": {
            "long": cluster_items(long_items),
            "short": cluster_items(short_items),
            "wait": cluster_items(wait_items),
        },
    }


def _seed_items() -> list[dict[str, Any]]:
    return list(load_fallback().get("news") or [])


def news_is_fresh(row: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _now()
    secs = row.get("seconds_to")
    if secs is not None:
        try:
            return abs(int(secs)) <= NEWS_MAX_AGE_SEC
        except (TypeError, ValueError):
            pass
    when = _parse_time(row.get("when_utc") or row.get("created_at") or row.get("published_at"))
    if not when:
        return False
    return abs((when - now).total_seconds()) <= NEWS_MAX_AGE_SEC


def filter_fresh_news(rows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    return [row for row in rows or [] if news_is_fresh(row, now)]


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        prev = out.get(key)
        if prev is None or int(row.get("score") or 0) > int(prev.get("score") or 0):
            out[key] = row
    return list(out.values())


async def scan_news() -> dict[str, Any]:
    errors: list[str] = []
    tasks = [_fetch_rss(name, url) for name, url in RSS_FEEDS]
    tasks.append(_fetch_calendar())
    tasks.append(_fetch_binance())
    wrapped = [asyncio.wait_for(task, timeout=9) for task in tasks]
    results = await asyncio.gather(*wrapped, return_exceptions=True)
    live: list[dict[str, Any]] = []
    for idx, result in enumerate(results):
        label = (RSS_FEEDS[idx][0] if idx < len(RSS_FEEDS) else ("宏观日历" if idx == len(RSS_FEEDS) else "币安公告"))
        if isinstance(result, Exception):
            errors.append(f"{label}: {result}")
            continue
        live.extend(result)
    items = filter_fresh_news(_dedupe(live))
    items.sort(key=lambda x: (not x.get("alert"), -(x.get("score") or 0), x.get("seconds_to") is None, abs(x.get("seconds_to") or 10**12)))
    if not items:
        items = filter_fresh_news(merge_items([], _seed_items()))
        note = "过去 24 小时没有可用催化剂，结论先按观望，刷新后再试。"
    else:
        items = items[:60]
        note = "只保留过去 24 小时的消息，并整理成做多 / 做空 / 观望，不是投资建议。"
    stance = synthesize_stance(items)
    alerts = [x for x in items if x.get("alert")]
    return {
        "updated_at": _now().isoformat(),
        "items": items,
        "alerts": alerts,
        "stance": stance,
        "count": len(items),
        "alert_count": len(alerts),
        "errors": errors[:6],
        "note": note,
    }
