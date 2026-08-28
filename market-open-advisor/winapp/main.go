package main

import (
	"encoding/json"
	"fmt"
	"html"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	perMarket = 40
	tenBillion = 10_000_000_000
	ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

type market struct {
	Key, Name, Exchange string
	Sina, Tencent, Yahoo string
	Index bool
}

type instrument struct {
	M              market
	Symbol, Name   string
	Sina, Tencent, Yahoo string
}

type bars struct {
	M          market
	Symbol, Name, Source, LastDate string
	Dates      []string
	Closes     []float64
	Spot, Chg  float64
}

type stats struct {
	Exp, PUp, P05, P50, P95, Sigma float64
}

type advice struct {
	M          market
	Symbol, Name, Action, Regime, Source, LastDate string
	Spot, Chg, LastClose float64
	Size       int
	Exp, PUp, P05, P50, P95, Sigma, Mom20, Vol20 float64
	NHist, NRegime int
	Reasons    []string
	Stocks     []advice
}

var client = &http.Client{Timeout: 18 * time.Second}

var markets = []market{
	{Key: "sse", Name: "上交所主板", Exchange: "SSE", Sina: "sh000001", Tencent: "sh000001", Yahoo: "000001.SS"},
	{Key: "szse", Name: "深交所主板", Exchange: "SZSE", Sina: "sz399001", Tencent: "sz399001", Yahoo: "399001.SZ"},
	{Key: "chinext", Name: "创业板", Exchange: "SZSE ChiNext", Sina: "sz399006", Tencent: "sz399006", Yahoo: "399006.SZ"},
	{Key: "star", Name: "科创板", Exchange: "SSE STAR", Sina: "sh000688", Tencent: "sh000688", Yahoo: "000688.SS"},
	{Key: "bse", Name: "北交所", Exchange: "BSE", Sina: "bj899050", Tencent: "bj899050"},
	{Key: "hkex", Name: "港交所", Exchange: "HKEX", Tencent: "hkHSI", Yahoo: "^HSI"},
	{Key: "us", Name: "美股", Exchange: "NYSE/Nasdaq", Tencent: "usNDX", Yahoo: "^NDX"},
}

var boardNode = map[string]string{"sse": "sh_a", "szse": "sz_a", "chinext": "cyb", "star": "kcb", "bse": "hs_bjs"}

var hkNames = [][2]string{
	{"0700.HK", "腾讯控股"}, {"9988.HK", "阿里巴巴"}, {"3690.HK", "美团"}, {"1810.HK", "小米集团"},
	{"9618.HK", "京东集团"}, {"0941.HK", "中国移动"}, {"1299.HK", "友邦保险"}, {"0388.HK", "香港交易所"},
	{"0005.HK", "汇丰控股"}, {"0939.HK", "建设银行"}, {"1398.HK", "工商银行"}, {"3988.HK", "中国银行"},
	{"0883.HK", "中国海洋石油"}, {"2318.HK", "中国平安"}, {"1211.HK", "比亚迪股份"}, {"2020.HK", "安踏体育"},
	{"0175.HK", "吉利汽车"}, {"1024.HK", "快手"}, {"9868.HK", "小鹏汽车"}, {"2015.HK", "理想汽车"},
}

var usNames = [][2]string{
	{"AAPL", "苹果"}, {"MSFT", "微软"}, {"NVDA", "英伟达"}, {"AMZN", "亚马逊"}, {"GOOGL", "谷歌"},
	{"META", "Meta"}, {"TSLA", "特斯拉"}, {"AVGO", "博通"}, {"COST", "开市客"}, {"NFLX", "奈飞"},
	{"AMD", "超威"}, {"INTC", "英特尔"}, {"QCOM", "高通"}, {"PEP", "百事"}, {"CSCO", "思科"},
	{"AMGN", "安进"}, {"TXN", "德州仪器"}, {"AMAT", "应用材料"}, {"SBUX", "星巴克"}, {"MU", "美光"},
}

func main() {
	fmt.Println("开盘建议：正在按交易场所拉取个股行情并计算（大约几十秒）…")
	opened := time.Now()
	var venues []advice
	var errs []string
	for _, m := range markets {
		fmt.Println("  ", m.Name)
		idx, err := fetchIndex(m)
		if err != nil {
			errs = append(errs, m.Name+": "+err.Error())
			continue
		}
		v, err := analyze(idx, true, opened)
		if err != nil {
			errs = append(errs, m.Name+": "+err.Error())
			continue
		}
		insts := listInstruments(m, perMarket)
		fmt.Printf("    个股 %d 只\n", len(insts))
		stocks := fetchAll(insts)
		var rows []advice
		for _, b := range stocks {
			a, err := analyze(b, false, opened)
			if err != nil {
				errs = append(errs, m.Name+" "+b.Symbol+": "+err.Error())
				continue
			}
			rows = append(rows, a)
		}
		sort.Slice(rows, func(i, j int) bool {
			rank := map[string]int{"偏多": 0, "观望": 1, "偏空": 2}
			if rank[rows[i].Action] != rank[rows[j].Action] {
				return rank[rows[i].Action] < rank[rows[j].Action]
			}
			return rows[i].Exp > rows[j].Exp
		})
		v.Stocks = rows
		venues = append(venues, v)
	}
	page := renderHTML(opened, venues, errs)
	out := filepath.Join(os.TempDir(), "open-advisor.html")
	if err := os.WriteFile(out, []byte(page), 0644); err != nil {
		fmt.Println("写文件失败:", err)
		waitExit(1)
	}
	fmt.Println("建议已生成，正在打开浏览器…")
	fmt.Println(out)
	openFile(out)
	if len(errs) > 0 {
		fmt.Println("部分失败：")
		for _, e := range errs {
			fmt.Println(" ", e)
		}
	}
	waitExit(0)
}

func waitExit(code int) {
	if runtime.GOOS == "windows" {
		fmt.Println("\n窗口可以关闭。按回车退出。")
		fmt.Scanln()
	}
	os.Exit(code)
}

func openFile(path string) {
	switch runtime.GOOS {
	case "windows":
		_ = exec.Command("cmd", "/c", "start", "", path).Start()
	case "darwin":
		_ = exec.Command("open", path).Start()
	default:
		_ = exec.Command("xdg-open", path).Start()
	}
}

func httpGet(rawURL, referer string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", ua)
	req.Header.Set("Accept", "application/json,text/plain,*/*")
	if referer != "" {
		req.Header.Set("Referer", referer)
	}
	var last error
	for i := 0; i < 2; i++ {
		resp, err := client.Do(req)
		if err != nil {
			last = err
			time.Sleep(time.Duration(i+1) * 200 * time.Millisecond)
			continue
		}
		b, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		if resp.StatusCode >= 400 {
			last = fmt.Errorf("http %d", resp.StatusCode)
			continue
		}
		return b, nil
	}
	return nil, last
}

func fetchIndex(m market) (bars, error) {
	return fetchIDs(m, m.Name, "", m.Sina, m.Tencent, m.Yahoo)
}

func fetchIDs(m market, name, symbol, sina, tencent, yahoo string) (bars, error) {
	var errs []string
	if sina != "" {
		if b, err := fetchSina(m, name, symbol, sina); err == nil {
			return b, nil
		} else {
			errs = append(errs, "sina "+err.Error())
		}
	}
	if tencent != "" {
		if b, err := fetchTencent(m, name, symbol, tencent); err == nil {
			return b, nil
		} else {
			errs = append(errs, "tencent "+err.Error())
		}
	}
	if yahoo != "" {
		if b, err := fetchYahoo(m, name, symbol, yahoo); err == nil {
			return b, nil
		} else {
			errs = append(errs, "yahoo "+err.Error())
		}
	}
	return bars{}, fmt.Errorf("%s", strings.Join(errs, "; "))
}

func fetchSina(m market, name, symbol, sina string) (bars, error) {
	u := "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?" +
		url.Values{"symbol": {sina}, "scale": {"240"}, "ma": {"no"}, "datalen": {"240"}}.Encode()
	body, err := httpGet(u, "https://finance.sina.com.cn/")
	if err != nil {
		return bars{}, err
	}
	var raw []map[string]any
	if err := json.Unmarshal(body, &raw); err != nil || len(raw) == 0 {
		return bars{}, fmt.Errorf("sina kline")
	}
	var dates []string
	var closes []float64
	for _, r := range raw {
		d, _ := r["day"].(string)
		cs, _ := r["close"].(string)
		c, err := strconv.ParseFloat(cs, 64)
		if err != nil {
			if f, ok := r["close"].(float64); ok {
				c = f
			} else {
				continue
			}
		}
		if len(d) >= 10 {
			d = d[:10]
		}
		dates = append(dates, d)
		closes = append(closes, c)
	}
	return makeBars(m, name, symbol, "sina", dates, closes, 0, 0)
}

func fetchTencent(m market, name, symbol, code string) (bars, error) {
	u := "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=" + url.QueryEscape(code+",day,,,240,qfq")
	body, err := httpGet(u, "https://finance.qq.com/")
	if err != nil {
		return bars{}, err
	}
	var payload struct {
		Data map[string]map[string]any `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return bars{}, err
	}
	block := payload.Data[code]
	if block == nil {
		return bars{}, fmt.Errorf("empty")
	}
	var rows []any
	if v, ok := block["day"].([]any); ok {
		rows = v
	} else if v, ok := block["qfqday"].([]any); ok {
		rows = v
	}
	var dates []string
	var closes []float64
	for _, row := range rows {
		arr, ok := row.([]any)
		if !ok || len(arr) < 3 {
			continue
		}
		d := fmt.Sprint(arr[0])
		if len(d) >= 10 {
			d = d[:10]
		}
		c, err := strconv.ParseFloat(fmt.Sprint(arr[2]), 64)
		if err != nil {
			continue
		}
		dates = append(dates, d)
		closes = append(closes, c)
	}
	spot := 0.0
	nm := name
	if qt, ok := block["qt"].(map[string]any); ok {
		if arr, ok := qt[code].([]any); ok && len(arr) >= 4 {
			if s, ok := arr[1].(string); ok && s != "" {
				nm = s
			}
			if f, err := strconv.ParseFloat(fmt.Sprint(arr[3]), 64); err == nil {
				spot = f
			}
		}
	}
	return makeBars(m, nm, symbol, "tencent", dates, closes, spot, 0)
}

func fetchYahoo(m market, name, symbol, ysym string) (bars, error) {
	u := "https://query1.finance.yahoo.com/v8/finance/chart/" + url.PathEscape(ysym) + "?interval=1d&range=2y"
	body, err := httpGet(u, "https://finance.yahoo.com/")
	if err != nil {
		return bars{}, err
	}
	var payload struct {
		Chart struct {
			Result []struct {
				Meta struct {
					ShortName           string  `json:"shortName"`
					RegularMarketPrice  float64 `json:"regularMarketPrice"`
				} `json:"meta"`
				Timestamp  []int64 `json:"timestamp"`
				Indicators struct {
					Quote []struct {
						Close []*float64 `json:"close"`
					} `json:"quote"`
				} `json:"indicators"`
			} `json:"result"`
		} `json:"chart"`
	}
	if err := json.Unmarshal(body, &payload); err != nil || len(payload.Chart.Result) == 0 {
		return bars{}, fmt.Errorf("yahoo")
	}
	res := payload.Chart.Result[0]
	var dates []string
	var closes []float64
	if len(res.Indicators.Quote) == 0 {
		return bars{}, fmt.Errorf("yahoo quote")
	}
	for i, ts := range res.Timestamp {
		if i >= len(res.Indicators.Quote[0].Close) || res.Indicators.Quote[0].Close[i] == nil {
			continue
		}
		dates = append(dates, time.Unix(ts, 0).UTC().Format("2006-01-02"))
		closes = append(closes, *res.Indicators.Quote[0].Close[i])
	}
	nm := res.Meta.ShortName
	if nm == "" {
		nm = name
	}
	return makeBars(m, nm, symbol, "yahoo", dates, closes, res.Meta.RegularMarketPrice, 0)
}

func makeBars(m market, name, symbol, source string, dates []string, closes []float64, spot, chg float64) (bars, error) {
	if len(closes) < 80 {
		return bars{}, fmt.Errorf("K线过短 %d", len(closes))
	}
	if spot == 0 {
		spot = closes[len(closes)-1]
	}
	chg = changePct(closes, spot)
	lastDate := ""
	if len(dates) > 0 {
		lastDate = dates[len(dates)-1]
	}
	return bars{M: m, Symbol: symbol, Name: name, Source: source, LastDate: lastDate, Dates: dates, Closes: closes, Spot: spot, Chg: chg}, nil
}

func changePct(closes []float64, spot float64) float64 {
	if len(closes) < 2 {
		return 0
	}
	last := closes[len(closes)-1]
	prev := closes[len(closes)-2]
	if last == 0 || prev == 0 {
		return 0
	}
	if math.Abs(spot-last)/last < 5e-4 {
		return (last/prev - 1) * 100
	}
	return (spot/last - 1) * 100
}

func listInstruments(m market, limit int) []instrument {
	if m.Key == "hkex" {
		var out []instrument
		for i, p := range hkNames {
			if i >= limit {
				break
			}
			digits := strings.Split(p[0], ".")[0]
			out = append(out, instrument{M: m, Symbol: digits, Name: p[1], Tencent: "hk" + pad5(digits), Yahoo: p[0]})
		}
		return out
	}
	if m.Key == "us" {
		var out []instrument
		for i, p := range usNames {
			if i >= limit {
				break
			}
			out = append(out, instrument{M: m, Symbol: p[0], Name: p[1], Tencent: "us" + p[0], Yahoo: p[0]})
		}
		return out
	}
	node := boardNode[m.Key]
	if node == "" {
		return nil
	}
	u := "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?" +
		url.Values{"page": {"1"}, "num": {"80"}, "sort": {"amount"}, "asc": {"0"}, "node": {node}}.Encode()
	body, err := httpGet(u, "https://finance.sina.com.cn/")
	if err != nil {
		return nil
	}
	var rows []map[string]any
	if err := json.Unmarshal(body, &rows); err != nil {
		return nil
	}
	var out []instrument
	seen := map[string]bool{}
	for _, r := range rows {
		sina, _ := r["symbol"].(string)
		name, _ := r["name"].(string)
		if sina == "" || skipName(name) {
			continue
		}
		code, tencent, yahoo := idsFromSina(sina)
		if !codeBelongs(m.Key, code) || seen[code] {
			continue
		}
		seen[code] = true
		out = append(out, instrument{M: m, Symbol: code, Name: name, Sina: sina, Tencent: tencent, Yahoo: yahoo})
		if len(out) >= limit {
			break
		}
	}
	return out
}

func pad5(s string) string {
	for len(s) < 5 {
		s = "0" + s
	}
	return s
}

func skipName(name string) bool {
	n := strings.TrimSpace(name)
	if n == "" {
		return true
	}
	u := strings.ToUpper(n)
	if strings.HasPrefix(u, "N") && len(n) <= 6 {
		return true
	}
	return strings.Contains(n, "*ST") || strings.Contains(u, "ST") && strings.HasPrefix(u, "ST") || strings.Contains(n, "退市")
}

func codeBelongs(key, code string) bool {
	switch key {
	case "sse":
		return strings.HasPrefix(code, "600") || strings.HasPrefix(code, "601") || strings.HasPrefix(code, "603") || strings.HasPrefix(code, "605")
	case "szse":
		return strings.HasPrefix(code, "000") || strings.HasPrefix(code, "001") || strings.HasPrefix(code, "002") || strings.HasPrefix(code, "003")
	case "chinext":
		return strings.HasPrefix(code, "300") || strings.HasPrefix(code, "301")
	case "star":
		return strings.HasPrefix(code, "688")
	case "bse":
		return true
	}
	return true
}

func idsFromSina(sina string) (code, tencent, yahoo string) {
	s := strings.ToLower(strings.TrimSpace(sina))
	switch {
	case strings.HasPrefix(s, "sh"):
		code = s[2:]
		return code, s, code + ".SS"
	case strings.HasPrefix(s, "sz"):
		code = s[2:]
		return code, s, code + ".SZ"
	case strings.HasPrefix(s, "bj"):
		code = s[2:]
		return code, s, code + ".BJ"
	}
	return s, s, ""
}

func fetchAll(insts []instrument) []bars {
	var mu sync.Mutex
	var out []bars
	sem := make(chan struct{}, 12)
	var wg sync.WaitGroup
	for _, inst := range insts {
		inst := inst
		wg.Add(1)
		sem <- struct{}{}
		go func() {
			defer wg.Done()
			defer func() { <-sem }()
			b, err := fetchIDs(inst.M, inst.Name, inst.Symbol, inst.Sina, inst.Tencent, inst.Yahoo)
			if err != nil {
				return
			}
			mu.Lock()
			out = append(out, b)
			mu.Unlock()
		}()
	}
	wg.Wait()
	return out
}

type fitted struct {
	Returns                    []float64
	Regime                     string
	Last, MA20, MA60, Mom20, Vol20 float64
	LastDate                   string
	NHist, NRegime             int
}

func mean(x []float64) float64 {
	if len(x) == 0 {
		return 0
	}
	s := 0.0
	for _, v := range x {
		s += v
	}
	return s / float64(len(x))
}

func stdSample(x []float64) float64 {
	if len(x) < 2 {
		return 0
	}
	m := mean(x)
	s := 0.0
	for _, v := range x {
		d := v - m
		s += d * d
	}
	return math.Sqrt(s / float64(len(x)-1))
}

func quantile(x []float64, p float64) float64 {
	if len(x) == 0 {
		return 0
	}
	y := append([]float64{}, x...)
	sort.Float64s(y)
	if len(y) == 1 {
		return y[0]
	}
	idx := p * float64(len(y)-1)
	i := int(math.Floor(idx))
	if i >= len(y)-1 {
		return y[len(y)-1]
	}
	frac := idx - float64(i)
	return y[i]*(1-frac) + y[i+1]*frac
}

func classify(last, ma20, ma60, mom float64) string {
	if last > ma20 && ma20 > ma60 && mom > 0 {
		return "上升"
	}
	if last < ma20 && ma20 < ma60 && mom < 0 {
		return "下降"
	}
	return "震荡"
}

func fit(closes []float64, dates []string) (fitted, error) {
	if len(closes) < 80 {
		return fitted{}, fmt.Errorf("历史不足")
	}
	simple := make([]float64, len(closes)-1)
	for i := 0; i < len(closes)-1; i++ {
		simple[i] = (closes[i+1] - closes[i]) / closes[i]
	}
	last := closes[len(closes)-1]
	ma20 := mean(closes[len(closes)-20:])
	ma60 := mean(closes[len(closes)-60:])
	mom := closes[len(closes)-1]/closes[len(closes)-21] - 1
	vol := stdSample(simple[len(simple)-20:])
	regime := classify(last, ma20, ma60, mom)
	// rolling ma20 aligned to simple returns
	var cond []float64
	for i := 19; i < len(closes)-1; i++ {
		w := mean(closes[i-19 : i+1])
		px := closes[i+1]
		r := simple[i]
		ok := false
		switch regime {
		case "上升":
			ok = px > w
		case "下降":
			ok = px < w
		default:
			ok = math.Abs(px/w-1) <= 0.04
		}
		if ok {
			cond = append(cond, r)
		}
	}
	if len(cond) < 40 {
		if len(simple) > 250 {
			cond = simple[len(simple)-250:]
		} else {
			cond = simple
		}
	}
	ld := ""
	if len(dates) > 0 {
		ld = dates[len(dates)-1]
	}
	return fitted{Returns: cond, Regime: regime, Last: last, MA20: ma20, MA60: ma60, Mom20: mom, Vol20: vol, LastDate: ld, NHist: len(simple), NRegime: len(cond)}, nil
}

func limitStats(r []float64) stats {
	up := 0.0
	for _, v := range r {
		if v > 0 {
			up++
		}
	}
	return stats{
		Exp: mean(r), PUp: up / float64(len(r)),
		P05: quantile(r, 0.05), P50: quantile(r, 0.50), P95: quantile(r, 0.95),
		Sigma: stdSample(r),
	}
}

func analyze(b bars, isIndex bool, opened time.Time) (advice, error) {
	f, err := fit(b.Closes, b.Dates)
	if err != nil {
		return advice{}, err
	}
	st := limitStats(f.Returns)
	act, size, reasons := decide(st, f, isIndex)
	if b.Chg != 0 {
		reasons = append(reasons, fmt.Sprintf("打开时刻现价涨跌 %.2f%%。", b.Chg))
	}
	reasons = append(reasons, "行情源 "+b.Source+"（交易所公开成交）。")
	return advice{
		M: b.M, Symbol: b.Symbol, Name: b.Name, Action: act, Regime: f.Regime, Source: b.Source,
		LastDate: f.LastDate, Spot: b.Spot, Chg: b.Chg, LastClose: f.Last, Size: size,
		Exp: st.Exp, PUp: st.PUp, P05: st.P05, P50: st.P50, P95: st.P95, Sigma: st.Sigma,
		Mom20: f.Mom20, Vol20: f.Vol20, NHist: f.NHist, NRegime: f.NRegime, Reasons: reasons,
	}, nil
}

func decide(st stats, f fitted, isIndex bool) (string, int, []string) {
	reasons := []string{
		fmt.Sprintf("当前趋势状态为「%s」，从同类状态下的 %d 个历史交易日收益做条件自助抽样。", f.Regime, f.NRegime),
		fmt.Sprintf("100亿次独立模拟的解析极限：期望日收益 %.3f%%，上涨概率 %.1f%%，5%%分位 %.3f%%。", st.Exp*100, st.PUp*100, st.P05*100),
		fmt.Sprintf("20日动量 %.2f%%，20日波动 %.2f%%，收盘相对 MA20 %.2f%%。", f.Mom20*100, f.Vol20*100, (f.Last/f.MA20-1)*100),
	}
	edge := st.Exp / math.Max(st.Sigma, 1e-8)
	var action string
	var size int
	if st.Exp > 0.0015 && st.PUp >= 0.54 && st.P05 > -0.035 {
		action = "偏多"
		size = int(math.Max(10, math.Min(60, math.Round(18*math.Max(edge, 0)*100))))
		if isIndex {
			reasons = append(reasons, "期望收益为正且左尾可控，建议该市场指数相关仓位偏多、控制总仓。")
		} else {
			reasons = append(reasons, "期望收益为正且左尾可控，建议该股票偏多、控制单票仓位。")
		}
	} else if st.Exp < -0.0015 && st.PUp <= 0.46 {
		action = "偏空"
		size = int(math.Max(0, math.Min(40, math.Round(12*math.Max(-edge, 0)*100))))
		if isIndex {
			reasons = append(reasons, "条件期望为负、上涨概率偏低，建议该市场以减仓或对冲为主，不做追空杠杆。")
		} else {
			reasons = append(reasons, "条件期望为负，建议该股票减仓或回避，不做追空杠杆。")
		}
	} else {
		action = "观望"
		size = 0
		reasons = append(reasons, "期望收益接近零或分位风险不对称，建议观望，等待状态切换。")
	}
	if f.Vol20 > 0.025 {
		size = int(math.Round(float64(size) * 0.7))
		reasons = append(reasons, "近20日波动偏高，仓位再打七折。")
	}
	return action, size, reasons
}

func colorOf(a string) string {
	switch a {
	case "偏多":
		return "#3dd68c"
	case "偏空":
		return "#ff6b6b"
	default:
		return "#e6c35c"
	}
}

func renderHTML(opened time.Time, venues []advice, errs []string) string {
	var b strings.Builder
	b.WriteString(`<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/><title>开盘建议</title>
<style>
body{background:#10141c;color:#e8eef7;font-family:"Segoe UI","Microsoft YaHei",sans-serif;margin:0;padding:24px}
h1{margin:0 0 8px} .sub{color:#93a0b5;margin-bottom:20px}
.card{background:#1b2230;border:1px solid #2c3648;border-radius:12px;padding:16px 20px;margin:0 0 14px}
header{display:flex;justify-content:space-between;align-items:center}
.action{font-size:20px;font-weight:700}
.meta,.stats,li,td,th{font-size:13px} .meta{color:#93a0b5}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #2c3648}
.foot{color:#93a0b5;font-size:12px;margin-top:18px} .err{color:#ff6b6b}
</style></head><body>`)
	fmt.Fprintf(&b, "<h1>打开时刻个股操作建议</h1><p class='sub'>打开时刻 %s · 按交易场所列出每只股票 · 建议取值 = 100亿次独立模拟解析极限</p>",
		html.EscapeString(opened.Format(time.RFC3339)))
	for _, v := range venues {
		fmt.Fprintf(&b, `<article class="card"><header><h2>%s <span style="color:#93a0b5;font-size:14px;font-weight:normal">%s</span></h2>
<p class="action" style="color:%s">%s · 仓位 %d%%</p></header>`,
			html.EscapeString(v.M.Name), html.EscapeString(v.M.Exchange), colorOf(v.Action), html.EscapeString(v.Action), v.Size)
		fmt.Fprintf(&b, `<p class="meta">%s 现价 %.2f %+.2f%% · %s · 收盘 %.2f（%s） · 源 %s</p>`,
			html.EscapeString(v.Name), v.Spot, v.Chg, html.EscapeString(v.Regime), v.LastClose, html.EscapeString(v.LastDate), html.EscapeString(v.Source))
		fmt.Fprintf(&b, `<p class="stats">100亿极限 E[r]=%.3f%% &nbsp; P(up)=%.1f%% &nbsp; P5/P50/P95=%.3f%%/%.3f%%/%.3f%%</p><ul>`,
			v.Exp*100, v.PUp*100, v.P05*100, v.P50*100, v.P95*100)
		for _, r := range v.Reasons {
			fmt.Fprintf(&b, "<li>%s</li>", html.EscapeString(r))
		}
		b.WriteString("</ul>")
		if len(v.Stocks) > 0 {
			b.WriteString("<table><thead><tr><th>代码</th><th>名称</th><th>现价</th><th>涨跌</th><th>建议</th><th>仓位</th><th>E[r]</th><th>P(up)</th><th>状态</th></tr></thead><tbody>")
			for _, s := range v.Stocks {
				fmt.Fprintf(&b, `<tr><td>%s</td><td>%s</td><td>%.2f</td><td>%+.2f%%</td><td style="color:%s">%s</td><td>%d%%</td><td>%.3f%%</td><td>%.1f%%</td><td>%s</td></tr>`,
					html.EscapeString(s.Symbol), html.EscapeString(s.Name), s.Spot, s.Chg, colorOf(s.Action), html.EscapeString(s.Action), s.Size, s.Exp*100, s.PUp*100, html.EscapeString(s.Regime))
			}
			b.WriteString("</tbody></table>")
		}
		b.WriteString("</article>")
	}
	if len(errs) > 0 {
		b.WriteString("<pre class='err'>")
		for _, e := range errs {
			b.WriteString(html.EscapeString(e) + "\n")
		}
		b.WriteString("</pre>")
	}
	b.WriteString(`<p class="foot">本工具根据公开行情做量化研究，输出不是投资建议、不是收益承诺。股市有风险，交易需自负。</p></body></html>`)
	return b.String()
}
