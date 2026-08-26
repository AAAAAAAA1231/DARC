import numpy as np
import pandas as pd

from ashare_quant.config import AppConfig
from ashare_quant.ensemble.weighting import rolling_weights
from ashare_quant.signals.methods import method_scores


def test_methods_in_unit_interval(tiny_cfg, tiny_market):
    bars, _ = tiny_market
    sym = bars["symbol"].iloc[0]
    g = bars[bars["symbol"] == sym]
    sc = method_scores(g, tiny_cfg)
    for col in ["trend", "momentum", "mean_reversion", "volatility", "relative_strength"]:
        assert sc[col].between(-1.0001, 1.0001).all()


def test_dynamic_weights_shift_with_recent_oos():
    cfg = AppConfig().ensemble
    n = 80
    idx = pd.date_range("2024-01-02", periods=n, freq="B")
    # trend wins recently, mean reversion dies
    trend = np.concatenate([np.full(40, -0.001), np.full(40, 0.004)])
    mr = np.concatenate([np.full(40, 0.003), np.full(40, -0.003)])
    others = np.zeros(n)
    rets = pd.DataFrame(
        {
            "trend": trend,
            "momentum": others,
            "mean_reversion": mr,
            "volatility": others,
            "relative_strength": others,
        },
        index=idx,
    )
    w = rolling_weights(rets, cfg)
    assert w.iloc[-1]["trend"] > w.iloc[-1]["mean_reversion"]
    assert w.iloc[25]["mean_reversion"] >= w.iloc[-1]["mean_reversion"] - 1e-9
    assert (w.sum(axis=1) - 1.0).abs().max() < 1e-6
    assert w.max().max() <= cfg.max_weight + 1e-6
    assert w.min().min() >= cfg.min_weight - 1e-6
