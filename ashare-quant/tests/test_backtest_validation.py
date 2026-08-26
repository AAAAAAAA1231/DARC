import pandas as pd

from ashare_quant.backtest.engine import run_backtest
from ashare_quant.backtest.walkforward import walk_forward
from ashare_quant.monte_carlo.simulator import run_monte_carlo
from ashare_quant.paper.simulator import run_paper
from ashare_quant.universe.filter import filter_universe


def test_backtest_respects_t_plus_one_and_costs(tiny_cfg, tiny_market):
    bars, meta = tiny_market
    asof = pd.to_datetime(bars["date"]).max()
    uni = filter_universe(bars, meta, asof, tiny_cfg)
    selected = uni.loc[uni["selected"], "symbol"].tolist()
    bt = run_backtest(bars, meta, tiny_cfg, symbols=selected)
    assert not bt.equity.empty
    assert bt.metrics["end_equity"] > 0
    if not bt.trades.empty:
        buys = bt.trades[bt.trades["side"] == "buy"]
        sells = bt.trades[bt.trades["side"] == "sell"]
        if not buys.empty:
            assert (buys["cost"] > 0).all()
            assert "earliest_exit" in buys.columns
        if not buys.empty and not sells.empty:
            # A sell of a name cannot happen on its buy date (T+1).
            merged = buys.merge(sells, on="symbol", suffixes=("_b", "_s"))
            if not merged.empty:
                assert not (merged["date_s"] == merged["date_b"]).any()


def test_walkforward_reports_oos_not_just_insample(tiny_cfg, tiny_market):
    bars, meta = tiny_market
    asof = pd.to_datetime(bars["date"]).max()
    uni = filter_universe(bars, meta, asof, tiny_cfg)
    selected = uni.loc[uni["selected"], "symbol"].head(8).tolist()
    wf = walk_forward(bars, meta, tiny_cfg, symbols=selected)
    assert wf.oos_metrics["days"] >= 10
    assert "max_drawdown" in wf.oos_metrics
    assert "sharpe" in wf.oos_metrics
    assert "robust_score" in wf.oos_metrics


def test_monte_carlo_distribution_and_calibration(tiny_cfg, tiny_market):
    bars, meta = tiny_market
    eq = pd.Series(1_000_000 * (1.001 ** pd.Series(range(80))).astype(float))
    eq.index = pd.date_range("2024-01-02", periods=80, freq="B")
    # Inject a drawdown so calibration has something to chew on
    eq.iloc[40:55] = eq.iloc[40] * 0.82
    mc = run_monte_carlo(eq, bars, meta, tiny_cfg, symbols=None, skip_execution=True)
    assert mc.summary["n_return_sims"] == tiny_cfg.monte_carlo.n_sims
    assert "sharpe_median" in mc.summary
    assert mc.adjusted_risk
    assert mc.notes


def test_paper_disclaimer(tiny_cfg, tiny_market):
    bars, meta = tiny_market
    paper = run_paper(bars, meta, tiny_cfg, days=30)
    assert "模拟盘" in paper.disclaimer or "不是实盘" in paper.disclaimer
    assert not paper.result.equity.empty
