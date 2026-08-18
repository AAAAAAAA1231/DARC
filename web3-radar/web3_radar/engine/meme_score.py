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


def enrich_and_score(item: dict[str, Any], min_liq: float = 40_000) -> dict[str, Any]:
    """提高胜率：只买「1小时已启动、5分钟在回踩」的票。

    飞刀K、过新池、出货K仍然避开。赢面靠 1.6 倍先锁定一笔，剩下再博 3–5 倍。
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
    src = _src(out)
    pump_inner = "pump.fun" in src or "pumpfun" in src

    reasons: list[str] = []
    reject: list[str] = []

    if liq < min_liq:
        reject.append(f"流动性 ${liq:,.0f} 太薄，撤池后出不去")
    if liq > 800_000:
        reject.append("池子已经很大，不像还能翻多倍的小妖")
    if fdv and fdv > 15_000_000:
        reject.append(f"FDV ${fdv:,.0f} 已偏大，倍数空间不够")
    if sells_m5 > 0 and buys_m5 > 0 and sells_m5 >= buys_m5:
        reject.append("5 分钟正在出货")
    if sells > 0 and ratio < 1.35:
        reject.append(f"买卖比 {ratio:.2f} 已经翻弱")
    if chg_m5 >= 40:
        reject.append(f"5 分钟已涨 {chg_m5:.0f}%，这根K是飞刀")
    if chg_h1 >= 160:
        reject.append(f"1 小时已涨 {chg_h1:.0f}%，高潮末期")
    if chg_h24 >= 350:
        reject.append(f"24h 已涨 {chg_h24:.0f}%，倍数大头过了")
    if age is not None and age < 20:
        reject.append("池子不足 20 分钟，撤池/狙击太多")
    if age is not None and age > 60 * 48:
        reject.append("超过 48 小时还当新妖，胜率差")
    if pump_inner and liq < min_liq:
        reject.append("Pump 内盘且池子不够")

    heat = 0.0
    heat += min(22.0, max(0.0, (m5_ratio - 1.1) * 12))
    heat += min(16.0, buyers / 2.0)
    heat += min(14.0, max(0.0, growth) * 1.1)
    if 0.2 <= turnover <= 5:
        heat += min(14.0, turnover * 5)
    if "+" in src:
        heat += 6
    dip_in_trend = (28 <= chg_h1 <= 95) and (2 <= chg_m5 <= 22) and m5_ratio >= 1.5
    if dip_in_trend:
        heat += 24
        reasons.append("1h 启动 + 5m 回踩，胜率最高的买点")
    elif 20 <= chg_h1 <= 120:
        heat += 10
        reasons.append("1h 已启动")
    elif 8 <= chg_h1 < 20:
        heat += 4
    if 120 < chg_h1 < 160:
        heat -= 6
        reasons.append("偏热")
    if 8 <= chg_m5 <= 22:
        heat += 10
        reasons.append("5m 没有垂直")
    elif chg_m5 > 22:
        heat -= 10
        reasons.append("5m 太陡，接盘胜率差")
    if fdv and 50_000 <= fdv <= 2_000_000:
        heat += 16
        reasons.append("盘还小，有翻倍空间")
    elif fdv and fdv <= 5_000_000:
        heat += 8
    if liq and 40_000 <= liq <= 280_000:
        heat += 10
        reasons.append("池子够出、又没大到没倍数")
    if age is not None and 25 <= age <= 60 * 24:
        heat += 10
        reasons.append("过了最毒的前 20 分钟")
    if pump_inner and liq >= min_liq:
        heat += 4
        reasons.append("内盘也能出倍，但仓位当彩票")
    if chg_h24 >= 300:
        heat -= 12
    heat = max(0.0, min(100.0, heat))

    risk = 22.0
    if liq < 40_000:
        risk += 14
        reasons.append("浅池，归零概率高")
    if fdv and fdv < 80_000:
        risk += 8
    if age is None:
        risk += 8
    elif age < 25:
        risk += 14
        reasons.append("极新，可能撤池")
    if holders and holders < 40:
        risk += 10
    if pump_inner:
        risk += 12
        reasons.append("内盘彩票，只许小仓")
    if chg_h1 > 90:
        risk += 10
    if chg_m5 > 20:
        risk += 8
    if not sells and not sells_m5:
        risk += 6
    risk = max(0.0, min(100.0, risk))

    small_enough = (not fdv) or fdv <= 5_000_000
    still_early = chg_h1 < 160 and chg_h24 < 350
    if reject:
        grade = "避开"
    elif dip_in_trend and heat >= 64 and risk <= 55 and small_enough and still_early:
        grade = "可跟"
    elif heat >= 52 and not reject and still_early:
        grade = "观察"
    else:
        grade = "避开"

    expectancy = round(heat - 0.8 * risk, 1)
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
            "crowd_ok": buyers >= 10 or buys >= 12,
            "holders_rising": growth >= 5 or (holders >= 40 and ratio >= 1.2),
            "action": {"可跟": "回踩小仓", "观察": "只看不买", "避开": "禁止买入"}[grade],
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 40_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    kept = [x for x in scored if x["grade"] in {"可跟", "观察"}]
    kept.sort(
        key=lambda x: ({"可跟": 3, "观察": 2}[x["grade"]], x.get("expectancy") or (x["heat"] - 0.8 * x["risk"])),
        reverse=True,
    )
    return kept[:40]
