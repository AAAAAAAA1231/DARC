package main

import (
	"net/url"
	"strings"
	"time"
)

func parseTime(s string) (time.Time, error) {
	return time.Parse(time.RFC3339, s)
}

func fetchPump() []TokenSnapshot {
	sorts := []string{"created_timestamp", "last_trade_timestamp", "reply_count"}
	out := map[string]TokenSnapshot{}
	for _, sort := range sorts {
		payload, err := getJSON("https://frontend-api-v3.pump.fun/coins", url.Values{
			"offset":      {"0"},
			"limit":       {"50"},
			"sort":        {sort},
			"order":       {"DESC"},
			"includeNsfw": {"false"},
		}, nil, true)
		if err != nil {
			continue
		}
		for _, item := range asSlice(payload) {
			coin := asMap(item)
			snap := coinToSnapshot(coin)
			if snap == nil {
				continue
			}
			fixAth(coin, snap)
			if prev, ok := out[snap.Key()]; ok && prev.Pump != nil && snap.Pump != nil {
				if prev.Pump.ReplyCount > snap.Pump.ReplyCount {
					snap.Pump.ReplyCount = prev.Pump.ReplyCount
				}
				if prev.VolumeH1 > snap.VolumeH1 {
					snap.VolumeH1 = prev.VolumeH1
				}
			}
			out[snap.Key()] = *snap
		}
	}
	res := make([]TokenSnapshot, 0, len(out))
	for _, v := range out {
		res = append(res, v)
	}
	return res
}

func coinToSnapshot(coin map[string]any) *TokenSnapshot {
	if coin == nil {
		return nil
	}
	mint := str(coin["mint"])
	if mint == "" || truthy(coin["is_banned"]) {
		return nil
	}
	mc := num(coin["market_cap_usd"])
	if mc == 0 {
		mc = num(coin["usd_market_cap"])
	}
	created := int64(num(coin["created_timestamp"]))
	realSol := num(coin["real_sol_reserves"])
	if realSol == 0 {
		realSol = num(coin["real_quote_reserves"])
	}
	realSol /= 1e9
	image := str(coin["image_uri"])
	if image == "" {
		image = str(coin["profile_image"])
	}
	var socials []Social
	if t := str(coin["twitter"]); t != "" {
		socials = append(socials, Social{Type: "twitter", URL: t})
	}
	if t := str(coin["telegram"]); t != "" {
		socials = append(socials, Social{Type: "telegram", URL: t})
	}
	var websites []string
	if w := str(coin["website"]); w != "" {
		websites = []string{w}
	}
	if websites == nil {
		websites = []string{}
	}
	if socials == nil {
		socials = []Social{}
	}
	supply := num(coin["total_supply"])
	if supply == 0 {
		supply = 1e15
	}
	decimals := int(num(coin["base_decimals"]))
	if decimals == 0 {
		decimals = 6
	}
	price := num(coin["price_usd"])
	den := supply / pow10(decimals)
	if price == 0 && mc > 0 && den > 0 {
		price = mc / den
	}
	complete := truthy(coin["complete"])
	dex := "pumpfun"
	if complete {
		dex = "pumpswap"
	}
	pair := str(coin["bonding_curve"])
	if pair == "" {
		pair = str(coin["pool_address"])
	}
	createdMs := created
	if created > 0 && created <= 10_000_000_000 {
		createdMs = created * 1000
	}
	var liq *float64
	if !complete && realSol > 0 {
		v := realSol * 103
		liq = &v
	}
	u := "https://pump.fun/coin/" + mint
	curve := str(coin["bonding_curve"])
	creator := str(coin["creator"])
	return &TokenSnapshot{
		Chain: "solana", Address: mint, Symbol: clip(str(coin["symbol"]), 16),
		Name: clip(str(coin["name"]), 48), Dex: dex, Source: "pump.fun",
		PairAddress: ptrStr(pair), PriceUSD: price, MarketCapUSD: mc, FdvUSD: mc,
		LiquidityUSD: liq, CreatedAtMs: createdMs, Image: ptrStr(image),
		Websites: websites, Socials: socials, URL: &u,
		Pump: &PumpState{
			Complete: complete, RealSol: realSol, ReplyCount: int(num(coin["reply_count"])),
			Livestream: truthy(coin["is_currently_live"]), NSFW: truthy(coin["nsfw"]),
			BondingCurve: ptrStr(curve), Creator: ptrStr(creator),
		},
	}
}

