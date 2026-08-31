import { ageLabel, dexUrl, keyOf, money, multiple } from "../api";
import type { Ranked } from "../types";

type Props = {
  tokens: Ranked[];
  selectedKey: string | null;
  onPick: (key: string) => void;
  onlyPassed: boolean;
};

export default function TokenList({ tokens, selectedKey, onPick, onlyPassed }: Props) {
  const live = tokens.filter((t) => t.score.passed);
  const dead = tokens.filter((t) => !t.score.passed);
  const rows = onlyPassed ? live : [...live, ...dead];
  if (!rows.length) {
    return <div className="empty">这一轮没有活标的。雷达会继续转。</div>;
  }

  const renderCard = (row: Ranked, idx: number) => {
    const k = keyOf(row.token.chain, row.token.address);
    const t = row.token;
    const s = row.score;
    return (
      <article
        key={k}
        className={`card grade-${s.grade} ${k === selectedKey ? "selected" : ""} ${s.passed ? "" : "rejected"}`}
        onClick={() => onPick(k)}
      >
        <div className="card-index">{String(idx + 1).padStart(2, "0")}</div>
        <div className="card-id">
          {t.image ? <img src={t.image} alt="" /> : <div className="ph">{t.symbol.slice(0, 2)}</div>}
          <div>
            <div className="sym">
              {t.symbol || "???"}
              <span className="chain">{t.chain}</span>
            </div>
            <div className="nm">{t.name}</div>
          </div>
        </div>
        <div className="card-metrics">
          <div>
            <span>市值</span>
            <b>{money(t.market_cap_usd || t.fdv_usd)}</b>
          </div>
          <div>
            <span>开盘</span>
            <b>{ageLabel(row.age_min)}</b>
          </div>
          <div>
            <span>到 $5M</span>
            <b className={s.x_if_5m >= 100 ? "hot" : ""}>{multiple(s.x_if_5m)}</b>
          </div>
          <div>
            <span>1h</span>
            <b className={t.change_h1 >= 0 ? "up" : "down"}>
              {t.change_h1 >= 0 ? "+" : ""}
              {t.change_h1.toFixed(0)}%
            </b>
          </div>
        </div>
        <div className={`badge grade-${s.grade}`}>
          <em>{s.grade}</em>
          <strong>{s.total}</strong>
        </div>
        <a
          className="go"
          href={t.url || dexUrl(t.chain, t.address, t.pair_address)}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
        >
          打开
        </a>
      </article>
    );
  };

  if (onlyPassed) {
    return <div className="tape">{live.map((row, idx) => renderCard(row, idx))}</div>;
  }
  return (
    <div className="tape">
      {live.length > 0 && <div className="tape-label">过门禁 {live.length}</div>}
      {live.map((row, idx) => renderCard(row, idx))}
      {dead.length > 0 && <div className="tape-label">未过门禁 {dead.length}（空间不够或结构已坏）</div>}
      {dead.map((row, idx) => renderCard(row, live.length + idx))}
    </div>
  );
}
