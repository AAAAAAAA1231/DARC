"""Spot opportunities from live Binance USDT spot volume, with profile-scaled risk."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import ModuleName, RiskProfile
from backend.core.identity import build_project_identity
from backend.core.logging import get_logger
from backend.data_sources.binance import BinanceProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import SpotPrediction
from backend.services.model_center import ensure_default_version
from backend.services.projects import upsert_project
from backend.strategies.indicators import atr, candles_to_arrays, rsi
from backend.strategies.plugins import ALL_STRATEGIES
from backend.strategies.weights import load_weights

logger = get_logger("spot")

PROFILE_ATR = {
    RiskProfile.CONSERVATIVE: 2.4,
    RiskProfile.BALANCED: 1.8,
    RiskProfile.AGGRESSIVE: 1.2,
}


async def scan(session: Session, profile: RiskProfile = RiskProfile.BALANCED, analyze_n: int = 12) -> dict[str, Any]:
    version = ensure_default_version(session, "SPOT")
    weights = load_weights(session, "SPOT")
    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    tickers = await provider.spot_ticker_24h()
    if not tickers.ok:
        return {"ok": False, "source_status": tickers.as_dict(), "opportunities": []}
    usdt = [t for t in tickers.payload if t["symbol"].endswith("USDT")]
    usdt.sort(key=lambda t: float(t["quote_volume"]), reverse=True)
    out = []
    sl_mult = PROFILE_ATR[profile]
    for row in usdt[:analyze_n]:
        symbol = row["symbol"]
        kl = await provider.klines(symbol, "4h", 200, futures=False)
        if not kl.ok or not kl.payload or len(kl.payload) < 50:
            continue
        ohlcv = candles_to_arrays(kl.payload)
        last = float(ohlcv["close"][-1])
        atr_v = float(atr(ohlcv["high"], ohlcv["low"], ohlcv["close"])[-1])
        rsi_v = float(rsi(ohlcv["close"])[-1])
        score = 0.0
        conf = 0.0
        reasons = []
        for plugin in ALL_STRATEGIES:
            sig = plugin.evaluate(ohlcv)
            w = weights.weights.get(plugin.name, 0)
            score += sig.score * w
            conf += sig.confidence * w
            if sig.score >= 62:
                reasons.extend(sig.reasons)
        buy_low = last - 0.8 * atr_v
        buy_high = last - 0.15 * atr_v
        sl = last - sl_mult * atr_v
        tps = [last + 1.0 * atr_v, last + 2.0 * atr_v, last + 3.2 * atr_v]
        identity = build_project_identity(name=symbol.replace("USDT", ""), chain="binance-spot", contract=symbol)
        project = upsert_project(session, identity, module=ModuleName.SPOT.value, symbol=symbol.replace("USDT", ""))
        holding = {"CONSERVATIVE": "weeks to months", "BALANCED": "days to weeks", "AGGRESSIVE": "hours to days"}[profile.value]
        item = {
            "project_id": project.project_id,
            "symbol": symbol,
            "current_price": last,
            "buy_zone": [buy_low, buy_high],
            "ideal_buy_zone": (buy_low + buy_high) / 2,
            "stop_loss": sl,
            "tp1": tps[0],
            "tp2": tps[1],
            "tp3": tps[2],
            "position_suggestion": f"{profile.value} paper size only",
            "risk": profile.value,
            "holding_period": holding,
            "score": round(score, 2),
            "confidence": round(min(0.9, conf), 4),
            "rsi": rsi_v,
            "reasons": reasons[:8],
            "invalidation": f"4h close below {sl:.6g}",
            "model_version": weights.version,
        }
        session.add(
            SpotPrediction(
                project_id=project.project_id,
                symbol=symbol,
                profile=profile.value,
                current_price=Decimal(str(last)),
                buy_zone={"zone": item["buy_zone"], "ideal": item["ideal_buy_zone"]},
                stop_loss=Decimal(str(sl)),
                take_profits={"tp1": tps[0], "tp2": tps[1], "tp3": tps[2]},
                position_suggestion=item["position_suggestion"],
                risk=profile.value,
                holding_period=holding,
                score=score,
                confidence=item["confidence"],
                reasons={"for": reasons},
                model_version=weights.version,
            )
        )
        out.append(item)
    out.sort(key=lambda x: x["score"], reverse=True)
    logger.info("spot_scan n=%s profile=%s", len(out), profile.value)
    return {
        "ok": True,
        "profile": profile.value,
        "universe_count": len(usdt),
        "opportunities": out,
        "disclaimer": "现货区间来自实时K线与策略集成。不是保证买入。",
        "model_version": version.version,
    }


def latest(session: Session, profile: str | None = None) -> dict[str, Any]:
    q = session.query(SpotPrediction)
    if profile:
        q = q.filter(SpotPrediction.profile == profile.upper())
    rows = q.order_by(SpotPrediction.created_at.desc()).limit(40).all()
    seen: set[str] = set()
    opportunities = []
    for row in rows:
        if row.symbol in seen:
            continue
        seen.add(row.symbol)
        zone = (row.buy_zone or {}).get("zone") if isinstance(row.buy_zone, dict) else None
        tps = row.take_profits or {}
        opportunities.append(
            {
                "project_id": row.project_id,
                "symbol": row.symbol,
                "current_price": float(row.current_price) if row.current_price is not None else None,
                "buy_zone": zone,
                "stop_loss": float(row.stop_loss) if row.stop_loss is not None else None,
                "tp1": tps.get("tp1"),
                "tp2": tps.get("tp2"),
                "tp3": tps.get("tp3"),
                "score": float(row.score) if row.score is not None else None,
                "confidence": float(row.confidence) if row.confidence is not None else None,
                "risk": row.risk,
                "reasons": (row.reasons or {}).get("for"),
                "invalidation": None,
                "model_version": row.model_version,
            }
        )
    return {
        "ok": True,
        "from_cache": True,
        "profile": profile or "ALL",
        "opportunities": opportunities,
        "disclaimer": "上次保存的现货扫描。点击扫描可拉取新的实时宇宙。",
    }