func fixAth(coin map[string]any, snap *TokenSnapshot) {
	if snap == nil || snap.Pump == nil {
		return
	}
	ath := num(coin["ath_market_cap"])
	mcSol := num(coin["market_cap"])
	mcUSD := snap.MarketCapUSD
	if ath > 0 && mcSol > 0 && mcUSD > 0 {
		snap.Pump.AthMc = ath * (mcUSD / mcSol)
	} else if ath > 1000 {
		snap.Pump.AthMc = ath
	}
}

func pow10(n int) float64 {
	p := 1.0
	for i := 0; i < n; i++ {
		p *= 10
	}
	return p
}

func fetchGecko() []TokenSnapshot {
	type job struct{ url, source string }
	var jobs []job
	for _, net := range []string{"solana", "base", "bsc"} {
		jobs = append(jobs, job{"https://api.geckoterminal.com/api/v2/networks/" + net + "/new_pools", "gt-new"})
		jobs = append(jobs, job{"https://api.geckoterminal.com/api/v2/networks/" + net + "/trending_pools", "gt-trend"})
	}
	jobs = append(jobs, job{"https://api.geckoterminal.com/api/v2/networks/new_pools", "gt-global-new"})
	fns := make([]func() any, len(jobs))
	for i, j := range jobs {
		j := j
		fns[i] = func() any {
			v, _ := getJSON(j.url, url.Values{"include": {"base_token,quote_token,dex"}, "page": {"1"}}, map[string]string{"Accept": "application/json;version=20230302"}, false)
			return v
		}
	}
	payloads := gather(4, fns)
	out := map[string]TokenSnapshot{}
	quoteOK := map[string]bool{"sol": true, "wsol": true, "eth": true, "weth": true, "bnb": true, "wbnb": true, "usdc": true, "usdt": true, "usd1": true}
	for i, payload := range payloads {
		root := asMap(payload)
		if root == nil {
			continue
		}
		included := map[string]map[string]any{}
		for _, item := range asSlice(root["included"]) {
			im := asMap(item)
			id := str(im["id"])
			if id != "" {
				included[id] = asMap(im["attributes"])
			}
		}
		for _, pool := range asSlice(root["data"]) {
			snap := poolToSnapshot(asMap(pool), included, jobs[i].source, quoteOK)
			if snap == nil {
				continue
			}
			if prev, ok := out[snap.Key()]; ok {
				snap = mergeSnap(prev, *snap)
			}
			out[snap.Key()] = *snap
		}
	}
	res := make([]TokenSnapshot, 0, len(out))
	for _, v := range out {
		res = append(res, v)
	}
	return res
}

