import { useState } from "react";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";

function fmtNumbers(n: any) {
  if (!n) return "—";
  if (n.red) return `R ${n.red.join(" ")} + B ${n.blue?.join(" ") || ""}`;
  if (n.front) return `F ${n.front.join(" ")} + B ${n.back?.join(" ") || ""}`;
  if (n.digits) return n.digits.join(" ");
  return JSON.stringify(n);
}

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
            <option value="qxc">七星彩</option>
          </select>
          <Button disabled={busy} onClick={refresh}>{busy ? "Fetching draws…" : "Load history"}</Button>
          <Button onClick={simulate}>Simulate 1M</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer || "Lottery is random. Nothing here guarantees a prize. Simulation count is not accuracy."} />
      <div className="mt-3 text-sm">
        Draws loaded: {data?.draws?.length ?? 0}
        {data?.source_status?.meta?.failover && <span className="ml-2 text-xs text-[#f5c542]">failover {data.source_status.meta.failover}</span>}
        {data?.ok === false && <span className="ml-2 text-[#ff5d73]">{data?.source_status?.error || "source down"}</span>}
      </div>
      <table className="mt-3 w-full text-left text-xs">
        <thead className="text-[#8aa0c2]"><tr><th>Issue</th><th>Time</th><th>Numbers</th><th>Source</th></tr></thead>
        <tbody>
          {(data?.draws || []).slice(0, 12).map((d: any) => (
            <tr key={d.issue} className="border-t border-[#1e2a44]">
              <td className="py-1 font-mono">{d.issue}</td>
              <td>{d.draw_time || "UNKNOWN"}</td>
              <td className="font-mono">{fmtNumbers(d.numbers)}</td>
              <td>{d.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <pre className="mt-2 overflow-auto text-xs text-[#8aa0c2]">{JSON.stringify(data?.recommended_combinations || [], null, 2)}</pre>
      {sim && <div className="text-xs">Job {sim.simulation_id} status {sim.status}</div>}
    </Panel>
  );
}
