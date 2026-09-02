import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Panel } from "../components/ui";
import { fmtNum, fmtPct } from "../format";

export default function Portfolio() {
  const [data, setData] = useState<any>(null);
  const [module, setModule] = useState("");
  const [fill, setFill] = useState({ module: "SPOT", symbol: "BTCUSDT", side: "BUY", quantity: "0.01", price: "", fee: "0" });

  async function load() {
    setData(await api(`/api/portfolio${module ? `?module=${module}` : ""}`));
  }
  useEffect(() => { load(); }, [module]);

  return (
    <div className="space-y-4">
      <Panel title="Global portfolio" action={
        <select value={module} onChange={(e) => setModule(e.target.value)} className="bg-transparent text-xs">
          <option value="">ALL</option>
          {["50X","FUTURES","SPOT","AIRDROP","LAUNCH","FOOTBALL","LOTTERY"].map((m) => <option key={m}>{m}</option>)}
        </select>
      }>
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>Invested {fmtNum(data?.total_invested, 2)}</div>
          <div>Value {fmtNum(data?.current_value, 2)}</div>
          <div>Gross {fmtNum(data?.gross_pnl, 2)}</div>
          <div>Costs {fmtNum(data?.total_cost, 4)}</div>
          <div>Net {fmtNum(data?.net_pnl, 2)}</div>
          <div>Today {data?.today_pnl != null ? fmtNum(data.today_pnl, 2) : "UNKNOWN"}</div>
          <div>Week {data?.week_pnl != null ? fmtNum(data.week_pnl, 2) : "UNKNOWN"}</div>
          <div>Month {data?.month_pnl != null ? fmtNum(data.month_pnl, 2) : "UNKNOWN"}</div>
          <div>ROI {data?.roi != null ? fmtPct(data.roi) : "—"}</div>
          <div>Realized {fmtNum(data?.realized_pnl, 2)}</div>
          <div>Unrealized {fmtNum(data?.unrealized_pnl, 2)}</div>
        </div>
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{data?.period_note}</p>
      </Panel>
      <Panel title="Record actual fill">
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
          <input className="bg-transparent" value={fill.symbol} onChange={(e) => setFill({ ...fill, symbol: e.target.value })} />
          <select className="bg-transparent" value={fill.side} onChange={(e) => setFill({ ...fill, side: e.target.value })}><option>BUY</option><option>SELL</option></select>
          <input className="bg-transparent" value={fill.quantity} onChange={(e) => setFill({ ...fill, quantity: e.target.value })} />
          <input className="bg-transparent" placeholder="price" value={fill.price} onChange={(e) => setFill({ ...fill, price: e.target.value })} />
          <input className="bg-transparent" placeholder="fee" value={fill.fee} onChange={(e) => setFill({ ...fill, fee: e.target.value })} />
          <select className="bg-transparent" value={fill.module} onChange={(e) => setFill({ ...fill, module: e.target.value })}>
            {["50X","FUTURES","SPOT"].map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
        <Button onClick={async () => { await api("/api/portfolio/fill", { method: "POST", body: JSON.stringify({ ...fill, quantity: Number(fill.quantity), price: Number(fill.price), fee: Number(fill.fee) }) }); load(); }}>Save fill</Button>
      </Panel>
      <Panel title="Positions">
        <table className="w-full text-left text-sm">
          <thead style={{ color: "var(--muted)" }}><tr><th>Symbol</th><th>Status</th><th>Qty</th><th>Avg</th><th>Value</th><th>Net</th><th>Signal</th></tr></thead>
          <tbody>
            {(data?.positions || []).map((p: any) => (
              <tr key={p.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="py-2"><Link style={{ color: "var(--accent)" }} to={`/assets/${p.symbol}`}>{p.symbol}</Link></td>
                <td>{p.status}</td>
                <td>{fmtNum(p.quantity, 6)}</td>
                <td>{fmtNum(p.avg_cost, 2)}</td>
                <td>{p.current_value != null ? fmtNum(p.current_value, 2) : "UNKNOWN"}</td>
                <td>{p.net_pnl != null ? fmtNum(p.net_pnl, 2) : "UNKNOWN"}</td>
                <td>{p.original_model_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
