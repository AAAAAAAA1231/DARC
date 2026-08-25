import numpy as np

from a_share_trading.indicators import ema, rsi, sma


def test_sma_known_values():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(x, 3)
    assert np.isnan(out[1])
    assert out[2] == 2.0
    assert out[-1] == 4.0


def test_ema_reacts_to_last_print():
    x = np.array([10.0, 10.0, 10.0, 10.0, 20.0], dtype=float)
    out = ema(x, 3)
    assert out[-1] > out[-2]


def test_rsi_constant_up():
    x = np.linspace(10, 20, 40)
    value = rsi(x, 14)[-1]
    assert value > 70
