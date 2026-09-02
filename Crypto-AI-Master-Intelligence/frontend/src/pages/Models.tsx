import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

export default function Models() {
  const [module, setModule] = useState("FUTURES");
  const [data, setData] = useState<any>(null);
  const [review, setReview] = useState<any>(null);
  const [bt, setBt] = useState<any>(null);

  async function load() { setData(await api(`/api/models?module=${module}`)); }
  useEffect(() => { load(); }, [module]);

  return (
    <div className="space-y-4">
      <Panel title="Model versions" action={
        <select value={module} onChange={(e) => setModule(e.target.value)} className="bg-transparent text-xs">
          {["FUTURES","SPOT","RADAR","FOOTBALL","BTC_CYCLE","LOTTERY"].map((m) => <option key={m}>{m}</option>)}
        </select>
      }>
        {(data?.versions || []).map((v: any) => (
          <div key={v.version} className="flex items-center justify-between border-t border-[#1e2a44] py-2 text-sm">
            <div>{v.version} {v.active ? "(active)" : ""} · parent {v.parent || "—"}</div>
            {!v.active && <Button onClick={async () => { await api("/api/models/rollback", { method: "POST", body: JSON.stringify({ module, version: v.version }) }); load(); }}>Rollback</Button>}
          </div>
        ))}
      </Panel>
      <Panel title="Self review" action={<Button onClick={async () => setReview(await api(`/api/models/review?module=${module}`, { method: "POST" }))}>Run review</Button>}>
        <pre className="overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(review, null, 2)}</pre>
      </Panel>
      <Panel title="Walk-forward backtest" action={<Button onClick={async () => setBt(await api("/api/backtest/walk-forward?symbol=BTCUSDT", { method: "POST" }))}>Run BTCUSDT</Button>}>
        <pre className="overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(bt, null, 2)}</pre>
      </Panel>
    </div>
  );
}
