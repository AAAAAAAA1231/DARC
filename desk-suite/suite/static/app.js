const views = {
  radar: ["50 倍雷达", "新场子刚开张 + 独占叙事 + 极浅开盘。不是买卖信号。"],
  football: ["三大联赛胜负", "西甲 / 德甲 / 意甲，打开后可预测近期未赛。仅供观赛参考。"],
  contracts: ["合约分析", "主体是永续开单推荐。四年周期只给大方向和持仓时长。"],
  airdrops: ["空投推荐", "机构、是否明确空投、参与难度、预计总金额打分，再用历史空投修正。按得分排序。"],
  launches: ["打新", "搜 X 上发射、launch、新平台、newproject、预售、presale，只看近一个月，机构/名人/VC 关注排前面。"],
};

const $ = (id) => document.getElementById(id);
const store = { contracts: {} };
let currentView = "radar";
let analyzeJob = null;
let analyzeStarting = false;
let footballTimer = null;
let radarTimer = null;
let airdropTimer = null;
let launchTimer = null;

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
$("airdropScan").addEventListener("click", () => startAirdrops());
$("airdropFilter").addEventListener("input", () => filterTable("airdropRows", $("airdropFilter").value));
$("launchScan").addEventListener("click", () => startLaunches(true));
$("launchFilter").addEventListener("input", () => filterTable("launchRows", $("launchFilter").value));

function showView(name) {
  currentView = name;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("hidden", el.id !== "view-" + name));
  $("viewTitle").textContent = views[name][0];
  $("viewSub").textContent = views[name][1];
  if (name === "radar") startRadar();
  if (name === "football") pollFootball();
  if (name === "contracts") loadContracts();
  if (name === "airdrops") startAirdrops();
  if (name === "launches") openLaunches();
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
  return `<tr class="${tradable ? "trade-row" : ""}">
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

function decisionRank(r) {
  if (r.tradable) return 0;
  if (r.decision === "涨") return 1;
  if (r.decision === "跌") return 2;
  return 3;
}

function sortedRows(rows) {
  return [...rows].sort((a, b) => {
    const rank = decisionRank(a) - decisionRank(b);
    if (rank) return rank;
    return (Number(b.score) || 0) - (Number(a.score) || 0);
  });
}

function paintContracts(rows) {
  const list = sortedRows(rows.filter((r) => r.symbol && r.symbol !== "?"));
  const tradable = list.filter((r) => r.tradable).length;
  if ($("tradeCount")) $("tradeCount").textContent = tradable ? `开单推荐 ${tradable} 单` : "开单推荐";
  if (!list.length) {
    $("contractRows").innerHTML = `<tr><td colspan="12" class="muted">点「刷新开单」加载永续合约名单。</td></tr>`;
    return;
  }
  $("contractRows").innerHTML = list.map(contractRow).join("");
}

function renderCycle(view) {
  if (!view || !view.phase) return;
  $("cyclePhase").textContent = view.phase;
  $("cycleHold").textContent = view.hold || "—";
  $("cycleHold").className = "cycle-hold " + (view.regime === "熊市" ? "bear" : "bull");
  if (view.hold_days) {
    $("cycleHorizon").textContent = `建议持仓 ${view.hold_days} 天${view.hold_until ? "（至 " + view.hold_until + "）" : ""}`;
  } else {
    $("cycleHorizon").textContent = "持仓时长 —";
  }
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
      $("cyclePhase").textContent = "四年周期暂时拉不到";
      $("cycleHorizon").textContent = inner.message || err.message;
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
    if (rows.length) paintContracts(rows);
    else {
      const uni = await api("/chain/api/contracts/universe");
      $("contractRows").innerHTML = (uni.items || []).slice(0, 40).map((u) => {
        const row = { symbol: u.binance_symbol || u.symbol, name: u.name, market_cap_rank: u.market_cap_rank, decision: "待分析" };
        store.contracts[row.symbol] = row;
        return contractRow(row);
      }).join("") || `<tr><td colspan="12" class="muted">名单为空，请检查网络后点刷新开单。</td></tr>`;
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
    if (rows.length) paintContracts(rows);
    const phase = data.phase ? " · " + data.phase : "";
    setStatus(`${data.kind === "fit" ? "校准权重" : "套用模型"} ${data.done || 0}/${data.total || 0}${phase}`);
    if (data.status === "running") setTimeout(pollAnalyze, 1200);
    else if (data.status === "error") setStatus("任务失败：" + String(data.error || "").slice(0, 180));
  } catch (err) {
    setStatus("分析任务查询失败：" + err.message);
  }
}

function airdropRow(a) {
  const confClass = a.confirmed === "official" || a.confirmed === "points" ? "up" : a.confirmed === "tge" ? "down" : "wait";
  const rec = a.recommend ? '<span class="tag seed">推荐</span>' : '<span class="tag wait">观察</span>';
  const vcs = (a.famous_investors || []).slice(0, 3).join("、") || "—";
  const parts = a.parts || {};
  const similar = (a.similar || []).join("、") || "—";
  const link = a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noreferrer">${esc(a.name)}</a>` : esc(a.name);
  return `<tr class="${a.recommend ? "trade-row" : ""}">
    <td>${a.rank ?? "-"}</td>
    <td><strong>${link}</strong><div class="muted">${esc(a.sector || "")} ${(a.chains || []).slice(0, 2).join("/")}</div></td>
    <td><strong>${a.score ?? "-"}</strong> ${rec}</td>
    <td>${esc(vcs)}<div class="muted">${a.famous_count || 0} 家</div></td>
    <td><span class="tag ${confClass}">${esc(a.confirmed_label || a.confirmed)}</span></td>
    <td>${esc(a.difficulty_label || a.difficulty)}</td>
    <td>${esc(a.expected_airdrop || "—")}</td>
    <td>${esc(similar)}</td>
    <td class="muted">机构${parts.institutions ?? "-"} 确定${parts.confirmed ?? "-"} 难度${parts.difficulty ?? "-"} 金额${parts.expected_amount ?? "-"} 修正${parts.history_adj ?? 0}</td>
  </tr>`;
}

