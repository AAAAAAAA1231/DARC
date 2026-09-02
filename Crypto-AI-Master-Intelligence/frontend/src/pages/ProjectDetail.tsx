import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

const STATUSES = ["PENDING", "FOLLOWING", "HIGH_PRIORITY", "WATCHING", "PARTICIPATED", "COMPLETED", "ABANDONED", "REJECTED", "EXPIRED"];

export default function ProjectDetail() {
  const id = decodeURIComponent(location.pathname.split("/").pop() || "");
  const [data, setData] = useState<any>(null);
  const [note, setNote] = useState("");
  const [fill, setFill] = useState({ side: "BUY", quantity: "", price: "", fee: "0", venue: "", wallet: "" });

  async function load() {
    setData(await api(`/api/projects/${id}`));
  }
  useEffect(() => { load(); }, [id]);

  if (!data) return <div>Loading…</div>;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Project">
        <div className="space-y-1 text-sm">
          <div className="text-lg">{data.name} {data.symbol}</div>
          <div className="font-mono text-xs">{data.project_id}</div>
          <div>Status {data.status} · Hidden {String(data.hidden)}</div>
          <div>Chain {data.chain || "—"} · Contract {data.contract || "—"}</div>
          <div>Sources {(data.sources || []).join(", ")}</div>
          <div>Security {data.last_security || "UNKNOWN"} · Score {data.last_score ?? "—"} · Signal {data.last_signal || "—"}</div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATUSES.map((s) => (
            <Button key={s} onClick={async () => { await api(`/api/projects/${id}/status`, { method: "POST", body: JSON.stringify({ status: s }) }); load(); }}>{s}</Button>
          ))}
        </div>
      </Panel>
      <Panel title="Notes">
        <textarea className="w-full bg-transparent text-sm" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
        <Button onClick={async () => { await api(`/api/projects/${id}/notes`, { method: "POST", body: JSON.stringify({ body: note }) }); setNote(""); load(); }}>Add note</Button>
        {(data.notes || []).map((n: any, i: number) => <div key={i} className="mt-2 text-xs text-[#8aa0c2]">{n.at}: {n.body}</div>)}
      </Panel>
      <Panel title="Score history">
        {(data.score_history || []).slice(0, 12).map((s: any, i: number) => (
          <div key={i} className="border-t border-[#1e2a44] py-1 text-xs">{s.at} {s.module} {s.signal} {JSON.stringify(s.scores?.score_50x || s.scores?.score)}</div>
        ))}
      </Panel>
      <Panel title="I already bought (paper tracking)">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <select value={fill.side} onChange={(e) => setFill({ ...fill, side: e.target.value })} className="bg-transparent"><option>BUY</option><option>SELL</option></select>
          <input placeholder="qty" value={fill.quantity} onChange={(e) => setFill({ ...fill, quantity: e.target.value })} className="bg-transparent" />
          <input placeholder="price" value={fill.price} onChange={(e) => setFill({ ...fill, price: e.target.value })} className="bg-transparent" />
          <input placeholder="fee" value={fill.fee} onChange={(e) => setFill({ ...fill, fee: e.target.value })} className="bg-transparent" />
          <input placeholder="venue" value={fill.venue} onChange={(e) => setFill({ ...fill, venue: e.target.value })} className="bg-transparent" />
          <input placeholder="public wallet only" value={fill.wallet} onChange={(e) => setFill({ ...fill, wallet: e.target.value })} className="bg-transparent" />
        </div>
        <Button onClick={async () => {
          await api("/api/portfolio/fill", { method: "POST", body: JSON.stringify({ module: "50X", symbol: data.symbol || data.name, project_id: id, ...fill, quantity: Number(fill.quantity), price: Number(fill.price), fee: Number(fill.fee || 0) }) });
        }}>Record fill</Button>
      </Panel>
    </div>
  );
}
