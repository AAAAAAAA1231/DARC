package main

// Pipeline 是加密狗 @jiamigou 2026-07-09 长文
// 《Robinhood Chain 「Memecoin」打新--保姆级教程（全流程）》里固化的发现顺序。
// 原文强调：看到新币后必须按顺序检查，而不是只看市值或 K 线。
var Pipeline = []PipelineStep{
	{
		Index:   0,
		ID:      "prep",
		Title:   "上场准备",
		Kind:    "manual",
		Summary: "钱包加入 Robinhood Chain，再跨入少量 ETH。没有 gas 就不要扫链。",
		Quote:   "网络名称：Robinhood Chain；RPC：rpc.mainnet.chain.robinhood.com；Chain ID：4663；货币符号：ETH。",
		Links: []Link{
			{Label: "官方跨链文档", URL: "https://docs.robinhood.com/chain/bridging/"},
			{Label: "Relay 桥", URL: "https://relay.link/bridge/robinhood"},
			{Label: "Arbitrum 桥", URL: "https://portal.arbitrum.io/bridge"},
			{Label: "Uniswap", URL: "https://app.uniswap.org/swap"},
		},
	},
	{
		Index:   1,
		ID:      "watch",
		Title:   "双监控发现",
		Kind:    "auto",
		Summary: "同时打开 Dexscreener 新交易对 + NOXA Fun 热门。BasedBot / GMGN 作为辅助入口。",
		Quote:   "（一）打开监控页面：Dexscreener Robinhood New Pairs + NOXA Fun Trending。",
		Links: []Link{
			{Label: "Dexscreener 新对", URL: "https://dexscreener.com/new-pairs/robinhood"},
			{Label: "NOXA Fun", URL: "https://fun.noxa.fi/robinhood"},
			{Label: "BasedBot", URL: "https://basedbot.app/robinhood"},
			{Label: "GMGN", URL: "https://gmgn.ai"},
		},
	},
	{
		Index:   2,
		ID:      "age",
		Title:   "年龄窗口",
		Kind:    "auto",
		Summary: "实时刷新，只盯新出现的池。越新潜力越大，但也更危险。",
		Quote:   "（二）实时刷新，关注新出现的对（年龄 < 30 分钟）。筛选建议：5–60 分钟。太老机会小。",
	},
	{
		Index:   3,
		ID:      "narrative",
		Title:   "叙事快筛",
		Kind:    "auto",
		Summary: "30 秒判断：有没有 Twitter/TG，叙事是否跟 Robinhood / GME / 官方 / 猫狗有关。",
		Quote:   "有无社交链接（Twitter/TG）吗？叙述是否强（Robinhood/GME/官方相关）？搜 X《$币名Robinhood》有没有热度？",
	},
	{
		Index:   4,
		ID:      "data",
		Title:   "数据确认",
		Kind:    "auto",
		Summary: "交易量上升且买入主导，持有人在增加，市值仍处早期（几万到百万美金）。",
		Quote:   "交易量上升+买入多；持有人数快速增加；市值低（早期几万到百万美元）。",
	},
	{
		Index:   5,
		ID:      "onchain",
		Title:   "链上核查",
		Kind:    "auto",
		Summary: "CA 丢进 Blockscout：前十大持仓是否过度集中，创建者有没有狂卖。流动性相对市值要健康。",
		Quote:   "看持有者：前 10 个太集中。看创造者有没有狂卖。流动性才是关键——宁可交易市值较低但流动性更高的币。",
		Links: []Link{
			{Label: "Blockscout", URL: "https://robinhoodchain.blockscout.com"},
		},
	},
	{
		Index:   6,
		ID:      "smart",
		Title:   "聪明钱确认",
		Kind:    "semi",
		Summary: "去 GMGN 看聪明钱有没有买、有没有地毯/蜜罐警告。本工具不自动跟单。",
		Quote:   "（5）GMGN 确认：聪明钱有没有买？有没有地毯警告？蜜罐或高税费（用工具扫描）。",
		Links: []Link{
			{Label: "GMGN", URL: "https://gmgn.ai"},
		},
	},
	{
		Index:   7,
		ID:      "size",
		Title:   "小仓试探",
		Kind:    "advice",
		Summary: "只拿总资金 1–2% 试水。出现开发者抛售、极端集中、无叙事、可撤池、蜜罐则立即回避。",
		Quote:   "（6）只买小仓：先买总资金的 1-2% 测试。永远小额测试+分批操作。",
	},
	{
		Index:   8,
		ID:      "exit",
		Title:   "止盈止损",
		Kind:    "advice",
		Summary: "2x 卖 30%，5x 卖 30%，10x 卖剩余；跌 50% 坚决走。同时看 3–5 个币，不要全仓一只。",
		Quote:   "止盈：涨 2x 卖 30%、5x 卖 30%、10x 卖剩余。止损：跌 50% 坚决卖。分散：同时看 3-5 个币。",
	},
}

type PipelineStep struct {
	Index   int    `json:"index"`
	ID      string `json:"id"`
	Title   string `json:"title"`
	Kind    string `json:"kind"` // manual / auto / semi / advice
	Summary string `json:"summary"`
	Quote   string `json:"quote"`
	Links   []Link `json:"links,omitempty"`
}

type Link struct {
	Label string `json:"label"`
	URL   string `json:"url"`
}

type ChainMeta struct {
	Name      string `json:"name"`
	RPC       string `json:"rpc"`
	ChainID   int    `json:"chainId"`
	Symbol    string `json:"symbol"`
	Explorer  string `json:"explorer"`
	DexNew    string `json:"dexNewPairs"`
	Noxa      string `json:"noxa"`
	BasedBot  string `json:"basedBot"`
	GMGN      string `json:"gmgn"`
	SourceURL string `json:"sourceUrl"`
}

var Chain = ChainMeta{
	Name:      "Robinhood Chain",
	RPC:       "https://rpc.mainnet.chain.robinhood.com",
	ChainID:   4663,
	Symbol:    "ETH",
	Explorer:  "https://robinhoodchain.blockscout.com",
	DexNew:    "https://dexscreener.com/new-pairs/robinhood",
	Noxa:      "https://fun.noxa.fi/robinhood",
	BasedBot:  "https://basedbot.app/robinhood",
	GMGN:      "https://gmgn.ai",
	SourceURL: "https://x.com/jiamigou/status/2075057589457735949",
}
