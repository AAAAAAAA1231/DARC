import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel } from "../components/ui";
import { fmtUsd } from "../format";

export default function Airdrop({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);

  async function scan() {
    setBusy(true);
    try { setData(await api("/api/airdrop/scan", { method: "POST" })); } finally { setBusy(false); }
  }

  useEffect(() => {
    api("/api/airdrop/latest").then(setData).catch(() => undefined);
  }, []);

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return (data?.projects || []).filter((p: any) => `${p.project} ${p.chain}`.toLowerCase().includes(q));
  }, [data, query]);
  const slice = rows.slice(page * 12, page * 12 + 12);

  return (
    <Panel title="Airdrop hunter" action={<Button disabled={busy} onClick={scan}>{busy ? "Scanning DefiLlama…" : "Scan"}</Button>}>
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead style={{ color: "var(--muted)" }}><tr><th>Project</th><th>Chain</th><th>TVL</th><th>Funding</th><th>Expected ROI</th><th>Risk</th></tr></thead>
        <tbody>
          {slice.map((p: any) => (
            <tr key={p.project_id} className="border-t" style={{ borderColor: "var(--border)" }}>
              <td className="py-2"><Link style={{ color: "var(--accent)" }} to={`/projects/${p.project_id}`}>{p.project}</Link></td>
              <td>{p.chain}</td>
              <td>{p.tvl != null ? fmtUsd(p.tvl) : "UNKNOWN"}</td>
              <td>{p.funding}</td>
              <td>{p.expected_roi}</td>
              <td>{p.risk}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex gap-2 text-xs">
        <Button onClick={() => setPage((n) => Math.max(0, n - 1))}>Prev</Button>
        <Button onClick={() => setPage((n) => n + 1)}>Next</Button>
      </div>
    </Panel>
  );
}
