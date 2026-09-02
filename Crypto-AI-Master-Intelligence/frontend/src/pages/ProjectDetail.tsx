import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

const STATUSES: [string, string][] = [
  ["PENDING", "待处理"],
  ["FOLLOWING", "跟进中"],
  ["HIGH_PRIORITY", "高优先级"],
  ["WATCHING", "观察"],
  ["PARTICIPATED", "已参与"],
  ["COMPLETED", "已完成"],
  ["ABANDONED", "已放弃"],
  ["REJECTED", "已拒绝"],
  ["EXPIRED", "已过期"],
];

export default function ProjectDetail() {
  const id = decodeURIComponent(location.pathname.split("/").pop() || "");
  const [data, setData] = useState<any>(null);
  const [note, setNote] = useState("");
  const [fill, setFill] = useState({ side: "BUY", quantity: "", price: "", fee: "0", venue: "", wallet: "" });

  async function load() {
    setData(await api(`/api/projects/${id}`));
  }
  useEffect(() => { load(); }, [id]);

  if (!data) return <div>加载中…</div>;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="项目">
        <div className="space-y-1 text-sm">
          <div className="text-lg">{data.name} {data.symbol}</div>
          <div className="font-mono text-xs">{data.project_id}</div>
          <div>状态 {data.status} · 隐藏 {String(data.hidden)}</div>
          <div>链 {data.chain || "—"} · 合约 {data.contract || "—"}</div>
          <div>来源 {(data.sources || []).join(", ")}</div>
          <div>安全 {data.last_security || "未知"} · 分数 {data.last_score ?? "—"} · 信号 {data.last_signal || "—"}</div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATUSES.map(([s, label]) => (
            <Button key={s} onClick={async () => { await api(`/api/projects/${id}/status`, { method: "POST", body: JSON.stringify({ status: s }) }); load(); }}>{label}</Button>
          ))}
        </div>
      </Panel>
      <Panel title="笔记">
        <textarea className="w-full bg-transparent text-sm" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
        <Button onClick={async () => { await api(`/api/projects/${id}/notes`, { method: "POST", body: JSON.stringify({ body: note }) }); setNote(""); load(); }}>添加笔记</Button>
        {(data.notes || []).map((n: any, i: number) => <div key={i} className="mt-2 text-xs text-[#8aa0c2]">{n.at}: {n.body}</div>)}
      </Panel>
      <Panel title="分数历史">
        {(data.score_history || []).slice(0, 12).map((s: any, i: number) => (
          <div key={i} className="border-t border-[#1e2a44] py-1 text-xs">{s.at} {s.module} {s.signal} {JSON.stringify(s.scores?.score_50x || s.scores?.score)}</div>
        ))}
      </Panel>
      <Panel title="我已买入（纸面跟踪）">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <select value={fill.side} onChange={(e) => setFill({ ...fill, side: e.target.value })} className="bg-transparent"><option value="BUY">买入</option><option value="SELL">卖出</option></select>
          <input placeholder="数量" value={fill.quantity} onChange={(e) => setFill({ ...fill, quantity: e.target.value })} className="bg-transparent" />
          <input placeholder="价格" value={fill.price} onChange={(e) => setFill({ ...fill, price: e.target.value })} className="bg-transparent" />
          <input placeholder="手续费" value={fill.fee} onChange={(e) => setFill({ ...fill, fee: e.target.value })} className="bg-transparent" />
          <input placeholder="场所" value={fill.venue} onChange={(e) => setFill({ ...fill, venue: e.target.value })} className="bg-transparent" />
          <input placeholder="仅公钥地址" value={fill.wallet} onChange={(e) => setFill({ ...fill, wallet: e.target.value })} className="bg-transparent" />
        </div>
        <Button onClick={async () => {
          await api("/api/portfolio/fill", { method: "POST", body: JSON.stringify({ module: "50X", symbol: data.symbol || data.name, project_id: id, ...fill, quantity: Number(fill.quantity), price: Number(fill.price), fee: Number(fill.fee || 0) }) });
        }}>记录成交</Button>
      </Panel>
    </div>
  );
}