func poolToSnapshot(pool map[string]any, included map[string]map[string]any, source string, quoteOK map[string]bool) *TokenSnapshot {
	attrs := asMap(pool["attributes"])
	rel := asMap(pool["relationships"])
	baseID := str(nested(rel, "base_token", "data", "id"))
	quoteID := str(nested(rel, "quote_token", "data", "id"))
	dexID := str(nested(rel, "dex", "data", "id"))
	network := strings.SplitN(str(pool["id"])+"_", "_", 2)[0]
	if network == "" {
		network = "solana"
	}
	base := included[baseID]
	quote := included[quoteID]
	if base == nil {
		base = map[string]any{}
	}
	if quote == nil {
		quote = map[string]any{}
	}
	name := str(attrs["name"])
	symbol := strings.TrimSpace(str(base["symbol"]))
	if symbol == "" && strings.Contains(name, "/") {
		symbol = strings.TrimSpace(strings.Split(name, "/")[0])
	}
	quoteSym := strings.TrimSpace(str(quote["symbol"]))
	if quoteSym == "" && strings.Contains(name, "/") {
		parts := strings.Split(name, "/")
		quoteSym = strings.TrimSpace(parts[len(parts)-1])
	}
	low := strings.ToLower(symbol)
	if low == "sol" || low == "wsol" || low == "weth" || low == "eth" || low == "wbnb" || low == "bnb" || low == "usdc" || low == "usdt" {
		return nil
	}
	if quoteSym != "" && !quoteOK[strings.ToLower(quoteSym)] {
		return nil
	}
	fdv := num(attrs["fdv_usd"])
	mc := num(attrs["market_cap_usd"])
	if mc == 0 {
		mc = fdv
	}
	var liq *float64
	if attrs["reserve_in_usd"] != nil {
		v := num(attrs["reserve_in_usd"])
		if v < 0 {
			return nil
		}
		liq = &v
	}
	vol := asMap(attrs["volume_usd"])
	chg := asMap(attrs["price_change_percentage"])
	tx := asMap(attrs["transactions"])
	addr := tokenAddr(baseID)
	if addr == "" {
		addr = str(base["address"])
	}
	if addr == "" {
		return nil
	}
	if dexID == "" {
		dexID = "unknown"
	}
	pair := str(attrs["address"])
	var u *string
	if pair != "" {
		s := "https://www.geckoterminal.com/" + network + "/pools/" + pair
		u = &s
	}
	img := str(base["image_url"])
	return &TokenSnapshot{
		Chain: network, Address: addr, Symbol: clip(symbol, 16),
		Name: clip(firstNonEmpty(str(base["name"]), symbol), 48), Dex: dexID, Source: source,
		PairAddress: ptrStr(pair), PriceUSD: num(attrs["base_token_price_usd"]),
		MarketCapUSD: mc, FdvUSD: fdv, LiquidityUSD: liq, CreatedAtMs: isoMs(str(attrs["pool_created_at"])),
		VolumeM5: num(vol["m5"]), VolumeH1: num(vol["h1"]), VolumeH6: num(vol["h6"]), VolumeH24: num(vol["h24"]),
		ChangeM5: num(chg["m5"]), ChangeH1: num(chg["h1"]), ChangeH6: num(chg["h6"]), ChangeH24: num(chg["h24"]),
		TxM5: readTx(asMap(tx["m5"])), TxM15: readTx(asMap(tx["m15"])), TxH1: readTx(asMap(tx["h1"])),
		Image: ptrStr(img), URL: u, Websites: []string{}, Socials: []Social{},
	}
}

func readTx(m map[string]any) TxWindow {
	return TxWindow{Buys: int(num(m["buys"])), Sells: int(num(m["sells"])), Buyers: int(num(m["buyers"])), Sellers: int(num(m["sellers"]))}
}

func tokenAddr(relID string) string {
	if i := strings.Index(relID, "_"); i >= 0 {
		return relID[i+1:]
	}
	return relID
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

func isoMs(s string) int64 {
	if s == "" {
		return 0
	}
	s = strings.ReplaceAll(s, "Z", "+00:00")
	t, err := parseTime(s)
	if err != nil {
		return 0
	}
	return t.UnixMilli()
}

func mergeSnap(a, b TokenSnapshot) *TokenSnapshot {
	pick, other := a, b
	if b.VolumeH1 > a.VolumeH1 || b.TxH1.Buyers > a.TxH1.Buyers {
		pick, other = b, a
	}
	if pick.LiquidityUSD == nil {
		pick.LiquidityUSD = other.LiquidityUSD
	}
	if pick.Image == nil {
		pick.Image = other.Image
	}
	if pick.Pump == nil {
		pick.Pump = other.Pump
	}
	return &pick
}
