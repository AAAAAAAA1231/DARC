from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from web3_radar.collectors.airdrop import score_airdrop, parse_raise_text, _keep_airdrop_focus, _decorate_airdrop, _funding_ok
from web3_radar.collectors.ecosystem import classify_btc_eth, is_solana
from web3_radar.collectors.meme import _passes_meme_filter, meme_age_ok
from web3_radar.collectors.social import extract_deadline, looks_like_solana_launch, score_ambassador
from web3_radar.engine.indicators import classify_regime, compute_all_indicators, last_atr, rsi, td_sequential
from web3_radar.engine.monte_carlo import decision_from_score, monte_carlo_reweight
from web3_radar.engine.signals import analyze_klines, average_weights_from_results, fit_global_weights, mark_top_recommendations, plan_limit_levels, pool_expectancies
from web3_radar.engine.live_learn import (
    apply_live_feedback,
    recommend_count,
    settle_recommendations,
    skip_symbols,
    update_weights_from_trades,
)


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
    progressed = []
    w2 = monte_carlo_reweight(
        names, exp, {"a": 10, "b": 10, "c": 10},
        n_sims=120_000, top_pct=1, rng=np.random.default_rng(1),
        on_progress=lambda done, total: progressed.append((done, total)),
    )
    assert pytest.approx(sum(w2.values()), rel=1e-6) == 1
    assert w2["a"] > w2["b"]
    assert progressed and progressed[-1] == (120_000, 120_000)


def test_format_sim_count():
    from web3_radar.config import format_sim_count
    assert format_sim_count(1_000_000_000) == "10亿次"
    assert format_sim_count(1_000_000) == "100万次"


def test_decision_threshold():
    assert decision_from_score(0.3) == "涨"
    assert decision_from_score(-0.3) == "跌"
    assert decision_from_score(0.01) == "观望"


def test_analyze_klines_prices():
    df = _ohlcv(trend=0.004)
    out = analyze_klines(df, "BTCUSDT", n_sims=8_000, top_pct=5)
    assert out["symbol"] == "BTCUSDT"
    assert out["decision"] in ("涨", "跌", "观望")
    assert out["regime"] in ("震荡", "单边", "过渡")
    assert out["entry"] > 0
    assert out["stop_loss"] > 0
    assert out["take_profit"] > 0
    assert out["n_sims"] == 8_000
    assert out["mode"] == "fit"
    assert out["weights_adjusted"] is True
    assert "recommend" in out
    if out["decision"] in ("涨", "跌"):
        assert out["recommend"] is True
    else:
        assert out["recommend"] is False
    if out["decision"] == "涨":
        assert out["stop_loss"] < out["entry"] < out["take_profit"]
        assert out["entry"] < out["price"]
    if out["decision"] == "跌":
        assert out["take_profit"] < out["entry"] < out["stop_loss"]
        assert out["entry"] > out["price"]
    if out["decision"] == "观望":
        assert out["entry"] == out["price"]


def test_limit_entry_waits_instead_of_hitting_last_price():
    df = _ohlcv(trend=0.004)
    price = float(df["close"].iloc[-1])
    atr_v = last_atr(df)
    long_e, sl, tp = plan_limit_levels(df, "涨", "单边", price, atr_v, 1.5, 2.5)
    assert long_e < price
    assert sl < long_e < tp
    assert price - long_e <= 0.45 * atr_v * 1.05
    short_e, sl2, tp2 = plan_limit_levels(df, "跌", "震荡", price, atr_v, 1.5, 2.5)
    assert short_e > price
    assert tp2 < short_e < sl2
    assert short_e - price <= 0.70 * atr_v * 1.05
    flat_e, _, _ = plan_limit_levels(df, "观望", "过渡", price, atr_v, 1.5, 2.5)
    assert flat_e == price


