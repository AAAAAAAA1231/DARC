package main

import (
	"fmt"
	"math"
	"math/big"
	"strings"
	"time"
)

const (
	VerdictGold  = "gold"  // 金狗候选
	VerdictWatch = "watch" // 观察
	VerdictAvoid = "avoid" // 回避
	VerdictStale = "stale" // 窗口已过
)

// TokenSnapshot 是公开行情快照，供评分流水线使用。
type TokenSnapshot struct {
	Name          string
	Symbol        string
	Address       string
	PairAddress   string
	DEX           string
	CreatedAt     time.Time
	PriceUSD      float64
	MarketCap     float64
	FDV           float64
	LiquidityUSD  float64
	VolumeM5      float64
	VolumeH1      float64
	VolumeH6      float64
	VolumeH24     float64
	BuysM5        int
	SellsM5       int
	BuysH1        int
	SellsH1       int
	BuysH6        int
	SellsH6       int
	PriceChangeH1 float64
	HasTwitter    bool
	HasTelegram   bool
	HasWebsite    bool
	TwitterURL    string
	TelegramURL   string
	WebsiteURL    string
	ImageURL      string
	Description   string
	Holders       int
	Top10Share    float64 // 0-1, excluding largest LP contract if known
	LPShare       float64
	HoldersKnown  bool
}

type Check struct {
	ID     string `json:"id"`
	Title  string `json:"title"`
	Pass   bool   `json:"pass"`
	Skip   bool   `json:"skip"`
	Detail string `json:"detail"`
	Points int    `json:"points"`
}

type Candidate struct {
	Symbol       string            `json:"symbol"`
	Name         string            `json:"name"`
	Address      string            `json:"address"`
	PairAddress  string            `json:"pairAddress"`
	DEX          string            `json:"dex"`
	AgeMinutes   float64           `json:"ageMinutes"`
	AgeLabel     string            `json:"ageLabel"`
	PriceUSD     float64           `json:"priceUsd"`
	MarketCap    float64           `json:"marketCap"`
	LiquidityUSD float64           `json:"liquidityUsd"`
	LiqMCRatio   float64           `json:"liqMcRatio"`
	VolumeH1     float64           `json:"volumeH1"`
	BuysH1       int               `json:"buysH1"`
	SellsH1      int               `json:"sellsH1"`
	Holders      int               `json:"holders"`
	Top10Share   float64           `json:"top10Share"`
	Score        int               `json:"score"`
	Verdict      string            `json:"verdict"`
	VerdictLabel string            `json:"verdictLabel"`
	Stage        int               `json:"stage"`
	StageTitle   string            `json:"stageTitle"`
	Flags        []string          `json:"flags"`
	Checks       []Check           `json:"checks"`
	Links        map[string]string `json:"links"`
	ImageURL     string            `json:"imageUrl"`
	HasTwitter   bool              `json:"hasTwitter"`
	HasTelegram  bool              `json:"hasTelegram"`
	HasWebsite   bool              `json:"hasWebsite"`
}

