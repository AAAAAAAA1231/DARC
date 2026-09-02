import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import HoldingBadge from "../components/HoldingBadge";
import { Button, Disclaimer, Panel, Status } from "../components/ui";
import { holdingFor, HoldingOverlay } from "../holdings";

export default function Radar({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [overlay, setOverlay] = useState<Record<string, HoldingOverlay>>({});
  const [busy, setBusy] = useState(false);
  const [sort, setSort] = useState("score");
  const [page, setPage] = useState(0);

  async function loadOverlay() {
    try {
      const res = await api<{ overlay: Record<string, HoldingOverlay> }>("/api/holdings/overlay");
      setOverlay(res.overlay || {});
    } catch {
      setOverlay({});
    }
  }

  async function loadCached() {
    try {
      const cached = await api<any>("/api/radar/latest");
      if ((cached.recommended || []).length) setData(cached);
    } catch {
      /* empty until first scan */
    }
  }

  async function scan() {
    setBusy(true);
    try {
      setData(await api("/api/radar/scan?limit=20", { method: "POST" }));
      await loadOverlay();
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadCached();
    loadOverlay();
  }, []);

  const rows = useMemo(() => {
    let list = [...(data?.recommended || []), ...(data?.candidates || []).filter((c: any) => !c.eligible_for_pool)];
    const seen = new Set();
    list = list.filter((r: any) => {
      if (seen.has(r.project_id)) return false;
      seen.add(r.project_id);
      return `${r.name} ${r.symbol}`.toLowerCase().includes(query.toLowerCase());
    });
    list.sort((a: any, b: any) => (sort === "score" ? (b.scores?.score_50x || 0) - (a.scores?.score_50x || 0) : a.name.localeCompare(b.name)));
    return list;
  }, [data, query, sort]);

  const pageSize = 10;
  const slice = rows.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="space-y-4">
      <Panel
        title="五十倍机会雷达"
        action={
          <div className="flex gap-2">
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="bg-transparent text-xs">
              <option value="score">分数</option>
              <option value="name">名称</option>
            </select>
            <Button disabled={busy} onClick={scan}>{busy ? "正在扫描实时接口…" : "扫描实时市场"}</Button>
          </div>
        }
      >
        <p className="text-sm" style={{ color: "var(--muted)" }}>安全是硬门槛。恶意 / 高风险 / 未知不能进入前 10/20。已持仓会显示成本与盈亏对照模型，绝不是实盘下单。{data?.from_cache ? " 当前为上次保存的扫描。" : ""}</p>
        <Disclaimer text={data?.disclaimer} />
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead style={{ color: "var(--muted)" }}>
              <tr>
                <th>项目</th><th>分数</th><th>安全</th><th>市值</th><th>入池</th><th>持仓</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((r: any) => (
                <tr key={r.project_id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="py-2">
                    <Link style={{ color: "var(--accent)" }} to={`/projects/${r.project_id}`}>{r.symbol} {r.name}</Link>
                    {r.symbol && (
                      <div>
                        <Link className="text-[11px]" style={{ color: "var(--muted)" }} to={`/assets/${String(r.symbol).toUpperCase()}`}>K线</Link>
                      </div>
                    )}
                  </td>
                    <td className="font-mono">{r.scores?.score_50x ?? "未知"}</td>
                  <td><Status value={r.security?.verdict} /></td>
                  <td className="font-mono">{r.market_cap ?? "未知"}</td>
                  <td>{r.eligible_for_pool ? "是" : "否"}</td>
                  <td><HoldingBadge overlay={holdingFor(overlay, r.symbol)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex gap-2 text-xs">
          <Button onClick={() => setPage((p) => Math.max(0, p - 1))}>上一页</Button>
          <Button onClick={() => setPage((p) => p + 1)}>下一页</Button>
        </div>
      </Panel>
    </div>
  );
}
