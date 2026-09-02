from backend.core.enums import NarrativeTag
from backend.services.scoring import classify_narrative, combine_50x, score_market_structure


def test_unknown_factors_lower_confidence():
    parts = {
        "market_structure": score_market_structure(10_000_000, 50_000_000, 1_000_000, 10_000_000),
        "liquidity": (None, "UNKNOWN"),
        "volume": (None, "UNKNOWN"),
        "holders": (None, "UNKNOWN"),
        "smart_money": (None, "UNKNOWN"),
        "whale": (None, "UNKNOWN"),
        "fund_flow": (None, "UNKNOWN"),
        "narrative": (70.0, "ok"),
        "social": (None, "UNKNOWN"),
        "vc": (None, "UNKNOWN"),
        "team": (None, "UNKNOWN"),
        "tokenomics": (None, "UNKNOWN"),
        "ecosystem": (None, "UNKNOWN"),
        "onchain": (None, "UNKNOWN"),
        "market_cycle": (None, "UNKNOWN"),
        "historical_similarity": (None, "UNKNOWN"),
    }
    out = combine_50x(parts, 80.0, "SAFE")
    assert out["score_50x"] is not None
    assert "liquidity" in out["unknown_factors"]
    assert out["confidence"] < 0.5


def test_narrative_from_text():
    assert classify_narrative(["Artificial Intelligence"], None) == NarrativeTag.AI
