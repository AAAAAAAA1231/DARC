package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"
	"unicode/utf8"
)

const (
	appName    = "HCWRadar"
	appVersion = "1.0.0"
	userAgent  = "HCWRadar/1.0 (research-screener; +https://localhost)"
)

var httpClient = &http.Client{Timeout: 18 * time.Second}

// Finance lexicon: only used when they appear in today's hot titles or token names.
var financeNeedles = []string{
	"牛来", "牛市", "暴拉", "暴富", "踏马", "哈基米", "半导体",
	"金狗", "土狗", "百倍", "涨停", "币安人生", "人生K线", "貔貅",
	"佩佩", "青蛙", "狗狗", "猫咪", "熊猫", "暴涨", "踏马了",
	"绊倒", "豹拉", "牛牛", "金牛", "铜牛", "罗牛",
}

var skipTitleNeedles = []string{
	"泥石流", "地震", "遇难", "死亡", "被查", "制裁", "谣言",
	"净网", "开学", "笔试", "PMI", "营收", "连放", "造谣", "反腐",
}

var sentenceMarks = []string{
	"的", "了", "吗", "呢", "把", "被", "让", "在", "是", "有",
	"和", "与", "就", "都", "也", "还", "刚", "曾", "已", "不",
	"没", "很", "最", "会", "能", "要", "到", "从", "为", "后",
	"如何", "为什么", "什么", "怎么", "回复", "官宣", "阵容",
	"震惊", "上岸", "解聘", "保洁", "自拍", "读懂", "可能",
	"宣布", "公布", "质疑", "一旦", "开始", "决定", "找到",
	"谈", "曾", "腿长", "休息", "卖不动",
}

var stableSymbols = map[string]bool{
	"USDT": true, "USDC": true, "USD1": true, "USDG": true, "DAI": true,
	"FDUSD": true, "BUSD": true, "WBNB": true, "WETH": true, "WBTC": true,
	"SOL": true, "WSOL": true, "BNB": true, "ETH": true, "BTC": true,
	"USD": true, "USDE": true,
}

type HotItem struct {
	Source string `json:"source"`
	Title  string `json:"title"`
	URL    string `json:"url,omitempty"`
	Rank   int    `json:"rank"`
}

type Candidate struct {
	Name          string   `json:"name"`
	Symbol        string   `json:"symbol"`
	Address       string   `json:"address"`
	Chain         string   `json:"chain"`
	PairURL       string   `json:"pairUrl"`
	MarketCap     float64  `json:"marketCap"`
	Liquidity     float64  `json:"liquidity"`
	Volume24      float64  `json:"volume24"`
	PairCreatedMs int64    `json:"pairCreatedMs"`
	AgeHours      float64  `json:"ageHours"`
	HotHits       []string `json:"hotHits"`
	MatchQuality  float64  `json:"matchQuality"`
	Archetype     string   `json:"archetype"`
	Gate1         string   `json:"gate1"`
	Gate2         string   `json:"gate2"`
	Gate3         string   `json:"gate3"`
	Score         float64  `json:"score"`
	Reasons       []string `json:"reasons"`
	VetoReasons   []string `json:"vetoReasons"`
	WindowLabel   string   `json:"windowLabel"`
	TopHolderPct  float64  `json:"topHolderPct"`
	BuyTax        string   `json:"buyTax,omitempty"`
	SellTax       string   `json:"sellTax,omitempty"`
	Honeypot      bool     `json:"honeypot"`
	Mintable      bool     `json:"mintable"`
	Turnover      float64  `json:"turnover"`
	ChineseName   bool     `json:"chineseName"`
}

type ScanResult struct {
	GeneratedAt time.Time   `json:"generatedAt"`
	Version     string      `json:"version"`
	Disclaimer  string      `json:"disclaimer"`
	Hot         []HotItem   `json:"hot"`
	Queries     []string    `json:"queries"`
	Watch       []Candidate `json:"watch"`
	Late        []Candidate `json:"late"`
	Onchain     []Candidate `json:"onchain"`
	Rejected    []Candidate `json:"rejected"`
	Errors      []string    `json:"errors"`
	Stats       ScanStats   `json:"stats"`
	Model       string      `json:"model"`
}

type ScanStats struct {
	HotCount     int `json:"hotCount"`
	QueryCount   int `json:"queryCount"`
	TokenCount   int `json:"tokenCount"`
	WatchCount   int `json:"watchCount"`
	LateCount    int `json:"lateCount"`
	OnchainCount int `json:"onchainCount"`
	Rejected     int `json:"rejected"`
}

type progressFn func(string)

