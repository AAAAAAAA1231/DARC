import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";

export default function Launch() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  async function scan() {
    setBusy(true);
    try { setData(await api("/api/launch/scan", { method: "POST" })); } finally { setBusy(false); }
  }
  return (
    <Panel title="Launch / Presale hunter" action={<Button disabled={busy} onClick={scan}>{busy ? "Searching DexScreener…" : "Scan"}</Button>}>
      <Disclaimer text={data?.disclaimer} />
      <table className="mt-3 w-full text-left text-sm">
        <thead className="text-[#8aa0c2]"><tr><th>Name</th><th>Class</th><th>Chain</th><th>Funding</th><th>Security</th></tr></thead>
        <tbody>
          {(data?.projects || []).map((p: any) => (
            <tr key={p.project_id} className="border-t border-[#1e2a44]">
              <td className="py-2"><Link className="text-[#3ee0b4]" to={`/projects/${p.project_id}`}>{p.name}</Link></td>
              <td>{p.launch_class}</td>
              <td>{p.chain}</td>
              <td>{p.funding}</td>
              <td><Status value={p.security?.verdict} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
