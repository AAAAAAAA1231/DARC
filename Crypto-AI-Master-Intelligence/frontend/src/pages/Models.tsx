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
      <Panel title="模型版本" action={
        <select value={module} onChange={(e) => setModule(e.target.value)} className="bg-transparent text-xs">
          <option value="FUTURES">合约</option>
          <option value="SPOT">现货</option>
          <option value="RADAR">雷达</option>
          <option value="FOOTBALL">足球</option>
          <option value="BTC_CYCLE">BTC周期</option>
          <option value="LOTTERY">彩票</option>
        </select>
      }>
        {(data?.versions || []).map((v: any) => (
          <div key={v.version} className="flex items-center justify-between border-t border-[#1e2a44] py-2 text-sm">
            <div>{v.version} {v.active ? "（当前）" : ""} · 父版本 {v.parent || "—"}</div>
            {!v.active && <Button onClick={async () => { await api("/api/models/rollback", { method: "POST", body: JSON.stringify({ module, version: v.version }) }); load(); }}>回滚</Button>}
          </div>
        ))}
      </Panel>
      <Panel title="自我复盘" action={<Button onClick={async () => setReview(await api(`/api/models/review?module=${module}`, { method: "POST" }))}>运行复盘</Button>}>
        <pre className="overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(review, null, 2)}</pre>
      </Panel>
      <Panel title="滚动样本外回测" action={<Button onClick={async () => setBt(await api("/api/backtest/walk-forward?symbol=BTCUSDT", { method: "POST" }))}>运行 BTCUSDT</Button>}>
        <pre className="overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(bt, null, 2)}</pre>
      </Panel>
    </div>
  );
}
