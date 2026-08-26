import pandas as pd

from ashare_quant.ideas import generate_ideas
from ashare_quant.risk.atr_stops import atr_bands
from ashare_quant.risk.confidence import residual_bootstrap_ci
from ashare_quant.risk.position import BookState, size_long
from ashare_quant.config import Board


def test_stops_scale_with_atr_not_fixed_points():
    n = 80
    close = pd.Series([10.0] * n, dtype=float)
    # quiet then violent
    high_q = close + 0.05
    low_q = close - 0.05
    from ashare_quant.config import RiskConfig

    cfg = RiskConfig()
    quiet = atr_bands(high_q, low_q, close, cfg, entry=10.0)
    high_v = close + 0.80
    low_v = close - 0.80
    violent = atr_bands(high_v, low_v, close, cfg, entry=10.0)
    assert violent["atr"] > quiet["atr"]
    assert (violent["take_profit"] - 10.0) > (quiet["take_profit"] - 10.0)
    assert (10.0 - violent["stop_loss"]) > (10.0 - quiet["stop_loss"])


def test_confidence_interval_not_point_forecast():
    rng = pd.Series(range(80), dtype=float)
    fwd = (rng % 7 - 3) / 200.0
    scores = (rng % 5 - 2) / 5.0
    ci = residual_bootstrap_ci(fwd, scores, 0.4, levels=[0.1, 0.5, 0.9], n_paths=80, seed=1)
    assert "p10" in ci and "p50" in ci and "p90" in ci
    assert ci["p10"] <= ci["p50"] <= ci["p90"]


def test_position_caps_single_and_gross(tiny_cfg):
    book = BookState(nav=1_000_000, gross_exposure=800_000, names_held=2, board_exposure={"sse_main": 400_000}, weight_by_symbol={})
    tiny_cfg.risk.max_gross_exposure = 0.80
    tiny_cfg.risk.max_single_weight = 0.08
    r = size_long(
        cfg=tiny_cfg,
        nav=1_000_000,
        price=10.0,
        stop_distance_pct=0.05,
        adv_shares=1_000_000,
        board=Board.SSE_MAIN,
        book=book,
        already_held=False,
    )
    assert r.action.value == "no_trade"
    assert "gross_cap" in r.reasons

    book2 = BookState(nav=1_000_000, gross_exposure=0, names_held=0, board_exposure={}, weight_by_symbol={})
    r2 = size_long(
        cfg=tiny_cfg,
        nav=1_000_000,
        price=10.0,
        stop_distance_pct=0.04,
        adv_shares=1_000_000,
        board=Board.SSE_MAIN,
        book=book2,
        already_held=False,
    )
    assert r2.shares % 100 == 0
    assert r2.notional / 1_000_000 <= tiny_cfg.risk.max_single_weight + 1e-9


def test_ideas_follow_t_plus_one_and_ci(tiny_cfg, tiny_market, asof):
    bars, meta = tiny_market
    ideas = generate_ideas(bars, meta, tiny_cfg, asof)
    assert not ideas.empty
    row = ideas.iloc[0]
    assert row["execute_date"] > row["signal_date"]
    assert row["earliest_exit_date"] > row["execute_date"]
    assert "ci_p10" in ideas.columns and "ci_p90" in ideas.columns
    assert "stop_loss" in ideas.columns and "take_profit" in ideas.columns
    buys = ideas[ideas["action"] == "buy"]
    if not buys.empty:
        assert (buys["shares"] % 100 == 0).all()
