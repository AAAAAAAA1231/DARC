import { useEffect, useState } from "react";
import { api } from "../api";
import { Panel, Status } from "../components/ui";

export default function SettingsPage() {
  const [data, setData] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    api("/api/settings").then(setData);
    api("/api/health").then(setHealth);
  }, []);
  const providers = health?.providers || {};
  const keys = data?.keys_present || {};
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="运行环境">
        <div className="space-y-1 text-sm">
          <div>地址 {data?.host}:{data?.port}</div>
          <div>数据库 {data?.database_url}</div>
          <div>GPU {health?.gpu ? "可用" : "无"}</div>
          <div>自动交易 {String(data?.auto_trading)} · 允许私钥 {String(health?.private_keys_allowed)}</div>
        </div>
        <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>{data?.disclaimer}</p>
      </Panel>
      <Panel title="数据源状态（实时）">
        <table className="w-full text-left text-sm">
          <thead style={{ color: "var(--muted)" }}><tr><th>数据源</th><th>状态</th><th>密钥</th><th>错误</th></tr></thead>
          <tbody>
            {Object.entries(providers).map(([name, info]: any) => (
              <tr key={name} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="py-1 font-mono">{name}</td>
                <td><Status value={info.status} /></td>
                <td>{keys[name] === true ? "已配置" : keys[name] === false ? "空" : "不适用"}</td>
                <td className="text-xs" style={{ color: "var(--muted)" }}>{info.error || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>缺少密钥会显示为 missing_key。这不是假装健康检查成功。密钥永远不会返回给界面。</p>
      </Panel>
    </div>
  );
}
