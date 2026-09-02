import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";

export default function Radar({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [sort, setSort] = useState("score");
  const [page, setPage] = useState(0);

  async function scan() {
    setBusy(true);
    try {
      setData(await api("/api/radar/scan?limit=20", { method: "POST" }));
    } finally {
      setBusy(false);
    }
  }

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
        title="50X Opportunity Radar"
        action={
          <div className="flex gap-2">
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="bg-transparent text-xs">
              <option value="score">Score</option>
              <option value="name">Name</option>
            </select>
            <Button disabled={busy} onClick={scan}>{busy ? "Scanning live APIs…" : "Scan live market"}</Button>
          </div>
        }
      >
        <p className="text-sm text-[#8aa0c2]">Security is a hard filter. MALICIOUS / HIGH_RISK / UNKNOWN cannot enter Top 10/20.</p>
        <Disclaimer text={data?.disclaimer} />
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[#8aa0c2]">
              <tr>
                <th>Project</th><th>Score</th><th>Security</th><th>MCap</th><th>Eligible</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((r: any) => (
                <tr key={r.project_id} className="border-t border-[#1e2a44]">
                  <td className="py-2"><Link className="text-[#3ee0b4]" to={`/projects/${r.project_id}`}>{r.symbol} {r.name}</Link></td>
                  <td className="font-mono">{r.scores?.score_50x ?? "UNKNOWN"}</td>
                  <td><Status value={r.security?.verdict} /></td>
                  <td className="font-mono">{r.market_cap ?? "UNKNOWN"}</td>
                  <td>{r.eligible_for_pool ? "YES" : "NO"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex gap-2 text-xs">
          <Button onClick={() => setPage((p) => Math.max(0, p - 1))}>Prev</Button>
          <Button onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      </Panel>
    </div>
  );
}
