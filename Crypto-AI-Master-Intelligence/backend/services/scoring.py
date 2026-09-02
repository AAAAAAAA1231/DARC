"""Multi-factor 50X scoring. Missing inputs stay UNKNOWN and lower confidence; they are never invented."""

from __future__ import annotations

from typing import Any

from backend.core.enums import NarrativeTag

NARRATIVE_KEYWORDS: dict[NarrativeTag, tuple[str, ...]] = {
    NarrativeTag.AI: ("ai", "artificial intelligence", "gpt", "llm", "inference"),
    NarrativeTag.DEPIN: ("depin", "wireless", "sensor network", "physical infrastructure"),
    NarrativeTag.RWA: ("rwa", "real world asset", "treasury bill", "tokenized"),
    NarrativeTag.DEFI: ("defi", "amm", "lending", "dex", "yield"),
    NarrativeTag.BTCFI: ("btcfi", "bitcoin defi", "btc l2"),
    NarrativeTag.LAYER2: ("layer 2", "l2", "rollup", "optimistic", "zk"),
    NarrativeTag.LAYER1: ("layer 1", "l1", "blockchain"),
    NarrativeTag.MEME: ("meme", "dog", "cat", "pepe"),
    NarrativeTag.GAMING: ("game", "gaming", "nft game"),
    NarrativeTag.INFRA: ("infra", "oracle", "rpc", "data availability"),
    NarrativeTag.RESTAKING: ("restak", "eigen"),
    NarrativeTag.STABLECOIN: ("stablecoin", "usd", "peg"),
    NarrativeTag.PRIVACY: ("privacy", "zk", "mixer"),
    NarrativeTag.SOCIALFI: ("socialfi", "social"),
    NarrativeTag.DESCI: ("desci", "science"),
}


def classify_narrative(categories: list[str] | None, description: str | None) -> NarrativeTag:
    blob = " ".join(categories or []).lower() + " " + (description or "").lower()
    for tag, keys in NARRATIVE_KEYWORDS.items():
        if any(k in blob for k in keys):
            return tag
    if blob.strip():
        return NarrativeTag.EMERGING
    return NarrativeTag.UNKNOWN


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def score_market_structure(mcap: float | None, fdv: float | None, circ: float | None, total: float | None) -> tuple[float | None, str]:
    if mcap is None:
        return None, "UNKNOWN"
    score = 55.0
    if mcap < 50_000_000:
        score += 20
    elif mcap < 300_000_000:
        score += 10
    elif mcap > 5_000_000_000:
        score -= 20
    if fdv and mcap and fdv > 0:
        ratio = mcap / fdv
        if ratio < 0.2:
            score -= 15
        elif ratio > 0.6:
            score += 8
    if circ and total and total > 0:
        circ_ratio = circ / total
        if circ_ratio < 0.15:
            score -= 10
        elif circ_ratio > 0.5:
            score += 6
    return _clip(score), "ok"


def score_volume(volume: float | None, mcap: float | None, change_24h: float | None) -> tuple[float | None, str]:
    if volume is None or mcap is None or mcap <= 0:
        return None, "UNKNOWN"
    turnover = volume / mcap
    score = 40 + min(40.0, turnover * 200)
    if change_24h is not None and change_24h > 8:
        score += 8
    return _clip(score), "ok"


def score_liquidity(liq_usd: float | None) -> tuple[float | None, str]:
    if liq_usd is None:
        return None, "UNKNOWN"
    if liq_usd < 20_000:
        return 15.0, "ok"
    if liq_usd < 100_000:
        return 40.0, "ok"
    if liq_usd < 1_000_000:
        return 65.0, "ok"
    return 80.0, "ok"


def score_holders(holder_count: Any) -> tuple[float | None, str]:
    try:
        n = int(float(holder_count))
    except (TypeError, ValueError):
        return None, "UNKNOWN"
    if n < 50:
        return 20.0, "ok"
    if n < 500:
        return 45.0, "ok"
    if n < 5000:
        return 65.0, "ok"
    return 80.0, "ok"


