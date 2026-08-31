import { ageLabel, dexUrl, money, multiple, shortAddr } from "../api";
import type { Ranked } from "../types";

type Props = {
  row: Ranked | null;
};

export default function GenePanel({ row }: Props) {
  if (!row) {
    return (
      <aside className="panel">
        <h3>基因解剖</h3>
        <p className="muted">点选左侧一只狗，看它为什么还能谈 100x。</p>
      </aside>
    );
  }
  const t = row.token;
  const s = row.score;
  const cap = t.market_cap_usd || t.fdv_usd;
  return (
    <aside className="panel">
      <header className="panel-head">
        <div>
          <div className="kicker">{s.band}</div>
          <h3>
            {t.symbol} <span>{t.name}</span>
          </h3>
        </div>
        <div className={`badge grade-${s.grade} lg`}>
          <em>{s.grade}</em>
          <strong>{s.total}</strong>
        </div>
      </header>
      <p className="verdict">{s.verdict}</p>
      <p className="thesis">{s.thesis}</p>

      <div className="xgrid">
        <div>
          <span>现价市值</span>
          <b>{money(cap)}</b>
        </div>
        <div>
          <span>100x 目标</span>
          <b>{money(s.x100_target_mc)}</b>
        </div>
        <div>
          <span>$1.5M 时</span>
          <b className={s.x_if_1m5 >= 100 ? "hot" : ""}>{multiple(s.x_if_1m5)}</b>
        </div>
        <div>
          <span>$5M 时</span>
          <b className={s.x_if_5m >= 100 ? "hot" : ""}>{multiple(s.x_if_5m)}</b>
        </div>
        <div>
          <span>$20M 时</span>
          <b>{multiple(s.x_if_20m)}</b>
        </div>
        <div>
          <span>可达性</span>
          <b>{Math.round(s.feasibility * 100)}%</b>
        </div>
      </div>

      <div className="meta-row">
        <span>{t.chain}</span>
        <span>{t.dex}</span>
        <span>{ageLabel(row.age_min)}</span>
        <span>{shortAddr(t.address)}</span>
      </div>

      <h4>七条基因</h4>
      <ul className="genes">
        {s.genes.map((g) => (
          <li key={g.id}>
            <div className="gene-top">
              <span>{g.name}</span>
              <b>
                {g.score.toFixed(0)}/{g.max}
              </b>
            </div>
            <div className="bar">
              <i style={{ width: `${(g.score / g.max) * 100}%` }} />
            </div>
            <p>{g.reason}</p>
          </li>
        ))}
      </ul>

      {s.kill_reasons.length > 0 && (
        <>
          <h4>门禁击杀</h4>
          <ul className="kills">
            {s.kill_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}

      <div className="links">
        <a href={t.url || dexUrl(t.chain, t.address, t.pair_address)} target="_blank" rel="noreferrer">
          Dex / Pump
        </a>
        <a href={`https://dexscreener.com/${t.chain}/${t.address}`} target="_blank" rel="noreferrer">
          DexScreener
        </a>
        {t.chain === "solana" && (
          <a href={`https://solscan.io/token/${t.address}`} target="_blank" rel="noreferrer">
            Solscan
          </a>
        )}
      </div>
    </aside>
  );
}
