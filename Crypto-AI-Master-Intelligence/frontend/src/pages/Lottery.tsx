import { useState } from "react";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";

export default function Lottery() {
  const [game, setGame] = useState("ssq");
  const [data, setData] = useState<any>(null);
  const [sim, setSim] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setBusy(true);
    try { setData(await api(`/api/lottery/refresh?game=${game}`, { method: "POST" })); } finally { setBusy(false); }
  }
  async function simulate() {
    const created = await api<any>("/api/simulations", { method: "POST", body: JSON.stringify({ kind: "lottery", paths: 1000000, parameters: { game } }) });
    setSim(created);
  }

  return (
    <Panel
      title="Lottery — frequency + Monte Carlo"
      action={
        <div className="flex gap-2">
          <select value={game} onChange={(e) => setGame(e.target.value)} className="bg-transparent text-xs">
            <option value="ssq">双色球</option>
            <option value="dlt">大乐透</option>
            <option value="pl3">排列三</option>
            <option value="pl5">排列五</option>
            <option value="3d">3D</option>
          </select>
          <Button disabled={busy} onClick={refresh}>{busy ? "Fetching draws…" : "Load history"}</Button>
          <Button onClick={simulate}>Simulate 1M</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer || "Lottery is random. Nothing here guarantees a prize. Simulation count is not accuracy."} />
      <div className="mt-3 text-sm">Draws loaded: {data?.draws?.length ?? 0}</div>
      <pre className="mt-2 overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(data?.recommended_combinations || [], null, 2)}</pre>
      {sim && <div className="text-xs">Job {sim.simulation_id} status {sim.status}</div>}
    </Panel>
  );
}