func Evaluate(t TokenSnapshot, now time.Time) Candidate {
	if now.IsZero() {
		now = time.Now()
	}
	age := now.Sub(t.CreatedAt)
	if t.CreatedAt.IsZero() {
		age = 24 * time.Hour
	}
	ageMin := age.Minutes()

	c := Candidate{
		Symbol:       t.Symbol,
		Name:         t.Name,
		Address:      t.Address,
		PairAddress:  t.PairAddress,
		DEX:          t.DEX,
		AgeMinutes:   ageMin,
		AgeLabel:     formatAge(age),
		PriceUSD:     t.PriceUSD,
		MarketCap:    t.MarketCap,
		LiquidityUSD: t.LiquidityUSD,
		VolumeH1:     t.VolumeH1,
		BuysH1:       t.BuysH1,
		SellsH1:      t.SellsH1,
		Holders:      t.Holders,
		Top10Share:   t.Top10Share,
		ImageURL:     t.ImageURL,
		HasTwitter:   t.HasTwitter,
		HasTelegram:  t.HasTelegram,
		HasWebsite:   t.HasWebsite,
		Flags:        []string{},
		Links:        tokenLinks(t),
	}
	if t.MarketCap > 0 {
		c.LiqMCRatio = t.LiquidityUSD / t.MarketCap
	}

	ageCheck := scoreAge(ageMin)
	narrCheck := scoreNarrative(t)
	dataCheck := scoreData(t)
	chainCheck := scoreOnchain(t)
	smartCheck := scoreSmart(t)

	c.Checks = []Check{ageCheck, narrCheck, dataCheck, chainCheck, smartCheck}

	avoid := false
	if !ageCheck.Pass && ageMin > 6*60 {
		c.Flags = append(c.Flags, "窗口已过：帖子写明太老机会小")
	}
	if !narrCheck.Pass {
		c.Flags = append(c.Flags, "叙事/社交偏弱")
	}
	if t.SellsH1 > 0 && t.BuysH1*2 < t.SellsH1 {
		c.Flags = append(c.Flags, "卖盘主导")
		avoid = true
	}
	if t.MarketCap >= 5000 && t.LiquidityUSD > 0 && t.LiquidityUSD/t.MarketCap < 0.05 {
		c.Flags = append(c.Flags, "有价无市：流动性相对市值过低")
		avoid = true
	}
	if t.HoldersKnown && t.Top10Share >= 0.45 {
		c.Flags = append(c.Flags, "前十大持仓过度集中")
		avoid = true
	}
	if !t.HasTwitter && !t.HasTelegram && !t.HasWebsite && !narrCheck.Pass {
		c.Flags = append(c.Flags, "无社交/无叙事，疑似虚假流量")
		avoid = true
	}

	score := 0
	for _, ch := range c.Checks {
		score += ch.Points
	}
	if score < 0 {
		score = 0
	}
	if score > 100 {
		score = 100
	}
	c.Score = score

	// 发现进度：从第 2 步年龄开始，连续通过才算走到哪一步。
	stage := 1 // 已被双监控发现
	if ageCheck.Pass {
		stage = 2
		if narrCheck.Pass {
			stage = 3
			if dataCheck.Pass {
				stage = 4
				if chainCheck.Pass {
					stage = 5
					if smartCheck.Pass {
						stage = 6
					}
				}
			}
		}
	}
	c.Stage = stage
	c.StageTitle = stageTitle(stage)

	switch {
	case avoid || score < 38:
		c.Verdict = VerdictAvoid
		c.VerdictLabel = "回避"
	case !ageCheck.Pass && ageMin >= 180:
		c.Verdict = VerdictStale
		c.VerdictLabel = "窗口已过"
	case score >= 62 && stage >= 5:
		// 必须按原文顺序连续过完：年龄 → 叙事 → 数据 → 链上，才能叫金狗候选。
		c.Verdict = VerdictGold
		c.VerdictLabel = "金狗候选"
	default:
		c.Verdict = VerdictWatch
		c.VerdictLabel = "观察"
	}
	return c
}

func stageTitle(stage int) string {
	titles := map[int]string{
		1: "已发现，待过年龄窗",
		2: "年龄合格，待叙事",
		3: "叙事过关，待数据",
		4: "数据过关，待链上",
		5: "链上过关，待聪明钱",
		6: "筛选通过",
	}
	if s, ok := titles[stage]; ok {
		return s
	}
	return "排队中"
}

