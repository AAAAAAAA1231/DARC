from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from web3_radar.collectors.airdrop import score_airdrop, parse_raise_text
from web3_radar.collectors.meme import _passes_meme_filter
from web3_radar.collectors.social import extract_deadline, score_ambassador
from web3_radar.engine.indicators import compute_all_indicators, rsi, td_sequential
from web3_radar.engine.monte_carlo import decision_from_score, monte_carlo_reweight
from web3_radar.engine.signals import analyze_klines


def _ohlcv(n: int = 180, trend: float = 0.002, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + trend + rng.normal(0, 0.01, n))
    high = close * (1 + rng.uniform(0.001, 0.012, n))
    low = close * (1 - rng.uniform(0.001, 0.012, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(1e5, 5e5, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_rsi_bounds():
    df = _ohlcv()
    values = rsi(df["close"].to_numpy())
    assert values.min() >= 0
    assert values.max() <= 100


def test_td_and_all_indicators_run():
    df = _ohlcv()
    td = td_sequential(df)
    assert td.name == "td13"
    assert td.signal in (-1, 0, 1)
    inds = compute_all_indicators(df)
    names = {i.name for i in inds}
    assert "td13" in names
    assert "harmonic" in names
    assert "macd" in names
    assert len(inds) >= 25


def test_monte_carlo_weights_sum_and_favor_winners():
    names = ["a", "b", "c"]
    exp = np.array([0.05, -0.02, 0.01])
    w = monte_carlo_reweight(names, exp, {"a": 10, "b": 10, "c": 10}, n_sims=20_000, top_pct=5, rng=np.random.default_rng(0))
    assert pytest.approx(sum(w.values()), rel=1e-6) == 1
    assert w["a"] > w["b"]


def test_decision_threshold():
    assert decision_from_score(0.3) == "涨"
    assert decision_from_score(-0.3) == "跌"
    assert decision_from_score(0.01) == "观望"


def test_analyze_klines_prices():
    df = _ohlcv(trend=0.004)
    out = analyze_klines(df, "BTCUSDT", n_sims=8_000, top_pct=5)
    assert out["symbol"] == "BTCUSDT"
    assert out["decision"] in ("涨", "跌", "观望")
    assert out["entry"] > 0
    assert out["stop_loss"] > 0
    assert out["take_profit"] > 0
    assert out["n_sims"] == 8_000
    if out["decision"] == "涨":
        assert out["stop_loss"] < out["entry"] < out["take_profit"]
    if out["decision"] == "跌":
        assert out["take_profit"] < out["entry"] < out["stop_loss"]


def test_meme_liquidity_filter():
    good = {
        "liquidity_usd": 25_000,
        "unique_buyers_est": 12,
        "buys": 20,
        "holder_growth_est": 6,
    }
    bad = dict(good, liquidity_usd=5_000)
    assert _passes_meme_filter(good, 20_000, 8, 5)
    assert not _passes_meme_filter(bad, 20_000, 8, 5)


def test_parse_raise_text():
    assert parse_raise_text("Talos Extends Series B to $150M in Strategic Fundraise") == 150_000_000
    assert parse_raise_text("Yuga Labs raised $ 450 M in Seed round") == 450_000_000
    assert parse_raise_text("no money here") is None
    high, _ = score_airdrop(80_000_000, 4, "未发币（待核验）", 1_000_000_000)
    low, _ = score_airdrop(5_000_000, 0, "可能已有协议/代币", None)
    assert high > low
    assert high >= 70


def test_ambassador_priority_and_deadline():
    score, priority = score_ambassador("Apply now paid ambassador stipend deadline March 20 form", None)
    assert score >= 70
    assert priority.startswith("高")
    assert "March" in extract_deadline("deadline: March 20 apply now")
