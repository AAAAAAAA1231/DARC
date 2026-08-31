package main

import (
	"sync"
	"time"
)

const cacheTTL = 40 * time.Second
const rugcheckTop = 18

var allowedChains = map[string]bool{
	"solana": true, "base": true, "bsc": true, "ethereum": true,
	"arbitrum": true, "blast": true, "sonic": true, "abstract": true,
	"hyperevm": true, "monad": true,
}

var thesis = map[string]any{
	"title":      "百倍金狗基因",
	"promise":    "不预测谁会涨，只捕捉“现在买、100x 在几何上还做得到”的链上结构。",
	"disclaimer": "迷因币默认归零。高分只说明结构像历史百倍入口，不说明接下来会 100x。本工具不是投资建议。",
	"gates": []string{
		"市值 $5,000–$220,000：100x 后仍落在迷因币可实现终点（约 $50万–$2200万）",
		"开盘 6 分钟–36 小时：避开狙击带，也丢掉已经冷掉的微型盘",
		"必须看到真实独立买家；成交额畸高但地址极少视为骗量",
		"铸造/冻结权仍在、LP 未锁、或正在 5 分钟崩盘的直接淘汰",
		"相对典型 $5k 开盘已涨超过约 40x 的，从此处再 100x 视为幻想",
	},
	"genes": []map[string]string{
		{"id": "room", "name": "百倍空间", "why": "现价越低，100x 所需终点越接近真实 runner 顶部。最密的历史入口在 $8k–$35k。"},
		{"id": "window", "name": "黄金时间窗", "why": "12–90 分钟是人类可执行的发现盘；更早是捆绑，更晚要靠第二波叙事。"},
		{"id": "flow", "name": "真实买盘", "why": "独立买家增加且买卖比偏多，才是扩散；对倒只堆 volume。"},
		{"id": "liq", "name": "曲线/流动性", "why": "Pump 内盘 18%–72% 或外盘 LP 锁定，才能活到第二波。"},
		{"id": "sec", "name": "安全结构", "why": "丢铸造/冻结、LP 锁、持仓不过分集中，否则涨幅不属于你。"},
		{"id": "mom", "name": "动量结构", "why": "温和确认（1h +8%～+180%）优于垂直泡沫，也优于自由落体。"},
		{"id": "ignite", "name": "传播点火", "why": "社交/助推/评论只是乘数，不是入场理由。"},
	},
	"targets": map[string]int{"conservative": 1500000, "runner": 5000000, "stretch": 20000000},
}

type scanCache struct {
	mu      sync.Mutex
	at      time.Time
	payload map[string]any
}

var cache scanCache

func mergeUniverse(parts ...[]TokenSnapshot) map[string]TokenSnapshot {
	universe := map[string]TokenSnapshot{}
	for _, batch := range parts {
		for _, snap := range batch {
			prev, ok := universe[snap.Key()]
			if !ok {
				universe[snap.Key()] = snap
				continue
			}
			if snap.VolumeH1 > prev.VolumeH1 || snap.TxH1.Buyers > prev.TxH1.Buyers {
				if snap.Pump == nil {
					snap.Pump = prev.Pump
				}
				if snap.Security == nil {
					snap.Security = prev.Security
				}
				if snap.CreatedAtMs == 0 {
					snap.CreatedAtMs = prev.CreatedAtMs
				}
				if snap.Image == nil {
					snap.Image = prev.Image
				}
				universe[snap.Key()] = snap
			} else {
				if prev.Pump == nil {
					prev.Pump = snap.Pump
				}
				if prev.Image == nil {
					prev.Image = snap.Image
				}
				if len(prev.Socials) == 0 {
					prev.Socials = snap.Socials
				}
				universe[snap.Key()] = prev
			}
		}
	}
	return universe
}

func prefilter(snap TokenSnapshot) bool {
	mc := snap.Cap()
	if mc <= 0 || !allowedChains[snap.Chain] {
		return false
	}
	if mc < minMC*0.5 || mc > maxMC*1.6 {
		return false
	}
	return true
}

