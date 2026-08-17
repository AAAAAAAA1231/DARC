from web3_radar.engine.meme_score import enrich_and_score
from web3_radar.copytrade import _exit_reason, _pnl


def test_meme_score_rejects_thin_and_late_pump():
    thin = {
        "liquidity_usd": 5000,
        "buys": 20,
        "sells": 2,
        "unique_buyers_est": 20,
        "holder_growth_est": 10,
        "volume_h1": 8000,
        "price_change_h1": 12,
        "fdv": 100000,
        "price_usd": 0.001,
    }
    late = dict(thin, liquidity_usd=40000, price_change_h1=180, buys=30)
    good = {
        "liquidity_usd": 45000,
        "buys": 40,
        "sells": 12,
        "unique_buyers_est": 28,
        "holder_growth_est": 12,
        "volume_h1": 22000,
        "price_change_h1": 28,
        "fdv": 400000,
        "price_usd": 0.002,
        "source": "gmgn+geckoterminal",
        "created_at": None,
    }
    assert enrich_and_score(thin)["grade"] == "避开"
    assert enrich_and_score(late)["grade"] == "避开"
    assert enrich_and_score(good)["followable"] is True


def test_copy_sl_tp():
    pos = {"entry": 1.0, "qty": 30, "sl": 0.82, "tp": 1.4}
    assert _exit_reason(pos, 0.80, {}) == "止损"
    assert _exit_reason(pos, 1.41, {}) == "止盈"
    assert _exit_reason(pos, 1.1, {}) is None
    assert _pnl(pos, 1.1) == 3.0
