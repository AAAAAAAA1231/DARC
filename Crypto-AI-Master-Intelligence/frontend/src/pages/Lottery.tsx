import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";

function balls(v: any) {
  if (Array.isArray(v)) return v.join(" ");
  if (v == null) return "";
  return String(v);
}

function fmtNumbers(n: any) {
  if (!n) return "—";
  if (n.red) return `R ${balls(n.red)} + B ${balls(n.blue)}`;
  if (n.front) return `F ${balls(n.front)} + B ${balls(n.back)}`;
  if (n.digits) return balls(n.digits);
  return JSON.stringify(n);
}

export default function Lottery() {
  const [game, setGame] = useState("ssq");
  const [data, setData] = useState<any>(null);
  const [sim, setSim] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function loadCached() {
    try { setData(await api(`/api/lottery/latest?game=${game}`)); } catch { /* none yet */ }
  }
  async function refresh() {
    setBusy(true);
    try { setData(await api(`/api/lottery/refresh?game=${game}`, { method: "POST" })); } finally { setBusy(false); }
  }
  async function simulate() {
    const created = await api<any>("/api/simulations", { method: "POST", body: JSON.stringify({ kind: "lottery", paths: 1000000, parameters: { game } }) });
    setSim(created);
  }

  useEffect(() => { loadCached(); }, [game]);

  return (
    <Panel
      title="彩票 — 频率 + 蒙特卡洛"
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
          <Button disabled={busy} onClick={refresh}>{busy ? "正在拉取开奖…" : "加载历史"}</Button>
          <Button onClick={simulate}>模拟 100 万路径</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer || "彩票是随机的。这里不能保证中奖。模拟次数不等于准确率。"} />
      <div className="mt-3 text-sm">
        已加载期数：{data?.draws?.length ?? 0}
        {data?.source_status?.meta?.failover && <span className="ml-2 text-xs" style={{ color: "#c9a227" }}>故障转移 {data.source_status.meta.failover}</span>}
        {data?.from_cache && <span className="ml-2 text-xs" style={{ color: "var(--muted)" }}>（缓存）</span>}
        {data?.ok === false && <span className="ml-2" style={{ color: "var(--danger)" }}>{data?.source_status?.error || "数据源不可用"}</span>}
      </div>
      <table className="mt-3 w-full text-left text-xs">
        <thead style={{ color: "var(--muted)" }}><tr><th>期号</th><th>时间</th><th>号码</th><th>来源</th></tr></thead>
        <tbody>
          {(data?.draws || []).slice(0, 12).map((d: any) => (
            <tr key={d.issue} className="border-t" style={{ borderColor: "var(--border)" }}>
              <td className="py-1 font-mono">{d.issue}</td>
              <td>{d.draw_time || "未知"}</td>
              <td className="font-mono">{fmtNumbers(d.numbers)}</td>
              <td>{d.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 text-xs" style={{ color: "var(--muted)" }}>频率样本组合（未来开奖仍是随机的）</div>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {(data?.recommended_combinations || []).map((c: any, i: number) => (
          <li key={i} className="font-mono">{fmtNumbers(c)}</li>
        ))}
      </ul>
      {sim && <div className="text-xs">任务 {sim.simulation_id} 状态 {sim.status}</div>}
    </Panel>
  );
}
