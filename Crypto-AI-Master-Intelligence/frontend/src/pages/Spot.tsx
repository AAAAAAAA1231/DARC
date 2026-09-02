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
      title="Spot opportunities"
      action={
        <div className="flex gap-2">
          <select value={profile} onChange={(e) => setProfile(e.target.value)} className="bg-transparent text-xs">
            <option>CONSERVATIVE</option>
            <option>BALANCED</option>
            <option>AGGRESSIVE</option>
          </select>
          <Button disabled={busy} onClick={scan}>{busy ? "Scanning…" : "Scan"}</Button>
        </div>
      }
    >
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead style={{ color: "var(--muted)" }}><tr><th>Symbol</th><th>Price</th><th>Buy zone</th><th>SL</th><th>TP1</th><th>Score</th><th>Holding</th></tr></thead>
        <tbody>
          {rows.map((r: any) => (
            <tr key={r.symbol} className="border-t" style={{ borderColor: "var(--border)" }}>
              <td className="py-2 font-mono"><Link style={{ color: "var(--accent)" }} to={`/assets/${r.symbol}`}>{r.symbol}</Link></td>
              <td>{fmtNum(r.current_price)}</td>
              <td>{fmtNum(r.buy_zone?.[0])} – {fmtNum(r.buy_zone?.[1])}</td>
              <td>{fmtNum(r.stop_loss)}</td>
              <td>{fmtNum(r.tp1)}</td>
              <td>{r.score ?? "UNKNOWN"}</td>
              <td><HoldingBadge overlay={holdingFor(overlay, r.symbol)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
