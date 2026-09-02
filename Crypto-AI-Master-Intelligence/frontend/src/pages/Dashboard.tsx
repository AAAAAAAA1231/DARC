import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";

export default function Dashboard() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      setErr(null);
      setData(await api("/api/dashboard"));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const cycle = data?.btc_cycle || {};
  const port = data?.portfolio || {};

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel title="Market Regime / BTC Cycle" action={<Button onClick={load}>Refresh</Button>}>
        {err && <div className="text-[#ff5d73]">{err}</div>}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Regime <Status value={cycle.regime} /></div>
          <div>Phase <span className="font-mono">{cycle.phase || "—"}</span></div>
          <div>Bull {cycle.bull_score ?? "UNKNOWN"}</div>
          <div>Bear {cycle.bear_score ?? "UNKNOWN"}</div>
          <div>Confidence {cycle.confidence ?? "—"}</div>
          <div>Price {cycle.current_price ?? "—"}</div>
        </div>
        <Disclaimer text={cycle.disclaimer} />
      </Panel>
      <Panel title="Portfolio">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Invested {port.total_invested ?? "0"}</div>
          <div>Value {port.current_value ?? "0"}</div>
          <div>Net PnL {port.net_pnl ?? "0"}</div>
          <div>ROI {port.roi != null ? `${(port.roi * 100).toFixed(2)}%` : "—"}</div>
        </div>
        <Link className="mt-3 inline-block text-xs text-[#3ee0b4]" to="/portfolio">Open tracking center →</Link>
      </Panel>
      <Panel title="Alerts">
        {(data?.notifications || []).slice(0, 6).map((n: any) => (
          <div key={n.id} className="border-b border-[#1e2a44] py-1 text-sm">{n.title}</div>
        ))}
        {!data?.notifications?.length && <div className="text-sm text-[#8aa0c2]">No unread alerts.</div>}
      </Panel>
      <Panel title="50X Radar">
        <p className="text-sm text-[#8aa0c2]">Run a live CoinGecko + GoPlus scan. UNKNOWN security never enters the recommendation pool.</p>
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/radar">Open 50X Radar →</Link>
      </Panel>
      <Panel title="Futures Top 3">
        <p className="text-sm text-[#8aa0c2]">Dynamic Binance USDT-M volume universe. No hardcoded BTC/ETH list.</p>
        <Link className="mt-2 inline-block text-xs text-[#3ee0b4]" to="/futures">Open Futures →</Link>
      </Panel>
      <Panel title="Spot / Airdrop / Launch / Football / Lottery">
        <div className="flex flex-wrap gap-3 text-xs text-[#3ee0b4]">
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
