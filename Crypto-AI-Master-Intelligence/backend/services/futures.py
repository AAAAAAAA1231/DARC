"""Futures scanner: live Binance USDT-M volume Top 100, strategy ensemble, Top 3 watchlist."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from backend.core.enums import ModuleName
from backend.core.logging import get_logger
from backend.data_sources.binance import BinanceProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import FuturesPrediction, PredictionRecord
from backend.services.model_center import ensure_default_version
from backend.strategies.indicators import adx, atr, candles_to_arrays, ema, macd, obv, rsi, vwap
from backend.strategies.plugins import ALL_STRATEGIES
from backend.strategies.weights import load_weights

logger = get_logger("futures")


def _ensemble(ohlcv: dict[str, np.ndarray], weights: dict[str, float]) -> dict[str, Any]:
    signals = [p.evaluate(ohlcv) for p in ALL_STRATEGIES]
    long_score = 0.0
    conf = 0.0
    reasons: list[str] = []
    against: list[str] = []
    breakdown = []
    for sig in signals:
        w = weights.get(sig.name, 0.0)
        long_score += sig.score * w
        conf += sig.confidence * w
        if sig.score >= 60:
            reasons.extend([f"{sig.name}: {r}" for r in sig.reasons])
        if sig.score <= 40:
            against.extend([f"{sig.name}: {r}" for r in (sig.against or sig.reasons)])
        breakdown.append(sig.as_dict())
    if long_score >= 58:
        direction, signal = "LONG", "BUY"
    elif long_score <= 42:
        direction, signal = "SHORT", "SELL"
    else:
        direction, signal = "NEUTRAL", "HOLD"
    return {
        "score": round(long_score, 2),
        "confidence": round(min(0.95, conf), 4),
        "direction": direction,
        "signal": signal,
        "reasons": reasons[:12],
        "against": against[:12],
        "breakdown": breakdown,
    }


def _levels(close: float, atr_v: float, direction: str) -> dict[str, Any]:
    if direction == "LONG":
        entry_low, entry_high = close - 0.5 * atr_v, close + 0.15 * atr_v
        sl = close - 1.6 * atr_v
        tps = [close + 1.2 * atr_v, close + 2.2 * atr_v, close + 3.5 * atr_v]
    elif direction == "SHORT":
        entry_low, entry_high = close - 0.15 * atr_v, close + 0.5 * atr_v
        sl = close + 1.6 * atr_v
        tps = [close - 1.2 * atr_v, close - 2.2 * atr_v, close - 3.5 * atr_v]
    else:
        entry_low, entry_high = close - 0.4 * atr_v, close + 0.4 * atr_v
        sl = close - 2.0 * atr_v
        tps = [close + 1.0 * atr_v, close + 2.0 * atr_v, close + 3.0 * atr_v]
    rr = abs((tps[0] - close) / (close - sl)) if close != sl else None
    return {
        "entry_zone": [entry_low, entry_high],
        "ideal_entry": close,
        "stop_loss": sl,
        "tp1": tps[0],
        "tp2": tps[1],
        "tp3": tps[2],
        "risk_reward": rr,
    }


async def scan(session: Session, top_n: int = 100, analyze_n: int = 15) -> dict[str, Any]:
    version = ensure_default_version(session, "FUTURES")
    weights = load_weights(session, "FUTURES")
    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    tickers = await provider.futures_ticker_24h()
    if not tickers.ok:
        return {
            "ok": False,
            "universe": [],
            "top3": [],
            "source_status": tickers.as_dict(),
            "disclaimer": "Futures universe not fetched. No hardcoded symbol list is substituted.",
        }
    universe = tickers.payload[:top_n]
    analyzed: list[dict[str, Any]] = []
    for row in universe[:analyze_n]:
        symbol = row["symbol"]
        kl = await provider.klines(symbol, "1h", 240, futures=True)
        if not kl.ok or not kl.payload or len(kl.payload) < 60:
            analyzed.append(
                {
                    "symbol": symbol,
                    "quote_volume": row["quote_volume"],
                    "error": kl.error or "insufficient candles",
                    "source_status": kl.status.value,
                }
            )
            continue
        ohlcv = candles_to_arrays(kl.payload)
        ens = _ensemble(ohlcv, weights.weights)
        last = float(ohlcv["close"][-1])
        atr_v = float(atr(ohlcv["high"], ohlcv["low"], ohlcv["close"])[-1])
        levels = _levels(last, atr_v if atr_v == atr_v else last * 0.01, ens["direction"])
        rsi_v = float(rsi(ohlcv["close"])[-1])
        macd_line, _, hist = macd(ohlcv["close"])
        funding = await provider.funding_rate(symbol, 8)
        oi = await provider.open_interest(symbol)
        ls = await provider.long_short_ratio(symbol)
        taker = await provider.taker_buy_sell(symbol)
        item = {
            "symbol": symbol,
            "quote_volume": row["quote_volume"],
            "current_price": last,
            "direction": ens["direction"],
            "signal": ens["signal"],
            "score": ens["score"],
            "confidence": ens["confidence"],
            **levels,
            "position_suggestion": "Paper size only. No live order is sent.",
            "main_reasons": ens["reasons"],
            "against": ens["against"],
            "invalidation": f"Close beyond stop {levels['stop_loss']:.6g} or ADX collapse.",
            "indicators": {
                "rsi": rsi_v,
                "atr": atr_v,
                "macd": float(macd_line[-1]),
                "macd_hist": float(hist[-1]),
                "adx": float(adx(ohlcv["high"], ohlcv["low"], ohlcv["close"])[-1]),
                "obv": float(obv(ohlcv["close"], ohlcv["volume"])[-1]),
                "vwap": float(vwap(ohlcv["high"], ohlcv["low"], ohlcv["close"], ohlcv["volume"])[-1]),
                "ema20": float(ema(ohlcv["close"], 20)[-1]),
            },
            "funding": funding.payload[-1] if funding.ok and funding.payload else {"status": funding.status.value},
            "open_interest": oi.payload if oi.ok else {"status": oi.status.value},
            "long_short": ls.payload[-1] if ls.ok and ls.payload else {"status": ls.status.value},
            "taker": taker.payload[-1] if taker.ok and taker.payload else {"status": taker.status.value},
            "strategy_breakdown": ens["breakdown"],
            "model_version": weights.version,
        }
        analyzed.append(item)

    tradable = [a for a in analyzed if "score" in a]
    ranked = sorted(tradable, key=lambda a: (abs(a["score"] - 50) * a["confidence"]), reverse=True)
    top3 = ranked[:3]
    for i, item in enumerate(top3, start=1):
        session.add(
            FuturesPrediction(
                symbol=item["symbol"],
                rank=i,
                direction=item["direction"],
                confidence=item["confidence"],
                current_price=Decimal(str(item["current_price"])),
                entry_zone={"zone": item["entry_zone"], "ideal": item["ideal_entry"]},
                stop_loss=Decimal(str(item["stop_loss"])),
                take_profits={"tp1": item["tp1"], "tp2": item["tp2"], "tp3": item["tp3"]},
                risk_reward=item.get("risk_reward"),
                position_suggestion=item["position_suggestion"],
                reasons={"for": item["main_reasons"], "against": item["against"]},
                invalidation=item["invalidation"],
                strategy_breakdown=item["strategy_breakdown"],
                model_version=item["model_version"],
            )
        )
        session.add(
            PredictionRecord(
                module=ModuleName.FUTURES.value,
                subject=item["symbol"],
                model_version=item["model_version"],
                direction=item["direction"],
                predicted_price=Decimal(str(item["current_price"])),
                confidence=item["confidence"],
                entry={"zone": item["entry_zone"], "ideal": item["ideal_entry"]},
                stop_loss=Decimal(str(item["stop_loss"])),
                take_profits={"tp1": item["tp1"], "tp2": item["tp2"], "tp3": item["tp3"]},
                payload=item,
            )
        )
    logger.info("futures_scan universe=%s analyzed=%s top3=%s", len(universe), len(analyzed), [t["symbol"] for t in top3])
    return {
        "ok": True,
        "universe_count": len(universe),
        "universe": [{"symbol": u["symbol"], "quote_volume": u["quote_volume"], "last": u["last"]} for u in universe],
        "analyzed": analyzed,
        "top3": [{**t, "rank": i} for i, t in enumerate(top3, start=1)],
        "model_version": weights.version,
        "disclaimer": "Ensemble of technical plugins on live Binance USDT-M data. Not a 100% direction forecast. No live orders are placed.",
    }


def latest_top3(session: Session) -> dict[str, Any]:
    rows = session.query(FuturesPrediction).order_by(FuturesPrediction.created_at.desc()).limit(12).all()
    seen: set[int] = set()
    top3 = []
    for row in rows:
        if row.rank is None or row.rank in seen:
            continue
        seen.add(row.rank)
        tps = row.take_profits or {}
        reasons = row.reasons or {}
        entry = row.entry_zone or {}
        top3.append(
            {
                "rank": row.rank,
                "symbol": row.symbol,
                "direction": row.direction,
                "confidence": float(row.confidence) if row.confidence is not None else None,
                "current_price": float(row.current_price) if row.current_price is not None else None,
                "ideal_entry": entry.get("ideal"),
                "entry_zone": entry.get("zone"),
                "stop_loss": float(row.stop_loss) if row.stop_loss is not None else None,
                "tp1": tps.get("tp1"),
                "tp2": tps.get("tp2"),
                "tp3": tps.get("tp3"),
                "risk_reward": float(row.risk_reward) if row.risk_reward is not None else None,
                "main_reasons": reasons.get("for") or [],
                "against": reasons.get("against") or [],
                "invalidation": row.invalidation,
                "model_version": row.model_version,
            }
        )
        if len(top3) >= 3:
            break
    top3.sort(key=lambda x: x.get("rank") or 99)
    return {
        "ok": True,
        "from_cache": True,
        "universe_count": None,
        "top3": top3,
        "disclaimer": "Last stored futures analysis. Click Scan for a fresh live volume universe.",
    }
