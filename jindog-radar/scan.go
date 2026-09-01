package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	dexAPI        = "https://api.dexscreener.com"
	blockscoutAPI = "https://robinhoodchain.blockscout.com/api/v2"
	chainSlug     = "robinhood"
	userAgent     = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

var httpClient = &http.Client{
	Timeout: 12 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        32,
		IdleConnTimeout:     30 * time.Second,
		TLSHandshakeTimeout: 8 * time.Second,
	},
}

type ScanResult struct {
	GeneratedAt time.Time      `json:"generatedAt"`
	Source      string         `json:"source"`
	Logic       string         `json:"logic"`
	Count       int            `json:"count"`
	Gold        int            `json:"gold"`
	Watch       int            `json:"watch"`
	Avoid       int            `json:"avoid"`
	Stale       int            `json:"stale"`
	Candidates  []Candidate    `json:"candidates"`
	Errors      []string       `json:"errors,omitempty"`
	Chain       ChainMeta      `json:"chain"`
	Pipeline    []PipelineStep `json:"pipeline"`
}

type dexSearchResp struct {
	Pairs []dexPair `json:"pairs"`
}

type dexPair struct {
	ChainID       string        `json:"chainId"`
	DexID         string        `json:"dexId"`
	URL           string        `json:"url"`
	PairAddress   string        `json:"pairAddress"`
	BaseToken     dexToken      `json:"baseToken"`
	QuoteToken    dexToken      `json:"quoteToken"`
	PriceUSD      string        `json:"priceUsd"`
	FDV           float64       `json:"fdv"`
	MarketCap     float64       `json:"marketCap"`
	PairCreatedAt int64         `json:"pairCreatedAt"`
	Liquidity     *dexLiquidity `json:"liquidity"`
	Volume        *dexVolume    `json:"volume"`
	Txns          *dexTxns      `json:"txns"`
	PriceChange   *dexChange    `json:"priceChange"`
	Info          *dexInfo      `json:"info"`
}

type dexToken struct {
	Address string `json:"address"`
	Name    string `json:"name"`
	Symbol  string `json:"symbol"`
}

type dexLiquidity struct {
	USD float64 `json:"usd"`
}

type dexVolume struct {
	H24 float64 `json:"h24"`
	H6  float64 `json:"h6"`
	H1  float64 `json:"h1"`
	M5  float64 `json:"m5"`
}

type dexTxns struct {
	M5 *dexBS `json:"m5"`
	H1 *dexBS `json:"h1"`
	H6 *dexBS `json:"h6"`
}

type dexBS struct {
	Buys  int `json:"buys"`
	Sells int `json:"sells"`
}

type dexChange struct {
	H1 float64 `json:"h1"`
}

type dexInfo struct {
	ImageURL string      `json:"imageUrl"`
	Websites []dexNamed  `json:"websites"`
	Socials  []dexSocial `json:"socials"`
}

type dexNamed struct {
	URL   string `json:"url"`
	Label string `json:"label"`
}

type dexSocial struct {
	URL  string `json:"url"`
	Type string `json:"type"`
}

type dexProfile struct {
	ChainID      string      `json:"chainId"`
	TokenAddress string      `json:"tokenAddress"`
	Description  string      `json:"description"`
	Links        []dexSocial `json:"links"`
}

type bsToken struct {
	AddressHash  string `json:"address_hash"`
	HoldersCount string `json:"holders_count"`
	TotalSupply  string `json:"total_supply"`
	Name         string `json:"name"`
	Symbol       string `json:"symbol"`
}

type bsHolders struct {
	Items []struct {
		Value   string `json:"value"`
		Address struct {
			Hash       string `json:"hash"`
			IsContract bool   `json:"is_contract"`
		} `json:"address"`
	} `json:"items"`
}

func ScanMarket(now time.Time) ScanResult {
	if now.IsZero() {
		now = time.Now()
	}
	res := ScanResult{
		GeneratedAt: now,
		Source:      Chain.SourceURL,
		Logic:       "筛选顺序：双监控发现 → 年龄窗口 → 叙事快筛 → 数据确认 → 链上核查 → 聪明钱确认。",
		Chain:       Chain,
		Pipeline:    Pipeline,
		Errors:      []string{},
	}

	pairs, errs := collectPairs()
	res.Errors = append(res.Errors, errs...)
	snaps := map[string]TokenSnapshot{}
	for _, p := range pairs {
		s := pairToSnapshot(p)
		if s.Address == "" {
			continue
		}
		key := strings.ToLower(s.Address)
		prev, ok := snaps[key]
		if !ok || s.LiquidityUSD > prev.LiquidityUSD {
			snaps[key] = s
		}
	}

	out := make([]Candidate, 0, len(snaps))
	for _, s := range snaps {
		out = append(out, Evaluate(s, now))
	}
	sortCandidates(out)
	for i := range out {
		switch out[i].Verdict {
		case VerdictGold:
			res.Gold++
		case VerdictWatch:
			res.Watch++
		case VerdictAvoid:
			res.Avoid++
		case VerdictStale:
			res.Stale++
		}
	}
	res.Candidates = out
	res.Count = len(out)
	return res
}

