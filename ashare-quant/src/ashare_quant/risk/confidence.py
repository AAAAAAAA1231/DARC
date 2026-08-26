"""Bootstrap confidence intervals around signal-conditioned expected returns.

Outputs an interval, never a single 'predicted price'.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def residual_bootstrap_ci(
    fwd_returns: pd.Series,
    scores: pd.Series,
    current_score: float,
    *,
    levels: list[float],
    n_paths: int = 200,
    seed: int = 42,
    horizon: int = 5,
) -> dict[str, float]:
    """Map current score to a 5-day expected-return interval via residual bootstrap.

    Model: r = beta * score + eps. Interval reflects residual uncertainty, not
    a point forecast of the next close.
    """
    df = pd.DataFrame({"r": fwd_returns, "s": scores}).dropna()
    if len(df) < 30:
        # Uninformative prior
        return {f"p{int(lv * 100):02d}": 0.0 for lv in levels} | {"expected": 0.0, "paths": 0}

    beta = float(np.cov(df["r"], df["s"], ddof=1)[0, 1] / (np.var(df["s"]) + 1e-12))
    fitted = beta * df["s"]
    resid = (df["r"] - fitted).to_numpy()
    rng = np.random.default_rng(seed)
    mu = beta * float(current_score)
    # Path of horizon-day compounded residuals
    draws = rng.choice(resid, size=(n_paths, horizon), replace=True)
    path = np.prod(1.0 + mu + draws, axis=1) - 1.0
    out = {"expected": float(np.median(path)), "paths": int(n_paths), "beta": beta}
    for lv in levels:
        out[f"p{int(lv * 100):02d}"] = float(np.quantile(path, lv))
    return out