def score_social(community: dict | None, developer: dict | None) -> tuple[float | None, str]:
    if not community and not developer:
        return None, "UNKNOWN"
    twitter = (community or {}).get("twitter_followers") or 0
    stars = (developer or {}).get("stars") or 0
    commits = (developer or {}).get("commit_count_4_weeks") or 0
    try:
        score = 20 + min(40.0, float(twitter) / 5000) + min(20.0, float(stars) / 50) + min(20.0, float(commits) / 2)
    except (TypeError, ValueError):
        return None, "UNKNOWN"
    return _clip(score), "ok"


def score_historical_similarity(ath: float | None, atl: float | None, price: float | None, mcap: float | None) -> tuple[float | None, str]:
    """Similarity uses only observed ATH/ATL/price/mcap. Not a claim that the token will 50x."""
    if not ath or not atl or not price or atl <= 0:
        return None, "UNKNOWN"
    historical_multiple = ath / atl
    dist_from_ath = price / ath
    score = 30.0
    if historical_multiple >= 50 and dist_from_ath < 0.35 and mcap and mcap < 500_000_000:
        score = 75.0
    elif historical_multiple >= 10 and dist_from_ath < 0.5:
        score = 60.0
    elif dist_from_ath > 0.85:
        score = 25.0
    return _clip(score), "ok"


def score_narrative(tag: NarrativeTag) -> tuple[float, str]:
    if tag == NarrativeTag.UNKNOWN:
        return 40.0, "UNKNOWN"
    hot = {NarrativeTag.AI, NarrativeTag.RWA, NarrativeTag.BTCFI, NarrativeTag.DEPIN, NarrativeTag.RESTAKING}
    if tag in hot:
        return 70.0, "ok"
    return 55.0, "ok"


def combine_50x(parts: dict[str, tuple[float | None, str]], security_score: float | None, security_verdict: str) -> dict[str, Any]:
    known = {k: v[0] for k, v in parts.items() if v[0] is not None}
    unknown = [k for k, v in parts.items() if v[0] is None]
    if not known:
        return {
            "score_50x": None,
            "confidence": 0.0,
            "unknown_factors": unknown,
            "parts": {k: {"score": v[0], "quality": v[1]} for k, v in parts.items()},
            "grade": "INSUFFICIENT_DATA",
        }
    weights = {
        "market_structure": 0.12,
        "liquidity": 0.10,
        "volume": 0.10,
        "holders": 0.08,
        "smart_money": 0.08,
        "whale": 0.06,
        "fund_flow": 0.06,
        "narrative": 0.08,
        "social": 0.07,
        "vc": 0.04,
        "team": 0.04,
        "tokenomics": 0.05,
        "ecosystem": 0.04,
        "onchain": 0.04,
        "market_cycle": 0.02,
        "historical_similarity": 0.02,
    }
    total_w = 0.0
    acc = 0.0
    for key, weight in weights.items():
        if key in known:
            acc += known[key] * weight
            total_w += weight
    base = acc / total_w if total_w else 0.0
    if security_score is not None:
        blended = 0.85 * base + 0.15 * security_score
    else:
        blended = base
    confidence = max(0.05, min(0.95, total_w * (1 - 0.08 * len(unknown))))
    grade = "WATCH"
    if blended >= 80:
        grade = "HIGH"
    elif blended >= 65:
        grade = "MEDIUM"
    elif blended >= 50:
        grade = "LOW"
    return {
        "score_50x": round(blended, 2),
        "confidence": round(confidence, 4),
        "unknown_factors": unknown,
        "parts": {k: {"score": v[0], "quality": v[1]} for k, v in parts.items()},
        "growth_score": known.get("volume"),
        "narrative_score": known.get("narrative"),
        "smart_money_score": known.get("smart_money"),
        "liquidity_score": known.get("liquidity"),
        "fundamental_score": known.get("market_structure"),
        "similarity_score": known.get("historical_similarity"),
        "security_score": security_score,
        "security_verdict": security_verdict,
        "grade": grade,
    }