func runScan(force bool) map[string]any {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	if !force && cache.payload != nil && time.Since(cache.at) < cacheTTL {
		return cache.payload
	}
	t0 := time.Now()
	var errors []string
	var pump, gt []TokenSnapshot
	var discover []map[string]any
	var wg sync.WaitGroup
	wg.Add(3)
	go func() { defer wg.Done(); defer func() { recover() }(); pump = fetchPump() }()
	go func() { defer wg.Done(); defer func() { recover() }(); gt = fetchGecko() }()
	go func() { defer wg.Done(); defer func() { recover() }(); discover = fetchDiscoveryLists() }()
	wg.Wait()

	universe := mergeUniverse(pump, gt)
	dsAddrs := map[string][]string{}
	for _, item := range discover {
		chain := str(item["chainId"])
		addr := str(item["tokenAddress"])
		if chain != "" && addr != "" {
			dsAddrs[chain] = append(dsAddrs[chain], addr)
		}
	}
	n := 0
	for chain, addrs := range dsAddrs {
		if n >= 5 {
			break
		}
		n++
		if len(addrs) > 30 {
			addrs = addrs[:30]
		}
		for _, snap := range fetchPairsForTokens(chain, addrs) {
			snap.HasProfile = true
			if _, ok := universe[snap.Key()]; !ok {
				universe[snap.Key()] = snap
			}
		}
	}

	byChain := map[string][]string{}
	for _, snap := range universe {
		byChain[snap.Chain] = append(byChain[snap.Chain], snap.Address)
	}
	order := []string{"solana", "base", "bsc", "ethereum"}
	var chains []string
	seenC := map[string]bool{}
	for _, c := range order {
		if _, ok := byChain[c]; ok {
			chains = append(chains, c)
			seenC[c] = true
		}
	}
	for c := range byChain {
		if !seenC[c] {
			chains = append(chains, c)
		}
	}
	if len(chains) > 4 {
		chains = chains[:4]
	}
	for _, chain := range chains {
		addrs := byChain[chain]
		if len(addrs) > 80 {
			addrs = addrs[:80]
		}
		for _, ds := range fetchPairsForTokens(chain, addrs) {
			if prev, ok := universe[ds.Key()]; ok {
				overlayDex(&prev, ds)
				universe[ds.Key()] = prev
			} else {
				universe[ds.Key()] = ds
			}
		}
	}

	var candidates []TokenSnapshot
	for _, s := range universe {
		if prefilter(s) {
			candidates = append(candidates, s)
		}
	}
	ranked := rankTokens(candidates, 0)

	var targets []int
	for i, row := range ranked {
		if row.Score.Passed && row.Token.Chain == "solana" {
			targets = append(targets, i)
		}
		if len(targets) >= rugcheckTop {
			break
		}
	}
	if len(targets) == 0 {
		for i, row := range ranked {
			if row.Token.Chain == "solana" {
				targets = append(targets, i)
			}
			if len(targets) >= 8 {
				break
			}
		}
	}
	fns := make([]func() any, len(targets))
	for i, idx := range targets {
		tok := ranked[idx].Token
		fns[i] = func() any { return enrichSecurity(tok) }
	}
	reports := gather(4, fns)
	for i, idx := range targets {
		if sec, ok := reports[i].(*SecurityState); ok && sec != nil {
			ranked[idx].Token.Security = sec
			ranked[idx].Score = scoreToken(ranked[idx].Token, 0)
		}
	}
	ranked = rankTokens(tokensFromRanked(ranked), 0)

	passed := 0
	topScore := 0
	topGrade := "—"
	for _, r := range ranked {
		if r.Score.Passed {
			if passed == 0 {
				topScore = r.Score.Total
				topGrade = r.Score.Grade
			}
			passed++
		}
	}
	if len(ranked) > 80 {
		ranked = ranked[:80]
	}
	if errors == nil {
		errors = []string{}
	}
	payload := map[string]any{
		"scanned_at": time.Now().UnixMilli(),
		"elapsed_ms": time.Since(t0).Milliseconds(),
		"universe":   len(universe),
		"considered": len(candidates),
		"passed":     passed,
		"top_score":  topScore,
		"top_grade":  topGrade,
		"errors":     errors,
		"thesis":     thesis,
		"tokens":     ranked,
	}
	cache.at = time.Now()
	cache.payload = payload
	return payload
}

func tokensFromRanked(rows []RankedToken) []TokenSnapshot {
	out := make([]TokenSnapshot, len(rows))
	for i, r := range rows {
		out[i] = r.Token
	}
	return out
}