func collectPairs() ([]dexPair, []string) {
	var (
		mu    sync.Mutex
		pairs []dexPair
		errs  []string
		wg    sync.WaitGroup
		sem   = make(chan struct{}, 5)
	)
	addErr := func(e string) {
		mu.Lock()
		errs = append(errs, e)
		mu.Unlock()
	}
	addPairs := func(ps []dexPair) {
		mu.Lock()
		pairs = append(pairs, ps...)
		mu.Unlock()
	}

	queries := []string{"cashcat", "GME", "DIH", "cat", "dog", "hood", "robin", "meme", "pepe", "click", "HOOD"}
	for _, q := range queries {
		q := q
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			ps, err := searchDex(q)
			if err != nil {
				addErr(fmt.Sprintf("search %s: %v", q, err))
				return
			}
			addPairs(filterRobinhood(ps))
		}()
	}

	wg.Add(1)
	go func() {
		defer wg.Done()
		sem <- struct{}{}
		defer func() { <-sem }()
		addrs, err := latestRobinhoodTokens()
		if err != nil {
			addErr(fmt.Sprintf("profiles: %v", err))
			return
		}
		ps, err := fetchTokens(addrs)
		if err != nil {
			addErr(fmt.Sprintf("tokens/v1: %v", err))
			return
		}
		addPairs(filterRobinhood(ps))
	}()

	wg.Wait()
	return pairs, errs
}

func searchDex(q string) ([]dexPair, error) {
	var resp dexSearchResp
	if err := getJSON(dexAPI+"/latest/dex/search?q="+urlQuery(q), &resp); err != nil {
		return nil, err
	}
	return resp.Pairs, nil
}

func latestRobinhoodTokens() ([]string, error) {
	seen := map[string]struct{}{}
	var addrs []string
	add := func(chain, addr string) {
		if !strings.EqualFold(chain, chainSlug) || addr == "" {
			return
		}
		key := strings.ToLower(addr)
		if _, ok := seen[key]; ok {
			return
		}
		seen[key] = struct{}{}
		addrs = append(addrs, addr)
	}

	var profiles []dexProfile
	if err := getJSON(dexAPI+"/token-profiles/latest/v1", &profiles); err == nil {
		for _, p := range profiles {
			add(p.ChainID, p.TokenAddress)
		}
	}
	var boosts []dexProfile
	if err := getJSON(dexAPI+"/token-boosts/latest/v1", &boosts); err == nil {
		for _, p := range boosts {
			add(p.ChainID, p.TokenAddress)
		}
	}
	var top []dexProfile
	if err := getJSON(dexAPI+"/token-boosts/top/v1", &top); err == nil {
		for _, p := range top {
			add(p.ChainID, p.TokenAddress)
		}
	}
	if len(addrs) > 30 {
		addrs = addrs[:30]
	}
	return addrs, nil
}

func fetchTokens(addrs []string) ([]dexPair, error) {
	if len(addrs) == 0 {
		return nil, nil
	}
	var all []dexPair
	for i := 0; i < len(addrs); i += 30 {
		end := i + 30
		if end > len(addrs) {
			end = len(addrs)
		}
		url := dexAPI + "/tokens/v1/" + chainSlug + "/" + strings.Join(addrs[i:end], ",")
		var batch []dexPair
		if err := getJSON(url, &batch); err != nil {
			return all, err
		}
		all = append(all, batch...)
	}
	return all, nil
}

func filterRobinhood(ps []dexPair) []dexPair {
	out := make([]dexPair, 0, len(ps))
	for _, p := range ps {
		if strings.EqualFold(p.ChainID, chainSlug) {
			out = append(out, p)
		}
	}
	return out
}

