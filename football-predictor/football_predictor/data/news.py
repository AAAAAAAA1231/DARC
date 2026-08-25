from __future__ import annotations

from xml.etree import ElementTree as ET

from .. import cache
from ..http_client import HttpError, fetch_text, quote
from .espn import NewsItem


def _parse_rss(xml_text: str, source: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        desc = (node.findtext("description") or "").strip()
        # 去掉 HTML 标签
        desc = ET.fromstring(f"<x>{desc}</x>").text if False else desc
        desc = desc.replace("<b>", "").replace("</b>", "")
        link = (node.findtext("link") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        if title:
            items.append(NewsItem(title=title, summary=desc[:280], source=source, published=pub, url=link))
    return items


def google_news(query: str, lang: str = "zh") -> list[NewsItem]:
    if lang == "zh":
        url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        )
        source = "Google新闻(中文)"
    else:
        url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=en-US&gl=US&ceid=US:en"
        )
        source = "Google News"
    key = f"news:{lang}:{query}"
    cached = cache.get_json(key, ttl_seconds=20 * 60)
    if isinstance(cached, list):
        return [NewsItem(**item) if isinstance(item, dict) else item for item in cached]
    try:
        xml_text = fetch_text(url, timeout=15)
    except HttpError:
        return []
    items = _parse_rss(xml_text, source)[:8]
    cache.set_json(
        key,
        [
            {
                "title": i.title,
                "summary": i.summary,
                "source": i.source,
                "published": i.published,
                "url": i.url,
            }
            for i in items
        ],
    )
    return items


def collect_match_news(
    home_cn: str,
    away_cn: str,
    home_en: str,
    away_en: str,
    league_cn: str,
    light: bool = False,
) -> list[NewsItem]:
    if light:
        queries = [
            (f'"{home_cn}" "{away_cn}" (前瞻 OR 伤停) when:14d', "zh"),
            (f'"{home_en}" "{away_en}" (preview OR injury) when:14d', "en"),
        ]
    else:
        queries = [
            (f'"{home_cn}" "{away_cn}" (前瞻 OR 伤停 OR 对阵) when:21d', "zh"),
            (f'"{home_cn}" (伤停 OR 停赛 OR 缺阵) when:14d', "zh"),
            (f'"{away_cn}" (伤停 OR 停赛 OR 缺阵) when:14d', "zh"),
            (f'"{home_en}" "{away_en}" (preview OR injury OR suspension) when:21d', "en"),
            (f'"{home_en}" (injured OR suspended OR doubtful OR lineup) when:14d', "en"),
            (f'"{away_en}" (injured OR suspended OR doubtful OR lineup) when:14d', "en"),
        ]
    cap = 8 if light else 18
    seen: set[str] = set()
    out: list[NewsItem] = []
    for q, lang in queries:
        for item in google_news(q, lang=lang):
            key = item.title.strip().lower()
            if key in seen or not item.title:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= cap:
                return out
    return out
