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


def _src(item: dict[str, Any]) -> str:
    return str(item.get("source") or "").lower()


def enrich_and_score(item: dict[str, Any], min_liq: float = 80_000) -> dict[str, Any]:
    """Survival-first meme rank.

    能活下来才谈赚钱：不追已经垂直的币、不要薄池、不要内盘土狗、
    5 分钟已经在出货的直接避开。热度奖励「买压质量」，惩罚「已经涨完」。
    """
    out = dict(item)
    liq = _n(out, "liquidity_usd")
    buys = _n(out, "buys_m5") or _n(out, "buys")
    sells = _n(out, "sells_m5") or _n(out, "sells")
    buys_m5 = _n(out, "buys_m5")
    sells_m5 = _n(out, "sells_m5")
    buyers = _n(out, "unique_buyers_est")
    holders = _n(out, "holders")
    growth = _n(out, "holder_growth_est")
    vol = _n(out, "volume_m5") or _n(out, "volume_h1")
    chg_h1 = _n(out, "price_change_h1")
    chg_m5 = _n(out, "price_change_m5")
    chg_h24 = _n(out, "price_change_h24")
    fdv = _n(out, "fdv")
    age = _age_minutes(out)
    ratio = buys / max(sells, 1.0)
    m5_ratio = (buys_m5 / max(sells_m5, 1.0)) if (buys_m5 or sells_m5) else ratio
    turnover = vol / max(liq, 1.0)
    fdv_liq = fdv / max(liq, 1.0) if fdv else 0.0
    src = _src(out)
    pump_inner = "pump.fun" in src or "pumpfun" in src
    boosted_only = src in {"dexscreener", "dexscreener-boosted"}

    reasons: list[str] = []
    reject: list[str] = []

    if liq < min_liq:
        reject.append(f"流动性 ${liq:,.0f} < ${min_liq:,.0f}，薄池插针可归零")
    if pump_inner and liq < 150_000:
        reject.append("Pump.fun 内盘/浅池，归零密度极高")
    if buyers < 15 and buys < 20:
        reject.append("真实买盘人数不足，更像庄控盘")
    if sells_m5 > 0 and buys_m5 > 0 and sells_m5 >= buys_m5:
        reject.append("5 分钟卖单已压过买单，正在出货")
    if sells > 0 and ratio < 1.4:
        reject.append(f"买卖比 {ratio:.2f} 偏弱")
    if chg_m5 >= 18:
        reject.append(f"5 分钟已涨 {chg_m5:.0f}%，这根K里追等于接盘")
    if chg_h1 >= 40:
        reject.append(f"1 小时已涨 {chg_h1:.0f}%，妖币这个位置后续常回吐/归零")
    if chg_h24 >= 120:
        reject.append(f"24h 已涨 {chg_h24:.0f}%，高潮末期")
    if fdv_liq and fdv_liq > 80:
        reject.append("FDV/池子过大，盘口托不住抛压")
    if turnover > 6:
        reject.append("换手过暴，洗盘或最后一波")
    if age is not None and age < 30:
        reject.append("池子不足 30 分钟，狙击/撤池风险")
    if age is not None and age > 60 * 24 * 21 and turnover < 0.12:
        reject.append("老池突然点亮，假突破居多")

    heat = 0.0
    heat += min(28.0, max(0.0, (m5_ratio - 1.3) * 14))
    heat += min(18.0, buyers / 2.5)
    heat += min(10.0, max(0.0, growth) * 0.8)
    if 0.15 <= turnover <= 1.8:
        heat += min(18.0, turnover * 12)
    elif 1.8 < turnover <= 3.5:
        heat += 8
        reasons.append("换手偏快，仓位必须更小")
    if "+" in src:
        heat += 10
        reasons.append("多源交叉")
    # 赚钱区间：已经动了，但还没垂直
    if 8 <= chg_h1 <= 28:
        heat += 16
        reasons.append("1h 涨幅仍在可跟区间")
    elif 28 < chg_h1 < 40:
        heat += 4
        reasons.append("1h 接近过热")
    elif 4 <= chg_m5 <= 12 and chg_h1 < 8:
        heat += 8
        reasons.append("5m 刚启动")
    if age is not None and 45 <= age <= 60 * 72:
        heat += 8
        reasons.append("池龄过了最毒的前半小时")
    if 0 < chg_m5 < 12:
        heat += 6
    if chg_h1 > 28:
        heat -= 12
    if pump_inner:
        heat -= 20
    if boosted_only:
        heat -= 8
        reasons.append("付费加热盘，质量打折")
    heat = max(0.0, min(100.0, heat))

    risk = 18.0
    if liq < min_liq * 1.8:
        risk += 16
        reasons.append("池子刚过门槛，滑点仍大")
    if fdv_liq > 35:
        risk += 14
        reasons.append("估值相对池子偏高")
    if m5_ratio < 1.6:
        risk += 10
    if age is None:
        risk += 10
        reasons.append("缺池龄，当未验证")
    elif age < 60:
        risk += 16
        reasons.append("仍偏新")
    if holders and holders < 80:
        risk += 10
        reasons.append("持币地址偏少")
    if chg_h1 > 25:
        risk += 14
    if chg_m5 > 10:
        risk += 10
    if pump_inner:
        risk += 22
    if boosted_only:
        risk += 12
    if not sells and not sells_m5:
        risk += 8
        reasons.append("看不到卖压，无法判断出货")
    risk = max(0.0, min(100.0, risk))

    momentum_ok = (8 <= chg_h1 <= 32) or (chg_h1 < 8 and 4 <= chg_m5 <= 15)
    if reject:
        grade = "避开"
    elif heat >= 70 and risk <= 38 and momentum_ok:
        grade = "可跟"
    elif heat >= 55 and risk <= 52 and not reject:
        grade = "观察"
    else:
        grade = "避开"

    expectancy = round(heat - 1.5 * risk, 1)
    out.update(
        {
            "buys": int(buys),
            "sells": int(sells),
            "buy_sell_ratio": round(ratio, 2),
            "turnover": round(turnover, 2),
            "age_minutes": round(age, 1) if age is not None else None,
            "heat": round(heat, 1),
            "risk": round(risk, 1),
            "expectancy": expectancy,
            "grade": grade,
            "reject_reasons": reject,
            "score_reasons": reasons,
            "followable": grade == "可跟",
            "crowd_ok": buyers >= 15 or buys >= 20,
            "holders_rising": growth >= 8 or (holders >= 80 and ratio >= 1.5),
            "action": {"可跟": "小仓试错", "观察": "只看不买", "避开": "禁止买入"}[grade],
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 80_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    # 避开不再送进列表：上一版把「避开但热度 40」仍展示，容易被当成能买。
    kept = [x for x in scored if x["grade"] in {"可跟", "观察"}]
    kept.sort(
        key=lambda x: ({"可跟": 3, "观察": 2}[x["grade"]], x.get("expectancy") or (x["heat"] - 1.5 * x["risk"])),
        reverse=True,
    )
    return kept[:40]
