"""Score new-launch tweets by VC / celebrity / KOL attention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Institutions / funds whose mention is a strong launch signal.
INSTITUTION_ALIASES: dict[str, tuple[str, ...]] = {
    "Paradigm": ("paradigm", "paradigm.xyz"),
    "a16z": ("a16z", "a16z crypto", "andreessen", "a16zcrypto"),
    "Binance Labs": ("binance labs", "binancelabs", "yzi labs", "yzilabs"),
    "Coinbase Ventures": ("coinbase ventures", "coinbaseventures"),
    "Polychain": ("polychain",),
    "Pantera": ("pantera",),
    "Sequoia": ("sequoia",),
    "Dragonfly": ("dragonfly",),
    "Multicoin": ("multicoin",),
    "Framework": ("framework ventures", "frameworkvc"),
    "Hack VC": ("hack vc", "hackvc"),
    "Delphi": ("delphi digital", "delphidigital", "delphi"),
    "Hashed": ("hashed",),
    "Animoca": ("animoca",),
    "OKX Ventures": ("okx ventures", "okxventures"),
    "Jump": ("jump crypto", "jump trading", "jumpcrypto"),
    "Wintermute": ("wintermute",),
    "GSR": ("gsr",),
    "Circle": ("circle ventures",),
    "Solana Ventures": ("solana ventures",),
}

# Notable handles: KOL / founder / celebrity. Keys are lowercase without @.
NOTABLE_HANDLES: dict[str, tuple[str, int]] = {
    # (display, bonus)
    "elonmusk": ("Elon Musk", 22),
    "vitalikbuterin": ("Vitalik", 20),
    "cz_binance": ("CZ", 20),
    "justinsuntron": ("Justin Sun", 16),
    "balajis": ("Balaji", 14),
    "naval": ("Naval", 12),
    "cobie": ("Cobie", 14),
    "hsaka": ("Hsaka", 10),
    "inversebrah": ("Inversebrah", 8),
    "thedefiedge": ("DeFi Edge", 10),
    "pentosh1": ("Pentoshi", 10),
    "cryptohayes": ("Arthur Hayes", 14),
    "haydenzadams": ("Hayden Adams", 12),
    "stani.eth": ("Stani", 12),
    "stani": ("Stani Kulechov", 12),
    "sandeepnailwal": ("Sandeep Nailwal", 12),
    "gakonst": ("Georgios", 10),
    "gavinwood": ("Gavin Wood", 12),
    "iohk_charles": ("Charles Hoskinson", 10),
    "jespow": ("Jesse Powell", 8),
    "brian_armstrong": ("Brian Armstrong", 14),
    "zachxbt": ("ZachXBT", 10),
    "lookonchain": ("Lookonchain", 8),
    "ai_9684xtpa": ("AI 9684", 8),
    "blknoiz06": ("Ansem", 12),
    "ansem": ("Ansem", 12),
    "0xngmi": ("0xngmi", 8),
    "tradermayor": ("Trader Mayor", 8),
    "cryptotrader": ("CryptoTrader", 6),
}

BACKING_PHRASES = (
    "backed by",
    "led by",
    "领投",
    "跟投",
    "战略投资",
    "raised from",
    "seed round",
    "invested by",
    "vc round",
)

LAUNCH_KEYWORDS = (
    "发射",
    "即将发射",
    "新平台",
    "新项目",
    "预售",
    "打新",
    "launch",
    "launched",
    "launching",
    "presale",
    "pre-sale",
    "pre sale",
    "new project",
    "newproject",
    "new platform",
    "fair launch",
    "token generation",
    "tge",
    "ido",
    "ico",
    "ieo",
    "stealth launch",
    "fairlaunch",
)

CEX_HINTS = (
    "will list",
    "will be listed",
    "listing on",
    "lists ",
    "listed on",
    "spot listing",
    "futures listing",
    "上线",
    "上币",
    "现货上线",
    "合约上线",
    "announcement",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def within_lookback(created_at: datetime | None, now: datetime | None = None, days: int = 30) -> bool:
    """Keep undated tweets (search already constrained) and anything inside the window."""
    ts = _as_aware(created_at)
    if ts is None:
        return True
    now = _as_aware(now) or _now()
    return ts >= now - timedelta(days=days)


def looks_like_cex_listing(text: str) -> bool:
    blob = (text or "").lower()
    return any(h in blob for h in CEX_HINTS) and not any(
        k in blob for k in ("presale", "预售", "fair launch", "发射", "ido")
    )


def extract_institutions(text: str) -> list[str]:
    blob = (text or "").lower()
    found: list[str] = []
    for name, aliases in INSTITUTION_ALIASES.items():
        if any(alias in blob for alias in aliases):
            found.append(name)
    return found


def notable_for_handle(handle: str) -> tuple[str, int] | None:
    key = (handle or "").lstrip("@").lower()
    return NOTABLE_HANDLES.get(key)


def recency_score(created_at: datetime | None, now: datetime | None = None) -> int:
    ts = _as_aware(created_at)
    if ts is None:
        return 8
    now = _as_aware(now) or _now()
    hours = max(0.0, (now - ts).total_seconds() / 3600)
    if hours <= 24:
        return 18
    if hours <= 72:
        return 14
    if hours <= 24 * 7:
        return 10
    if hours <= 24 * 14:
        return 6
    return 3


def keyword_score(text: str) -> int:
    blob = (text or "").lower()
    hits = sum(1 for k in LAUNCH_KEYWORDS if k in blob)
    if hits >= 3:
        return 18
    if hits == 2:
        return 14
    if hits == 1:
        return 10
    return 2


def engagement_score(metrics: dict[str, Any] | None) -> int:
    m = metrics or {}
    likes = int(m.get("like_count") or m.get("likes") or 0)
    rts = int(m.get("retweet_count") or m.get("reposts") or 0)
    replies = int(m.get("reply_count") or m.get("replies") or 0)
    quotes = int(m.get("quote_count") or 0)
    weighted = likes + rts * 3 + replies + quotes * 2
    if weighted >= 5000:
        return 16
    if weighted >= 1000:
        return 12
    if weighted >= 200:
        return 8
    if weighted >= 40:
        return 5
    if weighted >= 5:
        return 2
    return 0


def score_launch_item(
    *,
    text: str,
    handle: str = "",
    created_at: datetime | None = None,
    metrics: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    institutions = extract_institutions(text)
    notable = notable_for_handle(handle)
    inst_pts = min(30, 12 * len(institutions) + (8 if institutions else 0))
    notable_pts = notable[1] if notable else 0
    backing = any(p in (text or "").lower() for p in BACKING_PHRASES)
    backing_pts = 8 if backing and institutions else (4 if backing else 0)
    kw = keyword_score(text)
    rec = recency_score(created_at, now)
    eng = engagement_score(metrics)
    listing_penalty = 25 if looks_like_cex_listing(text) else 0
    total = max(0, min(100, inst_pts + notable_pts + backing_pts + kw + rec + eng - listing_penalty))
    reasons: list[str] = []
    if institutions:
        reasons.append("机构/VC：" + "、".join(institutions[:4]))
    if notable:
        reasons.append(f"名人/KOL：{notable[0]}")
    if backing:
        reasons.append("提到融资/领投")
    if kw >= 10:
        reasons.append("命中打新关键词")
    if rec >= 14:
        reasons.append("近三日新帖")
    if eng >= 8:
        reasons.append("互动较高")
    if listing_penalty:
        reasons.append("疑似交易所上币（降权）")
    return {
        "score": total,
        "institutions": institutions,
        "notable": notable[0] if notable else None,
        "reasons": reasons,
        "breakdown": {
            "institutions": inst_pts,
            "notable": notable_pts,
            "backing": backing_pts,
            "keywords": kw,
            "recency": rec,
            "engagement": eng,
            "listing_penalty": listing_penalty,
        },
    }


def rank_launch_items(items: list[dict[str, Any]], now: datetime | None = None, lookback_days: int = 30) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in items:
        created = item.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        if not within_lookback(created if isinstance(created, datetime) else None, now, lookback_days):
            continue
        scored = score_launch_item(
            text=str(item.get("text") or ""),
            handle=str(item.get("handle") or item.get("username") or ""),
            created_at=created if isinstance(created, datetime) else None,
            metrics=item.get("metrics") if isinstance(item.get("metrics"), dict) else None,
            now=now,
        )
        if scored["breakdown"]["listing_penalty"] and scored["breakdown"]["keywords"] < 10:
            continue
        row = dict(item)
        row.update(scored)
        ranked.append(row)
    ranked.sort(
        key=lambda r: (
            -int(r.get("score") or 0),
            -len(r.get("institutions") or []),
            0 if r.get("notable") else 1,
            str(r.get("created_at") or ""),
        )
    )
    return ranked
