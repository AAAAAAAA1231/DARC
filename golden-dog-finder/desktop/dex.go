package main

import (
	"strings"
)

func fetchDiscoveryLists() []map[string]any {
	urls := []string{
		"https://api.dexscreener.com/token-profiles/latest/v1",
		"https://api.dexscreener.com/token-boosts/latest/v1",
		"https://api.dexscreener.com/token-boosts/top/v1",
		"https://api.dexscreener.com/community-takeovers/latest/v1",
	}
	fns := make([]func() any, len(urls))
	for i, u := range urls {
		u := u
		fns[i] = func() any {
			v, _ := getJSON(u, nil, nil, false)
			return v
		}
	}
	var items []map[string]any
	for _, payload := range gather(4, fns) {
		for _, x := range asSlice(payload) {
			if m := asMap(x); m != nil {
				items = append(items, m)
			}
		}
	}
	return items
}

func fetchPairsForTokens(chain string, addresses []string) []TokenSnapshot {
	var uniq []string
	seen := map[string]bool{}
	for _, a := range addresses {
		k := strings.ToLower(a)
		if seen[k] {
			continue
		}
		seen[k] = true
		uniq = append(uniq, a)
	}
	var snaps []TokenSnapshot
	for i := 0; i < len(uniq); i += 25 {
		end := i + 25
		if end > len(uniq) {
			end = len(uniq)
		}
		chunk := uniq[i:end]
		payload, _ := getJSON("https://api.dexscreener.com/tokens/v1/"+chain+"/"+strings.Join(chunk, ","), nil, nil, false)
		var rows []any
		if s := asSlice(payload); s != nil {
			rows = s
		} else if m := asMap(payload); m != nil {
			rows = asSlice(m["pairs"])
		}
		if len(rows) == 0 {
			for _, addr := range chunk {
				one, _ := getJSON("https://api.dexscreener.com/latest/dex/tokens/"+addr, nil, nil, false)
				pairs := asSlice(asMap(one)["pairs"])
				if best := bestPair(pairs, addr); best != nil {
					if snap := pairToSnapshot(best, "dexscreener"); snap != nil {
						snaps = append(snaps, *snap)
					}
				}
			}
			continue
		}
		grouped := map[string][]any{}
		for _, pair := range rows {
			b := strings.ToLower(str(nested(asMap(pair), "baseToken", "address")))
			grouped[b] = append(grouped[b], pair)
		}
		for _, addr := range chunk {
			pairs := grouped[strings.ToLower(addr)]
			anyPairs := pairs
			if len(anyPairs) == 0 {
				anyPairs = rows
			}
			if best := bestPair(anyPairs, addr); best != nil {
				if snap := pairToSnapshot(best, "dexscreener"); snap != nil {
					snaps = append(snaps, *snap)
				}
			}
		}
	}
	return snaps
}

