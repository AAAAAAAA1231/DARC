from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median
from typing import Iterable

from .models import ScoredToken, ScoreBreakdown, TokenSnapshot, VenuePulse

NEW_CHAINS = {
    "robinhood": "Robinhood Chain（2026-07 上线，gas 补贴窗口）",
    "hyperevm": "HyperEVM（Hyperliquid 生态新场）",
    "hyperliquid": "Hyperliquid",
    "abstract": "Abstract（较新消费链）",
    "unichain": "Unichain（较新 L2）",
    "ink": "Ink（较新 L2）",
    "soneium": "Soneium（较新 L2）",
}

LAUNCHPAD_DEX = {
    "pumpswap": "Pump.fun / PumpSwap",
    "pumpfun": "Pump.fun",
    "moonshot": "Moonshot",
    "fourmeme": "Four.meme（BSC）",
    "flap": "Flap",
    "clanker": "Clanker（Base）",
    "virtuals": "Virtuals",
    "ramses": "Ramses（HyperEVM）",
    "pons": "Pons（Robinhood 发射台）",
    "hookr": "Hookr.fun",
    "believe": "Believe",
    "heaven": "Heaven",
    "boop": "Boop",
    "launchlab": "Raydium LaunchLab",
    "raydium": "Raydium",
    "meteora": "Meteora",
}

LAUNCHPAD_OWN_TOKENS = {
    "pons",
    "hookr",
    "pump",
    "clanker",
    "ramses",
    "virtuals",
    "four",
}

KOL_OR_CULTURE = (
    "ansem",
    "black bull",
    "牛来",
    "niu lai",
    "币安人生",
    "龙虾",
    "哈基米",
    "hims",
    "boner",
    "cashcat",
    "cash cat",
    "basecat",
)

COPYCAT_RE = re.compile(
    r"(baby\s*|mini\s*)?(doge|pepe|shib|bonk|wif|inu)\b|"
    r"\b2\.0\b|\.site\b|\.com\b|\[fake\]|fomo\.|inu$",
    re.I,
)
STABLE_RE = re.compile(r"^(usd|usdt|usdc|dai|usdg|busd|fdusd|usde|alusd)$", re.I)


def _clip(value: int, lo: int = 0, hi: int = 25) -> int:
    return max(lo, min(hi, value))


def score_token(token: TokenSnapshot, *, sibling_names: Iterable[str] = ()) -> ScoreBreakdown:
    reasons: list[str] = []
    warnings: list[str] = []
    tags: list[str] = []

    venue = _venue_score(token, reasons, tags)
    narrative = _narrative_score(token, sibling_names, reasons, warnings, tags)
    structure = _structure_score(token, reasons, warnings, tags)
    pillar = _pillar_score(token, reasons, tags)
    total = venue + narrative + structure + pillar

    if token.size_usd and token.size_usd >= 50_000_000:
        warnings.append("市值已偏大，不是开盘段的 50 倍买点")
        tags.append("已过大")
        total = min(total, 68)

    if STABLE_RE.match(token.symbol or ""):
        warnings.append("疑似稳定币，忽略")
        total = 0

    if token.liquidity_usd is not None and token.liquidity_usd < 8_000:
        warnings.append("池子过浅，极易被抽干")
        tags.append("极浅池")

    if total >= 72:
        priority = "focus"
    elif total >= 55:
        priority = "watch"
    else:
        priority = "skip"

    return ScoreBreakdown(
        total=total,
        venue=venue,
        narrative=narrative,
        structure=structure,
        pillar=pillar,
        reasons=reasons,
        warnings=warnings,
        tags=tags,
        watch=priority != "skip",
        priority=priority,
    )


def _venue_score(token: TokenSnapshot, reasons: list[str], tags: list[str]) -> int:
    score = 0
    chain = (token.chain or "").lower()
    dex = (token.dex or "").lower()

    if chain in NEW_CHAINS:
        score += 16
        reasons.append(f"新场子：{NEW_CHAINS[chain]}")
        tags.append("新链")
    if dex in LAUNCHPAD_DEX:
        score += 8
        reasons.append(f"发射台：{LAUNCHPAD_DEX[dex]}")
        tags.append("发射台")

    age = token.age_days
    if age is not None:
        if age <= 3:
            score += 10
            reasons.append(f"池子只有 {age:.1f} 天，仍在开盘窗口")
            tags.append("开盘窗口")
        elif age <= 21:
            score += 7
            reasons.append(f"池子 {age:.0f} 天，仍偏新")
        elif age <= 60:
            score += 3
        elif age > 180:
            score -= 8
            reasons.append("池子超过半年，不太像开盘段百倍")

    return _clip(score)


