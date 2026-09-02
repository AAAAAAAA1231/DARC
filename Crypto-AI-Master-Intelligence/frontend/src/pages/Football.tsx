import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";
import { fmtPct } from "../format";

export default function Football({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ match_external_id: "", user_placed_bet: false, selection: "HOME", stake: "", odds: "" });

  async function refresh() {
    setBusy(true);
    try {
      const live = await api<any>("/api/football/refresh", { method: "POST" });
      const cached = await api<any>("/api/football/latest");
      setData({ ...live, tracked: cached.tracked });
    } finally { setBusy(false); }
  }
  async function track() {
    await api("/api/football/track", {
      method: "POST",
      body: JSON.stringify({
        ...form,
        stake: form.stake ? Number(form.stake) : null,
        odds: form.odds ? Number(form.odds) : null,
      }),
    });
    setData(await api("/api/football/latest"));
  }

  useEffect(() => {
    api("/api/football/latest").then(setData).catch(() => undefined);
  }, []);

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return (data?.predictions || []).filter((m: any) => `${m.home} ${m.away} ${m.competition}`.toLowerCase().includes(q));
  }, [data, query]);

  return (
    <div className="space-y-4">
      <Panel title="足球 — 德甲 / 意甲 / 西甲" action={<Button disabled={busy} onClick={refresh}>{busy ? "正在加载 TheSportsDB…" : "刷新实时赛程"}</Button>}>
        <Disclaimer text={data?.disclaimer} />
        {rows.map((m: any) => (
          <div key={m.external_id} className="border-t py-3 text-sm" style={{ borderColor: "var(--border)" }}>
            <div className="font-semibold">{m.home} vs {m.away} · {m.competition}</div>
            <div className="font-mono text-xs">1 {fmtPct(m.home_win)} · X {fmtPct(m.draw)} · 2 {fmtPct(m.away_win)} · O2.5 {fmtPct(m.over_25)} · BTTS {fmtPct(m.btts)}</div>
            <div className="text-xs" style={{ color: "var(--muted)" }}>伤病：{m.injuries ?? "未知"} · 预期进球：{m.xg ?? "未知"} · 置信度 {m.confidence}</div>
            <div className="text-xs">高频比分：{(m.top_scorelines || []).map((s: any) => `${s.home}-${s.away}`).join(", ")}</div>
            <button className="mt-1 text-xs" style={{ color: "var(--accent)" }} onClick={() => setForm((f) => ({ ...f, match_external_id: m.external_id }))}>跟踪此预测</button>
          </div>
        ))}
      </Panel>
      <Panel title="跟踪：模型 vs 你的投注 vs 赛果">
        <div className="grid gap-2 text-sm md:grid-cols-2">
          <input className="bg-transparent" value={form.match_external_id} onChange={(e) => setForm({ ...form, match_external_id: e.target.value })} placeholder="比赛编号" />
          <select className="bg-transparent" value={form.selection} onChange={(e) => setForm({ ...form, selection: e.target.value })}>
            <option value="HOME">主胜</option>
            <option value="DRAW">平局</option>
            <option value="AWAY">客胜</option>
          </select>
          <input className="bg-transparent" value={form.stake} onChange={(e) => setForm({ ...form, stake: e.target.value })} placeholder="本金（可选）" />
          <input className="bg-transparent" value={form.odds} onChange={(e) => setForm({ ...form, odds: e.target.value })} placeholder="赔率（可选）" />
        </div>
        <label className="mt-2 block text-xs"><input type="checkbox" checked={form.user_placed_bet} onChange={(e) => setForm({ ...form, user_placed_bet: e.target.checked })} /> 我已实际投注（与模型分开记录）</label>
        <Button onClick={track}>保存跟踪</Button>
        {(data?.tracked || []).length > 0 && (
          <table className="mt-3 w-full text-left text-xs">
            <thead style={{ color: "var(--muted)" }}><tr><th>比赛</th><th>用户投注</th><th>选择</th><th>赛果</th><th>盈亏</th></tr></thead>
            <tbody>
              {data.tracked.map((b: any) => (
                <tr key={b.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="py-1">{b.match}</td>
                  <td>{b.user_placed_bet ? "是" : "仅模型"}</td>
                  <td>{b.selection}</td>
                  <td>{b.result}</td>
                  <td>{b.profit ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
