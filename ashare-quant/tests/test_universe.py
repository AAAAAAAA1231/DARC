from datetime import date

from ashare_quant.config import Board
from ashare_quant.universe.boards import infer_board, is_st_name, is_supported_ashare, normalize_symbol
from ashare_quant.universe.filter import filter_universe


def test_board_mapping():
    assert infer_board("600000") is Board.SSE_MAIN
    assert infer_board("000001.SZ") is Board.SZSE_MAIN
    assert infer_board("300001") is Board.CHINEXT
    assert infer_board("688001") is Board.STAR
    assert infer_board("301002") is Board.CHINEXT
    assert not is_supported_ashare("430001")
    assert normalize_symbol("sz000001") == "000001"
    assert is_st_name("ST华海电子")
    assert is_st_name("*ST退市测试")


def test_universe_drops_st_new_illiquid_suspended(tiny_cfg, tiny_market, asof):
    bars, meta = tiny_market
    uni = filter_universe(bars, meta, asof, tiny_cfg)
    assert not uni.empty
    selected = uni[uni["selected"]]
    assert len(selected) > 0
    assert len(selected) <= tiny_cfg.universe.max_names
    assert not selected["is_st"].any()
    assert (selected["listing_days"] >= tiny_cfg.universe.min_listing_days).all()
    assert (selected["avg_amount"] >= tiny_cfg.universe.min_avg_amount).all()
    rejected = uni[~uni["eligible"]]
    assert len(rejected) >= 1
    reasons = ",".join(rejected["reject_reasons"].astype(str))
    assert any(k in reasons for k in ("st", "listing_days", "liquidity", "suspension", "market_cap"))