func pairToSnapshot(p dexPair) TokenSnapshot {
	s := TokenSnapshot{
		Name:        p.BaseToken.Name,
		Symbol:      p.BaseToken.Symbol,
		Address:     p.BaseToken.Address,
		PairAddress: p.PairAddress,
		DEX:         p.DexID,
		MarketCap:   p.MarketCap,
		FDV:         p.FDV,
	}
	if p.PairCreatedAt > 0 {
		s.CreatedAt = time.UnixMilli(p.PairCreatedAt)
	}
	fmt.Sscanf(p.PriceUSD, "%f", &s.PriceUSD)
	if p.Liquidity != nil {
		s.LiquidityUSD = p.Liquidity.USD
	}
	if p.Volume != nil {
		s.VolumeM5 = p.Volume.M5
		s.VolumeH1 = p.Volume.H1
		s.VolumeH6 = p.Volume.H6
		s.VolumeH24 = p.Volume.H24
	}
	if p.Txns != nil {
		if p.Txns.M5 != nil {
			s.BuysM5, s.SellsM5 = p.Txns.M5.Buys, p.Txns.M5.Sells
		}
		if p.Txns.H1 != nil {
			s.BuysH1, s.SellsH1 = p.Txns.H1.Buys, p.Txns.H1.Sells
		}
		if p.Txns.H6 != nil {
			s.BuysH6, s.SellsH6 = p.Txns.H6.Buys, p.Txns.H6.Sells
		}
	}
	if p.PriceChange != nil {
		s.PriceChangeH1 = p.PriceChange.H1
	}
	if p.Info != nil {
		s.ImageURL = p.Info.ImageURL
		for _, w := range p.Info.Websites {
			if w.URL != "" {
				s.HasWebsite = true
				s.WebsiteURL = w.URL
				break
			}
		}
		for _, so := range p.Info.Socials {
			switch strings.ToLower(so.Type) {
			case "twitter", "x":
				s.HasTwitter = true
				s.TwitterURL = so.URL
			case "telegram":
				s.HasTelegram = true
				s.TelegramURL = so.URL
			}
		}
	}
	return s
}

func DeepCheck(address string, base TokenSnapshot, now time.Time) (Candidate, error) {
	address = strings.TrimSpace(address)
	if address == "" {
		return Candidate{}, fmt.Errorf("missing contract address")
	}
	if base.Address == "" {
		pairs, err := fetchTokens([]string{address})
		if err != nil {
			return Candidate{}, err
		}
		rh := filterRobinhood(pairs)
		if len(rh) == 0 {
			return Candidate{}, fmt.Errorf("dexscreener 上没有这条 Robinhood 代币")
		}
		best := rh[0]
		for _, p := range rh[1:] {
			if p.Liquidity != nil && (best.Liquidity == nil || p.Liquidity.USD > best.Liquidity.USD) {
				best = p
			}
		}
		base = pairToSnapshot(best)
	}

	tok, err := fetchBlockscoutToken(address)
	if err != nil {
		c := Evaluate(base, now)
		c.Flags = append(c.Flags, "Blockscout 深查失败，请打开浏览器链接人工核对")
		return c, nil
	}
	fmt.Sscanf(tok.HoldersCount, "%d", &base.Holders)
	holders, herr := fetchBlockscoutHolders(address)
	if herr != nil {
		c := Evaluate(base, now)
		c.Flags = append(c.Flags, "持仓列表读取失败，请打开 Blockscout 人工核对前十大")
		return c, nil
	}
	values := make([]string, 0, len(holders.Items))
	skipLP := false
	for i, it := range holders.Items {
		values = append(values, it.Value)
		if i == 0 && it.Address.IsContract {
			skipLP = true
		}
	}
	top10, lp := holderShare(values, tok.TotalSupply, skipLP)
	base.Top10Share = top10
	base.LPShare = lp
	base.HoldersKnown = true
	return Evaluate(base, now), nil
}

func fetchBlockscoutToken(addr string) (bsToken, error) {
	var tok bsToken
	err := getJSON(blockscoutAPI+"/tokens/"+addr, &tok)
	return tok, err
}

func fetchBlockscoutHolders(addr string) (bsHolders, error) {
	var h bsHolders
	err := getJSON(blockscoutAPI+"/tokens/"+addr+"/holders", &h)
	return h, err
}

func getJSON(url string, dest any) error {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	if strings.Contains(url, "blockscout.com") {
		req.Header.Set("Referer", "https://robinhoodchain.blockscout.com/")
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 400))
		return fmt.Errorf("HTTP %d %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	return json.NewDecoder(resp.Body).Decode(dest)
}

func urlQuery(q string) string {
	q = strings.ReplaceAll(q, " ", "+")
	return q
}

func sortCandidates(cs []Candidate) {
	for i := 0; i < len(cs); i++ {
		for j := i + 1; j < len(cs); j++ {
			if lessCandidate(cs[j], cs[i]) {
				cs[i], cs[j] = cs[j], cs[i]
			}
		}
	}
}

func lessCandidate(a, b Candidate) bool {
	rank := func(v string) int {
		switch v {
		case VerdictGold:
			return 0
		case VerdictWatch:
			return 1
		case VerdictStale:
			return 2
		default:
			return 3
		}
	}
	if rank(a.Verdict) != rank(b.Verdict) {
		return rank(a.Verdict) < rank(b.Verdict)
	}
	if a.Score != b.Score {
		return a.Score > b.Score
	}
	return a.AgeMinutes < b.AgeMinutes
}
