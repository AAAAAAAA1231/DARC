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


def enrich_and_score(item: dict[str, Any], min_liq: float = 25_000) -> dict[str, Any]:
    """妖币按倍数仓，不是合约剥头皮。

    要的是还小、已经在动、买盘还在的票；用小仓位承受归零，
    而不是 16% 止盈把 10 倍砍掉。已经高潮完的大盘、正在出货的盘仍避开。
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
    if sells > 0 and ratio < 1.15:
        reject.append(f"买卖比 {ratio:.2f} 已经翻弱")
    if chg_m5 >= 80:
        reject.append(f"5 分钟已涨 {chg_m5:.0f}%，这根K里接飞刀")
    if chg_h1 >= 200:
        reject.append(f"1 小时已涨 {chg_h1:.0f}%，高潮末期")
    if chg_h24 >= 500:
        reject.append(f"24h 已涨 {chg_h24:.0f}%，倍数大头过了")
    if age is not None and age < 8:
        reject.append("池子不足 8 分钟，纯狙击")
    if age is not None and age > 60 * 24 * 7:
        reject.append("超过 7 天还在当新妖炒，假突破居多")
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
    # 妖币黄金区：已经启动，但盘还小
    if 20 <= chg_h1 <= 120:
        heat += 22
        reasons.append("1h 已启动，还在倍数区")
    elif 8 <= chg_h1 < 20:
        heat += 12
        reasons.append("刚启动")
    elif 120 < chg_h1 < 200:
        heat += 6
        reasons.append("偏热，仓位必须更小")
    if 8 <= chg_m5 < 45:
        heat += 8
        reasons.append("5m 买盘还在抬")
    if fdv and 50_000 <= fdv <= 2_000_000:
        heat += 16
        reasons.append("盘还小，有翻倍空间")
    elif fdv and fdv <= 5_000_000:
        heat += 8
    if liq and 25_000 <= liq <= 250_000:
        heat += 8
        reasons.append("池子够出、又没大到没倍数")
    if age is not None and 15 <= age <= 60 * 36:
        heat += 10
        reasons.append("新票窗口")
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
    if chg_h1 > 100:
        risk += 10
    if not sells and not sells_m5:
        risk += 6
    risk = max(0.0, min(100.0, risk))

    small_enough = (not fdv) or fdv <= 8_000_000
    still_early = chg_h1 < 200 and chg_h24 < 500
    if reject:
        grade = "避开"
    elif heat >= 60 and risk <= 62 and small_enough and still_early:
        grade = "可跟"
    elif heat >= 48 and not reject:
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
            "action": {"可跟": "小仓博倍数", "观察": "只看不买", "避开": "禁止买入"}[grade],
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 25_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    kept = [x for x in scored if x["grade"] in {"可跟", "观察"}]
    kept.sort(
        key=lambda x: ({"可跟": 3, "观察": 2}[x["grade"]], x.get("expectancy") or (x["heat"] - 0.8 * x["risk"])),
        reverse=True,
    )
    return kept[:40]
