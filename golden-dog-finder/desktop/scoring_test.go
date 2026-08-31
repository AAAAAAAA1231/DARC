package main

import "testing"

func snap(now int64, mods func(*TokenSnapshot)) TokenSnapshot {
	liq := 6000.0
	t := TokenSnapshot{
		Chain: "solana", Address: "Dog111111111111111111111111111111111111111",
		Symbol: "GOLD", Name: "Golden Dog", Dex: "pumpfun", Source: "test",
		CreatedAtMs: now - 25*60*1000, MarketCapUSD: 18000, FdvUSD: 18000,
		PriceUSD: 0.000018, LiquidityUSD: &liq, VolumeH1: 4200, VolumeM5: 900,
		ChangeM5: 6, ChangeH1: 42,
		TxM5:  TxWindow{Buys: 22, Sells: 9, Buyers: 18, Sellers: 7},
		TxM15: TxWindow{Buys: 40, Sells: 16, Buyers: 31, Sellers: 12},
		TxH1:  TxWindow{Buys: 58, Sells: 24, Buyers: 44, Sellers: 18},
		Pump:  &PumpState{Complete: false, RealSol: 28, ReplyCount: 12, AthMc: 22000},
	}
	if mods != nil {
		mods(&t)
	}
	return t
}

func TestIdealCandidateIsHighGrade(t *testing.T) {
	now := int64(1_788_167_331_000)
	card := scoreToken(snap(now, nil), now)
	if !card.Passed {
		t.Fatalf("expected pass, kills=%v", card.KillReasons)
	}
	if card.Grade != "S" && card.Grade != "A" && card.Grade != "B" {
		t.Fatalf("grade %s", card.Grade)
	}
	if card.Total < 65 {
		t.Fatalf("total %d", card.Total)
	}
	if card.XIf5m < 100 {
		t.Fatalf("x5m %v", card.XIf5m)
	}
	if card.Band != "激进百倍仓" {
		t.Fatalf("band %s", card.Band)
	}
}

func TestHighMcapCannot100x(t *testing.T) {
	now := int64(1_788_167_331_000)
	card := scoreToken(snap(now, func(t *TokenSnapshot) { t.MarketCapUSD, t.FdvUSD = 900000, 900000 }), now)
	if card.Passed || card.Grade != "X" {
		t.Fatalf("should kill high mcap")
	}
	ok := false
	for _, r := range card.KillReasons {
		if contains(r, "100x") {
			ok = true
		}
	}
	if !ok {
		t.Fatalf("kills %v", card.KillReasons)
	}
}

func TestTooFreshIsKilled(t *testing.T) {
	now := int64(1_788_167_331_000)
	card := scoreToken(snap(now, func(t *TokenSnapshot) { t.CreatedAtMs = now - 90000 }), now)
	if card.Passed {
		t.Fatal("expected kill")
	}
	ok := false
	for _, r := range card.KillReasons {
		if contains(r, "6 分钟") {
			ok = true
		}
	}
	if !ok {
		t.Fatalf("kills %v", card.KillReasons)
	}
}

func TestAlreadyExtendedIsKilled(t *testing.T) {
	now := int64(1_788_167_331_000)
	card := scoreToken(snap(now, func(t *TokenSnapshot) { t.MarketCapUSD, t.FdvUSD = 210000, 210000 }), now)
	if card.Passed {
		t.Fatal("expected kill")
	}
	ok := false
	for _, r := range card.KillReasons {
		if contains(r, "已涨约") || contains(r, "百亿") {
			ok = true
		}
	}
	if !ok {
		t.Fatalf("kills %v", card.KillReasons)
	}
}

func TestWashTradingKilled(t *testing.T) {
	now := int64(1_788_167_331_000)
	card := scoreToken(snap(now, func(t *TokenSnapshot) {
		t.VolumeH1 = 900000
		t.TxH1 = TxWindow{Buys: 400, Sells: 400, Buyers: 4, Sellers: 4}
		t.TxM15 = TxWindow{Buys: 80, Sells: 80, Buyers: 3, Sellers: 3}
		t.TxM5 = TxWindow{Buys: 20, Sells: 20, Buyers: 2, Sellers: 2}
	}), now)
	if card.Passed {
		t.Fatal("expected kill")
	}
	ok := false
	for _, r := range card.KillReasons {
		if contains(r, "骗量") {
			ok = true
		}
	}
	if !ok {
		t.Fatalf("kills %v", card.KillReasons)
	}
}

func TestMintAuthorityKilledOnOuterPool(t *testing.T) {
	now := int64(1_788_167_331_000)
	auth := "SomeWallet111"
	card := scoreToken(snap(now, func(t *TokenSnapshot) {
		t.Pump = nil
		t.Dex = "raydium"
		t.Security = &SecurityState{MintAuthority: &auth}
	}), now)
	if card.Passed {
		t.Fatal("expected kill")
	}
	ok := false
	for _, r := range card.KillReasons {
		if contains(r, "增发") {
			ok = true
		}
	}
	if !ok {
		t.Fatalf("kills %v", card.KillReasons)
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || (func() bool {
		for i := 0; i+len(sub) <= len(s); i++ {
			if s[i:i+len(sub)] == sub {
				return true
			}
		}
		return false
	})())
}
