import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CandleChart from "../components/CandleChart";
import { Button, Disclaimer, Panel, Status } from "../components/ui";
import { fmtNum, fmtPct } from "../format";

export default function Dashboard() {
  const [data, setData] = useState<any>(null);
  const [candles, setCandles] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      setErr(null);
      const [dash, kl] = await Promise.all([
        api<any>("/api/dashboard"),
        api<any>("/api/market/klines?symbol=BTCUSDT&interval=1d&limit=180"),
      ]);
      setData(dash);
      setCandles(kl?.candles || []);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const cycle = data?.btc_cycle || {};
  const port = data?.portfolio || {};
  const ind = cycle.indicators || {};

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel
        className="xl:col-span-2"
        title="市场状态 / BTC 周期"
        action={<Button disabled={busy} onClick={load}>{busy ? "正在拉取行情…" : "刷新"}</Button>}
      >
        {err && <div className="text-[#ff5d73]">{err}</div>}
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>状态 <Status value={cycle.regime} /></div>
          <div>阶段 <span className="font-mono">{cycle.phase || "—"}</span></div>
          <div>偏多 {cycle.bull_score ?? "未知"}</div>
          <div>偏空 {cycle.bear_score ?? "未知"}</div>
          <div>置信度 {cycle.confidence ?? "—"}</div>
          <div>价格 {fmtNum(cycle.current_price, 2)}</div>
          <div>200日均线 {cycle.ma200 != null ? fmtNum(cycle.ma200, 2) : "未知"}</div>
          <div>相对历史高点回撤 {cycle.drawdown != null ? fmtPct(cycle.drawdown) : "未知"}</div>
          <div>算力 {ind.hashrate?.current_hashrate ? Number(ind.hashrate.current_hashrate).toExponential(2) : "未知"}</div>
          <div>区块高度 {ind.block_height?.height ?? "未知"}</div>
          <div>BTC 占比 {ind.btc_dominance ?? "未知"}%</div>
          <div>MVRV {cycle.missing_indicators?.mvrv ? "未知" : "—"}</div>
        </div>
        <div className="mt-3">
          <CandleChart candles={candles} />
        </div>
        <Disclaimer text={cycle.disclaimer} />
      </Panel>
      <Panel title="组合">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>投入 {fmtNum(port.total_invested, 2)}</div>
          <div>市值 {fmtNum(port.current_value, 2)}</div>
          <div>净盈亏 {fmtNum(port.net_pnl, 2)}</div>
          <div>收益率 {port.roi != null ? fmtPct(port.roi) : "—"}</div>
          <div>今日 {port.today_pnl != null ? fmtNum(port.today_pnl, 2) : "未知"}</div>
          <div>本周 {port.week_pnl != null ? fmtNum(port.week_pnl, 2) : "未知"}</div>
          <div>本月 {port.month_pnl != null ? fmtNum(port.month_pnl, 2) : "未知"}</div>
        </div>
        <p className="mt-2 text-xs text-[#8aa0c2]">{port.period_note}</p>
        <Link className="mt-3 inline-block text-xs text-[#3ee0b4]" to="/portfolio">打开跟踪中心 →</Link>
      </Panel>
      <Panel title="提醒">
        {(data?.notifications || []).slice(0, 6).map((n: any) => (
          <div key={n.id} className="border-b border-[#1e2a44] py-1 text-sm">{n.title}</div>
        ))}
        {!data?.notifications?.length && <div className="text-sm text-[#8aa0c2]">暂无未读提醒。</div>}
      </Panel>
      <Panel title="五十倍雷达（最近一次扫描）">
        {(data?.radar_latest || []).length === 0 && (
          <p className="text-sm text-[#8aa0c2]">还没有保存的雷达分数。请运行一次 CoinGecko + GoPlus 实盘扫描。</p>
        )}
        {(data?.radar_latest || []).slice(0, 8).map((r: any) => (
          <div key={r.project_id} className="flex items-center justify-between border-b border-[#1e2a44] py-1 text-sm">
            <Link className="text-[#3ee0b4]" to={`/projects/${encodeURIComponent(r.project_id)}`}>{r.symbol || r.name}</Link>
            <span className="font-mono">{r.score}</span>
          </div>
        ))}
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/radar">打开五十倍雷达 →</Link>
      </Panel>
      <Panel title="合约成交额前三（实时）">
        {(data?.futures_volume_top || []).map((r: any) => (
          <div key={r.symbol} className="flex items-center justify-between border-b border-[#1e2a44] py-1 text-sm">
            <Link className="font-mono text-[#3ee0b4]" to={`/assets/${r.symbol}`}>#{r.rank} {r.symbol}</Link>
            <span>{r.last} · {r.change_pct}%</span>
          </div>
        ))}
        {!(data?.futures_volume_top || []).length && <div className="text-sm text-[#8aa0c2]">行情不可用：{data?.ticker_status?.status || "未知"}</div>}
        {(data?.futures_analyzed_top || []).length > 0 && (
          <div className="mt-3 text-xs text-[#8aa0c2]">最近分析前三：{(data.futures_analyzed_top || []).map((t: any) => `${t.symbol} ${t.direction}`).join(" · ")}</div>
        )}
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/futures">打开合约 →</Link>
      </Panel>
      <Panel title="足球（最近一次模型）">
        {(data?.football_latest || []).slice(0, 4).map((m: any) => (
          <div key={m.match} className="border-b border-[#1e2a44] py-1 text-xs">
            {m.home && m.away ? `${m.home} vs ${m.away}` : m.match} · 主 {m.home_win} 平 {m.draw} 客 {m.away_win}
          </div>
        ))}
        {!(data?.football_latest || []).length && <div className="text-sm text-[#8aa0c2]">还没有保存的足球预测。</div>}
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-[#3ee0b4]">
          <Link to="/spot">现货</Link>
          <Link to="/airdrop">空投</Link>
          <Link to="/launch">新盘</Link>
          <Link to="/football">足球</Link>
          <Link to="/lottery">彩票</Link>
        </div>
      </Panel>
    </div>
  );
}
