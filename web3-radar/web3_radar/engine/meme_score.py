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


def enrich_and_score(item: dict[str, Any], min_liq: float = 50_000) -> dict[str, Any]:
    """提高胜率：只买「1小时已启动、5分钟确认回踩反弹」的票。

    飞刀K、过新池、出货K、日线已经见顶回落，一律避开。
    赢面靠 1.5 倍先锁定一半，剩下再博 2.5–10 倍。
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
    multi_source = "+" in src

    reasons: list[str] = []
    reject: list[str] = []

    if liq < min_liq:
        reject.append(f"流动性 ${liq:,.0f} 太薄，撤池后出不去")
    if liq > 600_000:
        reject.append("池子已经很大，不像还能翻多倍的小妖")
    if fdv and fdv > 8_000_000:
        reject.append(f"FDV ${fdv:,.0f} 已偏大，倍数空间不够")
    if chg_m5 < 0:
        reject.append("5 分钟还在跌，不是回踩结束")
    if sells_m5 > 0 and buys_m5 > 0 and sells_m5 >= buys_m5:
        reject.append("5 分钟正在出货")
    if sells > 0 and ratio < 1.6:
        reject.append(f"买卖比 {ratio:.2f} 已经翻弱")
    if chg_m5 >= 22:
        reject.append(f"5 分钟已涨 {chg_m5:.0f}%，这根K是飞刀")
    if chg_h1 >= 90:
        reject.append(f"1 小时已涨 {chg_h1:.0f}%，高潮末期")
    if chg_h24 >= 220:
        reject.append(f"24h 已涨 {chg_h24:.0f}%，倍数大头过了")
    if chg_h1 > 0 and chg_h24 >= max(80.0, chg_h1 * 2.2):
        reject.append("24h 远高于 1h，日线已经见顶回落")
    if age is not None and age < 25:
        reject.append("池子不足 25 分钟，撤池/狙击太多")
    if age is not None and age > 60 * 36:
        reject.append("超过 36 小时还当新妖，胜率差")
    if pump_inner and liq < min_liq:
        reject.append("Pump 内盘且池子不够")
    if buyers < 12 and buys < 16:
        reject.append("买盘人数不够，容易是庄家自拉")

    heat = 0.0
    heat += min(22.0, max(0.0, (m5_ratio - 1.2) * 11))
    heat += min(16.0, buyers / 2.0)
    heat += min(14.0, max(0.0, growth) * 1.1)
    if 0.25 <= turnover <= 4:
        heat += min(14.0, turnover * 5)
    if multi_source:
        heat += 8
        reasons.append("多源交叉确认")
    dip_in_trend = (
        32 <= chg_h1 <= 72
        and 4 <= chg_m5 <= 15
        and m5_ratio >= 1.8
        and chg_h1 >= chg_m5 * 2.4
    )
    if dip_in_trend:
        heat += 26
        reasons.append("1h 启动 + 5m 回踩反弹，胜率最高的买点")
    elif 24 <= chg_h1 <= 85:
        heat += 8
        reasons.append("1h 已启动，但 5m 还不是干净回踩")
    elif 8 <= chg_h1 < 24:
        heat += 3
    if 72 < chg_h1 < 90:
        heat -= 8
        reasons.append("偏热，接盘胜率差")
    if 4 <= chg_m5 <= 15:
        heat += 12
        reasons.append("5m 在回踩区间，没有垂直")
    elif chg_m5 > 15:
        heat -= 12
        reasons.append("5m 太陡，接盘胜率差")
    if fdv and 80_000 <= fdv <= 1_500_000:
        heat += 16
        reasons.append("盘还小，有翻倍空间")
    elif fdv and fdv <= 4_000_000:
        heat += 8
    if liq and 50_000 <= liq <= 250_000:
        heat += 10
        reasons.append("池子够出、又没大到没倍数")
    if age is not None and 30 <= age <= 60 * 18:
        heat += 10
        reasons.append("过了最毒的前 25 分钟")
    if pump_inner and liq >= min_liq:
        heat += 2
        reasons.append("内盘也能出倍，但仓位当彩票")
    if chg_h24 >= 180:
        heat -= 12
    heat = max(0.0, min(100.0, heat))

    risk = 20.0
    if liq < 50_000:
        risk += 16
        reasons.append("浅池，归零概率高")
    if fdv and fdv < 80_000:
        risk += 8
    if age is None:
        risk += 8
    elif age < 30:
        risk += 12
        reasons.append("极新，可能撤池")
    if holders and holders < 50:
        risk += 10
    if pump_inner:
        risk += 14
        reasons.append("内盘彩票，只许小仓")
    if chg_h1 > 72:
        risk += 10
    if chg_m5 > 15:
        risk += 8
    if not sells and not sells_m5:
        risk += 8
    if not multi_source:
        risk += 6
    risk = max(0.0, min(100.0, risk))

    small_enough = (not fdv) or fdv <= 4_000_000
    still_early = chg_h1 < 90 and chg_h24 < 220
    crowd_ok = buyers >= 15 or buys >= 18 or buys_m5 >= 16
    if reject:
        grade = "避开"
    elif (
        dip_in_trend
        and heat >= 68
        and risk <= 48
        and small_enough
        and still_early
        and crowd_ok
        and multi_source
    ):
        grade = "可跟"
    elif heat >= 54 and not reject and still_early:
        grade = "观察"
    else:
        grade = "避开"

    expectancy = round(heat - 0.9 * risk, 1)
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
            "crowd_ok": crowd_ok,
            "holders_rising": growth >= 5 or (holders >= 50 and ratio >= 1.4),
            "multi_source": multi_source,
            "dip_in_trend": dip_in_trend,
            "action": {"可跟": "回踩小仓", "观察": "只看不买", "避开": "禁止买入"}[grade],
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 50_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    kept = [x for x in scored if x["grade"] in {"可跟", "观察"}]
    kept.sort(
        key=lambda x: ({"可跟": 3, "观察": 2}[x["grade"]], x.get("expectancy") or (x["heat"] - 0.9 * x["risk"])),
        reverse=True,
    )
    return kept[:40]