async function startAirdrops() {
  setStatus("正在按模型给空投项目打分…");
  $("airdropRows").innerHTML = `<tr><td colspan="9" class="muted">正在拉融资和历史对照…</td></tr>`;
  try {
    await api("/api/airdrops/scan", { method: "POST", body: {} });
    pollAirdrops();
  } catch (err) {
    setStatus("空投扫描失败：" + err.message);
  }
}

async function pollAirdrops() {
  if (airdropTimer) clearTimeout(airdropTimer);
  try {
    const data = await api("/api/airdrops/status");
    setStatus(data.phase || data.status || "就绪");
    const rows = data.items || [];
    if (rows.length) {
      $("airdropRows").innerHTML = rows.map(airdropRow).join("");
      filterTable("airdropRows", $("airdropFilter").value);
    } else if (data.status === "done") {
      $("airdropRows").innerHTML = `<tr><td colspan="9" class="muted">这一轮没有扫到候选。</td></tr>`;
    }
    if (data.status === "error") setStatus("失败：" + String(data.error || "").slice(0, 180));
    if (data.status === "running") airdropTimer = setTimeout(pollAirdrops, 1000);
  } catch (err) {
    setStatus("空投查询失败：" + err.message);
  }
}

function timeAgo(iso) {
  if (!iso) return "近一个月";
  const ts = Date.parse(iso);
  if (!Number.isFinite(ts)) return "近一个月";
  const hours = Math.max(0, (Date.now() - ts) / 3600000);
  if (hours < 1) return "刚刚";
  if (hours < 24) return Math.round(hours) + " 小时前";
  const days = Math.round(hours / 24);
  if (days <= 30) return days + " 天前";
  return iso.slice(0, 10);
}

function launchRow(a) {
  const handle = (a.handle || "").replace(/^@/, "");
  const profile = handle ? `https://x.com/${handle}` : (a.url || "#");
  const account = handle
    ? `<a href="${esc(profile)}" target="_blank" rel="noreferrer">@${esc(handle)}</a>`
    : "—";
  const text = a.url
    ? `<a class="tweet-link" href="${esc(a.url)}" target="_blank" rel="noreferrer">${esc(a.text || "查看原帖")}</a>`
    : esc(a.text || "—");
  const inst = (a.institutions || []).slice(0, 3).join("、") || "—";
  const notable = a.notable
    ? `<span class="tag seed">${esc(a.notable)}</span>`
    : '<span class="muted">—</span>';
  const hot = (a.score || 0) >= 55;
  return `<tr class="${hot ? "trade-row" : ""}">
    <td>${a.rank ?? "-"}</td>
    <td><strong>${a.score ?? "-"}</strong></td>
    <td>${account}</td>
    <td class="wrap">${text}</td>
    <td>${esc(inst)}</td>
    <td>${notable}</td>
    <td>${esc(timeAgo(a.created_at))}</td>
    <td class="wrap muted">${esc((a.reasons || []).join(" · ") || "关键词匹配")}</td>
  </tr>`;
}

async function openLaunches() {
  try {
    const data = await api("/api/launches/status");
    if (data.status === "running") {
      setStatus(data.phase || "正在检索…");
      pollLaunches();
      return;
    }
    if ((data.items || []).length) {
      $("launchRows").innerHTML = data.items.map(launchRow).join("");
      filterTable("launchRows", $("launchFilter").value);
      setStatus(data.phase || "就绪");
      return;
    }
  } catch (err) {
    setStatus("打新查询失败：" + err.message);
  }
  startLaunches(true);
}

async function startLaunches(force) {
  if (!force) return openLaunches();
  setStatus("正在搜近一个月的发射 / launch / 预售…");
  const existing = $("launchRows").querySelectorAll("tr").length;
  if (!existing || $("launchRows").innerText.includes("点「刷新打新」") || $("launchRows").innerText.includes("正在检索")) {
    $("launchRows").innerHTML = `<tr><td colspan="8" class="muted">正在检索 X，并按机构、名人、VC 关注排序…</td></tr>`;
  }
  try {
    await api("/api/launches/scan", { method: "POST", body: {} });
    pollLaunches();
  } catch (err) {
    setStatus("打新扫描失败：" + err.message);
  }
}

async function pollLaunches() {
  if (launchTimer) clearTimeout(launchTimer);
  try {
    const data = await api("/api/launches/status");
    setStatus(data.phase || data.status || "就绪");
    const rows = data.items || [];
    if (rows.length) {
      $("launchRows").innerHTML = rows.map(launchRow).join("");
      filterTable("launchRows", $("launchFilter").value);
    } else if (data.status === "done") {
      const hint = (data.errors || []).length
        ? "这一轮没搜到帖子。可在链上雷达设置里填 Twitter Bearer，覆盖会更稳。"
        : "这一轮没有扫到候选。";
      $("launchRows").innerHTML = `<tr><td colspan="8" class="muted">${esc(hint)}</td></tr>`;
    }
    if (data.status === "error") setStatus("失败：" + String(data.error || "").slice(0, 180));
    if (data.status === "running") launchTimer = setTimeout(pollLaunches, 1000);
  } catch (err) {
    setStatus("打新查询失败：" + err.message);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
}

window.showDetail = showDetail;
showView("radar");
