const views = {
  radar: ["50 倍雷达", "新场子刚开张 + 独占叙事 + 极浅开盘。不是买卖信号。"],
  football: ["三大联赛胜负", "西甲 / 德甲 / 意甲，打开后可预测近期未赛。仅供观赛参考。"],
  contracts: ["合约分析", "先看四年周期：现在是牛是熊、持 U 还是持币、拿什么、拿多久。下面才是市值前 100 永续信号。"],
};

const $ = (id) => document.getElementById(id);
const store = { contracts: {} };
let currentView = "radar";
let analyzeJob = null;
let analyzeStarting = false;
let footballTimer = null;
let radarTimer = null;

document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
$("radarScan").addEventListener("click", () => startRadar());
$("footballAll").addEventListener("click", () => startFootball("all"));
$("footballSearch").addEventListener("click", () => startFootball("search"));
$("footballQuery").addEventListener("keydown", (e) => {
  if (e.key === "Enter") startFootball("search");
});
$("analyzeAll").addEventListener("click", () => startAnalyze("infer"));
$("refitWeights").addEventListener("click", () => startAnalyze("fit"));
$("contractFilter").addEventListener("input", () => filterTable("contractRows", $("contractFilter").value));

function showView(name) {
  currentView = name;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("hidden", el.id !== "view-" + name));
  $("viewTitle").textContent = views[name][0];
  $("viewSub").textContent = views[name][1];
  if (name === "radar") startRadar();
  if (name === "football") pollFootball();
  if (name === "contracts") loadContracts();
}

