import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Button, Panel } from "../components/ui";
import { fmtNum, fmtPct } from "../format";

export default function Portfolio() {
  const [data, setData] = useState<any>(null);
  const [module, setModule] = useState("");
  const [fill, setFill] = useState({ module: "SPOT", symbol: "BTCUSDT", side: "BUY", quantity: "0.01", price: "", fee: "0" });

  async function load() {
    setData(await api(`/api/portfolio${module ? `?module=${module}` : ""}`));
  }
  useEffect(() => { load(); }, [module]);

  return (
    <div className="space-y-4">
      <Panel title="全局组合" action={
        <select value={module} onChange={(e) => setModule(e.target.value)} className="bg-transparent text-xs">
          <option value="">全部</option>
          <option value="50X">五十倍</option>
          <option value="FUTURES">合约</option>
          <option value="SPOT">现货</option>
          <option value="AIRDROP">空投</option>
          <option value="LAUNCH">新盘</option>
          <option value="FOOTBALL">足球</option>
          <option value="LOTTERY">彩票</option>
        </select>
      }>
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>投入 {fmtNum(data?.total_invested, 2)}</div>
          <div>市值 {fmtNum(data?.current_value, 2)}</div>
          <div>毛盈亏 {fmtNum(data?.gross_pnl, 2)}</div>
          <div>成本 {fmtNum(data?.total_cost, 4)}</div>
          <div>净盈亏 {fmtNum(data?.net_pnl, 2)}</div>
          <div>今日 {data?.today_pnl != null ? fmtNum(data.today_pnl, 2) : "未知"}</div>
          <div>本周 {data?.week_pnl != null ? fmtNum(data.week_pnl, 2) : "未知"}</div>
          <div>本月 {data?.month_pnl != null ? fmtNum(data.month_pnl, 2) : "未知"}</div>
          <div>收益率 {data?.roi != null ? fmtPct(data.roi) : "—"}</div>
          <div>已实现 {fmtNum(data?.realized_pnl, 2)}</div>
          <div>未实现 {fmtNum(data?.unrealized_pnl, 2)}</div>
        </div>
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{data?.period_note}</p>
      </Panel>
      <Panel title="记录实际成交">
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
          <input className="bg-transparent" value={fill.symbol} onChange={(e) => setFill({ ...fill, symbol: e.target.value })} />
          <select className="bg-transparent" value={fill.side} onChange={(e) => setFill({ ...fill, side: e.target.value })}><option value="BUY">买入</option><option value="SELL">卖出</option></select>
          <input className="bg-transparent" value={fill.quantity} onChange={(e) => setFill({ ...fill, quantity: e.target.value })} />
          <input className="bg-transparent" placeholder="价格" value={fill.price} onChange={(e) => setFill({ ...fill, price: e.target.value })} />
          <input className="bg-transparent" placeholder="手续费" value={fill.fee} onChange={(e) => setFill({ ...fill, fee: e.target.value })} />
          <select className="bg-transparent" value={fill.module} onChange={(e) => setFill({ ...fill, module: e.target.value })}>
            <option value="50X">五十倍</option>
            <option value="FUTURES">合约</option>
            <option value="SPOT">现货</option>
          </select>
        </div>
        <Button onClick={async () => { await api("/api/portfolio/fill", { method: "POST", body: JSON.stringify({ ...fill, quantity: Number(fill.quantity), price: Number(fill.price), fee: Number(fill.fee) }) }); load(); }}>保存成交</Button>
      </Panel>
      <Panel title="持仓">
        <table className="w-full text-left text-sm">
          <thead style={{ color: "var(--muted)" }}><tr><th>交易对</th><th>状态</th><th>数量</th><th>均价</th><th>市值</th><th>净盈亏</th><th>信号</th></tr></thead>
          <tbody>
            {(data?.positions || []).map((p: any) => (
              <tr key={p.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="py-2"><Link style={{ color: "var(--accent)" }} to={`/assets/${p.symbol}`}>{p.symbol}</Link></td>
                <td>{p.status}</td>
                <td>{fmtNum(p.quantity, 6)}</td>
                <td>{fmtNum(p.avg_cost, 2)}</td>
                <td>{p.current_value != null ? fmtNum(p.current_value, 2) : "未知"}</td>
                <td>{p.net_pnl != null ? fmtNum(p.net_pnl, 2) : "未知"}</td>
                <td>{p.original_model_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