def _narrative_score(
    token: TokenSnapshot,
    sibling_names: Iterable[str],
    reasons: list[str],
    warnings: list[str],
    tags: list[str],
) -> int:
    score = 0
    blob = f"{token.name} {token.symbol} {token.description}".lower()
    symbol = (token.symbol or "").lower().lstrip("$")

    if COPYCAT_RE.search(blob):
        score -= 12
        warnings.append("名字像仿盘 / 经典梗复制")
        tags.append("疑似仿盘")
    else:
        score += 6

    if symbol in LAUNCHPAD_OWN_TOKENS or any(k in blob for k in LAUNCHPAD_OWN_TOKENS):
        score += 12
        reasons.append("发射台自身代币，可能吃手续费")
        tags.append("发射台币")

    if any(k in blob for k in KOL_OR_CULTURE):
        score += 10
        reasons.append("命中名人 / 文化事件叙事")
        tags.append("独占叙事")

    rwa_hints = ("hims", "hood", "stock", "rwa", "tokenized", "netnet")
    if any(k in blob for k in rwa_hints):
        score += 8
        reasons.append("和 RWA / 股票代币缠在一起，叙事难复制")
        tags.append("RWA")

    siblings = [n.lower() for n in sibling_names if n]
    similar = sum(1 for n in siblings if token.name and token.name.lower() in n and n != token.name.lower())
    if similar >= 3:
        score -= 8
        warnings.append("同批出现多个近名复制盘")
        tags.append("跟风盘")

    if token.description and len(token.description) >= 40:
        score += 2

    return _clip(score)


def _structure_score(
    token: TokenSnapshot,
    reasons: list[str],
    warnings: list[str],
    tags: list[str],
) -> int:
    score = 0
    size = token.size_usd
    if size is None:
        return 4

    if 150_000 <= size <= 20_000_000:
        score += 14
        reasons.append(f"市值/FDV 约 ${size:,.0f}，仍在开盘可做大的区间")
        tags.append("浅开盘")
    elif 20_000_000 < size < 50_000_000:
        score += 6
        reasons.append("市值已启动，但仍可能是场子龙头")
    elif size < 50_000:
        score += 2
        warnings.append("盘太小，噪音和骗局比例更高")
    else:
        score -= 4

    ratio = token.liq_to_size
    if ratio is not None:
        if 0.02 <= ratio <= 0.15:
            score += 8
            reasons.append(f"池子/市值 = {ratio:.1%}，浅池结构")
        elif ratio < 0.02:
            warnings.append(f"池子/市值只有 {ratio:.1%}，价格极易被操纵")
            score += 2
        elif ratio > 0.4:
            score -= 2

    turnover = token.vol_to_size
    if turnover is not None:
        if turnover >= 0.5:
            score += 6
            reasons.append(f"24h 换手 {turnover:.1f}x，赌场速度")
            tags.append("高换手")
        elif turnover >= 0.2:
            score += 3

    return _clip(score)


def _pillar_score(token: TokenSnapshot, reasons: list[str], tags: list[str]) -> int:
    score = 0
    vol = token.volume_h24 or 0
    if vol >= 5_000_000:
        score += 10
        reasons.append("24h 成交超过 500 万，热度能续")
        tags.append("第二支柱?")
    elif vol >= 1_000_000:
        score += 7
    elif vol >= 200_000:
        score += 4

    traders = token.buyers_h24 + token.sellers_h24
    if traders >= 1500:
        score += 6
        reasons.append(f"24h 独立交易地址约 {traders}")
    elif traders >= 400:
        score += 3

    age = token.age_days
    if age is not None and 3 <= age <= 45 and vol >= 300_000:
        score += 7
        reasons.append("活过了前几天，热度还在，更像能站住的盘")
        tags.append("已存活")

    change = token.price_change_h24
    if change is not None and change <= -70:
        score -= 6

    return _clip(score)


def score_many(tokens: Iterable[TokenSnapshot]) -> list[ScoredToken]:
    items = list(tokens)
    names = [t.name for t in items]
    scored = [ScoredToken(token=t, score=score_token(t, sibling_names=names)) for t in items]
    scored.sort(key=lambda s: s.score.total, reverse=True)
    return scored


def summarize_venues(tokens: Iterable[TokenSnapshot]) -> list[VenuePulse]:
    buckets: dict[tuple[str, str], list[TokenSnapshot]] = defaultdict(list)
    for token in tokens:
        buckets[(token.chain, token.dex)].append(token)

    pulses: list[VenuePulse] = []
    for (chain, dex), group in buckets.items():
        ages = [t.age_days for t in group if t.age_days is not None]
        volume = sum(t.volume_h24 or 0 for t in group)
        reasons: list[str] = []
        label = "普通场"
        if chain.lower() in NEW_CHAINS:
            label = "新链"
            reasons.append(NEW_CHAINS[chain.lower()])
        if dex.lower() in LAUNCHPAD_DEX:
            label = "新发射台" if label == "普通场" else f"{label} + 发射台"
            reasons.append(LAUNCHPAD_DEX[dex.lower()])
        if ages and median(ages) <= 21 and volume >= 500_000:
            reasons.append("近三周新池成交已经起来")
            if label == "普通场":
                label = "升温场"

        symbols = []
        seen = Counter()
        for token in sorted(group, key=lambda t: t.volume_h24 or 0, reverse=True):
            sym = token.symbol or token.name
            if seen[sym]:
                continue
            seen[sym] += 1
            symbols.append(sym)
            if len(symbols) >= 4:
                break

        pulses.append(
            VenuePulse(
                chain=chain,
                dex=dex,
                token_count=len(group),
                volume_h24=volume,
                median_age_days=median(ages) if ages else None,
                label=label,
                reasons=reasons,
                sample_symbols=symbols,
            )
        )

    pulses.sort(key=lambda p: (p.label != "普通场", p.volume_h24), reverse=True)
    return pulses
