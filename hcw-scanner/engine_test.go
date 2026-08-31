package main

import "testing"

func TestMatchQualityExact(t *testing.T) {
	if got := matchQuality("牛来", "牛来", "牛来"); got != 1 {
		t.Fatalf("exact = %v", got)
	}
}

func TestMatchQualityLooseSentence(t *testing.T) {
	got := matchQuality("人生没有假如过去但可以把握现在", "人生", "人生")
	if got >= 0.7 {
		t.Fatalf("long sentence should not be a strong match, got %v", got)
	}
}

func TestExtractQueriesPrefersShortCJK(t *testing.T) {
	hot := []HotItem{
		{Source: "微博", Title: "牛来票房破亿", Rank: 1},
		{Source: "微博", Title: "装腔启示录", Rank: 2},
		{Source: "微博", Title: "西藏泥石流已致16死", Rank: 3},
	}
	qs := extractQueries(hot)
	for _, q := range qs {
		if q == "西藏泥石流已致16死" || q == "泥石流" {
			t.Fatalf("disaster title leaked into queries: %v", qs)
		}
	}
	if !containsStr(qs, "牛来") && !containsStr(qs, "牛来票房破亿") {
		t.Fatalf("expected 牛来-related query, got %v", qs)
	}
	if !containsStr(qs, "装腔启示录") {
		t.Fatalf("expected short title 装腔启示录, got %v", qs)
	}
}

func TestScoreVetoHoneypot(t *testing.T) {
	c := Candidate{Name: "牛来", Symbol: "牛来", MarketCap: 80_000, Liquidity: 20_000, Volume24: 50_000, HotHits: []string{"牛来"}, MatchQuality: 1, ChineseName: true, Honeypot: true}
	scoreCandidate(&c)
	if len(c.VetoReasons) == 0 || c.Gate2 != "veto" {
		t.Fatalf("honeypot should veto: %+v", c)
	}
}

func TestScoreEarlyHotWindow(t *testing.T) {
	c := Candidate{Name: "牛来", Symbol: "牛来", MarketCap: 120_000, Liquidity: 40_000, Volume24: 90_000, HotHits: []string{"牛来"}, MatchQuality: 1, ChineseName: true, AgeHours: 8, Turnover: 0.7}
	scoreCandidate(&c)
	if c.Archetype != "A" || c.Gate3 != "early" || c.Score < 6 {
		t.Fatalf("expected A/early high-ish score, got %+v", c)
	}
}

func TestScoreLateWindow(t *testing.T) {
	c := Candidate{Name: "牛来", Symbol: "牛来", MarketCap: 110_000_000, Liquidity: 1_200_000, Volume24: 40_000_000, HotHits: []string{"牛来"}, MatchQuality: 1, ChineseName: true}
	scoreCandidate(&c)
	if c.Gate3 != "late" {
		t.Fatalf("110M should be late, got %s", c.Gate3)
	}
}

func TestConcentratedSupplyVeto(t *testing.T) {
	c := Candidate{Name: "COPPERINU", Symbol: "COPPERINU", MarketCap: 2_000_000, TopHolderPct: 0.40, MatchQuality: 0.5}
	scoreCandidate(&c)
	if c.Gate2 != "veto" {
		t.Fatalf("40%% holder should veto, got %s %v", c.Gate2, c.VetoReasons)
	}
}

func TestExtractQueriesIgnoresSentenceFragments(t *testing.T) {
	hot := []HotItem{
		{Source: "微博", Title: "她三个月暴瘦二十斤", Rank: 1},
		{Source: "微博", Title: "羽毛球反腐", Rank: 2},
	}
	qs := extractQueries(hot)
	if containsStr(qs, "个月暴瘦") || containsStr(qs, "羽毛球反腐") {
		t.Fatalf("noise leaked into queries: %v", qs)
	}
}

func containsStr(xs []string, want string) bool {
	for _, x := range xs {
		if x == want {
			return true
		}
	}
	return false
}
