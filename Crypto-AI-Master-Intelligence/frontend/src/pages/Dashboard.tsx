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
        title="Market Regime / BTC Cycle"
        action={<Button disabled={busy} onClick={load}>{busy ? "Loading live…" : "Refresh"}</Button>}
      >
        {err && <div className="text-[#ff5d73]">{err}</div>}
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>Regime <Status value={cycle.regime} /></div>
          <div>Phase <span className="font-mono">{cycle.phase || "—"}</span></div>
          <div>Bull {cycle.bull_score ?? "UNKNOWN"}</div>
          <div>Bear {cycle.bear_score ?? "UNKNOWN"}</div>
          <div>Confidence {cycle.confidence ?? "—"}</div>
          <div>Price {fmtNum(cycle.current_price, 2)}</div>
          <div>200D MA {cycle.ma200 != null ? fmtNum(cycle.ma200, 2) : "UNKNOWN"}</div>
          <div>ATH DD {cycle.drawdown != null ? fmtPct(cycle.drawdown) : "UNKNOWN"}</div>
          <div>Hashrate {ind.hashrate?.current_hashrate ? Number(ind.hashrate.current_hashrate).toExponential(2) : "UNKNOWN"}</div>
          <div>Height {ind.block_height?.height ?? "UNKNOWN"}</div>
          <div>BTC.D {ind.btc_dominance ?? "UNKNOWN"}%</div>
          <div>MVRV {cycle.missing_indicators?.mvrv ? "UNKNOWN" : "—"}</div>
        </div>
        <div className="mt-3">
          <CandleChart candles={candles} />
        </div>
        <Disclaimer text={cycle.disclaimer} />
      </Panel>
      <Panel title="Portfolio">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Invested {fmtNum(port.total_invested, 2)}</div>
          <div>Value {fmtNum(port.current_value, 2)}</div>
          <div>Net PnL {fmtNum(port.net_pnl, 2)}</div>
          <div>ROI {port.roi != null ? fmtPct(port.roi) : "—"}</div>
          <div>Today {port.today_pnl != null ? fmtNum(port.today_pnl, 2) : "UNKNOWN"}</div>
          <div>Week {port.week_pnl != null ? fmtNum(port.week_pnl, 2) : "UNKNOWN"}</div>
          <div>Month {port.month_pnl != null ? fmtNum(port.month_pnl, 2) : "UNKNOWN"}</div>
        </div>
        <p className="mt-2 text-xs text-[#8aa0c2]">{port.period_note}</p>
        <Link className="mt-3 inline-block text-xs text-[#3ee0b4]" to="/portfolio">Open tracking center →</Link>
      </Panel>
      <Panel title="Alerts">
        {(data?.notifications || []).slice(0, 6).map((n: any) => (
          <div key={n.id} className="border-b border-[#1e2a44] py-1 text-sm">{n.title}</div>
        ))}
        {!data?.notifications?.length && <div className="text-sm text-[#8aa0c2]">No unread alerts.</div>}
      </Panel>
      <Panel title="50X Radar (last scan)">
        {(data?.radar_latest || []).length === 0 && (
          <p className="text-sm text-[#8aa0c2]">No persisted radar scores yet. Run a live CoinGecko + GoPlus scan.</p>
        )}
        {(data?.radar_latest || []).slice(0, 8).map((r: any) => (
          <div key={r.project_id} className="flex items-center justify-between border-b border-[#1e2a44] py-1 text-sm">
            <Link className="text-[#3ee0b4]" to={`/projects/${encodeURIComponent(r.project_id)}`}>{r.symbol || r.name}</Link>
            <span className="font-mono">{r.score}</span>
          </div>
        ))}
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/radar">Open 50X Radar →</Link>
      </Panel>
      <Panel title="Futures volume Top 3 (live)">
        {(data?.futures_volume_top || []).map((r: any) => (
          <div key={r.symbol} className="flex items-center justify-between border-b border-[#1e2a44] py-1 text-sm">
            <Link className="font-mono text-[#3ee0b4]" to={`/assets/${r.symbol}`}>#{r.rank} {r.symbol}</Link>
            <span>{r.last} · {r.change_pct}%</span>
          </div>
        ))}
        {!(data?.futures_volume_top || []).length && <div className="text-sm text-[#8aa0c2]">Ticker unavailable: {data?.ticker_status?.status || "UNKNOWN"}</div>}
        {(data?.futures_analyzed_top || []).length > 0 && (
          <div className="mt-3 text-xs text-[#8aa0c2]">Last analyzed Top 3: {(data.futures_analyzed_top || []).map((t: any) => `${t.symbol} ${t.direction}`).join(" · ")}</div>
        )}
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/futures">Open Futures →</Link>
      </Panel>
      <Panel title="Football (last model run)">
        {(data?.football_latest || []).slice(0, 4).map((m: any) => (
          <div key={m.match} className="border-b border-[#1e2a44] py-1 text-xs">
            {m.home && m.away ? `${m.home} vs ${m.away}` : m.match} · H {m.home_win} D {m.draw} A {m.away_win}
          </div>
        ))}
        {!(data?.football_latest || []).length && <div className="text-sm text-[#8aa0c2]">No stored football predictions yet.</div>}
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-[#3ee0b4]">
          <Link to="/spot">Spot</Link>
          <Link to="/airdrop">Airdrop</Link>
          <Link to="/launch">Launch</Link>
          <Link to="/football">Football</Link>
          <Link to="/lottery">Lottery</Link>
        </div>
      </Panel>
    </div>
  );
}
