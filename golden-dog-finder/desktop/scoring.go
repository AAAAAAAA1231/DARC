package main

import (
	"fmt"
	"math"
	"sort"
	"strings"
	"time"
)

const (
	minMC            = 5000.0
	maxMC            = 220000.0
	minAgeSec        = 6 * 60
	maxAgeSec        = 36 * 3600
	typicalLaunchMC  = 5000.0
	conservativeTop  = 1500000.0
	baseRunnerTop    = 5000000.0
	stretchTop       = 20000000.0
	pumpGraduateSol  = 85.0
)

var junkBase = map[string]bool{
	"sol": true, "wsol": true, "eth": true, "weth": true, "bnb": true, "wbnb": true,
	"usdc": true, "usdt": true, "dai": true, "usd1": true, "wbtc": true, "btc": true,
}

func clamp(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func ratio(a, b float64) float64 {
	if b <= 0 {
		return 0
	}
	return a / b
}

func comma0(v float64) string {
	n := int64(math.Round(v))
	neg := n < 0
	if neg {
		n = -n
	}
	s := fmt.Sprintf("%d", n)
	var out []byte
	for i, c := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			out = append(out, ',')
		}
		out = append(out, byte(c))
	}
	if neg {
		return "-" + string(out)
	}
	return string(out)
}

func ageSeconds(token TokenSnapshot, nowMs int64) float64 {
	if nowMs == 0 {
		nowMs = time.Now().UnixMilli()
	}
	if token.CreatedAtMs <= 0 {
		return 0
	}
	a := float64(nowMs-token.CreatedAtMs) / 1000.0
	if a < 0 {
		return 0
	}
	return a
}

func band(mc float64) string {
	if mc <= 25000 {
		return "激进百倍仓"
	}
	if mc <= 80000 {
		return "标准百倍仓"
	}
	return "长尾百倍仓"
}

func grade(total int, passed bool) string {
	if !passed {
		return "X"
	}
	if total >= 82 {
		return "S"
	}
	if total >= 70 {
		return "A"
	}
	if total >= 58 {
		return "B"
	}
	if total >= 45 {
		return "C"
	}
	return "D"
}

func pumpProgress(token TokenSnapshot) *float64 {
	if token.Pump == nil {
		return nil
	}
	if token.Pump.Complete {
		v := 1.0
		return &v
	}
	if token.Pump.RealSol > 0 {
		v := clamp(token.Pump.RealSol/pumpGraduateSol, 0, 1)
		return &v
	}
	mc := token.Cap()
	if mc > 0 {
		v := clamp(mc/69000.0, 0, 1)
		return &v
	}
	return nil
}

func txPressure(tx TxWindow) (float64, int) {
	buys := tx.Buys + tx.Sells
	if buys <= 0 {
		return 0, tx.Buyers
	}
	return float64(tx.Buys) / float64(buys), tx.Buyers
}

func alreadyExtended(mc float64) float64 { return ratio(mc, typicalLaunchMC) }

