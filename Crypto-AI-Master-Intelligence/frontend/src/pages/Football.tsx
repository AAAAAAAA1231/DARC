import { useState } from "react";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";

export default function Football() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ match_external_id: "", user_placed_bet: false, selection: "HOME", stake: "", odds: "" });

  async function refresh() {
    setBusy(true);
    try { setData(await api("/api/football/refresh", { method: "POST" })); } finally { setBusy(false); }
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
  }

  return (
    <div className="space-y-4">
      <Panel title="Football — Bundesliga / Serie A / La Liga" action={<Button disabled={busy} onClick={refresh}>{busy ? "Loading TheSportsDB…" : "Refresh live fixtures"}</Button>}>
        <Disclaimer text={data?.disclaimer} />
        {(data?.predictions || []).map((m: any) => (
          <div key={m.external_id} className="border-t border-[#1e2a44] py-3 text-sm">
            <div className="font-semibold">{m.home} vs {m.away} · {m.competition}</div>
            <div className="font-mono text-xs">1 { (m.home_win*100).toFixed(1)}% · X {(m.draw*100).toFixed(1)}% · 2 {(m.away_win*100).toFixed(1)}% · O2.5 {(m.over_25*100).toFixed(1)}% · BTTS {(m.btts*100).toFixed(1)}%</div>
            <div className="text-xs text-[#8aa0c2]">Injuries: {m.injuries} · xG: {m.xg} · conf {m.confidence}</div>
            <div className="text-xs">Top scorelines: {(m.top_scorelines || []).map((s: any) => `${s.home}-${s.away}`).join(", ")}</div>
            <button className="mt-1 text-xs text-[#3ee0b4]" onClick={() => setForm((f) => ({ ...f, match_external_id: m.external_id }))}>Track this prediction</button>
          </div>
        ))}
      </Panel>
      <Panel title="Track model vs user bet vs result">
        <div className="grid gap-2 text-sm md:grid-cols-2">
          <input className="bg-transparent" value={form.match_external_id} onChange={(e) => setForm({ ...form, match_external_id: e.target.value })} placeholder="match id" />
          <input className="bg-transparent" value={form.selection} onChange={(e) => setForm({ ...form, selection: e.target.value })} placeholder="HOME/DRAW/AWAY" />
          <input className="bg-transparent" value={form.stake} onChange={(e) => setForm({ ...form, stake: e.target.value })} placeholder="stake (optional)" />
          <input className="bg-transparent" value={form.odds} onChange={(e) => setForm({ ...form, odds: e.target.value })} placeholder="odds (optional)" />
        </div>
        <label className="mt-2 block text-xs"><input type="checkbox" checked={form.user_placed_bet} onChange={(e) => setForm({ ...form, user_placed_bet: e.target.checked })} /> I placed a bet (separate from the model)</label>
        <Button onClick={track}>Save tracking</Button>
      </Panel>
    </div>
  );
}
