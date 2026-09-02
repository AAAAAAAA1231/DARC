import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";

export default function Futures() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function scan() {
    setBusy(true);
    try {
      setData(await api("/api/futures/scan?analyze_n=8", { method: "POST" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel title="Futures — live USDT-M volume universe" action={<Button disabled={busy} onClick={scan}>{busy ? "Fetching Binance…" : "Scan Top 100"}</Button>}>
        <div className="text-sm">Universe size: {data?.universe_count ?? "—"}</div>
        <Disclaimer text={data?.disclaimer} />
      </Panel>
      <div className="grid gap-4 md:grid-cols-3">
        {(data?.top3 || []).map((t: any) => (
          <Panel key={t.symbol} title={`#${t.rank} ${t.symbol}`}>
            <div className="space-y-1 text-sm">
              <div><Link className="text-[#3ee0b4] font-mono" to={`/assets/${t.symbol}`}>{t.symbol} chart</Link></div>
              <div>Direction <Status value={t.direction} /></div>
              <div>Confidence {t.confidence}</div>
              <div>Price {t.current_price}</div>
              <div>Ideal entry {t.ideal_entry}</div>
              <div>SL {t.stop_loss}</div>
              <div>TP1 {t.tp1} / TP2 {t.tp2} / TP3 {t.tp3}</div>
              <div>R/R {t.risk_reward?.toFixed?.(2) ?? t.risk_reward}</div>
              <div className="text-xs text-[#8aa0c2]">Invalidation: {t.invalidation}</div>
              <ul className="list-disc pl-4 text-xs">{(t.main_reasons || []).slice(0, 4).map((r: string) => <li key={r}>{r}</li>)}</ul>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
