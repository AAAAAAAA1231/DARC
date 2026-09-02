import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

export default function Simulations() {
  const [job, setJob] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);

  async function start(paths: number) {
    const created = await api<any>("/api/simulations", { method: "POST", body: JSON.stringify({ kind: "gbm", paths, parameters: { spot: 100, mu: 0.05, sigma: 0.4, dt: 1 } }) });
    setJob(created);
    setDetail(created);
  }
  async function poll() {
    if (!job?.simulation_id) return;
    setDetail(await api(`/api/simulations/${job.simulation_id}`));
  }

  useEffect(() => {
    if (!job?.simulation_id) return;
    const id = window.setInterval(poll, 1500);
    return () => window.clearInterval(id);
  }, [job?.simulation_id]);

  const status = detail?.status || job?.status;
  return (
    <Panel title="蒙特卡洛任务">
      <p className="text-sm" style={{ color: "var(--muted)" }}>向量化几何布朗运动。路径数不是预测准确率。仅在有 CUDA 时用 GPU，否则用 CPU。</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {[1_000_000, 10_000_000].map((n) => <Button key={n} onClick={() => start(n)}>{n.toLocaleString("zh-CN")} 条路径</Button>)}
        <Button onClick={poll}>刷新状态</Button>
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/pause`, { method: "POST" })}>暂停</Button>}
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/resume`, { method: "POST" })}>继续</Button>}
        {job && <Button onClick={() => api(`/api/simulations/${job.simulation_id}/cancel`, { method: "POST" })}>取消</Button>}
      </div>
      <div className="mt-3 text-sm">状态 {status || "—"} · 路径 {detail?.paths ?? job?.paths ?? "—"}</div>
      {detail?.result && (
        <div className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          模拟置信度不是准确率。 {JSON.stringify(detail.result.disclaimer || detail.result.simulation_confidence || "")}
        </div>
      )}
      <pre className="mt-3 overflow-auto text-xs">{JSON.stringify(detail || job, null, 2)}</pre>
    </Panel>
  );
}