func scoreAge(ageMin float64) Check {
	ch := Check{ID: "age", Title: "（1）年龄：小于 30 分钟"}
	switch {
	case ageMin < 0:
		ageMin = 0
		fallthrough
	case ageMin <= 30:
		ch.Pass = true
		ch.Points = 26
		ch.Detail = fmt.Sprintf("已诞生 %.0f 分钟，落在帖子强调的黄金窗口（<30 分钟）。", ageMin)
	case ageMin <= 60:
		ch.Pass = true
		ch.Points = 16
		ch.Detail = fmt.Sprintf("已诞生 %.0f 分钟，仍在 Dexscreener 建议的 5–60 分钟观察带。", ageMin)
	case ageMin <= 180:
		ch.Pass = false
		ch.Points = 6
		ch.Detail = fmt.Sprintf("已诞生 %.0f 分钟，窗口开始变老，机会下降。", ageMin)
	default:
		ch.Pass = false
		ch.Points = 0
		ch.Detail = fmt.Sprintf("已诞生 %s，原文：太老机会小。", formatAge(time.Duration(ageMin)*time.Minute))
	}
	return ch
}

func scoreNarrative(t TokenSnapshot) Check {
	ch := Check{ID: "narrative", Title: "（2）记述：Robinhood / GME / 官方 / 猫狗"}
	blob := strings.ToLower(strings.Join([]string{t.Name, t.Symbol, t.Description}, " "))
	hits := []string{}
	points := 0

	strong := []struct {
		keys []string
		tag  string
		pts  int
	}{
		{[]string{"cashcat", "cash cat"}, "CASHCAT 龙头叙事", 10},
		{[]string{"gme", "gamestop"}, "GME 相关", 10},
		{[]string{"dih"}, "DIH 热门", 6},
		{[]string{"robinhood", "robin hood"}, "Robinhood 官方相关", 10},
		{[]string{"hood"}, "HOOD 相关", 6},
		{[]string{"vlad", "tenev", "ceo"}, "官方人物暗示", 8},
		{[]string{"cat", "kitten", "neko", "猫"}, "猫叙事", 5},
		{[]string{"dog", "doge", "shib", "inu", "狗"}, "狗叙事", 5},
	}
	seen := map[string]bool{}
	for _, s := range strong {
		for _, k := range s.keys {
			if strings.Contains(blob, k) && !seen[s.tag] {
				seen[s.tag] = true
				hits = append(hits, s.tag)
				points += s.pts
				break
			}
		}
	}
	social := 0
	if t.HasTwitter {
		social += 6
		hits = append(hits, "有 Twitter")
	}
	if t.HasTelegram {
		social += 4
		hits = append(hits, "有 Telegram")
	}
	if t.HasWebsite {
		social += 3
		hits = append(hits, "有官网")
	}
	points += social
	if points > 22 {
		points = 22
	}
	ch.Points = points
	ch.Pass = points >= 8 && (len(seen) > 0 || t.HasTwitter || t.HasTelegram)
	if len(hits) == 0 {
		ch.Detail = "未发现社交链接，也没有 Robinhood/GME/猫狗等强叙事。"
	} else {
		ch.Detail = "命中：" + strings.Join(hits, "、")
	}
	return ch
}

