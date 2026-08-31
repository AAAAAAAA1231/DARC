from backend.models import PumpState, TokenSnapshot, TxWindow
from backend.scoring import score_token


def _snap(**kwargs) -> TokenSnapshot:
    now = 1_788_167_331_000
    base = dict(
        chain="solana",
        address="Dog111111111111111111111111111111111111111",
        symbol="GOLD",
        name="Golden Dog",
        dex="pumpfun",
        source="test",
        created_at_ms=now - 25 * 60 * 1000,
        market_cap_usd=18_000,
        fdv_usd=18_000,
        price_usd=0.000018,
        liquidity_usd=6_000,
        volume_h1=4_200,
        volume_m5=900,
        change_m5=6.0,
        change_h1=42.0,
        tx_m5=TxWindow(buys=22, sells=9, buyers=18, sellers=7),
        tx_m15=TxWindow(buys=40, sells=16, buyers=31, sellers=12),
        tx_h1=TxWindow(buys=58, sells=24, buyers=44, sellers=18),
        pump=PumpState(complete=False, real_sol=28.0, reply_count=12, ath_mc=22_000),
    )
    base.update(kwargs)
    return TokenSnapshot(**base)


def test_ideal_candidate_is_high_grade():
    card = score_token(_snap(), now_ms=1_788_167_331_000)
    assert card.passed
    assert card.grade in {"S", "A", "B"}
    assert card.total >= 65
    assert card.x_if_5m >= 100
    assert card.band == "激进百倍仓"


def test_high_mcap_cannot_100x_inside_meme_band():
    card = score_token(_snap(market_cap_usd=900_000, fdv_usd=900_000), now_ms=1_788_167_331_000)
    assert not card.passed
    assert card.grade == "X"
    assert any("100x" in r for r in card.kill_reasons)


def test_too_fresh_is_killed():
    now = 1_788_167_331_000
    card = score_token(_snap(created_at_ms=now - 90_000), now_ms=now)
    assert not card.passed
    assert any("6 分钟" in r for r in card.kill_reasons)


def test_already_extended_is_killed():
    card = score_token(_snap(market_cap_usd=210_000, fdv_usd=210_000), now_ms=1_788_167_331_000)
    # 210k is inside MAX_MC but 42x from $5k launch → kill
    assert not card.passed
    assert any("已涨约" in r or "百亿" in r for r in card.kill_reasons)


def test_wash_trading_killed():
    card = score_token(
        _snap(
            volume_h1=900_000,
            tx_h1=TxWindow(buys=400, sells=400, buyers=4, sellers=4),
            tx_m15=TxWindow(buys=80, sells=80, buyers=3, sellers=3),
            tx_m5=TxWindow(buys=20, sells=20, buyers=2, sellers=2),
        ),
        now_ms=1_788_167_331_000,
    )
    assert not card.passed
    assert any("骗量" in r for r in card.kill_reasons)


def test_mint_authority_killed_on_outer_pool():
    from backend.models import SecurityState

    card = score_token(
        _snap(
            pump=None,
            dex="raydium",
            security=SecurityState(mint_authority="SomeWallet111", freeze_authority=None),
        ),
        now_ms=1_788_167_331_000,
    )
    assert not card.passed
    assert any("增发" in r for r in card.kill_reasons)
