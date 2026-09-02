"""BTC four-year cycle. Probability + window + confidence. Never a single-day top call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.parsing import ensure_aware, utcnow

from backend.core.enums import MarketRegime
from backend.core.logging import get_logger
from backend.data_sources.binance import BinanceProvider
from backend.data_sources.onchain import BlockchainInfoProvider, CoinPaprikaProvider, MempoolProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import BtcCycle, BtcCycleHistory
from backend.services.model_center import ensure_default_version
from backend.strategies.indicators import sma

logger = get_logger("btc_cycle")

# Historical Bitcoin halving dates (protocol facts, not forecasts).
HALVINGS = [
    datetime(2012, 11, 28, tzinfo=timezone.utc),
    datetime(2016, 7, 9, tzinfo=timezone.utc),
    datetime(2020, 5, 11, tzinfo=timezone.utc),
    datetime(2024, 4, 20, tzinfo=timezone.utc),
]


def _last_halving(now: datetime) -> datetime:
    past = [h for h in HALVINGS if h <= now]
    return past[-1] if past else HALVINGS[0]


async def latest_or_analyze(session: Session, max_age_minutes: int = 90) -> dict[str, Any]:
    """Serve the last persisted cycle if fresh so Dashboard is not blocked on 800 daily klines."""
    hist = session.execute(select(BtcCycleHistory).order_by(BtcCycleHistory.created_at.desc()).limit(1)).scalar_one_or_none()
    if hist and hist.snapshot and hist.created_at:
        created = ensure_aware(hist.created_at)
        if created is not None:
            age = utcnow() - created
            if age <= timedelta(minutes=max_age_minutes):
                snap = dict(hist.snapshot)
                snap.pop("klines", None)
                snap["cached"] = True
                snap["cached_age_seconds"] = int(age.total_seconds())
                return snap
    payload = await analyze(session)
    slim = dict(payload)
    slim.pop("klines", None)
    slim["cached"] = False
    return slim


async def analyze(session: Session) -> dict[str, Any]:
    version = ensure_default_version(session, "BTC_CYCLE")
    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    kl = await provider.klines("BTCUSDT", "1d", 800, futures=False)
    extras: dict[str, Any] = {}
    extra_status: dict[str, Any] = {}
    try:
        mempool: MempoolProvider = get_provider("mempool")  # type: ignore[assignment]
        chain: BlockchainInfoProvider = get_provider("blockchain_info")  # type: ignore[assignment]
        paprika: CoinPaprikaProvider = get_provider("coinpaprika")  # type: ignore[assignment]
        h = await mempool.hashrate()
        tip = await mempool.health()
        tx = await chain.chart("n-transactions", "7days")
        glob = await paprika.global_market()
        extra_status = {
            "mempool": {"status": h.status.value, "error": h.error},
            "blockchain_info": {"status": tx.status.value, "error": tx.error},
            "coinpaprika": {"status": glob.status.value, "error": glob.error},
        }
        if h.ok:
            extras["hashrate"] = h.payload
        if tip.ok:
            extras["block_height"] = tip.payload
        if tx.ok:
            extras["confirmed_tx"] = tx.payload
        if glob.ok:
            extras["btc_dominance"] = glob.payload.get("btc_dominance")
            extras["global_mcap"] = glob.payload.get("market_cap_usd")
    except KeyError:
        extra_status = {"onchain": "providers_not_registered"}
    missing = {
        "mvrv": "UNKNOWN — no on-chain provider configured",
        "nupl": "UNKNOWN — no on-chain provider configured",
        "sopr": "UNKNOWN — no on-chain provider configured",
        "puell": "UNKNOWN — no on-chain provider configured",
        "realized_price": "UNKNOWN — no on-chain provider configured",
        "lth_supply": "UNKNOWN — no on-chain provider configured",
        "exchange_balance": "UNKNOWN — no on-chain provider configured",
        "etf_flow": "UNKNOWN — no ETF flow provider configured",
        "stablecoin_liquidity": "UNKNOWN — no stablecoin-supply provider configured",
        "macro_liquidity": "UNKNOWN — no macro provider configured",
    }
    if not kl.ok or not kl.payload:
        result = {
            "ok": False,
            "regime": MarketRegime.RANGE.value,
            "phase": "DATA_UNAVAILABLE",
            "bull_score": None,
            "bear_score": None,
            "confidence": 0.0,
            "top_window": None,
            "bottom_window": None,
            "indicators": {},
            "missing_indicators": missing,
            "source_status": {"binance": kl.as_dict()},
            "disclaimer": "Cycle output withheld because BTC daily candles were not retrieved. No date is invented.",
        }
        return result

    closes = np.array([float(c["close"]) for c in kl.payload], dtype=float)
    last = float(closes[-1])
    ma200 = sma(closes, 200)
    ma_now = float(ma200[-1]) if not np.isnan(ma200[-1]) else None
    ath = float(closes.max())
    drawdown = (last / ath) - 1.0
    now = datetime.now(timezone.utc)
    last_h = _last_halving(now)
    days_since = (now - last_h).days
    cycle_progress = days_since / (4 * 365.25)

    bull = 50.0
    bear = 50.0
    reasons = []
    if ma_now:
        if last > ma_now:
            bull += 15
            bear -= 10
            reasons.append("spot > 200D MA")
        else:
            bear += 15
            bull -= 10
            reasons.append("spot < 200D MA")
    if drawdown > -0.15:
        bull += 10
        reasons.append(f"drawdown from ATH {drawdown:.2%} (near highs)")
    elif drawdown < -0.5:
        bear += 10
        reasons.append(f"drawdown from ATH {drawdown:.2%}")
    if 0.4 <= cycle_progress <= 0.75:
        bull += 8
        reasons.append("mid-to-late post-halving window historically associated with expansion — not a guarantee")
    elif cycle_progress > 0.9:
        bear += 8
        reasons.append("late-cycle window; tops are probabilistic ranges, not a date")

    bull = max(0, min(100, bull))
    bear = max(0, min(100, bear))
    if bull - bear > 15:
        regime = MarketRegime.BULL
        phase = "EXPANSION"
    elif bear - bull > 15:
        regime = MarketRegime.BEAR
        phase = "CONTRACTION"
    elif abs(drawdown) < 0.12:
        regime = MarketRegime.RANGE
        phase = "HIGH_RANGE"
    else:
        regime = MarketRegime.TRANSITION
        phase = "TRANSITION"

    confidence = 0.35 + (0.15 if ma_now else 0)
    top_window = {
        "from": (last_h.replace(year=last_h.year + 2)).date().isoformat(),
        "to": (last_h.replace(year=last_h.year + 4)).date().isoformat(),
        "note": "Historical post-halving window only. Not a prediction that price must top inside it.",
    }
    bottom_window = {
        "from": (last_h.replace(year=last_h.year + 3)).date().isoformat(),
        "to": (last_h.replace(year=last_h.year + 5)).date().isoformat(),
        "note": "Wide probabilistic zone. A specific bottom date is not produced.",
    }
    if extras.get("btc_dominance"):
        reasons.append(f"BTC dominance {extras['btc_dominance']}% (CoinPaprika live)")
        confidence += 0.05
    payload = {
        "ok": True,
        "as_of": now.isoformat(),
        "regime": regime.value,
        "phase": phase,
        "bull_score": round(bull, 2),
        "bear_score": round(bear, 2),
        "confidence": round(min(0.7, confidence), 4),
        "current_price": last,
        "ath": ath,
        "drawdown": drawdown,
        "ma200": ma_now,
        "days_since_halving": days_since,
        "cycle_progress": round(cycle_progress, 4),
        "last_halving": last_h.date().isoformat(),
        "top_window": top_window,
        "bottom_window": bottom_window,
        "klines": kl.payload[-180:] if kl.payload else [],
        "indicators": {
            "price": last,
            "ma200": ma_now,
            "ath": ath,
            "drawdown": drawdown,
            "halving": last_h.isoformat(),
            **extras,
        },
        "missing_indicators": missing,
        "reasons": reasons,
        "source_status": {"binance": {"status": kl.status.value, "n": len(kl.payload)}, **extra_status},
        "model_version": version.version,
        "disclaimer": "Statistical regime sketch from live price/MA/halving plus optional mempool/blockchain.info/paprika metrics. MVRV/NUPL/SOPR remain UNKNOWN without a dedicated on-chain valuation provider. Not a date-certain top or bottom call.",
    }
    row = BtcCycle(
        as_of=now,
        regime=payload["regime"],
        phase=phase,
        bull_score=bull,
        bear_score=bear,
        confidence=confidence,
        top_window=top_window,
        bottom_window=bottom_window,
        indicators=payload["indicators"],
        missing_indicators=missing,
        source_status=payload["source_status"],
        model_version=version.version,
    )
    session.add(row)
    session.add(BtcCycleHistory(snapshot=payload))
    logger.info("btc_cycle regime=%s bull=%s bear=%s", regime.value, bull, bear)
    return payload