func RunScan(ctx context.Context, progress progressFn) (*ScanResult, error) {
	if progress == nil {
		progress = func(string) {}
	}
	out := &ScanResult{
		GeneratedAt: time.Now(),
		Version:     appVersion,
		Disclaimer:  "这是注意力筛选工具，不是买卖建议。绝大多数土狗会归零。高分只说明「这个梗配得上被观察」，不说明你能赚到钱。",
		Model:       "HCW 三闸 · ATTN-7（外热 / 结构 / 窗口）",
	}

	progress("正在拉取微博 / 抖音 / 百度 / 雪球热榜…")
	hot, herr := fetchAllHots(ctx)
	out.Hot = hot
	out.Errors = append(out.Errors, herr...)

	queries := extractQueries(hot)
	out.Queries = queries
	progress(fmt.Sprintf("今日提取 %d 个检索词，正在扫描链上…", len(queries)))

	raw, merr := collectTokens(ctx, queries, progress)
	out.Errors = append(out.Errors, merr...)
	out.Stats.TokenCount = len(raw)
	out.Stats.HotCount = len(hot)
	out.Stats.QueryCount = len(queries)

	progress(fmt.Sprintf("找到 %d 个候选，正在做合约结构检查…", len(raw)))
	enrichSecurity(ctx, raw)

	progress("正在按 HCW 三闸打分…")
	for i := range raw {
		scoreCandidate(&raw[i])
	}

	for _, c := range raw {
		switch {
		case len(c.VetoReasons) > 0:
			out.Rejected = append(out.Rejected, c)
		case c.Archetype == "A" && c.Gate3 == "late":
			out.Late = append(out.Late, c)
		case c.Archetype == "A":
			out.Watch = append(out.Watch, c)
		default:
			out.Onchain = append(out.Onchain, c)
		}
	}
	sort.Slice(out.Watch, func(i, j int) bool { return out.Watch[i].Score > out.Watch[j].Score })
	sort.Slice(out.Late, func(i, j int) bool { return out.Late[i].Score > out.Late[j].Score })
	sort.Slice(out.Onchain, func(i, j int) bool { return out.Onchain[i].Score > out.Onchain[j].Score })
	sort.Slice(out.Rejected, func(i, j int) bool { return out.Rejected[i].Score > out.Rejected[j].Score })

	const capN = 20
	if len(out.Watch) > capN {
		out.Watch = out.Watch[:capN]
	}
	if len(out.Late) > 12 {
		out.Late = out.Late[:12]
	}
	if len(out.Onchain) > 16 {
		out.Onchain = out.Onchain[:16]
	}
	if len(out.Rejected) > 10 {
		out.Rejected = out.Rejected[:10]
	}

	if out.Watch == nil {
		out.Watch = []Candidate{}
	}
	if out.Late == nil {
		out.Late = []Candidate{}
	}
	if out.Onchain == nil {
		out.Onchain = []Candidate{}
	}
	if out.Rejected == nil {
		out.Rejected = []Candidate{}
	}
	if out.Hot == nil {
		out.Hot = []HotItem{}
	}
	if out.Queries == nil {
		out.Queries = []string{}
	}
	if out.Errors == nil {
		out.Errors = []string{}
	}

	out.Stats.WatchCount = len(out.Watch)
	out.Stats.LateCount = len(out.Late)
	out.Stats.OnchainCount = len(out.Onchain)
	out.Stats.Rejected = len(out.Rejected)

	_ = saveCache(out)
	return out, nil
}

func fetchAllHots(ctx context.Context) ([]HotItem, []string) {
	var (
		mu     sync.Mutex
		items  []HotItem
		errors []string
	)
	add := func(got []HotItem, err error, name string) {
		mu.Lock()
		defer mu.Unlock()
		if err != nil {
			errors = append(errors, name+": "+err.Error())
			return
		}
		items = append(items, got...)
	}

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		got, err := fetchWeiboXX(ctx)
		add(got, err, "微博")
	}()
	wg.Add(1)
	go func() {
		defer wg.Done()
		for i, s := range []struct {
			id, name string
		}{
			{"weibo", "微博备份"},
			{"douyin", "抖音"},
			{"baidu", "百度"},
			{"toutiao", "头条"},
			{"xueqiu", "雪球"},
		} {
			if i > 0 {
				select {
				case <-ctx.Done():
					return
				case <-time.After(220 * time.Millisecond):
				}
			}
			got, err := fetchNewsNow(s.id, strings.TrimSuffix(s.name, "备份"))(ctx)
			add(got, err, s.name)
		}
	}()
	wg.Wait()

	seen := map[string]bool{}
	var uniq []HotItem
	for _, it := range items {
		key := it.Source + "|" + strings.TrimSpace(it.Title)
		if it.Title == "" || seen[key] {
			continue
		}
		seen[key] = true
		uniq = append(uniq, it)
	}
	sort.Slice(uniq, func(i, j int) bool {
		if uniq[i].Source != uniq[j].Source {
			return uniq[i].Source < uniq[j].Source
		}
		return uniq[i].Rank < uniq[j].Rank
	})
	return uniq, errors
}

