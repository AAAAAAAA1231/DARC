package main

import (
	"testing"
	"time"
)

func baseToken(age time.Duration) TokenSnapshot {
	return TokenSnapshot{
		Name:         "Cash Cat",
		Symbol:       "CASHCAT",
		Address:      "0xabc",
		PairAddress:  "0xpair",
		DEX:          "uniswap",
		CreatedAt:    time.Now().Add(-age),
		MarketCap:    80000,
		LiquidityUSD: 28000,
		VolumeM5:     4000,
		VolumeH1:     22000,
		VolumeH6:     30000,
		BuysH1:       40,
		SellsH1:      12,
		HasTwitter:   true,
		HasTelegram:  true,
		Description:  "Robinhood cat meme",
	}
}

func TestGoldCandidateFollowsArticleOrder(t *testing.T) {
	c := Evaluate(baseToken(12*time.Minute), time.Now())
	if c.Verdict != VerdictGold {
		t.Fatalf("expected gold, got %s score=%d flags=%v checks=%+v", c.Verdict, c.Score, c.Flags, c.Checks)
	}
	if c.Stage < 5 {
		t.Fatalf("gold candidate should pass through on-chain stage, stage=%d", c.Stage)
	}
	if c.Checks[0].ID != "age" || c.Checks[1].ID != "narrative" || c.Checks[2].ID != "data" || c.Checks[3].ID != "onchain" {
		t.Fatalf("checklist order drifted: %+v", c.Checks)
	}
}

func TestOldTokenLosesAgeWindow(t *testing.T) {
	c := Evaluate(baseToken(48*time.Hour), time.Now())
	if c.Checks[0].Pass {
		t.Fatal("2-day token should fail age window")
	}
	if c.Verdict == VerdictGold {
		t.Fatal("stale token must not be gold")
	}
}

func TestPreferHealthyLiquidityLikeArticleExample(t *testing.T) {
	now := time.Now()
	weak := baseToken(20 * time.Minute)
	weak.Name, weak.Symbol, weak.Description = "Hype A", "HYA", "robinhood"
	weak.MarketCap = 1_000_000
	weak.LiquidityUSD = 100_000 // 10%，原文里的币 A

	healthy := baseToken(20 * time.Minute)
	healthy.Name, healthy.Symbol, healthy.Description = "Solid B", "SOB", "robinhood"
	healthy.MarketCap = 600_000
	healthy.LiquidityUSD = 300_000 // 50%，原文里的币 B

	a := Evaluate(weak, now)
	b := Evaluate(healthy, now)
	if b.Score <= a.Score {
		t.Fatalf("token B (healthier liquidity) should outrank A: A=%d B=%d", a.Score, b.Score)
	}
	if a.LiqMCRatio >= b.LiqMCRatio {
		t.Fatalf("ratio calc wrong: A=%f B=%f", a.LiqMCRatio, b.LiqMCRatio)
	}
}

func TestGoldRequiresConsecutivePipeline(t *testing.T) {
	tok := baseToken(15 * time.Minute)
	tok.Name, tok.Symbol, tok.Description = "NoStory", "ZZZ", ""
	tok.HasTwitter, tok.HasTelegram, tok.HasWebsite = false, false, false
	c := Evaluate(tok, time.Now())
	if c.Verdict == VerdictGold {
		t.Fatalf("missing narrative must not be gold even if data is strong, score=%d stage=%d", c.Score, c.Stage)
	}
	if c.Stage >= 3 {
		t.Fatalf("pipeline should stop before narrative pass, stage=%d", c.Stage)
	}
}

func TestAvoidNoSocialNoNarrative(t *testing.T) {
	tok := baseToken(8 * time.Minute)
	tok.Name, tok.Symbol, tok.Description = "Random", "XYZ123", ""
	tok.HasTwitter, tok.HasTelegram, tok.HasWebsite = false, false, false
	c := Evaluate(tok, time.Now())
	if c.Checks[1].Pass {
		t.Fatal("empty narrative should fail fast screen")
	}
}

func TestSellPressureAvoid(t *testing.T) {
	tok := baseToken(10 * time.Minute)
	tok.BuysH1, tok.SellsH1 = 3, 40
	c := Evaluate(tok, time.Now())
	if c.Verdict != VerdictAvoid {
		t.Fatalf("heavy sell should avoid, got %s", c.Verdict)
	}
}

func TestPipelineOrderIsFixed(t *testing.T) {
	if len(Pipeline) != 6 {
		t.Fatalf("expected 6 filter steps, got %d", len(Pipeline))
	}
	want := []string{"watch", "age", "narrative", "data", "onchain", "smart"}
	for i, id := range want {
		if Pipeline[i].ID != id || Pipeline[i].Index != i+1 {
			t.Fatalf("step %d want %s, got %+v", i, id, Pipeline[i])
		}
	}
}

func TestHolderShareSkipsLP(t *testing.T) {
	total := "1000"
	values := []string{"400", "100", "50"} // LP 40%, next two 15%
	top, lp := holderShare(values, total, true)
	if lp < 0.39 || lp > 0.41 {
		t.Fatalf("lp share %f", lp)
	}
	if top < 0.14 || top > 0.16 {
		t.Fatalf("top10 excluding lp %f", top)
	}
}