def _range_ohlcv(n: int = 180, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    close = 100 + 1.2 * np.sin(2 * np.pi * t / 20) + rng.normal(0, 0.08, n)
    high = close + rng.uniform(0.05, 0.25, n)
    low = close - rng.uniform(0.05, 0.25, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(1e5, 5e5, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def _trend_ohlcv(n: int = 180, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + 0.012 + rng.normal(0, 0.0015, n))
    high = close * (1 + rng.uniform(0.001, 0.004, n))
    low = close * (1 - rng.uniform(0.001, 0.004, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(1e5, 5e5, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_regime_range_vs_trend():
    ranging = classify_regime(_range_ohlcv())
    trending = classify_regime(_trend_ohlcv())
    assert ranging["regime"] == "震荡"
    assert trending["regime"] == "单边"
    chopped = analyze_klines(_range_ohlcv(), "RANGEUSDT", n_sims=2_000, top_pct=5, fitted_weights={"td13": 1})
    assert chopped["regime"] == "震荡"
    if chopped["raw_decision"] != "观望":
        assert chopped["decision"] == "观望" or chopped["playbook"] == "震荡短打"


def test_infer_uses_fitted_weights_without_resampling():
    df = _ohlcv(trend=0.004)
    fitted = {i.name: 1.0 for i in compute_all_indicators(df)}
    fitted["td13"] = 40
    out = analyze_klines(df, "ETHUSDT", n_sims=1_000_000, fitted_weights=fitted)
    assert out["mode"] == "infer"
    assert "套用" in out["sim_note"]
    assert out["n_sims"] == 1_000_000
    assert out["weights_adjusted"] is True
    again = analyze_klines(df, "ETHUSDT", n_sims=1_000_000, fitted_weights=fitted)
    assert again["decision"] == out["decision"]
    assert again["score"] == out["score"]


def test_pool_and_global_fit():
    names = ["a", "b"]
    maps = [{"a": 0.05, "b": -0.02}, {"a": 0.04, "b": -0.03}]
    pooled = pool_expectancies(maps, names)
    assert pooled["a"] > pooled["b"]
    w = fit_global_weights(maps, names, {"a": 10, "b": 10}, n_sims=8_000, top_pct=5, rng=np.random.default_rng(0))
    assert pytest.approx(sum(w.values()), rel=1e-6) == 1
    assert w["a"] > w["b"]
    avg = average_weights_from_results(
        [
            {"indicators": [{"name": "td13", "weight_optimized": 0.3}, {"name": "rsi", "weight_optimized": 0.1}]},
            {"indicators": [{"name": "td13", "weight_optimized": 0.5}, {"name": "rsi", "weight_optimized": 0.1}]},
        ]
    )
    assert avg["td13"] > avg["rsi"]


def test_mark_top_recommendations():
    rows = mark_top_recommendations(
        [
            {"symbol": "A", "score": 80, "decision": "涨", "recommend": True},
            {"symbol": "B", "score": -70, "decision": "跌", "recommend": True},
            {"symbol": "C", "score": 60, "decision": "涨", "recommend": True},
            {"symbol": "D", "score": 50, "decision": "涨", "recommend": True},
            {"symbol": "E", "score": 90, "decision": "观望", "recommend": True},
        ],
        3,
    )
    recommended = {row["symbol"] for row in rows if row["recommend"]}
    assert recommended == {"A", "B", "C"}
    skipped = mark_top_recommendations(rows, 3, skip_symbols={"A"})
    assert {row["symbol"] for row in skipped if row["recommend"]} == {"B", "C", "D"}
    by_wr = mark_top_recommendations(
        [
            {"symbol": "LOW", "score": 90, "decision": "涨", "win_rate": 0.2},
            {"symbol": "HIGH", "score": 10, "decision": "跌", "win_rate": 0.8},
            {"symbol": "MID", "score": 50, "decision": "涨", "win_rate": 0.5},
        ],
        1,
    )
    assert [row["symbol"] for row in by_wr if row["recommend"]] == ["HIGH"]


def test_live_weight_update_follows_pnl_and_time():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)
    weights = {"rsi": 0.5, "macd": 0.5}
    win = {
        "symbol": "BTCUSDT",
        "side": "涨",
        "ts": (now - timedelta(hours=4)).isoformat(),
        "closed_at": now.isoformat(),
        "pnl_pct": 0.02,
        "hit": True,
        "signals": {"rsi": 1, "macd": -1},
    }
    after_win = update_weights_from_trades(weights, [win], now=now)
    assert after_win["rsi"] > after_win["macd"]
    loss = dict(win, pnl_pct=-0.02, hit=False)
    after_loss = update_weights_from_trades(weights, [loss], now=now)
    assert after_loss["rsi"] < after_loss["macd"]
    old_loss = dict(loss, ts=(now - timedelta(hours=72)).isoformat())
    after_old = update_weights_from_trades(weights, [old_loss], now=now)
    assert abs(after_old["rsi"] - 0.5) < abs(after_loss["rsi"] - 0.5)


def test_live_feedback_still_updates_pending_and_ranks_by_win_rate():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)
    rows = [
        {"symbol": "AAAUSDT", "decision": "涨", "score": 80, "price": 110, "hist_win_rate": 0.9, "indicators": [{"name": "rsi", "signal": 1, "strength": 0.8}]},
        {"symbol": "BBBUSDT", "decision": "涨", "score": 70, "price": 50, "hist_win_rate": 0.4, "indicators": [{"name": "rsi", "signal": 1, "strength": 0.6}]},
        {"symbol": "CCCUSDT", "decision": "跌", "score": -65, "price": 9, "hist_win_rate": 0.7, "indicators": [{"name": "rsi", "signal": -1, "strength": 0.7}]},
        {"symbol": "DDDUSDT", "decision": "涨", "score": 40, "price": 3, "hist_win_rate": 0.2, "indicators": [{"name": "rsi", "signal": 1, "strength": 0.4}]},
    ]
    pending = [{
        "symbol": "AAAUSDT",
        "side": "涨",
        "entry": 100,
        "ts": (now - timedelta(minutes=20)).isoformat(),
        "interval": "4h",
        "signals": {"rsi": 1},
        "weights": {"rsi": 1.0},
    }]
    still, closed = settle_recommendations(pending, rows, now=now)
    assert still and not closed
    skip = skip_symbols(still, [], now=now)
    assert "AAAUSDT" in skip
    out = apply_live_feedback(
        rows,
        {"pending": pending, "closed": []},
        {"rsi": 1.0},
        "4h",
        now=now,
    )
    recs = {r["symbol"] for r in out["results"] if r.get("recommend")}
    assert "AAAUSDT" in recs
    assert out["results"][0]["symbol"] in recs
    ranked = sorted((r for r in out["results"] if r.get("recommend")), key=lambda r: float(r.get("win_rate") or 0), reverse=True)
    assert ranked[0]["symbol"] == "AAAUSDT"
    losses = [
        {"symbol": f"X{i}", "closed_at": (now - timedelta(hours=i)).isoformat(), "hit": False, "pnl_pct": -0.03}
        for i in range(3)
    ]
    assert recommend_count(losses, pending=[], now=now) == 3


def test_live_feedback_settles_and_rewrites_weights():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 21, 16, tzinfo=timezone.utc)
    rows = [
        {
            "symbol": "BTCUSDT",
            "decision": "涨",
            "score": 0.4,
            "price": 90,
            "regime": "单边",
            "indicators": [
                {"name": "rsi", "signal": 1, "strength": 0.9, "weight_optimized": 0.5},
                {"name": "macd", "signal": -1, "strength": 0.4, "weight_optimized": 0.5},
            ],
        },
        {
            "symbol": "ETHUSDT",
            "decision": "跌",
            "score": -0.3,
            "price": 2000,
            "regime": "单边",
            "indicators": [
                {"name": "rsi", "signal": -1, "strength": 0.5, "weight_optimized": 0.5},
                {"name": "macd", "signal": 1, "strength": 0.2, "weight_optimized": 0.5},
            ],
        },
    ]
    ledger = {
        "pending": [{
            "symbol": "BTCUSDT",
            "side": "涨",
            "entry": 100,
            "ts": (now - timedelta(hours=5)).isoformat(),
            "interval": "4h",
            "signals": {"rsi": 1, "macd": -1},
            "weights": {"rsi": 0.5, "macd": 0.5},
        }],
        "closed": [],
    }
    out = apply_live_feedback(rows, ledger, {"rsi": 0.5, "macd": 0.5}, "4h", now=now)
    assert out["closed_now"]
    assert out["closed_now"][0]["hit"] is False
    assert out["weights"]["rsi"] < out["weights"]["macd"]



def test_meme_liquidity_filter():
    good = {
        "liquidity_usd": 1_200_000,
        "unique_buyers_est": 12,
        "buys": 20,
        "holder_growth_est": 6,
    }
    bad = dict(good, liquidity_usd=5_000)
    assert _passes_meme_filter(good, 1_000_000, 8, 5)
    assert not _passes_meme_filter(bad, 1_000_000, 8, 5)


def test_parse_raise_text():
    assert parse_raise_text("Talos Extends Series B to $150M in Strategic Fundraise") == 150_000_000
    assert parse_raise_text("Yuga Labs raised $ 450 M in Seed round") == 450_000_000
    assert parse_raise_text("no money here") is None
    high, _ = score_airdrop(80_000_000, 4, "未发币（待核验）", 1_000_000_000)
    low, _ = score_airdrop(5_000_000, 0, "可能已有协议/代币", None)
    assert high > low
    assert high >= 70
    btc, _ = score_airdrop(80_000_000, 4, "未发币（待核验）", None, eco="bitcoin")
    other, _ = score_airdrop(80_000_000, 4, "未发币（待核验）", None, eco="other")
    assert btc > other
    assert classify_btc_eth("MegaETH", "L2", chains=["Ethereum"]) == "ethereum"
    assert classify_btc_eth("Babylon", "BTC staking", chains=["Bitcoin"]) == "bitcoin"
    assert classify_btc_eth("Monad", "L1", chains=["Monad"]) == "other"
    assert is_solana("Pump launch", "presale on solana")
    assert not is_solana("MegaETH", chains=["Ethereum"])
    mega = _decorate_airdrop({
        "name": "MegaETH", "chains": ["Ethereum"], "sector": "L2",
        "total_funding_usd": 450_000_000, "famous_count": 3,
        "token_status": "未发币（待核验）", "valuation": None,
    })
    monad = _decorate_airdrop({
        "name": "Monad", "chains": ["Monad"], "sector": "L1",
        "total_funding_usd": 50_000_000, "famous_count": 1,
        "token_status": "未发币（待核验）", "valuation": None,
    })
    assert _keep_airdrop_focus(mega)
    assert not _keep_airdrop_focus(monad)
    btc_ok = _decorate_airdrop({
        "name": "Babylon", "chains": ["Bitcoin"], "sector": "BTC staking",
        "total_funding_usd": 6_000_000, "famous_count": 2,
        "token_status": "未发币（待核验）", "valuation": None,
    })
    assert _funding_ok(btc_ok, 20_000_000, 5_000_000)
    eth_low = _decorate_airdrop({
        "name": "MegaETH", "chains": ["Ethereum"], "sector": "L2",
        "total_funding_usd": 6_000_000, "famous_count": 2,
        "token_status": "未发币（待核验）", "valuation": None,
    })
    assert not _funding_ok(eth_low, 20_000_000, 5_000_000)
    assert looks_like_solana_launch("Whitelist is open for our Solana TGE")
    assert not looks_like_solana_launch("Whitelist is open for our TGE on Ethereum")


def test_halving_cycle_bear_in_august_2026():
    from datetime import datetime, timezone

    from web3_radar.engine.cycle import assess_cycle, cycle_clock, pick_cycle_trade

    now = datetime(2026, 8, 26, tzinfo=timezone.utc)
    clock = cycle_clock(now)
    assert clock["phase"] == "熊市"
    assert clock["cash_bias"] == "持U"
    assert clock["top_signal"] is False
    out = assess_cycle(None, now)
    assert out["market"] == "熊市"
    pick = pick_cycle_trade(
        out,
        [
            {"symbol": "ETHUSDT", "decision": "跌", "entry": 100, "take_profit": 70, "stop_loss": 110, "win_rate": 0.6, "score": 2},
            {"symbol": "BTCUSDT", "decision": "涨", "entry": 100, "take_profit": 180, "stop_loss": 90, "win_rate": 0.9, "score": 9},
        ],
    )
    assert pick is not None
    assert pick["symbol"] == "ETHUSDT"
    assert pick["side"] == "做空"
    assert pick["hold_days"] >= 1
    from web3_radar.engine.cycle import attach_cycle_trade
    always = attach_cycle_trade(out, [])
    assert always["symbol"] == "BTCUSDT"
    assert always["side"] == "做空"


def test_meme_age_three_days():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    young = {"created_at": (now - timedelta(days=1)).isoformat()}
    old = {"created_at": (now - timedelta(days=4)).isoformat()}
    assert meme_age_ok(young)
    assert not meme_age_ok(old)


def test_ambassador_priority_and_deadline():
    score, priority = score_ambassador("Apply now paid ambassador stipend deadline March 20 form", None)
    assert score >= 70
    assert priority.startswith("高")
    assert "March" in extract_deadline("deadline: March 20 apply now")