async function api(path, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (opts.body && typeof opts.body !== "string") init.body = JSON.stringify(opts.body);
  const res = await fetch(path, init);
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

function setStatus(text) {
  $("statusLine").textContent = text;
}

function filterTable(tbodyId, q) {
  const query = (q || "").toLowerCase();
  document.querySelectorAll("#" + tbodyId + " tr").forEach((tr) => {
    tr.style.display = tr.innerText.toLowerCase().includes(query) ? "" : "none";
  });
}

async function startRadar() {
  setStatus("正在扫描新场子和新盘…");
  $("radarFrame").srcdoc = "<p style='color:#9aa0a6;font-family:sans-serif;padding:24px'>正在扫描…</p>";
  try {
    await api("/api/radar/scan", { method: "POST", body: {} });
    pollRadar();
  } catch (err) {
    setStatus("雷达启动失败：" + err.message);
  }
}

async function pollRadar() {
  if (radarTimer) clearTimeout(radarTimer);
  try {
    const st = await api("/api/radar/status");
    setStatus(st.phase || st.status);
    if (st.status === "done" || st.status === "error") {
      const html = await fetch("/api/radar/html").then((r) => r.text());
      $("radarFrame").srcdoc = html;
      return;
    }
  } catch (err) {
    setStatus("雷达查询失败：" + err.message);
  }
  radarTimer = setTimeout(pollRadar, 800);
}

async function startFootball(kind) {
  try {
    if (kind === "search") {
      const q = $("footballQuery").value.trim();
      if (!q) {
        setStatus("请输入：下一场皇马 / 巴萨vs马竞 / 德甲");
        return;
      }
      await api("/api/football/search", { method: "POST", body: { query: q } });
    } else {
      await api("/api/football/run", { method: "POST", body: {} });
    }
    pollFootball();
  } catch (err) {
    setStatus("联赛预测失败：" + err.message);
  }
}

async function pollFootball() {
  if (footballTimer) clearTimeout(footballTimer);
  try {
    const data = await api("/api/football/status");
    setStatus(data.phase || data.status || "就绪");
    if (data.error) setStatus("失败：" + data.error);
    const rows = data.results || [];
    if (rows.length) {
      $("footballRows").innerHTML = rows.map((r) => `<tr>
        <td>${esc(r.league_cn)}</td>
        <td>${esc(r.kickoff)}</td>
        <td>${esc(r.match)}</td>
        <td>${esc(r.pred_1x2_90)}</td>
        <td>${esc(r.final_1x2)}</td>
        <td>${esc(r.final_score)}</td>
        <td>${esc(r.probs)}</td>
        <td>${r.confidence != null ? Math.round(r.confidence * 100) + "%" : "-"}</td>
      </tr>`).join("");
    } else if (data.status === "done") {
      $("footballRows").innerHTML = `<tr><td colspan="8" class="muted">${esc(data.phase || "没有找到近期未赛场次")}</td></tr>`;
    }
    if (data.status === "running") footballTimer = setTimeout(pollFootball, 1000);
  } catch (err) {
    setStatus("联赛查询失败：" + err.message);
  }
}

function fmtPx(n) {
  return n == null || n === "" ? "-" : Number(n).toPrecision(6);
}
function tagClass(d) {
  return d === "涨" ? "up" : d === "跌" ? "down" : "wait";
}

function contractRow(r) {
  const id = encodeURIComponent(r.symbol);
  const tradable = !!r.tradable;
  const size = tradable && r.suggested_notional_pct ? `${Number(r.suggested_notional_pct).toFixed(1)}% 权益` : "-";
  const manage = tradable ? `${fmtPx(r.partial_tp)} / ${fmtPx(r.breakeven)}` : "-";
  return `<tr>
    <td><strong>${esc(r.symbol)}</strong><div class="muted">${esc(r.name || "")}</div></td>
    <td>${r.market_cap_rank || "-"}</td>
    <td><span class="tag ${tagClass(r.decision)}">${esc(r.decision || "观望")}</span>${tradable ? ' <span class="tag seed">可做</span>' : ""}</td>
    <td>${r.quality ?? "-"}</td>
    <td>${r.score ?? "-"}</td>
    <td>${fmtPx(r.price)}</td>
    <td>${fmtPx(r.entry)}</td>
    <td>${fmtPx(r.stop_loss)}</td>
    <td>${manage}</td>
    <td>${fmtPx(r.take_profit)}</td>
    <td>${size}</td>
    <td><button class="btn" type="button" onclick="showDetail('${id}')">指标</button></td>
  </tr>`;
}

function showDetail(id) {
  const r = store.contracts[decodeURIComponent(id)];
  if (!r) return;
  const inds = r.indicators || [];
  $("contractDetail").innerHTML = `
    <div class="panel">
      <h3>${esc(r.symbol)} 指标</h3>
      <p class="muted">${esc(r.plan_note || r.filter_note || "")}</p>
      <div class="table-wrap"><table>
        <thead><tr><th>指标</th><th>信号</th><th>强度</th><th>说明</th></tr></thead>
        <tbody>
          ${inds.map((i) => `<tr>
            <td>${esc(i.name)}</td>
            <td>${i.signal === 1 ? "涨" : i.signal === -1 ? "跌" : "观望"}</td>
            <td>${i.strength ?? "-"}</td>
            <td>${esc(i.detail)}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>
    </div>`;
}

function renderCycle(view) {
  if (!view || !view.phase) return;
  $("cyclePhase").textContent = view.phase;
  $("cycleNarrative").textContent = view.narrative || view.hold_detail || "";
  $("cycleHold").textContent = view.hold || "—";
  $("cycleHold").className = "cycle-hold " + (view.regime === "熊市" ? "bear" : "bull");
  $("cyclePrice").textContent = view.price ? "$" + Number(view.price).toLocaleString() : "—";
  $("cycleDrawdown").textContent = view.drawdown_pct != null ? "-" + Number(view.drawdown_pct).toFixed(1) + "%" : "—";
  $("cycleHalving").textContent = view.days_since_halving != null ? view.days_since_halving + " 天" : "—";
  $("cycleTypical").textContent = `${view.typical_bull_days || "—"} / ${view.typical_bear_days || "—"} 天`;
  $("cycleNext").textContent = view.next_event || "";
  const cards = view.allocations || [];
  $("cycleAlloc").innerHTML = cards.map((a) => `
    <article class="alloc-card">
      <div class="muted">${esc(a.name)} · 建议持有 ${a.hold_days} 天</div>
      <div><strong>${esc(a.symbol)}</strong> <span class="weight">${a.weight_pct}%</span></div>
      <p class="muted">拿到 ${esc(a.hold_until)}。${esc(a.reason)}</p>
    </article>`).join("") || "";
  const rows = view.history || [];
  $("cycleHistory").innerHTML = rows.map((r) => `<tr>
    <td>${esc(r.label)}</td>
    <td>${esc(r.halving)}</td>
    <td>${esc(r.peak)}</td>
    <td>${esc(r.bottom)}</td>
    <td>${r.bull_days != null ? r.bull_days + " 天" : "—"}</td>
    <td>${r.bear_days != null ? r.bear_days + " 天" : "—"}</td>
  </tr>`).join("") || `<tr><td colspan="6" class="muted">没有历史周期数据</td></tr>`;
}

async function loadCycle() {
  try {
    const view = await api("/chain/api/contracts/cycle");
    renderCycle(view);
  } catch (err) {
    try {
      const view = await api("/api/cycle");
      renderCycle(view);
    } catch (inner) {
      $("cyclePhase").textContent = "四年周期暂时拉不到行情";
      $("cycleNarrative").textContent = inner.message || err.message;
    }
  }
}

async function loadContracts() {
  loadCycle();
  try {
    const last = await api("/chain/api/contracts/status");
    if ($("simBadge") && last.fitted_note) $("simBadge").textContent = last.fitted_note;
    if (last.running && last.job_id) {
      analyzeJob = last.job_id;
      pollAnalyze();
    }
    (last.results || []).forEach((r) => { if (r.symbol) store.contracts[r.symbol] = r; });
    const rows = (last.results || []).filter((r) => r.symbol && r.symbol !== "?");
    if (rows.length) $("contractRows").innerHTML = rows.map(contractRow).join("");
    else {
      const uni = await api("/chain/api/contracts/universe");
      $("contractRows").innerHTML = (uni.items || []).slice(0, 40).map((u) => {
        const row = { symbol: u.binance_symbol || u.symbol, name: u.name, market_cap_rank: u.market_cap_rank, decision: "待分析" };
        store.contracts[row.symbol] = row;
        return contractRow(row);
      }).join("") || `<tr><td colspan="12" class="muted">名单为空，请检查网络后点刷新信号。</td></tr>`;
    }
    setStatus(last.fitted_note || "合约模块就绪");
  } catch (err) {
    setStatus("合约模块：" + err.message);
  }
}

async function startAnalyze(mode) {
  if (analyzeStarting) return;
  analyzeStarting = true;
  const interval = $("klineInterval").value;
  const kind = mode === "fit" ? "fit" : "infer";
  setStatus(kind === "fit" ? "开始校准指标权重（100 万次，只需偶尔做）…" : "套用已拟合模型出信号…");
  $("analyzeProgress").classList.remove("hidden");
  try {
    const job = await api("/chain/api/contracts/analyze", { method: "POST", body: { interval, mode: kind } });
    analyzeJob = job.job_id;
    pollAnalyze();
  } catch (err) {
    setStatus("无法启动分析：" + err.message);
  } finally {
    analyzeStarting = false;
  }
}

async function pollAnalyze() {
  if (!analyzeJob) return;
  try {
    const data = await api("/chain/api/contracts/analyze/" + analyzeJob);
    const pct = data.total ? (data.done / data.total) * 100 : 0;
    $("analyzeProgress").querySelector("div").style.width = pct + "%";
    (data.results || []).forEach((r) => { if (r.symbol) store.contracts[r.symbol] = r; });
    const rows = (data.results || []).filter((r) => r.symbol && r.symbol !== "?");
    if (rows.length) $("contractRows").innerHTML = rows.map(contractRow).join("");
    const phase = data.phase ? " · " + data.phase : "";
    setStatus(`${data.kind === "fit" ? "校准权重" : "套用模型"} ${data.done || 0}/${data.total || 0}${phase}`);
    if (data.status === "running") setTimeout(pollAnalyze, 1200);
    else if (data.status === "error") setStatus("任务失败：" + String(data.error || "").slice(0, 180));
  } catch (err) {
    setStatus("分析任务查询失败：" + err.message);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
}

window.showDetail = showDetail;
showView("radar");