func present(s *string) bool { return s != nil && *s != "" }

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func maxF(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

func hardKills(token TokenSnapshot, ageSec float64) []string {
	var reasons []string
	mc := token.Cap()
	symbol := strings.TrimSpace(strings.ToLower(token.Symbol))
	name := strings.TrimSpace(strings.ToLower(token.Name))
	if junkBase[symbol] || junkBase[name] {
		reasons = append(reasons, "报价资产/稳定币，不是迷因标的")
	}
	if mc < minMC {
		reasons = append(reasons, fmt.Sprintf("市值 $%s 过低，更像空池或骗量，不是可执行的百倍入口", comma0(mc)))
	}
	if mc > maxMC {
		reasons = append(reasons, fmt.Sprintf("市值 $%s 再 100x 需要 $%s，超出迷因币常态终点", comma0(mc), comma0(mc*100)))
	}
	if ageSec > 0 && ageSec < minAgeSec {
		reasons = append(reasons, "开盘不足 6 分钟，仍在狙击/捆绑抛压带，不作为百倍入口")
	}
	if ageSec > maxAgeSec {
		reasons = append(reasons, "已超过 36 小时仍是微型盘，百倍窗口大概率已经关闭")
	}
	if token.LiquidityUSD != nil && *token.LiquidityUSD < 0 {
		reasons = append(reasons, "池子储备异常（负流动性），数据不可交易")
	}
	if token.Pump != nil && token.Pump.NSFW {
		reasons = append(reasons, "标记 NSFW，排除")
	}
	if sec := token.Security; sec != nil {
		if sec.Rugged {
			reasons = append(reasons, "RugCheck 标记 rugged")
		}
		if present(sec.FreezeAuthority) {
			reasons = append(reasons, "冻账户权限未丢，可一键锁卖")
		}
		if present(sec.MintAuthority) && !(token.Pump != nil && !token.Pump.Complete) {
			reasons = append(reasons, "增发权限未丢，可无限稀释")
		}
		if sec.LpLockedPct != nil && *sec.LpLockedPct < 80 && token.Pump == nil {
			reasons = append(reasons, fmt.Sprintf("LP 仅锁定 %.0f%%，微型盘可直接撤池", *sec.LpLockedPct))
		}
		var severe []string
		for _, r := range sec.Risks {
			low := strings.ToLower(r)
			if strings.Contains(low, "honeypot") || strings.Contains(low, "scam") || strings.Contains(low, "rug") || strings.Contains(low, "freeze") || strings.Contains(low, "mint") {
				severe = append(severe, r)
			}
		}
		if len(severe) > 0 {
			if len(severe) > 3 {
				severe = severe[:3]
			}
			reasons = append(reasons, "安全扫描命中高危项: "+strings.Join(severe, ", "))
		}
		if sec.TopHolderPct != nil && *sec.TopHolderPct >= 35 && token.Pump == nil {
			reasons = append(reasons, fmt.Sprintf("最大持仓 %.0f%%（非曲线仓），筹码过于集中", *sec.TopHolderPct))
		}
	}
	buyers := maxInt(token.TxM5.Buyers, maxInt(token.TxM15.Buyers, token.TxH1.Buyers))
	buys := maxInt(token.TxM5.Buys, maxInt(token.TxM15.Buys, token.TxH1.Buys))
	crowd := buyers
	if crowd == 0 {
		crowd = buys
	}
	if crowd < 5 && token.VolumeH1 < 400 {
		reasons = append(reasons, "几乎没有真实买盘，更像死盘或自买自卖")
	}
	if token.VolumeH1 > 0 && mc > 0 && token.VolumeH1 > mc*40 && buyers < 12 {
		reasons = append(reasons, "成交额相对市值夸张且独立买家过少，骗量特征")
	}
	if token.ChangeM5 <= -40 && token.TxM5.Sells > token.TxM5.Buys {
		reasons = append(reasons, "5 分钟暴跌且卖盘主导，正在出货")
	}
	if alreadyExtended(mc) >= 40 {
		reasons = append(reasons, fmt.Sprintf("相对典型开盘市值已涨约 %.0fx，从此处再 100x 需要百亿级终点", alreadyExtended(mc)))
	}
	return reasons
}

func geneRoom(mc float64) Gene {
	x100 := mc * 100
	var score float64
	var reason string
	switch {
	case mc >= 8000 && mc <= 35000:
		score, reason = 24, fmt.Sprintf("现价市值 $%s，100x 只需到 $%s，落在迷因币最常见的局部顶部带", comma0(mc), comma0(x100))
	case mc >= 5000 && mc < 8000:
		score, reason = 18, fmt.Sprintf("市值 $%s 极早，100x 空间最大，但空池/砸盘概率同步升高", comma0(mc))
	case mc > 35000 && mc <= 80000:
		score, reason = 16, fmt.Sprintf("市值 $%s，100x 对应 $%s，需要成为出圈 runner", comma0(mc), comma0(x100))
	case mc > 80000 && mc <= 150000:
		score, reason = 9, fmt.Sprintf("市值 $%s，100x 对应 $%s，只有强叙事/CEX 级传播才够得到", comma0(mc), comma0(x100))
	default:
		score, reason = 4, fmt.Sprintf("市值 $%s 对 100x 已经偏贵", comma0(mc))
	}
	return Gene{"room", "百倍空间", score, 24, reason}
}

func geneWindow(ageSec float64) Gene {
	minutes := ageSec / 60
	var score float64
	var reason string
	switch {
	case minutes >= 12 && minutes <= 90:
		score, reason = 14, fmt.Sprintf("已开盘 %.0f 分钟：狙击盘出完，第二波发现盘通常在这一段", minutes)
	case minutes >= 8 && minutes < 12:
		score, reason = 10, fmt.Sprintf("开盘 %.0f 分钟，刚离开捆绑区，仍要防第一波砸盘", minutes)
	case minutes > 90 && minutes <= 360:
		score, reason = 11, fmt.Sprintf("开盘 %.0f 分钟，若买盘仍在加速，属于延续型百倍窗口", minutes)
	case minutes >= 6 && minutes < 8:
		score, reason = 7, fmt.Sprintf("开盘仅 %.0f 分钟，时间窗边缘", minutes)
	case minutes > 360 && minutes <= 720:
		score, reason = 7, fmt.Sprintf("开盘 %.1f 小时，窗口在收，必须看到持续独立买家", minutes/60)
	default:
		score, reason = 3, fmt.Sprintf("开盘 %.0f 分钟，不在黄金发现带", minutes)
	}
	return Gene{"window", "黄金时间窗", score, 14, reason}
}

func geneFlow(token TokenSnapshot) Gene {
	p5, b5 := txPressure(token.TxM5)
	p15, b15 := txPressure(token.TxM15)
	p1, b1 := txPressure(token.TxH1)
	uniqueKnown := maxInt(b5, maxInt(b15, b1)) > 0
	fills := maxInt(token.TxM5.Buys, maxInt(token.TxM15.Buys, token.TxH1.Buys))
	buyers := maxInt(b5, maxInt(b15, b1))
	uniqueVsFills := 0.45
	if uniqueKnown {
		uniqueVsFills = ratio(float64(buyers), float64(maxInt(fills, 1)))
	} else {
		buyers = fills
	}
	score := 0.0
	var bits []string
	if buyers >= 40 {
		score += 7
		bits = append(bits, fmt.Sprintf("%d 个独立买家，像扩散而不是对倒", buyers))
	} else if buyers >= 18 {
		score += 5
		bits = append(bits, fmt.Sprintf("%d 个独立买家，初步扩散", buyers))
	} else if buyers >= 8 {
		score += 3
		bits = append(bits, fmt.Sprintf("仅 %d 个独立买家，热度刚起", buyers))
	} else {
		bits = append(bits, fmt.Sprintf("独立买家 %d，热度不足", buyers))
	}
	pressure := p5
	if pressure == 0 {
		pressure = p15
	}
	if pressure == 0 {
		pressure = p1
	}
	if pressure >= 0.68 {
		score += 6
		bits = append(bits, fmt.Sprintf("买盘占比 %.0f%%，主动买入", pressure*100))
	} else if pressure >= 0.55 {
		score += 4
		bits = append(bits, fmt.Sprintf("买盘占比 %.0f%%，略偏多", pressure*100))
	} else if pressure >= 0.45 {
		score += 2
		bits = append(bits, fmt.Sprintf("买盘占比 %.0f%%，拉锯", pressure*100))
	} else {
		bits = append(bits, fmt.Sprintf("买盘占比 %.0f%%，卖压占优", pressure*100))
	}
	if uniqueVsFills >= 0.55 {
		score += 5
		bits = append(bits, "成交笔数和独立地址接近，更像真人")
	} else if uniqueVsFills >= 0.3 {
		score += 3
		bits = append(bits, "部分地址多次成交，轻度刷量可能")
	} else {
		bits = append(bits, "少量地址贡献大量成交，刷量嫌疑")
	}
	mc := token.Cap()
	if r := ratio(token.VolumeH1, mc); r >= 0.05 && r <= 1.2 && token.VolumeH1 >= 800 {
		score += 2
		bits = append(bits, "换手健康，既有成交又没有离奇放量")
	}
	return Gene{"flow", "真实买盘", clamp(score, 0, 20), 20, strings.Join(bits, "；")}
}

func geneLiquidity(token TokenSnapshot) Gene {
	mc := token.Cap()
	liq := token.LiquidityUSD
	var bits []string
	score := 0.0
	progress := pumpProgress(token)
	if token.Pump != nil && !token.Pump.Complete {
		if progress == nil {
			score += 5
			bits = append(bits, "Pump.fun 内盘，曲线本身锁死撤池")
		} else if *progress >= 0.18 && *progress <= 0.72 {
			score += 12
			bits = append(bits, fmt.Sprintf("内盘进度 %.0f%%，既不是刚开的死盘，也还没到毕业砸盘点", *progress*100))
		} else if *progress >= 0.08 && *progress < 0.18 {
			score += 7
			bits = append(bits, fmt.Sprintf("内盘进度 %.0f%%，偏早，需要买盘继续跟上", *progress*100))
		} else if *progress > 0.72 {
			score += 6
			bits = append(bits, fmt.Sprintf("内盘进度 %.0f%%，临近毕业，注意毕业瞬间抛压", *progress*100))
		} else {
			score += 3
			bits = append(bits, "内盘几乎没进度")
		}
	} else if token.Pump != nil && token.Pump.Complete {
		score += 8
		bits = append(bits, "刚毕业/已外盘，LP 由协议打出，结构好于手建池")
		if liq != nil && mc > 0 {
			r := ratio(*liq, mc)
			if r >= 0.12 && r <= 0.7 {
				score += 3
				bits = append(bits, fmt.Sprintf("流动性/市值 %.0f%%，可进出", r*100))
			}
		}
	} else {
		if liq == nil || *liq < 2500 {
			bits = append(bits, "外盘流动性过薄或缺失")
		} else {
			r := 0.0
			if mc > 0 {
				r = ratio(*liq, mc)
			}
			if r >= 0.18 && r <= 0.55 {
				score += 8
				bits = append(bits, fmt.Sprintf("流动性 $%s，占市值 %.0f%%，结构健康", comma0(*liq), r*100))
			} else if r >= 0.08 && r < 0.18 {
				score += 5
				bits = append(bits, fmt.Sprintf("流动性偏薄（%.0f%%），滑点会吃掉小资金优势", r*100))
			} else if r > 0.55 {
				score += 4
				bits = append(bits, "流动性相对市值过厚，要么是锁仓叙事，要么是出货垫子")
			} else {
				bits = append(bits, "流动性与市值不匹配")
			}
		}
		if token.Security != nil && token.Security.LpLockedPct != nil {
			p := *token.Security.LpLockedPct
			if p >= 99 {
				score += 4
				bits = append(bits, "LP 接近全锁")
			} else if p >= 80 {
				score += 2
				bits = append(bits, fmt.Sprintf("LP 锁定 %.0f%%", p))
			}
		}
	}
	reason := strings.Join(bits, "；")
	if reason == "" {
		reason = "流动性信息不足"
	}
	return Gene{"liq", "曲线/流动性", clamp(score, 0, 12), 12, reason}
}

func geneSecurity(token TokenSnapshot) Gene {
	sec := token.Security
	var bits []string
	score := 8.0
	if token.Pump != nil && !token.Pump.Complete {
		score = 11
		bits = append(bits, "内盘由协议托管，无法传统撤池")
	}
	if sec == nil {
		bits = append(bits, "尚未拉到持仓/权限报告，安全分按结构给基数")
		out := score
		if token.Pump == nil {
			out = 6
		}
		return Gene{"sec", "安全结构", out, 16, strings.Join(bits, "；")}
	}
	score = 0
	if !present(sec.MintAuthority) {
		score += 5
		bits = append(bits, "铸造权已丢")
	} else {
		bits = append(bits, "铸造权仍在")
	}
	if !present(sec.FreezeAuthority) {
		score += 4
		bits = append(bits, "冻结权已丢")
	} else {
		bits = append(bits, "冻结权仍在")
	}
	if sec.LpLockedPct != nil && *sec.LpLockedPct >= 99 {
		score += 3
		bits = append(bits, "LP 全锁")
	} else if token.Pump != nil {
		score += 3
		bits = append(bits, "曲线仓位不可被创建者抽走")
	}
	if sec.Holders != nil && *sec.Holders != 0 {
		h := *sec.Holders
		if h >= 40 && h <= 900 {
			score += 2
			bits = append(bits, fmt.Sprintf("%d 个持仓地址，处于扩散前期", h))
		} else if h > 900 {
			score += 1
			bits = append(bits, fmt.Sprintf("持仓地址 %d，可能已经较散", h))
		} else {
			bits = append(bits, fmt.Sprintf("持仓地址仅 %d", h))
		}
	}
	if sec.TopHolderPct != nil {
		p := *sec.TopHolderPct
		if token.Pump != nil && !token.Pump.Complete {
			score += 1
			bits = append(bits, "最大仓是曲线本身，不记作庄")
		} else if p < 8 {
			score += 2
			bits = append(bits, fmt.Sprintf("最大持仓 %.1f%%", p))
		} else if p < 18 {
			score += 1
			bits = append(bits, fmt.Sprintf("最大持仓 %.1f%%，可接受", p))
		} else {
			bits = append(bits, fmt.Sprintf("最大持仓 %.1f%%，需防砸", p))
		}
	}
	if sec.ScoreNormalised != nil {
		if *sec.ScoreNormalised <= 1 {
			bits = append(bits, fmt.Sprintf("RugCheck 归一分 %d", *sec.ScoreNormalised))
		} else if *sec.ScoreNormalised >= 10 {
			bits = append(bits, fmt.Sprintf("RugCheck 风险分偏高 (%d)", *sec.ScoreNormalised))
			score = maxF(0, score-3)
		}
	}
	if sec.InsiderNetworks != nil && *sec.InsiderNetworks >= 8 {
		bits = append(bits, fmt.Sprintf("检测到 %d 个内幕关联簇", *sec.InsiderNetworks))
		score = maxF(0, score-2)
	}
	return Gene{"sec", "安全结构", clamp(score, 0, 16), 16, strings.Join(bits, "；")}
}

func geneMomentum(token TokenSnapshot) Gene {
	var bits []string
	score := 0.0
	ch5, ch1 := token.ChangeM5, token.ChangeH1
	if ch1 >= 8 && ch1 <= 180 {
		score += 4
		bits = append(bits, fmt.Sprintf("1h %+.0f%% ，需求已被市场确认，但还没走成垂直泡沫", ch1))
	} else if ch1 > 180 && ch1 <= 400 {
		score += 2
		bits = append(bits, fmt.Sprintf("1h %+.0f%% ，偏热，追高会压缩剩余百倍空间", ch1))
	} else if ch1 > 400 {
		bits = append(bits, fmt.Sprintf("1h %+.0f%% ，过热", ch1))
	} else if ch1 >= -12 && ch1 < 8 {
		score += 3
		bits = append(bits, fmt.Sprintf("1h %+.0f%% 横盘吸筹，若买盘仍在属于更好的入口", ch1))
	} else {
		bits = append(bits, fmt.Sprintf("1h %+.0f%% 偏弱", ch1))
	}
	if ch5 >= 3 && token.TxM5.Buys >= token.TxM5.Sells {
		score += 3
		bits = append(bits, fmt.Sprintf("5m %+.0f%% 且买盘占优，第二波可能正在起", ch5))
	} else if ch5 >= -8 && ch5 < 3 && token.TxM5.Buyers >= 4 {
		score += 2
		bits = append(bits, "5m 回踩但买家还在")
	} else if ch5 < -20 {
		bits = append(bits, "5m 急跌")
	}
	if token.Pump != nil && token.Pump.AthMc > 0 && token.Cap() > 0 {
		drawdown := 1 - token.Cap()/math.Max(token.Pump.AthMc, 1)
		if drawdown >= 0.15 && drawdown <= 0.45 {
			score += 3
			bits = append(bits, fmt.Sprintf("相对内盘 ATH 回撤 %.0f%%，像洗盘而不是死亡", drawdown*100))
		} else if drawdown > 0.7 {
			bits = append(bits, "相对 ATH 深回撤，可能已经死")
		} else if drawdown < 0.1 {
			score += 1
			bits = append(bits, "接近内盘 ATH")
		}
	}
	reason := strings.Join(bits, "；")
	if reason == "" {
		reason = "动量中性"
	}
	return Gene{"mom", "动量结构", clamp(score, 0, 10), 10, reason}
}

func geneIgnition(token TokenSnapshot) Gene {
	score := 0.0
	var bits []string
	if token.HasProfile || token.Image != nil {
		score += 1
		bits = append(bits, "有基础资料")
	}
	if len(token.Socials) > 0 || len(token.Websites) > 0 {
		score += 1
		bits = append(bits, "有外链/社交")
	}
	if token.BoostAmount > 0 {
		score += 1
		bits = append(bits, fmt.Sprintf("Dex 助推 %d", token.BoostAmount))
	}
	if token.Pump != nil && token.Pump.ReplyCount >= 15 {
		score += 1
		bits = append(bits, fmt.Sprintf("内盘评论 %d", token.Pump.ReplyCount))
	} else if token.Pump != nil && token.Pump.Livestream {
		score += 1
		bits = append(bits, "正在直播")
	}
	if score == 0 {
		bits = append(bits, "链上热度尚未被社交点燃（不一定是坏事）")
	}
	return Gene{"ignite", "传播点火", clamp(score, 0, 4), 4, strings.Join(bits, "；")}
}

func feasibilityOf100x(mc float64) float64 {
	target := mc * 100
	switch {
	case target <= conservativeTop:
		return 0.92
	case target <= baseRunnerTop:
		return 0.72
	case target <= 10000000:
		return 0.45
	case target <= stretchTop:
		return 0.22
	default:
		return 0.08
	}
}

func scoreToken(token TokenSnapshot, nowMs int64) ScoreCard {
	mc := token.Cap()
	if mc < 0 {
		mc = 0
	}
	ageSec := ageSeconds(token, nowMs)
	kills := hardKills(token, ageSec)
	genes := []Gene{
		geneRoom(mc), geneWindow(ageSec), geneFlow(token), geneLiquidity(token),
		geneSecurity(token), geneMomentum(token), geneIgnition(token),
	}
	raw := 0.0
	for _, g := range genes {
		raw += g.Score
	}
	total := int(math.Round(clamp(raw, 0, 100)))
	passed := len(kills) == 0
	if !passed && total > 44 {
		total = 44
	}
	x100 := mc * 100
	feas := 0.0
	if passed {
		feas = feasibilityOf100x(mc)
		feas = math.Round(feas*1000) / 1000
	}
	var verdict, thesis string
	if passed && feas >= 0.7 && total >= 70 {
		verdict = "结构接近历史百倍入口，仍可能归零"
		thesis = fmt.Sprintf("现在买，100x 只要求市值到 $%s。这落在迷因币常见终点下沿，时间窗和买盘结构也还没走完。", comma0(x100))
	} else if passed && feas >= 0.4 {
		verdict = "有百倍几何空间，需要成为出圈盘"
		thesis = fmt.Sprintf("100x 目标市值 $%s。空间还在，但必须靠第二波传播，不能只靠开盘情绪。", comma0(x100))
	} else if passed {
		verdict = "空间勉强够，路径很窄"
		thesis = fmt.Sprintf("100x 需要冲到 $%s，这已经接近迷因币异常终点。", comma0(x100))
	} else {
		verdict = "未通过百倍入口门禁"
		thesis = strings.Join(kills, "；")
	}
	x1, x5, x20 := 0.0, 0.0, 0.0
	if mc > 0 {
		x1, x5, x20 = ratio(conservativeTop, mc), ratio(baseRunnerTop, mc), ratio(stretchTop, mc)
	}
	b := "—"
	if mc > 0 {
		b = band(mc)
	}
	if kills == nil {
		kills = []string{}
	}
	return ScoreCard{
		Total: total, Grade: grade(total, passed), Passed: passed, KillReasons: kills,
		Genes: genes, X100TargetMc: x100, XIf1m5: x1, XIf5m: x5, XIf20m: x20,
		Feasibility: feas, Band: b, Verdict: verdict, Thesis: thesis,
	}
}

func rankTokens(tokens []TokenSnapshot, nowMs int64) []RankedToken {
	if nowMs == 0 {
		nowMs = time.Now().UnixMilli()
	}
	out := make([]RankedToken, 0, len(tokens))
	for _, t := range tokens {
		c := scoreToken(t, nowMs)
		out = append(out, RankedToken{Token: t, Score: c, AgeMin: math.Round(ageSeconds(t, nowMs)/60.0*100) / 100})
	}
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if a.Score.Passed != b.Score.Passed {
			return a.Score.Passed
		}
		if a.Score.Total != b.Score.Total {
			return a.Score.Total > b.Score.Total
		}
		return a.Score.Feasibility > b.Score.Feasibility
	})
	return out
}
