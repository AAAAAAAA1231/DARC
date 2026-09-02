import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Disclaimer, Panel, Status } from "../components/ui";
import { fmtNum } from "../format";

export default function Futures({ query }: { query: string }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function scan() {
    setBusy(true);
    try {
      setData(await api("/api/futures/scan?analyze_n=8", { method: "POST" }));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api("/api/futures/latest").then((cached: any) => {
      if ((cached.top3 || []).length) setData(cached);
    }).catch(() => undefined);
  }, []);

  const top3 = useMemo(
    () => (data?.top3 || []).filter((t: any) => String(t.symbol || "").toLowerCase().includes(query.toLowerCase())),
    [data, query],
  );

  return (
    <div className="space-y-4">
      <Panel title="合约 — 实时 USDT 本位成交额宇宙" action={<Button disabled={busy} onClick={scan}>{busy ? "正在拉取币安…" : "扫描成交额前100"}</Button>}>
        <div className="text-sm">宇宙规模：{data?.universe_count ?? (data?.from_cache ? "缓存的前三" : "—")}</div>
        <Disclaimer text={data?.disclaimer} />
      </Panel>
      <div className="grid gap-4 md:grid-cols-3">
        {top3.map((t: any) => (
          <Panel key={t.symbol} title={`#${t.rank} ${t.symbol}`}>
            <div className="space-y-1 text-sm">
              <div><Link className="font-mono" style={{ color: "var(--accent)" }} to={`/assets/${t.symbol}`}>{t.symbol} K线</Link></div>
              <div>方向 <Status value={t.direction} /></div>
              <div>置信度 {t.confidence}</div>
              <div>价格 {fmtNum(t.current_price)}</div>
              <div>理想入场 {fmtNum(t.ideal_entry)}</div>
              <div>止损 {fmtNum(t.stop_loss)}</div>
              <div>止盈1 {fmtNum(t.tp1)} / 止盈2 {fmtNum(t.tp2)} / 止盈3 {fmtNum(t.tp3)}</div>
              <div>盈亏比 {t.risk_reward?.toFixed?.(2) ?? t.risk_reward}</div>
              <div className="text-xs" style={{ color: "var(--muted)" }}>失效条件：{t.invalidation}</div>
              <ul className="list-disc pl-4 text-xs">{(t.main_reasons || []).slice(0, 4).map((r: string) => <li key={r}>{r}</li>)}</ul>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
