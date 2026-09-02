import { useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

export default function Simulations() {
  const [job, setJob] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);

  async function start(paths: number) {
    const created = await api<any>("/api/simulations", { method: "POST", body: JSON.stringify({ kind: "gbm", paths, parameters: { spot: 100, mu: 0.05, sigma: 0.4, dt: 1 } }) });
    setJob(created);
  }
  async function poll() {
    if (!job?.simulation_id) return;
    setDetail(await api(`/api/simulations/${job.simulation_id}`));
  }

  return (
    <Panel title="Monte Carlo jobs">
      <p className="text-sm text-[#8aa0c2]">Vectorized GBM. Path count is not forecast accuracy. GPU is used only if CUDA is present; otherwise CPU.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {[1_000_000, 10_000_000].map((n) => <Button key={n} onClick={() => start(n)}>{n.toLocaleString()} paths</Button>)}
        <Button onClick={poll}>Refresh status</Button>
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/pause`, { method: "POST" })}>Pause</Button>}
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/resume`, { method: "POST" })}>Resume</Button>}
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/cancel`, { method: "POST" })}>Cancel</Button>}
      </div>
      <pre className="mt-3 overflow-auto text-xs">{JSON.stringify(detail || job, null, 2)}</pre>
    </Panel>
  );
}
