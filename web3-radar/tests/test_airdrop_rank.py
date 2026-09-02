from __future__ import annotations

from web3_radar.engine.airdrop_rank import (
    AirdropCandidate,
    confirmed_score,
    institution_score,
    load_history,
    rank_candidates,
    score_candidate,
)


def test_tier1_vcs_score_higher_than_unknown():
    high, _ = institution_score(["Paradigm", "a16z", "Coinbase Ventures"])
    low, _ = institution_score(["Random Ventures LLC"])
    assert high >= 20
    assert high > low


def test_official_airdrop_beats_rumor():
    official, _ = confirmed_score("official")
    rumor, _ = confirmed_score("rumored")
    none, _ = confirmed_score("none")
    assert official > rumor > none


def test_history_haircuts_high_raise_underperformers():
    history = load_history()
    # zkSync-like: huge raise, historically weaker airdrop vs model
    weak = AirdropCandidate(
        name="TestZK",
        sector="l2",
        funding_usd=450_000_000,
        famous_investors=["a16z"],
        confirmed="official",
        difficulty="hard",
    )
    # Arbitrum-like: moderate raise, historically strong
    strong = AirdropCandidate(
        name="TestArb",
        sector="l2",
        funding_usd=120_000_000,
        famous_investors=["Lightspeed", "Pantera", "Polychain"],
        confirmed="official",
        difficulty="medium",
    )
    a = score_candidate(weak, history)
    b = score_candidate(strong, history)
    assert b["score"] >= a["score"] or b["parts"]["history_adj"] >= a["parts"]["history_adj"]
    assert a["expected_airdrop_usd"] > 0
    assert b["expected_airdrop_usd"] > 0


def test_rank_orders_by_score_and_skips_tge_as_main_rec():
    history = load_history()
    rows = rank_candidates(
        [
            AirdropCandidate(
                name="DoneCoin",
                sector="l2",
                funding_usd=80_000_000,
                famous_investors=["Paradigm"],
                confirmed="tge",
                difficulty="medium",
                token_live=True,
            ),
            AirdropCandidate(
                name="PointsChain",
                sector="l2",
                funding_usd=150_000_000,
                famous_investors=["Paradigm", "a16z"],
                confirmed="points",
                difficulty="medium",
            ),
            AirdropCandidate(
                name="NoSignal",
                sector="nft",
                funding_usd=5_000_000,
                famous_investors=[],
                confirmed="none",
                difficulty="expert",
            ),
        ],
        history,
    )
    assert rows[0]["name"] == "PointsChain"
    assert rows[0]["rank"] == 1
    assert rows[0]["recommend"] is True
    done = next(r for r in rows if r["name"] == "DoneCoin")
    assert done["recommend"] is False
    assert done["score"] < rows[0]["score"]
