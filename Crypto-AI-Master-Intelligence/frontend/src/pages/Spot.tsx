import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import HoldingBadge from "../components/HoldingBadge";
import { Button, Disclaimer, Panel } from "../components/ui";
import { fmtNum } from "../format";
import { holdingFor, HoldingOverlay } from "../holdings";

export default function Spot({ query }: { query: string }) {
  const [profile, setProfile] = useState("BALANCED");
  const [data, setData] = useState<any>(null);
  const [overlay, setOverlay] = useState<Record<string, HoldingOverlay>>({});
  const [busy, setBusy] = useState(false);

  async function loadOverlay() {
    try {
      const res = await api<{ overlay: Record<string, HoldingOverlay> }>("/api/holdings/overlay");
      setOverlay(res.overlay || {});
    } catch {
      setOverlay({});
    }
  }

  async function scan() {
    setBusy(true);
    try {
      setData(await api(`/api/spot/scan?profile=${profile}`, { method: "POST" }));
      await loadOverlay();
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api(`/api/spot/latest?profile=${profile}`).then(setData).catch(() => undefined);
    loadOverlay();
  }, [profile]);

  const rows = useMemo(
    () => (data?.opportunities || []).filter((r: any) => String(r.symbol || "").toLowerCase().includes(query.toLowerCase())),
    [data, query],
  );

  return (
    <Panel
      title="现货机会"
      action={
        <div className="flex gap-2">
          <select value={profile} onChange={(e) => setProfile(e.target.value)} className="bg-transparent text-xs">
            <option value="CONSERVATIVE">保守</option>
            <option value="BALANCED">均衡</option>
            <option value="AGGRESSIVE">进取</option>
          </select>
          <Button disabled={busy} onClick={scan}>{busy ? "扫描中…" : "扫描"}</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead style={{ color: "var(--muted)" }}><tr><th>交易对</th><th>价格</th><th>买入区间</th><th>止损</th><th>止盈1</th><th>分数</th><th>持仓</th></tr></thead>
        <tbody>
          {rows.map((r: any) => (
            <tr key={r.symbol} className="border-t" style={{ borderColor: "var(--border)" }}>
              <td className="py-2 font-mono"><Link style={{ color: "var(--accent)" }} to={`/assets/${r.symbol}`}>{r.symbol}</Link></td>
              <td>{fmtNum(r.current_price)}</td>
              <td>{fmtNum(r.buy_zone?.[0])} – {fmtNum(r.buy_zone?.[1])}</td>
              <td>{fmtNum(r.stop_loss)}</td>
              <td>{fmtNum(r.tp1)}</td>
              <td>{r.score ?? "未知"}</td>
              <td><HoldingBadge overlay={holdingFor(overlay, r.symbol)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
