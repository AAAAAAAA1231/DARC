import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";

export default function Airdrop() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  async function scan() {
    setBusy(true);
    try { setData(await api("/api/airdrop/scan", { method: "POST" })); } finally { setBusy(false); }
  }
  return (
    <Panel title="Airdrop hunter" action={<Button disabled={busy} onClick={scan}>{busy ? "Scanning DefiLlama…" : "Scan"}</Button>}>
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead className="text-[#8aa0c2]"><tr><th>Project</th><th>Chain</th><th>TVL</th><th>Funding</th><th>Expected ROI</th><th>Risk</th></tr></thead>
        <tbody>
          {(data?.projects || []).map((p: any) => (
            <tr key={p.project_id} className="border-t border-[#1e2a44]">
              <td className="py-2"><Link className="text-[#3ee0b4]" to={`/projects/${p.project_id}`}>{p.project}</Link></td>
              <td>{p.chain}</td>
              <td>{p.tvl ?? "UNKNOWN"}</td>
              <td>{p.funding}</td>
              <td>{p.expected_roi}</td>
              <td>{p.risk}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