func scoreData(t TokenSnapshot) Check {
	ch := Check{ID: "data", Title: "（3）数据：量能上升 + 买入主导 + 早期市值"}
	points := 0
	parts := []string{}

	buys := t.BuysH1
	sells := t.SellsH1
	if buys+sells == 0 {
		buys, sells = t.BuysM5, t.SellsM5
	}
	if buys > sells && buys+sells >= 3 {
		points += 10
		parts = append(parts, fmt.Sprintf("买入主导（买 %d / 卖 %d）", buys, sells))
	} else if buys+sells == 0 {
		parts = append(parts, "近 1 小时几乎没有成交")
	} else {
		parts = append(parts, fmt.Sprintf("买 %d / 卖 %d，买盘不够强", buys, sells))
	}

	// 交易量上升：1 小时量如果按 6 小时节奏外推，应接近或超过 6 小时量。
	if t.VolumeH1 > 0 && t.VolumeH6 > 0 && t.VolumeH1*6 >= t.VolumeH6*0.85 {
		points += 8
		parts = append(parts, "短时成交量在抬升")
	} else if t.VolumeM5 > 0 && t.VolumeH1 > 0 && t.VolumeM5*12 >= t.VolumeH1*0.6 {
		points += 5
		parts = append(parts, "5 分钟仍有活跃成交")
	} else if t.VolumeH1 >= 8000 {
		points += 4
		parts = append(parts, "1 小时仍有一定成交额")
	}

	mc := t.MarketCap
	if mc <= 0 {
		mc = t.FDV
	}
	switch {
	case mc >= 10000 && mc <= 1_000_000:
		points += 8
		parts = append(parts, fmt.Sprintf("市值 $%s，仍处早期区间", compactUSD(mc)))
	case mc > 0 && mc < 10000:
		points += 5
		parts = append(parts, fmt.Sprintf("市值 $%s，极早期、风险也更大", compactUSD(mc)))
	case mc > 1_000_000 && mc <= 5_000_000:
		points += 2
		parts = append(parts, fmt.Sprintf("市值 $%s，已离开最早窗口", compactUSD(mc)))
	case mc > 5_000_000:
		parts = append(parts, fmt.Sprintf("市值 $%s，更像成熟盘而不是打新", compactUSD(mc)))
	default:
		parts = append(parts, "市值数据缺失")
	}

	if t.HoldersKnown && t.Holders >= 40 && t.Holders < 4000 {
		points += 4
		parts = append(parts, fmt.Sprintf("持有人 %d，有扩散迹象", t.Holders))
	}

	if points > 24 {
		points = 24
	}
	ch.Points = points
	ch.Pass = points >= 12
	ch.Detail = strings.Join(parts, "；")
	return ch
}

func scoreOnchain(t TokenSnapshot) Check {
	ch := Check{ID: "onchain", Title: "（4）链上：持仓 + 流动性健康度"}
	points := 0
	parts := []string{}

	mc := t.MarketCap
	if mc <= 0 {
		mc = t.FDV
	}
	ratio := 0.0
	if mc > 0 {
		ratio = t.LiquidityUSD / mc
	}

	// 原文例子：A 市值 100 万 / 流动 10 万（10%）不如 B 市值 60 万 / 流动 30 万（50%）。
	switch {
	case t.LiquidityUSD <= 0:
		parts = append(parts, "读不到流动性")
	case ratio >= 0.25:
		points += 14
		parts = append(parts, fmt.Sprintf("流动性/市值 %.0f%%，价格发现更健康", ratio*100))
	case ratio >= 0.12:
		points += 9
		parts = append(parts, fmt.Sprintf("流动性/市值 %.0f%%，尚可", ratio*100))
	case ratio >= 0.05:
		points += 4
		parts = append(parts, fmt.Sprintf("流动性/市值 %.0f%%，偏薄", ratio*100))
	default:
		parts = append(parts, fmt.Sprintf("流动性/市值仅 %.1f%%，接近有价无市", ratio*100))
	}

	if t.LiquidityUSD >= 15000 {
		points += 4
		parts = append(parts, fmt.Sprintf("池深 $%s", compactUSD(t.LiquidityUSD)))
	} else if t.LiquidityUSD > 0 && t.LiquidityUSD < 3000 {
		parts = append(parts, "池子很浅，容易被抽干")
	}

	if t.HoldersKnown {
		if t.Top10Share > 0 && t.Top10Share < 0.35 {
			points += 6
			parts = append(parts, fmt.Sprintf("前十大（剔除 LP）约占 %.0f%%，分散尚可", t.Top10Share*100))
		} else if t.Top10Share >= 0.45 {
			parts = append(parts, fmt.Sprintf("前十大（剔除 LP）约占 %.0f%%，过度集中", t.Top10Share*100))
		} else if t.Top10Share > 0 {
			points += 2
			parts = append(parts, fmt.Sprintf("前十大（剔除 LP）约占 %.0f%%", t.Top10Share*100))
		}
		if t.Holders > 0 {
			parts = append(parts, fmt.Sprintf("持有人 %d", t.Holders))
		}
	} else {
		ch.Skip = true
		parts = append(parts, "持仓明细需点开「深查」或去 Blockscout 人工确认创建者是否在砸盘")
	}

	if points > 20 {
		points = 20
	}
	ch.Points = points
	ch.Pass = t.LiquidityUSD >= 2000 && (ratio >= 0.08 || t.LiquidityUSD >= 20000)
	if t.HoldersKnown && t.Top10Share >= 0.45 {
		ch.Pass = false
	}
	ch.Detail = strings.Join(parts, "；")
	return ch
}

