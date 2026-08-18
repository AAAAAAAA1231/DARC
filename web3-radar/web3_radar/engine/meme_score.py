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


def _has_twitter(item: dict[str, Any]) -> bool:
    if item.get("has_twitter"):
        return True
    blob = " ".join(
        str(x)
        for x in (
            item.get("links") or [],
            item.get("twitter") or "",
            item.get("socials") or [],
            item.get("url") or "",
        )
    ).lower()
    return "x.com" in blob or "twitter" in blob


def enrich_and_score(item: dict[str, Any], min_liq: float = 100_000) -> dict[str, Any]:
    """一个月一买：meme 币，成功率优先，还要留倍数。

    不买 3 天内飞刀，不买已经上千万美元、翻倍空间没了的老币。
    赢面靠活下来 + 买盘 + 社交热度。
    """
    out = dict(item)
    liq = _n(out, "liquidity_usd")
    buys = _n(out, "buys_h24") or _n(out, "buys") or _n(out, "buys_m5")
    sells = _n(out, "sells_h24") or _n(out, "sells") or _n(out, "sells_m5")
    buys_m5 = _n(out, "buys_m5")
    sells_m5 = _n(out, "sells_m5")
    buyers = _n(out, "unique_buyers_est")
    holders = _n(out, "holders")
    growth = _n(out, "holder_growth_est")
    vol = _n(out, "volume_h24") or _n(out, "volume_h1") or _n(out, "volume_m5")
    chg_h1 = _n(out, "price_change_h1")
    chg_m5 = _n(out, "price_change_m5")
    chg_h6 = _n(out, "price_change_h6")
    chg_h24 = _n(out, "price_change_h24")
    fdv = _n(out, "fdv")
    age = _age_minutes(out)
    age_h = (age / 60.0) if age is not None else None
    ratio = buys / max(sells, 1.0)
    m5_ratio = (buys_m5 / max(sells_m5, 1.0)) if (buys_m5 or sells_m5) else ratio
    turnover = vol / max(liq, 1.0)
    src = _src(out)
    pump_inner = "pump.fun" in src or "pumpfun" in src
    multi_source = "+" in src
    has_twitter = _has_twitter(out)
    is_cto = bool(out.get("is_cto"))
    gecko_hot = bool(out.get("gecko_trending"))
    boost = _n(out, "boost_amount")
    text = " ".join(str(out.get(k) or "") for k in ("symbol", "name", "description")).lower()
    narrative_hit = any(w in text for w in ("bull", "ansem", "cat", "cate", "pengu", "season"))

    reasons: list[str] = []
    reject: list[str] = []

    if liq < min_liq:
        reject.append(f"流动性 ${liq:,.0f} 太薄，一个月持有出不去")
    if liq > 1_200_000:
        reject.append("池子已经很大，不像还能翻多倍的 meme")
    if fdv and fdv > 12_000_000:
        reject.append(f"FDV ${fdv:,.0f} 已偏大，一个月倍数不够")
    if fdv and fdv < 300_000:
        reject.append("盘太小，撤池/归零概率高")
    if age_h is not None and age_h < 72:
        reject.append("池子不足 3 天，还没活过第一波屠杀")
    if age_h is not None and age_h > 24 * 60:
        reject.append("超过 60 天还当新 meme，倍数空间差")
    if chg_h24 >= 150:
        reject.append(f"24h 已涨 {chg_h24:.0f}%，飞刀/高潮末期")
    if chg_h24 <= -35:
        reject.append("24h 跌超 35%，在接飞刀")
    if chg_m5 >= 35:
        reject.append(f"5 分钟已涨 {chg_m5:.0f}%，现在追等于接盘")
    if sells > 0 and ratio < 0.95:
        reject.append(f"24h 买卖比 {ratio:.2f}，主力在出")
    if sells_m5 > 0 and buys_m5 > 0 and sells_m5 >= buys_m5 * 1.5 and chg_m5 < 0:
        reject.append("5 分钟正在出货")
    if pump_inner and liq < min_liq:
        reject.append("Pump 内盘且池子不够")

    heat = 18.0
    if age_h is not None and 72 <= age_h <= 24 * 21:
        heat += 22
        reasons.append("活过 3–21 天，一个月胜率最高的区间")
    elif age_h is not None and 24 * 21 < age_h <= 24 * 45:
        heat += 16
        reasons.append("活过三周的小盘 meme，胜率优先")
    elif age_h is not None and 24 * 45 < age_h <= 24 * 60:
        heat += 8
        reasons.append("快满月，倍数还在才考虑")
    heat += min(18.0, max(0.0, (ratio - 1.0) * 20))
    if has_twitter:
        heat += 12
        reasons.append("有 X 热度入口")
    if is_cto:
        heat += 10
        reasons.append("社区接管，庄跑了也能活")
    if gecko_hot:
        heat += 8
        reasons.append("Gecko 热榜交叉确认")
    if multi_source:
        heat += 6
    if narrative_hit:
        heat += 8
        reasons.append("对着当前叙事")
    if 10 <= boost <= 150:
        heat += 4
    elif boost >= 250:
        heat -= 6
        reasons.append("广告费砸太猛，容易拉高出货")
    if 100_000 <= liq <= 400_000:
        heat += 10
        reasons.append("池子够出、盘还小")
    if fdv and 400_000 <= fdv <= 3_000_000:
        heat += 14
        reasons.append("市值还在 meme 倍数区间")
    elif fdv and fdv <= 8_000_000:
        heat += 6
    if 0.8 <= turnover <= 40:
        heat += min(10.0, turnover)
    if -8 <= chg_h24 <= 55 and chg_h1 > -8:
        heat += 10
        reasons.append("不是暴涨暴跌，适合拿一个月")
    if chg_h6 <= -20:
        heat -= 10
    if buyers:
        heat += min(8.0, buyers / 8.0)
    if growth:
        heat += min(8.0, growth / 3.0)
    heat = max(0.0, min(100.0, heat))

    risk = 18.0
    if liq < 120_000:
        risk += 14
        reasons.append("浅池，一个月里仍可能撤")
    if age_h is None:
        risk += 10
    elif age_h < 72:
        risk += 14
    if not has_twitter and not is_cto:
        risk += 12
        reasons.append("没有社交确认")
    if pump_inner:
        risk += 10
    if chg_h24 > 70:
        risk += 10
    if chg_h1 < -10:
        risk += 8
    if holders and holders < 80:
        risk += 8
    if not sells and not sells_m5:
        risk += 6
    risk = max(0.0, min(100.0, risk))

    conviction = (
        age_h is not None
        and 72 <= age_h <= 24 * 60
        and 100_000 <= liq <= 900_000
        and (not fdv or 400_000 <= fdv <= 8_000_000)
        and -18 <= chg_h24 <= 70
        and -8 <= chg_h1 <= 20
        and ratio >= 1.15
        and (has_twitter or is_cto or gecko_hot)
        and chg_m5 < 22
    )
    if reject:
        grade = "避开"
    elif conviction and heat >= 70 and risk <= 50:
        grade = "可跟"
    elif not reject and heat >= 52 and (not fdv or fdv <= 12_000_000):
        grade = "观察"
    else:
        grade = "避开"

    expectancy = round(heat - 0.85 * risk, 1)
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
            "crowd_ok": buyers >= 15 or buys >= 18,
            "holders_rising": growth >= 5 or (holders >= 80 and ratio >= 1.15),
            "multi_source": multi_source,
            "has_twitter": has_twitter,
            "is_cto": is_cto,
            "conviction": conviction,
            "action": {"可跟": "月度小仓", "观察": "只看不买", "避开": "禁止买入"}[grade],
        }
    )
    return out


def select_watchlist(items: list[dict[str, Any]], min_liq: float = 100_000) -> list[dict[str, Any]]:
    scored = [enrich_and_score(it, min_liq) for it in items]
    kept = [x for x in scored if x["grade"] in {"可跟", "观察"}]
    kept.sort(
        key=lambda x: (
            {"可跟": 3, "观察": 2}[x["grade"]],
            x.get("expectancy") or (x["heat"] - 0.85 * x["risk"]),
        ),
        reverse=True,
    )
    for i, row in enumerate(kept, start=1):
        row["period_rank"] = i
    return kept[:30]


def period_pick(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    followable = [x for x in items if x.get("followable")]
    return followable[0] if followable else None
