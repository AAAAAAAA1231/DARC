import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components/ui";

export default function NotificationsPage() {
  const [data, setData] = useState<any>(null);
  async function load() { setData(await api("/api/notifications")); }
  useEffect(() => { load(); }, []);
  return (
    <Panel title="Notifications">
      {(data?.items || []).map((n: any) => (
        <div key={n.id} className="flex items-center justify-between border-t border-[#1e2a44] py-2 text-sm">
          <div><div className="font-semibold">{n.title}</div><div className="text-xs text-[#8aa0c2]">{n.body}</div></div>
          {!n.read && <Button onClick={async () => { await api(`/api/notifications/${n.id}/read`, { method: "POST" }); load(); }}>Mark read</Button>}
        </div>
      ))}
    </Panel>
  );
}
