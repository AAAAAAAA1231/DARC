package main

// Pipeline 只保留筛选步骤：发现 → 年龄 → 叙事 → 数据 → 链上 → 聪明钱。
// 仓位、止盈止损不属于筛选顺序。
var Pipeline = []PipelineStep{
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
}

type PipelineStep struct {
	Index   int    `json:"index"`
	ID      string `json:"id"`
	Title   string `json:"title"`
	Kind    string `json:"kind"` // auto / semi
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
