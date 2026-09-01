from __future__ import annotations

import numpy as np

from web3_radar.engine.risk import (
    RiskConfig,
    adaptive_multiples,
    apply_portfolio_overlay,
    apply_quality_gate,
    position_plan,
    simulate_trade_r,
    size_equal_notional,
    size_risk_parity,
    trend_agreement,
)
from web3_radar.engine.signals import analyze_klines


def test_hype_style_equal_notional_loses_risk_parity_does_not():
    """HYPE hits full stop, ETH/ZEC still green but small — equal USD size stays red."""
    # percent moves and stop distances, matching a 4h ATR book
    returns_pct = [-8.0, 2.0, 3.0]  # HYPE, ETH, ZEC
    stop_pcts = [8.0, 3.0, 7.0]
    notionals = [1000.0, 1000.0, 1000.0]
    equal_pnls = [n * r / 100.0 for n, r in zip(notionals, returns_pct)]
    assert size_equal_notional(equal_pnls) < 0

    parity = size_risk_parity(returns_pct, stop_pcts, risk_unit=50.0)
    assert parity > 0
    assert parity > size_equal_notional(equal_pnls)


def test_adaptive_stop_wider_for_high_vol_alts():
    cfg = RiskConfig()
    sl_hi, tp_hi = adaptive_multiples(0.05, cfg)  # HYPE/ZEC class
    sl_lo, tp_lo = adaptive_multiples(0.01, cfg)  # ETH/BTC class
    assert sl_hi > cfg.base_sl_mult > sl_lo
    assert tp_hi > cfg.base_tp_mult > tp_lo
    assert abs((tp_hi / sl_hi) - (tp_lo / sl_lo)) < 0.05


def test_noise_stop_old_1_5_atr_vs_managed_wider_stop():
    entry, atr_v = 100.0, 2.0
    highs = np.array([101.0, 103.8, 105.0])
    lows = np.array([96.9, 100.2, 102.0])  # first bar tags 1.55 ATR then recovers
    old_sl, old_tp = entry - 1.5 * atr_v, entry + 2.5 * atr_v
    old_r = simulate_trade_r(highs, lows, 1, entry, old_sl, old_tp, atr_v, manage=False)
    assert old_r < 0

    cfg = RiskConfig()
    sl_m, tp_m = adaptive_multiples(atr_v / entry, cfg)
    sl, tp = entry - sl_m * atr_v, entry + tp_m * atr_v
    new_r = simulate_trade_r(highs, lows, 1, entry, sl, tp, atr_v, cfg, manage=True)
    assert sl < 96.9
    assert new_r > old_r
    assert new_r > 0


def test_partial_and_breakeven_locks_winner():
    entry, atr_v, sl_m = 100.0, 2.0, 1.8
    sl, tp = entry - sl_m * atr_v, entry + 2.8 * atr_v
    # trade goes +1.1R, then fully gives back through entry
    risk = sl_m * atr_v
    highs = np.array([entry + 1.1 * risk, entry + 0.2 * risk])
    lows = np.array([entry - 0.1 * risk, sl - 0.1])
    unmanaged = simulate_trade_r(highs, lows, 1, entry, sl, tp, atr_v, manage=False)
    managed = simulate_trade_r(highs, lows, 1, entry, sl, tp, atr_v, manage=True)
    assert unmanaged <= -0.99
    assert managed > 0
    assert managed >= 0.35  # ~40% scaled at 1R, rest stopped at breakeven


def test_position_plan_risk_parity_size():
    plan_hype = position_plan("long", 60.0, 3.0, 2.2, 3.2)  # ~11% stop
    plan_eth = position_plan("long", 1900.0, 28.0, 1.6, 2.6)  # ~2.4% stop
    assert plan_hype["notional_pct"] < plan_eth["notional_pct"]
    assert plan_hype["stop_pct"] > 8
    assert plan_eth["stop_pct"] < 4


def test_quality_gate_rejects_disagreement():
    decision, note = apply_quality_gate("涨", 0.23, 0.20)
    assert decision == "观望"
    assert "分歧" in note
    keep, _ = apply_quality_gate("涨", 0.50, 0.70)
    assert keep == "涨"


def test_portfolio_caps_three_and_same_side():
    rows = [
        {"symbol": f"A{i}", "side": "long", "decision": "涨", "quality": 2.0 - i * 0.1, "score": 0.5, "suggested_notional_pct": 10}
        for i in range(5)
    ]
    rows.append({"symbol": "S1", "side": "short", "decision": "跌", "quality": 1.2, "score": -0.4, "suggested_notional_pct": 8})
    apply_portfolio_overlay(rows, RiskConfig(max_positions=3, max_same_side=2))
    tradable = [r for r in rows if r.get("tradable")]
    assert len(tradable) == 3
    assert sum(1 for r in tradable if r["side"] == "long") <= 2
    assert any(r["symbol"] == "S1" for r in tradable)


def _ohlcv(n: int = 180, trend: float = 0.002, seed: int = 1):
    import pandas as pd

    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + trend + rng.normal(0, 0.01, n))
    high = close * (1 + rng.uniform(0.001, 0.012, n))
    low = close * (1 - rng.uniform(0.001, 0.012, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(1e5, 5e5, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_analyze_klines_exposes_management_plan():

    df = _ohlcv(trend=0.004)
    fitted = {name: 1.0 for name in [
        "td13", "harmonic", "elliott", "ichimoku", "macd", "rsi", "supertrend", "ema_cross",
        "bollinger", "fibonacci", "adx_dmi", "stochastic", "parabolic_sar", "keltner", "donchian",
        "mfi", "cci", "williams_r", "obv", "cmf", "vwap", "awesome_oscillator", "heikin_ashi",
        "engulfing", "volume_spike", "roc", "trix", "pivot_points", "ultimate_oscillator", "atr_breakout",
    ]}
    out = analyze_klines(df, "HYPEUSDT", n_sims=1_000, fitted_weights=fitted)
    assert "plan_note" in out
    assert "suggested_notional_pct" in out
    assert "quality" in out
    assert out["sl_mult"] > 0
    assert out["partial_tp"] > 0
    if out["decision"] == "涨":
        assert out["stop_loss"] < out["entry"] < out["take_profit"]
        assert out["breakeven"] == out["entry"] or abs(out["breakeven"] - out["entry"]) < 1e-6


def test_trend_agreement_bounds():
    class I:
        def __init__(self, name, signal, strength):
            self.name = name
            self.signal = signal
            self.strength = strength

    inds = [I("supertrend", 1, 0.8), I("ema_cross", 1, 0.7), I("macd", -1, 0.5), I("rsi", 1, 1.0)]
    up = trend_agreement(inds, 1)
    down = trend_agreement(inds, -1)
    assert 0 <= down < up <= 1