func fetchWeiboXX(ctx context.Context) ([]HotItem, error) {
	var payload struct {
		Code int `json:"code"`
		Data []struct {
			Hot   string `json:"hot"`
			Index int    `json:"index"`
			Title string `json:"title"`
			URL   string `json:"url"`
		} `json:"data"`
	}
	if err := getJSON(ctx, "https://v2.xxapi.cn/api/weibohot", &payload); err != nil {
		return nil, err
	}
	if payload.Code != 200 {
		return nil, fmt.Errorf("xxapi code %d", payload.Code)
	}
	out := make([]HotItem, 0, len(payload.Data))
	for _, d := range payload.Data {
		out = append(out, HotItem{Source: "微博", Title: d.Title, URL: d.URL, Rank: d.Index})
	}
	return out, nil
}

func fetchNewsNow(id, source string) func(context.Context) ([]HotItem, error) {
	return func(ctx context.Context) ([]HotItem, error) {
		var payload struct {
			Items []struct {
				Title string `json:"title"`
				URL   string `json:"url"`
			} `json:"items"`
		}
		u := "https://newsnow.busiyi.world/api/s?id=" + id
		if err := getJSON(ctx, u, &payload); err != nil {
			return nil, err
		}
		out := make([]HotItem, 0, len(payload.Items))
		for i, d := range payload.Items {
			if i >= 25 {
				break
			}
			out = append(out, HotItem{Source: source, Title: d.Title, URL: d.URL, Rank: i + 1})
		}
		return out, nil
	}
}

func extractQueries(hot []HotItem) []string {
	type scored struct {
		q string
		s int
	}
	var bag []scored
	push := func(q string, s int) {
		q = strings.TrimSpace(q)
		q = strings.Trim(q, "#　 ")
		if utf8.RuneCountInString(q) < 2 || utf8.RuneCountInString(q) > 10 {
			return
		}
		bag = append(bag, scored{q: q, s: s})
	}

	for _, h := range hot {
		title := strings.TrimSpace(h.Title)
		if title == "" || shouldSkipTitle(title) {
			continue
		}
		for _, needle := range financeNeedles {
			if strings.Contains(title, needle) {
				push(needle, 100)
			}
		}
		compact := stripNoise(title)
		n := utf8.RuneCountInString(compact)
		if n >= 2 && n <= 6 && isMostlyCJK(compact) && !looksLikeSentence(compact) {
			if h.Source == "雪球" && !hasFinanceRune(compact) {
				continue
			}
			score := 50
			if hasFinanceRune(compact) {
				score += 30
			}
			if n <= 4 {
				score += 10
			}
			push(compact, score)
		}
		for _, seq := range cjkSequences(title, 2, 6) {
			for _, needle := range financeNeedles {
				if seq == needle || strings.Contains(seq, needle) {
					push(needle, 90)
				}
			}
		}
	}

	sort.Slice(bag, func(i, j int) bool { return bag[i].s > bag[j].s })
	seen := map[string]bool{}
	var out []string
	for _, b := range bag {
		if seen[b.q] || b.s < 40 {
			continue
		}
		seen[b.q] = true
		out = append(out, b.q)
		if len(out) >= 10 {
			break
		}
	}
	return out
}

func looksLikeSentence(s string) bool {
	if utf8.RuneCountInString(s) >= 8 {
		return true
	}
	for _, m := range sentenceMarks {
		if strings.Contains(s, m) {
			return true
		}
	}
	return false
}

func shouldSkipTitle(title string) bool {
	for _, n := range skipTitleNeedles {
		if strings.Contains(title, n) {
			return true
		}
	}
	return false
}

