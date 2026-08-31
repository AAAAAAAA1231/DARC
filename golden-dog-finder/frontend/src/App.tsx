import { useEffect, useState } from "react";
import Radar from "./components/Radar";
import TokenList from "./components/TokenList";
import GenePanel from "./components/GenePanel";
import { fetchScan, keyOf } from "./api";
import type { Ranked, ScanResponse } from "./types";

export default function App() {
  const [data, setData] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [onlyPassed, setOnlyPassed] = useState(true);
  const [showThesis, setShowThesis] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  async function load(force = false) {
    try {
      setError(null);
      if (!data) setLoading(true);
      const next = await fetchScan(force);
      setData(next);
      if (!selected && next.tokens.length) {
        const first = next.tokens.find((t) => t.score.passed) || next.tokens[0];
        setSelected(keyOf(first.token.chain, first.token.address));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "扫描失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(true);
    const id = setInterval(() => load(false), 45000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tokens: Ranked[] = data?.tokens || [];
  const selectedRow = tokens.find((t) => keyOf(t.token.chain, t.token.address) === selected) || null;

  return (
    <div className="shell">
      <div className="grain" />
      <header className="top">
        <div className="brand">
          <div className="seal">犬</div>
          <div>
            <div className="title">金狗雷达</div>
            <div className="sub">只猎现价仍具备 100x 几何空间的链上新生盘</div>
          </div>
        </div>
        <div className="stats">
          <Stat k="宇宙" v={data ? String(data.universe) : "—"} />
          <Stat k="过门禁" v={data ? String(data.passed) : "—"} gold />
          <Stat k="最高分" v={data ? `${data.top_grade} ${data.top_score}` : "—"} />
          <Stat k="耗时" v={data ? `${(data.elapsed_ms / 1000).toFixed(1)}s` : "—"} />
        </div>
        <div className="actions">
          <label className="toggle">
            <input type="checkbox" checked={onlyPassed} onChange={(e) => setOnlyPassed(e.target.checked)} />
            只看活狗
          </label>
          <button onClick={() => setShowThesis(true)}>发掘逻辑</button>
          <button className="primary" onClick={() => load(true)} disabled={loading}>
            {loading ? "扫描中…" : "立刻复扫"}
          </button>
        </div>
      </header>

      {error && <div className="banner bad">{error}</div>}
      {data?.errors?.length ? (
        <div className="banner">{data.errors.length} 路数据源有缺口，已用其余源继续。</div>
      ) : null}

      <main className="layout">
        <section className="left">
          <Radar tokens={tokens.filter((t) => t.score.passed)} selectedKey={selected} onPick={setSelected} />
          <div className="live">
            <div className="pulse" />
            {loading ? "正在汇合流、曲线、安全结构…" : `上次扫描 ${data ? new Date(data.scanned_at).toLocaleTimeString() : ""}`}
          </div>
        </section>
        <section className="mid">
          {loading && !data ? <div className="empty">雷达启动中，正在拉新生池。</div> : (
            <TokenList tokens={tokens} selectedKey={selected} onPick={setSelected} onlyPassed={onlyPassed} />
          )}
        </section>
        <GenePanel row={selectedRow} />
      </main>

      {showThesis && data && (
        <div className="modal" onClick={() => setShowThesis(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2>{data.thesis.title}</h2>
            <p className="lead">{data.thesis.promise}</p>
            <ol>
              {data.thesis.gates.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ol>
            <dl>
              {data.thesis.genes.map((g) => (
                <div key={g.id}>
                  <dt>{g.name}</dt>
                  <dd>{g.why}</dd>
                </div>
              ))}
            </dl>
            <p className="disclaimer">{data.thesis.disclaimer}</p>
            <button className="primary" onClick={() => setShowThesis(false)}>
              知道了
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ k, v, gold }: { k: string; v: string; gold?: boolean }) {
  return (
    <div className={`stat ${gold ? "gold" : ""}`}>
      <span>{k}</span>
      <b>{v}</b>
    </div>
  );
}
