"""Per-venue stock universe: Sina board lists for A-shares, static books for HK/US."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .markets import MARKET_BY_KEY, MARKETS, Market
from .quotes import HttpGet, QuoteError, http_get_json

SINA_BOARD = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
DEFAULT_PER_MARKET = 40
SKIP_NAME_MARKERS = ("ST", "*ST", "退市", "退")

BOARD_NODE = {
    "sse": "sh_a",
    "szse": "sz_a",
    "chinext": "cyb",
    "star": "kcb",
    "bse": "hs_bjs",
}

HK_NAMES = (
    ("0700.HK", "腾讯控股"),
    ("9988.HK", "阿里巴巴"),
    ("3690.HK", "美团"),
    ("1810.HK", "小米集团"),
    ("9618.HK", "京东集团"),
    ("0941.HK", "中国移动"),
    ("1299.HK", "友邦保险"),
    ("0388.HK", "香港交易所"),
    ("0005.HK", "汇丰控股"),
    ("0939.HK", "建设银行"),
    ("1398.HK", "工商银行"),
    ("3988.HK", "中国银行"),
    ("0883.HK", "中国海洋石油"),
    ("0857.HK", "中国石油股份"),
    ("0386.HK", "中国石油化工"),
    ("2628.HK", "中国人寿"),
    ("2318.HK", "中国平安"),
    ("1211.HK", "比亚迪股份"),
    ("2020.HK", "安踏体育"),
    ("0175.HK", "吉利汽车"),
    ("0669.HK", "创科实业"),
    ("2382.HK", "舜宇光学"),
    ("1024.HK", "快手"),
    ("9868.HK", "小鹏汽车"),
    ("2015.HK", "理想汽车"),
    ("9866.HK", "蔚来"),
    ("0960.HK", "龙湖集团"),
    ("1109.HK", "华润置地"),
    ("0688.HK", "中国海外发展"),
    ("0016.HK", "新鸿基地产"),
)

US_NAMES = (
    ("AAPL", "苹果"),
    ("MSFT", "微软"),
    ("NVDA", "英伟达"),
    ("AMZN", "亚马逊"),
    ("GOOGL", "谷歌"),
    ("META", "Meta"),
    ("TSLA", "特斯拉"),
    ("AVGO", "博通"),
    ("COST", "开市客"),
    ("NFLX", "奈飞"),
    ("AMD", "超威"),
    ("INTC", "英特尔"),
    ("QCOM", "高通"),
    ("ADBE", "Adobe"),
    ("PEP", "百事"),
    ("CSCO", "思科"),
    ("AMGN", "安进"),
    ("INTU", "Intuit"),
    ("TXN", "德州仪器"),
    ("AMAT", "应用材料"),
    ("HON", "霍尼韦尔"),
    ("SBUX", "星巴克"),
    ("GILD", "吉列德"),
    ("MU", "美光"),
    ("BKNG", "Booking"),
    ("ADP", "ADP"),
    ("VRTX", "Vertex"),
    ("LRCX", "拉姆研究"),
    ("ISRG", "直觉外科"),
    ("TMUS", "T-Mobile"),
)


@dataclass(frozen=True)
class Instrument:
    market: Market
    symbol: str
    name: str
    sina: str | None
    tencent: str | None
    yahoo: str | None


def skip_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return True
    upper = text.upper()
    if upper.startswith("N") and not upper.startswith("NIO"):
        # Sina marks unseasoned listings as Nxxx; keep 宁德时代 etc. which do not start with N.
        if len(text) <= 6:
            return True
    return any(mark in text or mark in upper for mark in ("*ST", "ST", "退市"))


def code_belongs(market_key: str, code: str) -> bool:
    code = str(code).zfill(6) if str(code).isdigit() else str(code)
    if market_key == "sse":
        return code.startswith(("600", "601", "603", "605"))
    if market_key == "szse":
        return code.startswith(("000", "001", "002", "003"))
    if market_key == "chinext":
        return code.startswith(("300", "301"))
    if market_key == "star":
        return code.startswith("688")
    if market_key == "bse":
        return code.startswith(("4", "8", "9", "83", "87", "92", "43"))
    return True


def ids_from_sina_symbol(sina_symbol: str) -> tuple[str, str, str | None]:
    s = sina_symbol.strip().lower()
    if s.startswith("sh"):
        code = s[2:].zfill(6)
        return code, s, f"{code}.SS"
    if s.startswith("sz"):
        code = s[2:].zfill(6)
        return code, s, f"{code}.SZ"
    if s.startswith("bj"):
        code = s[2:]
        return code, s, f"{code}.BJ"
    return s, s, None


def parse_sina_board(rows: Any, market: Market, limit: int) -> list[Instrument]:
    if not isinstance(rows, list):
        return []
    out: list[Instrument] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        sina_symbol = str(row.get("symbol") or "")
        name = str(row.get("name") or "")
        code = str(row.get("code") or "")
        if not sina_symbol or skip_name(name):
            continue
        code, tencent, yahoo = ids_from_sina_symbol(sina_symbol)
        if not code_belongs(market.key, code):
            continue
        if code in seen:
            continue
        seen.add(code)
        out.append(
            Instrument(
                market=market,
                symbol=code,
                name=name,
                sina=sina_symbol,
                tencent=tencent,
                yahoo=yahoo,
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_sina_board_rows(node: str, http_get: HttpGet, limit: int) -> list[dict]:
    page_size = 80
    pages = max(1, (limit + page_size - 1) // page_size)
    rows: list[dict] = []
    for page in range(1, pages + 1):
        payload = http_get(
            SINA_BOARD,
            {"page": str(page), "num": str(page_size), "sort": "amount", "asc": "0", "node": node},
        )
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < page_size:
            break
    return rows


def hk_instruments(limit: int) -> list[Instrument]:
    market = MARKET_BY_KEY["hkex"]
    out: list[Instrument] = []
    for yahoo, name in HK_NAMES[:limit]:
        digits = yahoo.split(".", 1)[0]
        tencent = "hk" + digits.zfill(5)
        out.append(Instrument(market=market, symbol=digits, name=name, sina=None, tencent=tencent, yahoo=yahoo))
    return out


def us_instruments(limit: int) -> list[Instrument]:
    market = MARKET_BY_KEY["us"]
    out: list[Instrument] = []
    for yahoo, name in US_NAMES[:limit]:
        out.append(
            Instrument(
                market=market,
                symbol=yahoo,
                name=name,
                sina=None,
                tencent="us" + yahoo,
                yahoo=yahoo,
            )
        )
    return out


def list_instruments(
    market: Market,
    http_get: HttpGet = http_get_json,
    limit: int = DEFAULT_PER_MARKET,
) -> list[Instrument]:
    if market.key == "hkex":
        return hk_instruments(limit)
    if market.key == "us":
        return us_instruments(limit)
    node = BOARD_NODE.get(market.key)
    if not node:
        return []
    try:
        rows = fetch_sina_board_rows(node, http_get, limit=max(limit * 3, limit))
    except QuoteError:
        return []
    return parse_sina_board(rows, market, limit)


def list_all_instruments(
    http_get: HttpGet = http_get_json,
    limit: int = DEFAULT_PER_MARKET,
    markets: tuple[Market, ...] = MARKETS,
) -> list[Instrument]:
    out: list[Instrument] = []
    for market in markets:
        out.extend(list_instruments(market, http_get=http_get, limit=limit))
    return out
