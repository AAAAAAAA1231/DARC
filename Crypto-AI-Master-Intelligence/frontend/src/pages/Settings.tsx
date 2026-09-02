import { useEffect, useState } from "react";
import { api } from "../api";
import { Panel } from "../components/ui";

export default function SettingsPage() {
  const [data, setData] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    api("/api/settings").then(setData);
    api("/api/health").then(setHealth);
  }, []);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Runtime">
        <pre className="overflow-auto text-xs">{JSON.stringify(data, null, 2)}</pre>
      </Panel>
      <Panel title="Provider status (live)">
        <pre className="overflow-auto text-xs">{JSON.stringify(health?.providers, null, 2)}</pre>
        <p className="mt-2 text-xs text-[#8aa0c2]">Missing keys show as missing_key. That is not a fake-success health check.</p>
      </Panel>
    </div>
  );
}