func pairToSnapshot(pair map[string]any, source string) *TokenSnapshot {
	if pair == nil {
		return nil
	}
	base := asMap(pair["baseToken"])
	addr := str(base["address"])
	if addr == "" {
		return nil
	}
	sym := strings.ToLower(str(base["symbol"]))
	if sym == "sol" || sym == "wsol" || sym == "weth" || sym == "eth" || sym == "wbnb" || sym == "usdc" || sym == "usdt" {
		return nil
	}
	liqMap := asMap(pair["liquidity"])
	vol := asMap(pair["volume"])
	chg := asMap(pair["priceChange"])
	tx := asMap(pair["txns"])
	info := asMap(pair["info"])
	var socials []Social
	for _, s := range asSlice(info["socials"]) {
		sm := asMap(s)
		if u := str(sm["url"]); u != "" {
			socials = append(socials, Social{Type: firstNonEmpty(str(sm["type"]), "social"), URL: u})
		}
	}
	var websites []string
	for _, w := range asSlice(info["websites"]) {
		wm := asMap(w)
		if u := str(wm["url"]); u != "" {
			websites = append(websites, u)
		}
	}
	if socials == nil {
		socials = []Social{}
	}
	if websites == nil {
		websites = []string{}
	}
	boosts := asMap(pair["boosts"])
	mc := num(pair["marketCap"])
	if mc == 0 {
		mc = num(pair["fdv"])
	}
	var liq *float64
	if liqMap["usd"] != nil {
		v := num(liqMap["usd"])
		liq = &v
	}
	img := str(info["imageUrl"])
	u := str(pair["url"])
	return &TokenSnapshot{
		Chain: str(pair["chainId"]), Address: addr, Symbol: clip(str(base["symbol"]), 16),
		Name: clip(str(base["name"]), 48), Dex: firstNonEmpty(str(pair["dexId"]), "unknown"), Source: source,
		PairAddress: ptrStr(str(pair["pairAddress"])), PriceUSD: num(pair["priceUsd"]),
		MarketCapUSD: mc, FdvUSD: num(pair["fdv"]), LiquidityUSD: liq,
		CreatedAtMs: int64(num(pair["pairCreatedAt"])),
		VolumeM5: num(vol["m5"]), VolumeH1: num(vol["h1"]), VolumeH6: num(vol["h6"]), VolumeH24: num(vol["h24"]),
		ChangeM5: num(chg["m5"]), ChangeH1: num(chg["h1"]), ChangeH6: num(chg["h6"]), ChangeH24: num(chg["h24"]),
		TxM5: TxWindow{Buys: int(num(asMap(tx["m5"])["buys"])), Sells: int(num(asMap(tx["m5"])["sells"]))},
		TxH1: TxWindow{Buys: int(num(asMap(tx["h1"])["buys"])), Sells: int(num(asMap(tx["h1"])["sells"]))},
		Image: ptrStr(img), Websites: websites, Socials: socials,
		BoostAmount: int(num(boosts["active"])), HasProfile: len(info) > 0, URL: ptrStr(u),
	}
}

func bestPair(pairs []any, token string) map[string]any {
	tokenL := strings.ToLower(token)
	var best map[string]any
	bestScore := -1.0
	for _, p := range pairs {
		m := asMap(p)
		base := strings.ToLower(str(nested(m, "baseToken", "address")))
		if base != tokenL {
			continue
		}
		liq := num(nested(m, "liquidity", "usd"))
		vol := num(nested(m, "volume", "h1"))
		if vol == 0 {
			vol = num(nested(m, "volume", "h24"))
		}
		if liq+vol > bestScore {
			bestScore = liq + vol
			best = m
		}
	}
	if best != nil {
		return best
	}
	if len(pairs) > 0 {
		return asMap(pairs[0])
	}
	return nil
}

func overlayDex(dst *TokenSnapshot, src TokenSnapshot) {
	if src.PriceUSD != 0 {
		dst.PriceUSD = src.PriceUSD
	}
	if src.MarketCapUSD != 0 {
		dst.MarketCapUSD = src.MarketCapUSD
		if src.FdvUSD != 0 {
			dst.FdvUSD = src.FdvUSD
		} else {
			dst.FdvUSD = src.MarketCapUSD
		}
	}
	if src.LiquidityUSD != nil {
		dst.LiquidityUSD = src.LiquidityUSD
	}
	if src.CreatedAtMs != 0 && dst.CreatedAtMs == 0 {
		dst.CreatedAtMs = src.CreatedAtMs
	}
	if src.VolumeH1 != 0 {
		dst.VolumeM5, dst.VolumeH1, dst.VolumeH6, dst.VolumeH24 = src.VolumeM5, src.VolumeH1, src.VolumeH6, src.VolumeH24
	}
	if src.TxH1.Buys != 0 || src.TxM5.Buys != 0 {
		if src.TxM5.Buyers == 0 {
			src.TxM5.Buyers = dst.TxM5.Buyers
			if src.TxM5.Sellers == 0 {
				src.TxM5.Sellers = dst.TxM5.Sellers
			}
		}
		if src.TxH1.Buyers == 0 {
			src.TxH1.Buyers = dst.TxH1.Buyers
			if src.TxH1.Sellers == 0 {
				src.TxH1.Sellers = dst.TxH1.Sellers
			}
		}
		dst.TxM5, dst.TxH1 = src.TxM5, src.TxH1
		if src.TxM15.Buys != 0 {
			dst.TxM15 = src.TxM15
		}
	}
	if src.ChangeH1 != 0 || src.ChangeM5 != 0 {
		dst.ChangeM5, dst.ChangeH1, dst.ChangeH6, dst.ChangeH24 = src.ChangeM5, src.ChangeH1, src.ChangeH6, src.ChangeH24
	}
	if src.Image != nil && dst.Image == nil {
		dst.Image = src.Image
	}
	if len(src.Socials) > 0 && len(dst.Socials) == 0 {
		dst.Socials = src.Socials
	}
	if len(src.Websites) > 0 && len(dst.Websites) == 0 {
		dst.Websites = src.Websites
	}
	if src.BoostAmount != 0 {
		dst.BoostAmount = src.BoostAmount
		dst.HasProfile = true
	}
	if src.URL != nil && dst.URL == nil {
		dst.URL = src.URL
	}
	if src.PairAddress != nil {
		dst.PairAddress = src.PairAddress
		if src.Dex != "" {
			dst.Dex = src.Dex
		}
	}
}

