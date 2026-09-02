import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";

export default function Launch({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [klass, setKlass] = useState("");
  const [page, setPage] = useState(0);

  async function scan() {
    setBusy(true);
    try { setData(await api("/api/launch/scan", { method: "POST" })); } finally { setBusy(false); }
  }

  useEffect(() => {
    api("/api/launch/latest").then(setData).catch(() => undefined);
  }, []);

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return (data?.projects || []).filter((p: any) => {
      if (klass && p.launch_class !== klass) return false;
      return `${p.name} ${p.symbol || ""} ${p.chain || ""}`.toLowerCase().includes(q);
    });
  }, [data, query, klass]);
  const slice = rows.slice(page * 12, page * 12 + 12);

  return (
    <Panel
      title="新盘 / 预售猎手"
      action={
        <div className="flex gap-2">
          <select value={klass} onChange={(e) => { setKlass(e.target.value); setPage(0); }} className="bg-transparent text-xs">
            <option value="">全部级别</option>
            <option value="A">A</option>
            <option value="B">B</option>
            <option value="C">C</option>
          </select>
          <Button disabled={busy} onClick={scan}>{busy ? "正在搜索 DexScreener…" : "扫描"}</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead style={{ color: "var(--muted)" }}><tr><th>名称</th><th>级别</th><th>链</th><th>融资</th><th>安全</th></tr></thead>
        <tbody>
          {slice.map((p: any) => (
            <tr key={p.project_id} className="border-t" style={{ borderColor: "var(--border)" }}>
              <td className="py-2"><Link style={{ color: "var(--accent)" }} to={`/projects/${p.project_id}`}>{p.name}</Link></td>
              <td>{p.launch_class}</td>
              <td>{p.chain}</td>
              <td>{p.funding}</td>
              <td><Status value={p.security?.verdict} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex gap-2 text-xs">
        <Button onClick={() => setPage((n) => Math.max(0, n - 1))}>上一页</Button>
        <Button onClick={() => setPage((n) => n + 1)}>下一页</Button>
      </div>
    </Panel>
  );
}