func stripNoise(s string) string {
	s = strings.ReplaceAll(s, " ", "")
	s = strings.ReplaceAll(s, "　", "")
	var b strings.Builder
	for _, r := range s {
		if unicode.IsPunct(r) || unicode.IsSymbol(r) {
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

func isMostlyCJK(s string) bool {
	n, cjk := 0, 0
	for _, r := range s {
		if unicode.IsSpace(r) {
			continue
		}
		n++
		if r >= 0x4e00 && r <= 0x9fff {
			cjk++
		}
	}
	return n > 0 && cjk*2 >= n
}

func hasCJK(s string) bool {
	for _, r := range s {
		if r >= 0x4e00 && r <= 0x9fff {
			return true
		}
	}
	return false
}

func hasFinanceRune(s string) bool {
	for _, n := range financeNeedles {
		if strings.Contains(s, n) {
			return true
		}
	}
	for _, r := range s {
		switch r {
		case '牛', '熊', '涨', '暴', '富', '狗', '蛙', '猫', '币':
			return true
		}
	}
	return false
}

func cjkSequences(s string, minN, maxN int) []string {
	var seq strings.Builder
	var out []string
	flush := func() {
		t := seq.String()
		seq.Reset()
		n := utf8.RuneCountInString(t)
		if n >= minN && n <= maxN {
			out = append(out, t)
		}
		if n > maxN {
			runes := []rune(t)
			if len(runes) >= minN {
				out = append(out, string(runes[:min(maxN, len(runes))]))
			}
		}
	}
	for _, r := range s {
		if r >= 0x4e00 && r <= 0x9fff {
			seq.WriteRune(r)
		} else {
			flush()
		}
	}
	flush()
	return out
}

func collectTokens(ctx context.Context, queries []string, progress progressFn) ([]Candidate, []string) {
	var (
		mu     sync.Mutex
		all    []Candidate
		errors []string
	)
	add := func(cs []Candidate, err error, src string) {
		mu.Lock()
		defer mu.Unlock()
		if err != nil {
			errors = append(errors, src+": "+err.Error())
			return
		}
		all = append(all, cs...)
	}

	var wg sync.WaitGroup
	for _, net := range []string{"bsc", "solana", "base"} {
		net := net
		wg.Add(1)
		go func() {
			defer wg.Done()
			cs, err := fetchGeckoPools(ctx, net, "new_pools")
			add(cs, err, "Gecko新池-"+net)
		}()
	}
	wg.Add(1)
	go func() {
		defer wg.Done()
		cs, err := fetchGeckoTrending(ctx)
		add(cs, err, "Gecko热门池")
	}()

	sem := make(chan struct{}, 4)
	for i, q := range queries {
		q := q
		i := i
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			progress(fmt.Sprintf("检索 DexScreener：「%s」(%d/%d)", q, i+1, len(queries)))
			cs, err := searchDex(ctx, q)
			add(cs, err, "Dex搜索-"+q)
		}()
	}
	wg.Wait()

	merged := mergeCandidates(all, queries)
	return merged, errors
}

func fetchGeckoPools(ctx context.Context, network, kind string) ([]Candidate, error) {
	u := fmt.Sprintf("https://api.geckoterminal.com/api/v2/networks/%s/%s?page=1&include=base_token", network, kind)
	var payload struct {
		Data []struct {
			ID         string `json:"id"`
			Attributes struct {
				Address       string  `json:"address"`
				Name          string  `json:"name"`
				PoolCreatedAt string  `json:"pool_created_at"`
				FDV           string  `json:"fdv_usd"`
				MC            *string `json:"market_cap_usd"`
				Reserve       string  `json:"reserve_in_usd"`
				VolumeUSD     struct {
					H24 string `json:"h24"`
				} `json:"volume_usd"`
			} `json:"attributes"`
			Relationships struct {
				BaseToken struct {
					Data struct {
						ID string `json:"id"`
					} `json:"data"`
				} `json:"base_token"`
			} `json:"relationships"`
		} `json:"data"`
		Included []struct {
			ID         string `json:"id"`
			Attributes struct {
				Address string `json:"address"`
				Name    string `json:"name"`
				Symbol  string `json:"symbol"`
			} `json:"attributes"`
		} `json:"included"`
	}
	if err := getJSON(ctx, u, &payload); err != nil {
		return nil, err
	}
	inc := map[string]struct{ Name, Symbol, Address string }{}
	for _, t := range payload.Included {
		inc[t.ID] = struct{ Name, Symbol, Address string }{t.Attributes.Name, t.Attributes.Symbol, t.Attributes.Address}
	}
	var out []Candidate
	chain := geckoChain(network)
	for _, p := range payload.Data {
		tok := inc[p.Relationships.BaseToken.Data.ID]
		if tok.Address == "" {
			continue
		}
		if stableSymbols[strings.ToUpper(tok.Symbol)] {
			continue
		}
		mc := parseFloat(p.Attributes.FDV)
		if p.Attributes.MC != nil && *p.Attributes.MC != "" {
			mc = parseFloat(*p.Attributes.MC)
		}
		created, _ := time.Parse(time.RFC3339, p.Attributes.PoolCreatedAt)
		c := Candidate{
			Name:          tok.Name,
			Symbol:        tok.Symbol,
			Address:       tok.Address,
			Chain:         chain,
			PairURL:       fmt.Sprintf("https://dexscreener.com/%s/%s", chain, p.Attributes.Address),
			MarketCap:     mc,
			Liquidity:     parseFloat(p.Attributes.Reserve),
			Volume24:      parseFloat(p.Attributes.VolumeUSD.H24),
			PairCreatedMs: created.UnixMilli(),
			ChineseName:   hasCJK(tok.Name) || hasCJK(tok.Symbol),
		}
		out = append(out, c)
	}
	return out, nil
}

func fetchGeckoTrending(ctx context.Context) ([]Candidate, error) {
	u := "https://api.geckoterminal.com/api/v2/networks/trending_pools?page=1&include=base_token"
	var payload struct {
		Data []struct {
			ID         string `json:"id"`
			Attributes struct {
				Address       string  `json:"address"`
				Name          string  `json:"name"`
				PoolCreatedAt string  `json:"pool_created_at"`
				FDV           string  `json:"fdv_usd"`
				MC            *string `json:"market_cap_usd"`
				Reserve       string  `json:"reserve_in_usd"`
				VolumeUSD     struct {
					H24 string `json:"h24"`
				} `json:"volume_usd"`
			} `json:"attributes"`
			Relationships struct {
				BaseToken struct {
					Data struct {
						ID string `json:"id"`
					} `json:"data"`
				} `json:"base_token"`
			} `json:"relationships"`
		} `json:"data"`
		Included []struct {
			ID         string `json:"id"`
			Attributes struct {
				Address string `json:"address"`
				Name    string `json:"name"`
				Symbol  string `json:"symbol"`
			} `json:"attributes"`
		} `json:"included"`
	}
	if err := getJSON(ctx, u, &payload); err != nil {
		return nil, err
	}
	inc := map[string]struct{ Name, Symbol, Address string }{}
	for _, t := range payload.Included {
		inc[t.ID] = struct{ Name, Symbol, Address string }{t.Attributes.Name, t.Attributes.Symbol, t.Attributes.Address}
	}
	var out []Candidate
	for _, p := range payload.Data {
		tok := inc[p.Relationships.BaseToken.Data.ID]
		if tok.Address == "" || stableSymbols[strings.ToUpper(tok.Symbol)] {
			continue
		}
		network := strings.Split(p.ID, "_")[0]
		chain := geckoChain(network)
		mc := parseFloat(p.Attributes.FDV)
		if p.Attributes.MC != nil && *p.Attributes.MC != "" {
			mc = parseFloat(*p.Attributes.MC)
		}
		created, _ := time.Parse(time.RFC3339, p.Attributes.PoolCreatedAt)
		out = append(out, Candidate{
			Name:          tok.Name,
			Symbol:        tok.Symbol,
			Address:       tok.Address,
			Chain:         chain,
			PairURL:       fmt.Sprintf("https://dexscreener.com/%s/%s", chain, p.Attributes.Address),
			MarketCap:     mc,
			Liquidity:     parseFloat(p.Attributes.Reserve),
			Volume24:      parseFloat(p.Attributes.VolumeUSD.H24),
			PairCreatedMs: created.UnixMilli(),
			ChineseName:   hasCJK(tok.Name) || hasCJK(tok.Symbol),
		})
	}
	return out, nil
}

func searchDex(ctx context.Context, query string) ([]Candidate, error) {
	u := "https://api.dexscreener.com/latest/dex/search?q=" + url.QueryEscape(query)
	var payload struct {
		Pairs []struct {
			ChainID     string `json:"chainId"`
			URL         string `json:"url"`
			PairCreated int64  `json:"pairCreatedAt"`
			BaseToken   struct {
				Address string `json:"address"`
				Name    string `json:"name"`
				Symbol  string `json:"symbol"`
			} `json:"baseToken"`
			QuoteToken struct {
				Symbol string `json:"symbol"`
			} `json:"quoteToken"`
			MarketCap float64 `json:"marketCap"`
			FDV       float64 `json:"fdv"`
			Liquidity struct {
				USD float64 `json:"usd"`
			} `json:"liquidity"`
			Volume struct {
				H24 float64 `json:"h24"`
			} `json:"volume"`
		} `json:"pairs"`
	}
	if err := getJSON(ctx, u, &payload); err != nil {
		return nil, err
	}
	var out []Candidate
	for _, p := range payload.Pairs {
		if stableSymbols[strings.ToUpper(p.BaseToken.Symbol)] {
			continue
		}
		mq := matchQuality(p.BaseToken.Name, p.BaseToken.Symbol, query)
		if mq < 0.5 {
			continue
		}
		mc := p.MarketCap
		if mc == 0 {
			mc = p.FDV
		}
		out = append(out, Candidate{
			Name:          p.BaseToken.Name,
			Symbol:        p.BaseToken.Symbol,
			Address:       p.BaseToken.Address,
			Chain:         p.ChainID,
			PairURL:       p.URL,
			MarketCap:     mc,
			Liquidity:     p.Liquidity.USD,
			Volume24:      p.Volume.H24,
			PairCreatedMs: p.PairCreated,
			HotHits:       []string{query},
			MatchQuality:  mq,
			ChineseName:   hasCJK(p.BaseToken.Name) || hasCJK(p.BaseToken.Symbol),
		})
	}
	return out, nil
}

func matchQuality(name, symbol, query string) float64 {
	name = strings.TrimSpace(name)
	symbol = strings.TrimSpace(symbol)
	query = strings.TrimSpace(query)
	nl, ql := utf8.RuneCountInString(name), utf8.RuneCountInString(query)
	if name == query {
		return 1
	}
	if symbol == query {
		if nl > ql*3 {
			return 0.45
		}
		return 0.9
	}
	if strings.Contains(name, query) && nl <= ql+2 {
		return 0.9
	}
	if strings.HasPrefix(name, query) || strings.HasPrefix(symbol, query) {
		return 0.75
	}
	if strings.Contains(name, query) || strings.Contains(symbol, query) {
		if nl > ql*4 {
			return 0.35
		}
		return 0.55
	}
	return 0
}

func mergeCandidates(in []Candidate, queries []string) []Candidate {
	type key struct{ chain, addr string }
	best := map[key]Candidate{}
	for _, c := range in {
		if c.Address == "" || c.Chain == "" {
			continue
		}
		if c.Liquidity > 0 && c.Liquidity < 2000 && c.MarketCap < 50000 {
			// keep very new microcaps only if they have a hot hit
			if len(c.HotHits) == 0 && c.MatchQuality < 0.7 {
				continue
			}
		}
		k := key{strings.ToLower(c.Chain), strings.ToLower(c.Address)}
		old, ok := best[k]
		if !ok {
			c.HotHits = uniqueStrings(append(c.HotHits, matchingQueries(c, queries)...))
			if mq := bestMatch(c, queries); mq > c.MatchQuality {
				c.MatchQuality = mq
			}
			best[k] = c
			continue
		}
		hits := uniqueStrings(append(append(old.HotHits, c.HotHits...), matchingQueries(c, queries)...))
		if c.Liquidity > old.Liquidity {
			c.HotHits = hits
			if c.MatchQuality < old.MatchQuality {
				c.MatchQuality = old.MatchQuality
			}
			best[k] = c
		} else {
			old.HotHits = hits
			if c.MatchQuality > old.MatchQuality {
				old.MatchQuality = c.MatchQuality
			}
			best[k] = old
		}
	}
	out := make([]Candidate, 0, len(best))
	for _, c := range best {
		if c.PairCreatedMs > 0 {
			c.AgeHours = time.Since(time.UnixMilli(c.PairCreatedMs)).Hours()
		}
		if c.MarketCap > 0 {
			c.Turnover = c.Volume24 / c.MarketCap
		}
		out = append(out, c)
	}
	// Pre-rank and keep a workable set before GoPlus.
	sort.Slice(out, func(i, j int) bool {
		si := out[i].MatchQuality*5 + logCap(out[i].Volume24)*0.3
		if out[i].ChineseName {
			si += 1
		}
		sj := out[j].MatchQuality*5 + logCap(out[j].Volume24)*0.3
		if out[j].ChineseName {
			sj += 1
		}
		return si > sj
	})
	if len(out) > 40 {
		out = out[:40]
	}
	return out
}

func matchingQueries(c Candidate, queries []string) []string {
	var hits []string
	for _, q := range queries {
		if matchQuality(c.Name, c.Symbol, q) >= 0.55 {
			hits = append(hits, q)
		}
	}
	return hits
}

func bestMatch(c Candidate, queries []string) float64 {
	best := c.MatchQuality
	for _, q := range queries {
		if m := matchQuality(c.Name, c.Symbol, q); m > best {
			best = m
		}
	}
	return best
}

func enrichSecurity(ctx context.Context, cs []Candidate) {
	var wg sync.WaitGroup
	sem := make(chan struct{}, 4)
	for i := range cs {
		i := i
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			checkGoPlus(ctx, &cs[i])
		}()
	}
	wg.Wait()
}

func checkGoPlus(ctx context.Context, c *Candidate) {
	chainID := goplusChain(c.Chain)
	if chainID == "" {
		c.Gate2 = "unknown"
		return
	}
	var raw map[string]any
	var err error
	if chainID == "solana" {
		err = getJSON(ctx, "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses="+url.QueryEscape(c.Address), &raw)
	} else {
		err = getJSON(ctx, "https://api.gopluslabs.io/api/v1/token_security/"+chainID+"?contract_addresses="+url.QueryEscape(c.Address), &raw)
	}
	if err != nil {
		c.Gate2 = "unknown"
		return
	}
	result, _ := raw["result"].(map[string]any)
	if result == nil {
		c.Gate2 = "unknown"
		return
	}
	var info map[string]any
	for _, v := range result {
		if m, ok := v.(map[string]any); ok {
			info = m
			break
		}
	}
	if info == nil {
		c.Gate2 = "unknown"
		return
	}
	c.Honeypot = asString(info["is_honeypot"]) == "1" || asString(info["honeypot"]) == "1"
	c.Mintable = asString(info["is_mintable"]) == "1" || asString(info["mintable"]) == "1"
	c.BuyTax = asString(info["buy_tax"])
	c.SellTax = asString(info["sell_tax"])
	if holders, ok := info["holders"].([]any); ok {
		for _, h := range holders {
			m, ok := h.(map[string]any)
			if !ok {
				continue
			}
			if fmt.Sprint(m["is_contract"]) == "1" || fmt.Sprint(m["is_locked"]) == "1" {
				continue
			}
			pct := parseFloat(fmt.Sprint(m["percent"]))
			if pct > 1 {
				pct = pct / 100
			}
			if pct > c.TopHolderPct {
				c.TopHolderPct = pct
			}
		}
	}
	if c.TopHolderPct == 0 {
		if v := asString(info["creator_percent"]); v != "" {
			c.TopHolderPct = parseFloat(v)
			if c.TopHolderPct > 1 {
				c.TopHolderPct = c.TopHolderPct / 100
			}
		}
	}
}

func scoreCandidate(c *Candidate) {
	c.Reasons = nil
	c.VetoReasons = nil

	hotStrong := len(c.HotHits) > 0 && c.MatchQuality >= 0.7
	hotWeak := len(c.HotHits) > 0 && c.MatchQuality >= 0.4

	// Gate 1 — exogenous attention
	g1 := 0.0
	switch {
	case hotStrong && (c.ChineseName || hasFinanceRune(c.Name+c.Symbol)):
		g1 = 10
		c.Gate1 = "pass"
		c.Reasons = append(c.Reasons, "链外热搜命中同名：「"+strings.Join(c.HotHits, " / ")+"」")
	case hotStrong:
		g1 = 7
		c.Gate1 = "pass"
		c.Reasons = append(c.Reasons, "热搜词命中，但金融谐音不强")
	case hotWeak:
		g1 = 4
		c.Gate1 = "weak"
		c.Reasons = append(c.Reasons, "热搜弱匹配")
	case c.ChineseName && hasFinanceRune(c.Name+c.Symbol):
		g1 = 4
		c.Gate1 = "weak"
		c.Reasons = append(c.Reasons, "中文金融谐音，但今日热搜未直接命中")
	default:
		g1 = 1
		c.Gate1 = "fail"
		c.Reasons = append(c.Reasons, "未发现链外热搜匹配，更像链上催化盘")
	}

	zeroExplain := 4.0
	nlen := utf8.RuneCountInString(c.Name)
	if nlen > 0 && nlen <= 4 && c.ChineseName {
		zeroExplain = 9
		c.Reasons = append(c.Reasons, "短中文名，解释成本低")
	} else if nlen <= 8 && c.ChineseName {
		zeroExplain = 7
	}

	pun := 3.0
	if hasFinanceRune(c.Name + c.Symbol) {
		pun = 9
		c.Reasons = append(c.Reasons, "带金融谐音或牛/暴/狗等投射层")
	}

	// Gate 2 — structure veto
	if c.Honeypot {
		c.VetoReasons = append(c.VetoReasons, "蜜罐 / 无法卖出")
	}
	if tax := parseFloat(c.SellTax); tax >= 10 {
		c.VetoReasons = append(c.VetoReasons, fmt.Sprintf("卖税过高 %s%%", c.SellTax))
	}
	if tax := parseFloat(c.BuyTax); tax >= 10 {
		c.VetoReasons = append(c.VetoReasons, fmt.Sprintf("买税过高 %s%%", c.BuyTax))
	}
	if c.Mintable {
		c.VetoReasons = append(c.VetoReasons, "仍可增发")
	}
	if c.TopHolderPct >= 0.40 {
		c.VetoReasons = append(c.VetoReasons, fmt.Sprintf("头部持仓约 %.0f%%，筹码过度集中", c.TopHolderPct*100))
	}
	if c.Liquidity > 0 && c.MarketCap > 0 && c.MarketCap/c.Liquidity > 80 {
		c.Reasons = append(c.Reasons, "市值/流动性比过高，退出滑点会很大")
	}

	g2 := 6.0
	switch {
	case len(c.VetoReasons) > 0:
		g2 = 1
		c.Gate2 = "veto"
	case c.Gate2 == "unknown":
		g2 = 4
		c.Gate2 = "unknown"
		c.Reasons = append(c.Reasons, "合约结构未能核验")
	default:
		c.Gate2 = "pass"
		if c.TopHolderPct > 0 && c.TopHolderPct < 0.15 {
			g2 = 8
			c.Reasons = append(c.Reasons, "头部持仓相对分散")
		} else {
			g2 = 6
		}
	}

	// Gate 3 — window
	mc := c.MarketCap
	switch {
	case mc <= 0:
		c.WindowLabel = "市值未知"
		c.Gate3 = "unknown"
	case mc < 500_000:
		c.WindowLabel = "发现区 < 50万"
		c.Gate3 = "early"
	case mc < 5_000_000:
		c.WindowLabel = "确认区 50万–500万"
		c.Gate3 = "early"
	case mc < 30_000_000:
		c.WindowLabel = "传播区 500万–3000万"
		c.Gate3 = "mid"
	default:
		c.WindowLabel = "公开区 > 3000万"
		c.Gate3 = "late"
	}
	if c.AgeHours > 0 && c.AgeHours < 72 && c.Gate3 == "early" {
		c.Reasons = append(c.Reasons, fmt.Sprintf("池龄约 %.0f 小时，仍在早期窗口", c.AgeHours))
	}
	if c.Turnover >= 0.3 {
		c.Reasons = append(c.Reasons, fmt.Sprintf("换手 %.2f，注意力仍在", c.Turnover))
	} else if c.Turnover > 0 && c.Turnover < 0.1 && mc > 1_000_000 {
		c.Reasons = append(c.Reasons, "换手偏低，热度可能在退")
	}

	g3 := 5.0
	switch c.Gate3 {
	case "early":
		g3 = 9
	case "mid":
		g3 = 5
	case "late":
		g3 = 2
	}

	if hotStrong {
		c.Archetype = "A"
	} else {
		c.Archetype = "B"
	}

	score := g1*0.25 + zeroExplain*0.15 + pun*0.15 + g2*0.15 + g3*0.15
	if len(c.HotHits) >= 2 {
		score += 0.6
		c.Reasons = append(c.Reasons, "多个热搜源命中，跨平台外溢")
	}
	if c.ChineseName {
		score += 0.3
	}
	c.Score = math.Round(math.Min(score, 10)*10) / 10

	if c.Gate1 == "fail" && c.Archetype == "B" {
		c.Reasons = append(c.Reasons, "B 类链上异动：可观察，不当作百倍发现")
	}
	if c.Gate3 == "late" {
		c.Reasons = append(c.Reasons, "公开渠道大概率已定价，剩余空间是博弈不是发现")
	}
}

func geckoChain(network string) string {
	switch strings.ToLower(network) {
	case "eth", "ethereum":
		return "ethereum"
	default:
		return strings.ToLower(network)
	}
}

func goplusChain(chain string) string {
	switch strings.ToLower(chain) {
	case "bsc", "bnb":
		return "56"
	case "ethereum", "eth":
		return "1"
	case "base":
		return "8453"
	case "solana":
		return "solana"
	default:
		return ""
	}
}

func getJSON(ctx context.Context, rawURL string, dest any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return err
	}
	if resp.StatusCode == 403 || resp.StatusCode == 429 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(400 * time.Millisecond):
		}
		req2, _ := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
		req2.Header.Set("User-Agent", userAgent)
		req2.Header.Set("Accept", "application/json")
		resp2, err2 := httpClient.Do(req2)
		if err2 != nil {
			return fmt.Errorf("http %d", resp.StatusCode)
		}
		defer resp2.Body.Close()
		body, err = io.ReadAll(io.LimitReader(resp2.Body, 8<<20))
		if err != nil {
			return err
		}
		resp = resp2
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("http %d", resp.StatusCode)
	}
	if err := json.Unmarshal(body, dest); err != nil {
		return fmt.Errorf("json: %w", err)
	}
	return nil
}

func parseFloat(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "<nil>" {
		return 0
	}
	f, _ := strconv.ParseFloat(s, 64)
	return f
}

func asString(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case float64:
		return strconv.FormatFloat(t, 'f', -1, 64)
	case json.Number:
		return t.String()
	case nil:
		return ""
	default:
		return fmt.Sprint(t)
	}
}

func uniqueStrings(in []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, s := range in {
		s = strings.TrimSpace(s)
		if s == "" || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	return out
}

func logCap(v float64) float64 {
	if v <= 0 {
		return 0
	}
	return math.Log10(v + 1)
}

func cachePath() string {
	exe, err := os.Executable()
	if err != nil {
		return "hcw-last-scan.json"
	}
	return filepath.Join(filepath.Dir(exe), "hcw-last-scan.json")
}

func saveCache(r *ScanResult) error {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(cachePath(), b, 0o644)
}

func loadCache() *ScanResult {
	b, err := os.ReadFile(cachePath())
	if err != nil {
		return nil
	}
	var r ScanResult
	if json.Unmarshal(b, &r) != nil {
		return nil
	}
	return &r
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