func enrichSecurity(token TokenSnapshot) *SecurityState {
	if token.Chain != "solana" {
		return nil
	}
	data, err := getJSON("https://api.rugcheck.xyz/v1/tokens/"+token.Address+"/report", nil, nil, false)
	root := asMap(data)
	if err != nil || root == nil || root["error"] != nil {
		sum, _ := getJSON("https://api.rugcheck.xyz/v1/tokens/"+token.Address+"/report/summary", nil, nil, false)
		root = asMap(sum)
		if root == nil {
			return nil
		}
	}
	var risks []string
	for _, r := range asSlice(root["risks"]) {
		if m := asMap(r); m != nil {
			name := firstNonEmpty(str(m["name"]), str(m["description"]))
			if name != "" {
				risks = append(risks, name)
			}
		} else if s := str(r); s != "" {
			risks = append(risks, s)
		}
	}
	if len(risks) > 8 {
		risks = risks[:8]
	}
	holders := asSlice(root["topHolders"])
	var curve *string
	if token.Pump != nil {
		curve = token.Pump.BondingCurve
	}
	sec := &SecurityState{Rugged: truthy(root["rugged"]), Risks: risks}
	if v, ok := root["score"].(float64); ok {
		n := int(v)
		sec.Score = &n
	}
	if v, ok := root["score_normalised"].(float64); ok {
		n := int(v)
		sec.ScoreNormalised = &n
	}
	if root["mintAuthority"] != nil {
		s := str(root["mintAuthority"])
		if s != "" && s != "<nil>" {
			sec.MintAuthority = &s
		}
	}
	if root["freezeAuthority"] != nil {
		s := str(root["freezeAuthority"])
		if s != "" && s != "<nil>" {
			sec.FreezeAuthority = &s
		}
	}
	if p := lpLock(root); p != nil {
		sec.LpLockedPct = p
	}
	if v, ok := root["totalHolders"].(float64); ok {
		n := int(v)
		sec.Holders = &n
	}
	if p := topNonCurve(holders, curve); p != nil {
		sec.TopHolderPct = p
	}
	if v, ok := root["graphInsidersDetected"].(float64); ok {
		n := int(v)
		sec.InsiderNetworks = &n
	}
	return sec
}

func topNonCurve(holders []any, pumpCurve *string) *float64 {
	curve := ""
	if pumpCurve != nil {
		curve = strings.ToLower(*pumpCurve)
	}
	for _, h := range holders {
		m := asMap(h)
		owner := strings.ToLower(firstNonEmpty(str(m["owner"]), str(m["address"])))
		if curve != "" && owner == curve {
			continue
		}
		if m["pct"] != nil {
			v := num(m["pct"])
			return &v
		}
	}
	if len(holders) > 0 {
		v := num(asMap(holders[0])["pct"])
		return &v
	}
	return nil
}

func lpLock(data map[string]any) *float64 {
	var pcts []float64
	for _, m := range asSlice(data["markets"]) {
		mm := asMap(m)
		if mm["lpLockedPct"] != nil {
			pcts = append(pcts, num(mm["lpLockedPct"]))
		}
		if mm["lp_locked_pct"] != nil {
			pcts = append(pcts, num(mm["lp_locked_pct"]))
		}
	}
	if len(pcts) > 0 {
		mx := pcts[0]
		for _, p := range pcts {
			if p > mx {
				mx = p
			}
		}
		return &mx
	}
	if data["lpLockedPct"] != nil {
		v := num(data["lpLockedPct"])
		return &v
	}
	return nil
}
