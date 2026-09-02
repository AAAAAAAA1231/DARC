import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import HoldingBadge from "../components/HoldingBadge";
import { Button, Disclaimer, Panel } from "../components/ui";
import { holdingFor, HoldingOverlay } from "../holdings";

export default function Spot() {
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
    loadOverlay();
  }, []);

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
        <thead className="text-[#8aa0c2]"><tr><th>Symbol</th><th>Price</th><th>Buy zone</th><th>SL</th><th>TP1</th><th>Score</th><th>Holding</th></tr></thead>
        <tbody>
          {(data?.opportunities || []).map((r: any) => (
            <tr key={r.symbol} className="border-t border-[#1e2a44]">
              <td className="py-2 font-mono"><Link className="text-[#3ee0b4]" to={`/assets/${r.symbol}`}>{r.symbol}</Link></td>
              <td>{r.current_price}</td>
              <td>{r.buy_zone?.[0]?.toFixed?.(4)} – {r.buy_zone?.[1]?.toFixed?.(4)}</td>
              <td>{r.stop_loss}</td>
              <td>{r.tp1}</td>
              <td>{r.score}</td>
              <td><HoldingBadge overlay={holdingFor(overlay, r.symbol)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
