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
      <Panel title="Runtime">
        <div className="space-y-1 text-sm">
          <div>Host {data?.host}:{data?.port}</div>
          <div>Database {data?.database_url}</div>
          <div>GPU {health?.gpu ? "available" : "none"}</div>
          <div>Auto trading {String(data?.auto_trading)} · Private keys allowed {String(health?.private_keys_allowed)}</div>
        </div>
        <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>{data?.disclaimer}</p>
      </Panel>
      <Panel title="Provider status (live)">
        <table className="w-full text-left text-sm">
          <thead style={{ color: "var(--muted)" }}><tr><th>Provider</th><th>Status</th><th>Key</th><th>Error</th></tr></thead>
          <tbody>
            {Object.entries(providers).map(([name, info]: any) => (
              <tr key={name} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="py-1 font-mono">{name}</td>
                <td><Status value={info.status} /></td>
                <td>{keys[name] === true ? "present" : keys[name] === false ? "empty" : "n/a"}</td>
                <td className="text-xs" style={{ color: "var(--muted)" }}>{info.error || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>Missing keys show as missing_key. That is not a fake-success health check. Secrets are never returned.</p>
      </Panel>
    </div>
  );
}