func scoreSmart(t TokenSnapshot) Check {
	ch := Check{
		ID:     "smart",
		Title:  "（5）GMGN：聪明钱 / 地毯警告",
		Skip:   true,
		Pass:   true, // 不阻断流水线，但不得分冒充已确认
		Points: 4,
		Detail: "公开接口拿不到 GMGN 聪明钱与蜜罐扫描。请用右侧链接人工确认。本工具只做筛选，不自动买入。",
	}
	_ = t
	return ch
}

func tokenLinks(t TokenSnapshot) map[string]string {
	ca := t.Address
	links := map[string]string{
		"dexscreener": fmt.Sprintf("https://dexscreener.com/robinhood/%s", strings.ToLower(t.PairAddress)),
		"newPairs":    "https://dexscreener.com/new-pairs/robinhood",
		"noxa":        "https://fun.noxa.fi/robinhood",
		"basedbot":    "https://basedbot.app/robinhood",
		"gmgn":        "https://gmgn.ai",
		"blockscout":  fmt.Sprintf("https://robinhoodchain.blockscout.com/token/%s", ca),
		"xSearch":     fmt.Sprintf("https://x.com/search?q=$%s%%20Robinhood&src=typed_query&f=live", t.Symbol),
	}
	if t.PairAddress == "" {
		links["dexscreener"] = fmt.Sprintf("https://dexscreener.com/robinhood/%s", strings.ToLower(ca))
	}
	if t.TwitterURL != "" {
		links["twitter"] = t.TwitterURL
	}
	if t.TelegramURL != "" {
		links["telegram"] = t.TelegramURL
	}
	if t.WebsiteURL != "" {
		links["website"] = t.WebsiteURL
	}
	return links
}

func formatAge(d time.Duration) string {
	if d < 0 {
		d = 0
	}
	m := int(d.Minutes())
	switch {
	case m < 1:
		return "刚刚"
	case m < 60:
		return fmt.Sprintf("%d 分钟", m)
	case m < 24*60:
		return fmt.Sprintf("%d 小时 %d 分", m/60, m%60)
	default:
		return fmt.Sprintf("%d 天", m/1440)
	}
}

func compactUSD(v float64) string {
	if v >= 1_000_000 {
		return fmt.Sprintf("%.2fM", v/1_000_000)
	}
	if v >= 1000 {
		return fmt.Sprintf("%.1fK", v/1000)
	}
	return fmt.Sprintf("%.0f", v)
}

func holderShare(values []string, totalSupply string, skipFirstContract bool) (top10 float64, lpShare float64) {
	total, ok := new(big.Float).SetString(totalSupply)
	if !ok || total.Cmp(big.NewFloat(0)) <= 0 {
		return 0, 0
	}
	sum := new(big.Float)
	start := 0
	if skipFirstContract && len(values) > 0 {
		lp, ok := new(big.Float).SetString(values[0])
		if ok {
			lpShare, _ = new(big.Float).Quo(lp, total).Float64()
			start = 1
		}
	}
	limit := start + 10
	if limit > len(values) {
		limit = len(values)
	}
	for i := start; i < limit; i++ {
		v, ok := new(big.Float).SetString(values[i])
		if !ok {
			continue
		}
		sum.Add(sum, v)
	}
	top10, _ = new(big.Float).Quo(sum, total).Float64()
	if math.IsNaN(top10) || math.IsInf(top10, 0) {
		return 0, lpShare
	}
	return top10, lpShare
}
