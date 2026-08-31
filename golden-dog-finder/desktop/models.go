package main

type TxWindow struct {
	Buys    int `json:"buys"`
	Sells   int `json:"sells"`
	Buyers  int `json:"buyers"`
	Sellers int `json:"sellers"`
}

type PumpState struct {
	Complete     bool    `json:"complete"`
	RealSol      float64 `json:"real_sol"`
	ReplyCount   int     `json:"reply_count"`
	Livestream   bool    `json:"livestream"`
	NSFW         bool    `json:"nsfw"`
	BondingCurve *string `json:"bonding_curve"`
	Creator      *string `json:"creator"`
	AthMc        float64 `json:"ath_mc"`
}

type SecurityState struct {
	Rugged           bool     `json:"rugged"`
	Score            *int     `json:"score"`
	ScoreNormalised  *int     `json:"score_normalised"`
	MintAuthority    *string  `json:"mint_authority"`
	FreezeAuthority  *string  `json:"freeze_authority"`
	LpLockedPct      *float64 `json:"lp_locked_pct"`
	Holders          *int     `json:"holders"`
	TopHolderPct     *float64 `json:"top_holder_pct"`
	InsiderNetworks  *int     `json:"insider_networks"`
	Risks            []string `json:"risks"`
}

type Social struct {
	Type string `json:"type"`
	URL  string `json:"url"`
}

type TokenSnapshot struct {
	Chain         string         `json:"chain"`
	Address       string         `json:"address"`
	Symbol        string         `json:"symbol"`
	Name          string         `json:"name"`
	Dex           string         `json:"dex"`
	Source        string         `json:"source"`
	PairAddress   *string        `json:"pair_address"`
	PriceUSD      float64        `json:"price_usd"`
	MarketCapUSD  float64        `json:"market_cap_usd"`
	FdvUSD        float64        `json:"fdv_usd"`
	LiquidityUSD  *float64       `json:"liquidity_usd"`
	CreatedAtMs   int64          `json:"created_at_ms"`
	VolumeM5      float64        `json:"volume_m5"`
	VolumeH1      float64        `json:"volume_h1"`
	VolumeH6      float64        `json:"volume_h6"`
	VolumeH24     float64        `json:"volume_h24"`
	ChangeM5      float64        `json:"change_m5"`
	ChangeH1      float64        `json:"change_h1"`
	ChangeH6      float64        `json:"change_h6"`
	ChangeH24     float64        `json:"change_h24"`
	TxM5          TxWindow       `json:"tx_m5"`
	TxM15         TxWindow       `json:"tx_m15"`
	TxH1          TxWindow       `json:"tx_h1"`
	Image         *string        `json:"image"`
	Websites      []string       `json:"websites"`
	Socials       []Social       `json:"socials"`
	BoostAmount   int            `json:"boost_amount"`
	HasProfile    bool           `json:"has_profile"`
	Pump          *PumpState     `json:"pump"`
	Security      *SecurityState `json:"security"`
	URL           *string        `json:"url"`
}

func (t TokenSnapshot) Key() string {
	return t.Chain + ":" + toLower(t.Address)
}

func (t TokenSnapshot) Cap() float64 {
	if t.MarketCapUSD != 0 {
		return t.MarketCapUSD
	}
	return t.FdvUSD
}

type Gene struct {
	ID     string  `json:"id"`
	Name   string  `json:"name"`
	Score  float64 `json:"score"`
	Max    float64 `json:"max"`
	Reason string  `json:"reason"`
}

type ScoreCard struct {
	Total         int      `json:"total"`
	Grade         string   `json:"grade"`
	Passed        bool     `json:"passed"`
	KillReasons   []string `json:"kill_reasons"`
	Genes         []Gene   `json:"genes"`
	X100TargetMc  float64  `json:"x100_target_mc"`
	XIf1m5        float64  `json:"x_if_1m5"`
	XIf5m         float64  `json:"x_if_5m"`
	XIf20m        float64  `json:"x_if_20m"`
	Feasibility   float64  `json:"feasibility"`
	Band          string   `json:"band"`
	Verdict       string   `json:"verdict"`
	Thesis        string   `json:"thesis"`
}

type RankedToken struct {
	Token  TokenSnapshot `json:"token"`
	Score  ScoreCard     `json:"score"`
	AgeMin float64       `json:"age_min"`
}

func ptrStr(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

func ptrF(v float64) *float64 { return &v }

func toLower(s string) string {
	b := make([]byte, len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' {
			c += 'a' - 'A'
		}
		b[i] = c
	}
	return string(b)
}
