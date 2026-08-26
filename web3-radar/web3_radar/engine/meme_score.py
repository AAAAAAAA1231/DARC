from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _n(item: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = item.get(key, default)
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _age_minutes(item: dict[str, Any]) -> float | None:
    raw = item.get("created_at") or item.get("pair_created_at")
    if raw in (None, ""):
        return None
    try:
        if isinstance(raw, (int, float)):
            ts = raw / 1000 if raw > 10_000_000_000 else raw
            created = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            text = str(raw).replace("Z", "+00:00")
            created = datetime.fromisoformat(text)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 60.0)
    except Exception:
        return None


def enrich_and_score(item: dict[str, Any], min_liq: float = 1_000_000) -> dict[str, Any]:
    """Rank a meme by short-term crowd buying quality vs rug/chase risk."""
    out = dict(item)
    liq = _n(out, "liquidity_usd")
    buys = _n(out, "buys_m5") or _n(out, "buys")
    sells = _n(out, "sells_m5") or _n(out, "sells")
    buyers = _n(out, "unique_buyers_est")
    holders = _n(out, "holders")
    growth = _n(out, "holder_growth_est")
    vol = _n(out, "volume_m5") or _n(out, "volume_h1")
    chg = _n(out, "price_change_m5") or _n(out, "price_change_h1")
    fdv = _n(out, "fdv")
    age = _age_minutes(out)
    ratio = buys / max(sells, 1.0)
    turnover = vol / max(liq, 1.0)
    fdv_liq = fdv / max(liq, 1.0) if fdv else 0.0

    reasons: list[str] = []
    reject: list[str] = []
    if liq < min_liq:
        reject.append(f"流动性 ${liq:,.0f} < ${min_liq:,.0f}")
    if buys < 6 and buyers < 8:
        reject.append("短期买入人数不足")
    if sells > 0 and ratio < 1.15:
        reject.append(f"买卖比 {ratio:.2f} 偏弱，更像出货")
    if chg >= 120:
        reject.append(f"1h/5m 已涨 {chg:.0f}%，跟单容易接盘")
    if fdv_liq and fdv_liq > 250:
        reject.append("FDV/池子过大，盘口薄、易插针")
    if age is not None and age < 2:
        reject.append("池子不足 2 分钟，狙击盘风险极高")

    heat = 0.0
    heat += min(25.0, max(0.0, (ratio - 1) * 12))
    heat += min(20.0, buyers / 2.0)
    heat += min(15.0, growth * 1.2)
    if 0.25 <= turnover <= 4:
        heat += min(20.0, turnover * 8)
    elif turnover > 4:
        heat += 8  # 换手过暴，质量打折
        reasons.append("换手过高")
    if "+" in str(out.get("source") or ""):
        heat += 8
        reasons.append("多源交叉验证")
    if 8 <= chg <= 70:
        heat += 10
        reasons.append("涨幅仍在可跟区间")
    elif 0 <= chg < 8:
        heat += 4
    heat = max(0.0, min(100.0, heat))

    risk = 15.0
    if liq < min_liq * 1.5:
        risk += 18
        reasons.append("池子刚过门槛，滑点大")
    if fdv_liq > 80:
        risk += 16
        reasons.append("估值相对池子偏高")
    if ratio < 1.4:
        risk += 12
    if age is not None:
        if age < 10:
            risk += 20
            reasons.append("新池，合约未充分验证")
        elif age > 60 * 24 * 30:
            risk += 8
            reasons.append("老池突然放量，需防假突破")
    if holders and holders < 40:
        risk += 10
        reasons.append("持币地址偏少")
    if not holders and not growth:
        risk += 8
        reasons.append("缺少真实持币增长数据")
    if chg > 80:
        risk += 20
    risk = max(0.0, min(100.0, risk))

    if reject:
        grade = "避开"
    elif heat >= 65 and risk <= 45:
        grade = "可跟"
    elif heat >= 50 and risk <= 62:
        grade = "观察"
    else:
        grade = "避开"

    out.update(
        {
            "buys": int(buys),
            "sells": int(sells),
            "buy_sell_ratio": round(ratio, 2),
            "turnover": round(turnover, 2),
            "age_minutes": round(age, 1) if age is not None else None,
            "heat": round(heat, 1),
            "risk": round(risk, 1),
            "grade": grade,
            "reject_reasons": reject,
            "score_reasons": reasons,
            "followable": grade == "可跟",
            "crowd_ok": buyers >= 8 or buys >= 10,
            "holders_rising": growth >= 5 or (holders >= 50 and ratio >= 1.3),
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 1_000_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    kept = [x for x in scored if x["grade"] != "避开" or (x["liquidity_usd"] >= min_liq and x["heat"] >= 40)]
    # 避开但仍过流动性的，保留少量供人工看，但排后面
    kept.sort(key=lambda x: ({"可跟": 3, "观察": 2, "避开": 1}[x["grade"]], x["heat"] - x["risk"] * 0.4), reverse=True)
    return kept[:60]
