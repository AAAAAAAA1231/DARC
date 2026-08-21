const views = {
  contracts: ["合约分析", "每次刷新会用上次推荐的涨跌和时间给指标重新加权。未到期持仓和刚亏过的不会再原样推；连亏会少推或观望。10 亿次只用于偶尔校准。"],
  news: ["单边快讯", "先把消息整理成做多 / 做空 / 观望。只保留 FOMC、ETF、监管、黑客、脱锚这类可能打开单边的催化剂。不是投资建议。"],
  meme: ["妖币监控", "只保留池子≥$1M、短期买压、持币在增加、且不像接盘的币。可跟才会进入自动跟单。"],
  copytrade: ["自动跟单", "跟随妖币「可跟」信号。每次刷新最多新开 1 笔；缓存页只盯市。连亏暂停、亏损后减仓，止损后冷却加倍。"],
  ambassador: ["大使招募", "新 Web3 项目在 X / 招聘页上的大使计划，不是 OKX、币安校园大使。可标记申请与成功。"],
  launch: ["打新监测", "Solana 只推 @solana/@toly 关注；BSC 只推 @cz_binance/@heyibinance 关注。不是官方关注的不显示。"],
  airdrop: ["空投雷达", "只盯比特币生态与 ETH 生态。BTC 融资 ≥ $500 万，ETH 融资 ≥ $2000 万，优先未发币。"],
  wallet: ["钱包执行", "连接 OKX 等钱包，将空投 / 打新 / 妖币 / 合约加入确认队列"],
  settings: ["设置", "X 接口令牌、权重模拟次数、阈值与自动参加上限"],
};

const $ = (id) => document.getElementById(id);
const store = { contracts: {}, meme: {}, ambassador: {}, launch: {}, airdrop: {}, news: {} };
const fmtUsd = (n) => n == null || Number.isNaN(Number(n)) ? "-" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const fmtPx = (n) => n == null || n === "" ? "-" : Number(n).toPrecision(6);
const tagClass = (d) => d === "涨" ? "up" : d === "跌" ? "down" : "wait";
const regimeClass = (r) => r === "单边" ? "trend" : r === "震荡" ? "range" : "mixed";

let currentView = "contracts";
let newsTimer = null;
let seenNewsAlerts = new Set();
let analyzeJob = null;
let analyzeStarting = false;
let settingsCache = {};

document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
$("refreshBtn").addEventListener("click", () => loadView(currentView, true));
$("analyzeAll").addEventListener("click", () => startAnalyze("infer"));
if ($("refitWeights")) $("refitWeights").addEventListener("click", () => startAnalyze("fit"));
$("saveSettings").addEventListener("click", saveSettings);
$("disconnectWallet").addEventListener("click", async () => {
  await api("/api/wallet/disconnect", { method: "POST" });
  loadWallet();
});
$("contractFilter").addEventListener("input", () => renderContracts());
if ($("onlyRecommend")) $("onlyRecommend").addEventListener("change", () => renderContracts());
$("memeFilter").addEventListener("input", () => filterTable("memeRows", $("memeFilter").value));
$("ambStatusFilter").addEventListener("change", () => loadView("ambassador"));
$("airdropStatusFilter").addEventListener("change", () => loadView("airdrop"));
$("autoParticipate").addEventListener("change", persistWalletFlags);
$("autoMaxSpend").addEventListener("change", persistWalletFlags);
if ($("copySave")) $("copySave").addEventListener("click", saveCopytrade);
if ($("ambAdd")) $("ambAdd").addEventListener("click", addAmbassador);
if ($("saveLaunchToken")) $("saveLaunchToken").addEventListener("click", saveLaunchToken);
if ($("newsFilter")) $("newsFilter").addEventListener("input", () => renderNews());
if ($("newsAlertOnly")) $("newsAlertOnly").addEventListener("change", () => renderNews());
if ($("newsBiasFilter")) $("newsBiasFilter").addEventListener("change", () => renderNews());

function showView(name) {
  currentView = name;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("hidden", el.id !== "view-" + name));
  $("viewTitle").textContent = views[name][0];
  $("viewSub").textContent = views[name][1];
  loadView(name, false);
}

async function api(path, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (opts.body && typeof opts.body !== "string") init.body = JSON.stringify(opts.body);
  const res = await fetch(path, init);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json();
}

function setStatus(text) { $("statusLine").textContent = text; }

function filterTable(tbodyId, q) {
  const query = (q || "").toLowerCase();
  document.querySelectorAll("#" + tbodyId + " tr").forEach((tr) => {
    tr.style.display = tr.innerText.toLowerCase().includes(query) ? "" : "none";
  });
}

async function loadView(name, refresh) {
  const q = refresh ? "?refresh=true" : "";
  try {
    if (name === "contracts") {
      setStatus("检查权重拟合状态…");
      const last = await api("/api/contracts/status");
      if (last.running && last.job_id) {
        analyzeJob = last.job_id;
        $("analyzeProgress").classList.remove("hidden");
        if (last.results && last.results.length) {
          last.results.forEach((r) => { store.contracts[r.symbol] = r; });
          renderContracts();
        }
        if ($("simBadge")) $("simBadge").textContent = last.fitted_note;
        setStatus(last.fitted_note);
        pollAnalyze();
        return;
      }
      if (last.results && last.results.length) {
        last.results.forEach((r) => { store.contracts[r.symbol] = r; });
        renderContracts();
        if ($("simBadge")) $("simBadge").textContent = last.fitted_note;
        setStatus(last.fitted_note);
        if (refresh && last.fitted) {
          startAnalyze("infer");
        }
        return;
      }
      if ($("simBadge")) $("simBadge").textContent = last.fitted_note || "尚未拟合";
      const uni = await api("/api/contracts/universe");
      if (!$("contractRows").children.length) {
        uni.items.forEach((u) => {
          const row = {
            key: u.binance_symbol, symbol: u.binance_symbol, name: u.name, venue: u.venue,
            market_cap_rank: u.market_cap_rank, decision: "观望", score: 0, recommend: false,
            price: u.price, entry: u.price, stop_loss: "", take_profit: "", n_sims: 0, mode: "",
            regime: "", playbook: "",
          };
          store.contracts[row.symbol] = row;
        });
        renderContracts();
      }
      if (last.fitted) {
        setStatus(`标的 ${uni.items.length} 个。权重已校准，正在套用模型出信号…`);
        if (!analyzeJob && uni.items.length) startAnalyze("infer");
      } else {
        setStatus(`标的 ${uni.items.length} 个。首次需要校准指标权重（10 亿次，只需一次）…`);
        if (!analyzeJob && uni.items.length) startAnalyze("fit");
      }
    } else if (name === "meme") {
      setStatus("正在拉取妖币（可能需要十几秒）…");
      if ($("memeRows")) $("memeRows").innerHTML = emptyRow(10, "加载中…");
      const data = await api("/api/meme" + q);
      store.meme = {};
      $("memeRows").innerHTML = (data.items || []).map((m) => {
        store.meme[m.key] = m;
        return memeRow(m);
      }).join("") || emptyRow(10, "暂无过线妖币（需要池子≥$1M且短期买压）");
      if ($("memeMsg")) $("memeMsg").textContent = (data.method || "") + ((data.errors || []).length ? "；部分源失败：" + data.errors.slice(0,2).join("；") : "");
      setStatus(`监控 ${data.count} · 可跟 ${data.followable_count || 0}`);
    } else if (name === "ambassador") {
      setStatus("正在加载大使计划…");
      $("ambassadorCards").innerHTML = "<p class='muted'>加载中…</p>";
      const data = await api("/api/ambassadors" + q);
      const want = $("ambStatusFilter").value;
      const items = (data.items || []).filter((x) => {
        const st = x.mark_status || "none";
        if (want === "rejected") return st === "rejected";
        if (st === "rejected") return false;
        if (!want) return true;
        return st === want;
      });
      store.ambassador = {};
      $("ambassadorCards").innerHTML = items.map((a) => {
        store.ambassador[a.key] = a;
        return ambassadorCard(a);
      }).join("") || "<p class='muted'>" + (want === "rejected" ? "没有标记为未通过的大使。" : "暂无新项目大使。标记未通过的下次不会再出现。") + "</p>";
      setStatus(`招募信息 ${items.length} 条` + ((data.note && " · " + data.note) || ""));
    } else if (name === "launch") {
      setStatus("正在核对 Solana / BSC 官方关注…");
      $("launchCards").innerHTML = "<p class='muted'>加载中…</p>";
      if ($("launchAlerts")) $("launchAlerts").innerHTML = "";
      await fillLaunchTokenBox();
      const data = await api("/api/launches" + q);
      store.launch = {};
      const alerts = data.alerts || (data.items || []).filter((x) => x.alert);
      if ($("launchAlerts")) {
        $("launchAlerts").innerHTML = alerts.slice(0, 6).map((a) => `
          <div class="alert-banner">
            <strong>官方关注 · ${escapeHtml(a.launch_status || "")}</strong>
            <div>${escapeHtml(a.name)} ${a.username ? "(@" + escapeHtml(a.username) + ")" : ""}</div>
            <div class="launch-when">${escapeHtml(a.launch_when_label || a.launch_when || "时间待确认")}</div>
          </div>`).join("");
      }
      const launchItems = (data.items || []).filter((x) => x.verified_follow && (x.followed_by || []).length);
      $("launchCards").innerHTML = launchItems.map((a) => {
        store.launch[a.key] = a;
        return launchCard(a);
      }).join("") || "<p class='muted'>现在没有已核实的官方关注项目。Solana 要 @solana/@toly 关注，BSC 要 CZ/何一关注。</p>";
      if ($("launchMsg")) $("launchMsg").textContent = data.note || "";
      const bits = [`已核实官方关注 ${data.follow_count || 0}`];
      if (data.sol_count) bits.push(`Solana ${data.sol_count}`);
      if (data.bsc_count) bits.push(`BSC ${data.bsc_count}`);
      if (data.alert_count) bits.push(`发射提醒 ${data.alert_count}`);
      setStatus(bits.join(" · "));
      pingLaunchAlerts(alerts);
    } else if (name === "news") {
      setStatus("正在整理可能打开单边的消息…");
      if ($("newsVerdict")) $("newsVerdict").innerHTML = "<p class='muted'>正在归类利多 / 利空 / 待公布…</p>";
      if ($("newsGroups")) $("newsGroups").innerHTML = "";
      const data = await api("/api/news" + q);
      store.news = {};
      store.newsStance = data.stance || {};
      (data.items || []).forEach((x) => { if (x.key) store.news[x.key] = x; });
      renderNews();
      if ($("newsMsg")) $("newsMsg").textContent = data.note || "";
      const alerts = data.alerts || (data.items || []).filter((x) => x.alert);
      pingNewsAlerts(data.stance, alerts);
      setStatus(`消息面 ${((data.stance || {}).stance) || "观望"} · 利多 ${(data.stance || {}).long_count || 0} · 利空 ${(data.stance || {}).short_count || 0}` + ((data.errors || []).length ? " · 部分源失败" : ""));
      if (!newsTimer) newsTimer = setInterval(() => { if (currentView === "news") loadView("news", false); }, 90 * 1000);
    } else if (name === "airdrop") {
      setStatus("正在扫描高融资未发币项目…");
      $("airdropRows").innerHTML = emptyRow(9, "加载中…");
      const data = await api("/api/airdrops" + q);
      const want = $("airdropStatusFilter").value;
      const items = (data.items || []).filter((x) => !want || x.mark_status === want);
      store.airdrop = {};
      $("airdropRows").innerHTML = items.map((a) => {
        store.airdrop[a.key] = a;
        return airdropRow(a);
      }).join("") || emptyRow(9, "暂无 BTC/ETH 空投候选");
      setStatus(`BTC/ETH 空投 ${items.length}` + ((data.errors && data.errors.length) ? " · 部分数据源失败已用观察池补齐" : "") + (data.note ? " · " + data.note : ""));
    } else if (name === "copytrade") {
      await loadCopytrade();
    } else if (name === "wallet") {
      await loadWallet();
    } else if (name === "settings") {
      await loadSettingsForm();
    }
  } catch (err) {
    setStatus("错误：" + err.message);
  }
}

function emptyRow(cols, text) {
  return `<tr><td colspan="${cols}" class="muted">${text}</td></tr>`;
}

function renderContracts() {
  const only = $("onlyRecommend") && $("onlyRecommend").checked;
  const q = (($("contractFilter") && $("contractFilter").value) || "").toLowerCase();
  const rows = Object.values(store.contracts).filter((r) => r && r.symbol && r.symbol !== "?");
  const shown = rows.filter((r) => {
    if (only && !r.recommend) return false;
    if (!q) return true;
    return (r.symbol + " " + (r.name || "") + " " + (r.decision || "") + " " + (r.regime || "") + (r.recommend ? " 推荐" : "")).toLowerCase().includes(q);
  }).sort((a, b) => {
    const rec = Number(!!b.recommend) - Number(!!a.recommend);
    if (rec) return rec;
    return Math.abs(Number(b.score || 0)) - Math.abs(Number(a.score || 0));
  });
    $("contractRows").innerHTML = shown.map(contractRow).join("") || emptyRow(11, only ? "暂无推荐（可能连亏或持仓未到期）" : "暂无标的");
}

function contractRow(r) {
  const id = encodeURIComponent(r.symbol);
  return `<tr>
    <td><strong>${r.symbol}</strong><div class="muted">${r.name || ""} ${r.venue ? "· " + r.venue : ""}</div></td>
    <td>${r.market_cap_rank || "-"}</td>
    <td><span class="tag ${tagClass(r.decision)}">${r.decision || "观望"}</span>${r.recommend ? " <span class='tag live'>推荐</span>" : ""}</td>
    <td><span class="tag ${regimeClass(r.regime)}">${r.regime || "-"}</span><div class="muted">${escapeHtml(r.playbook || r.regime_detail || "")}</div></td>
    <td>${r.score ?? "-"}</td>
    <td>${fmtPx(r.price)}</td>
    <td>${fmtPx(r.entry)}</td>
    <td>${fmtPx(r.stop_loss)}</td>
    <td>${fmtPx(r.take_profit)}</td>
    <td>${r.mode === "infer" ? "套用模型" : (r.n_sims ? ("校准 " + Number(r.n_sims).toLocaleString() + " 次") : "未校准")}</td>
    <td class="row-actions">
      <button class="btn" onclick="showDetail('${id}')">指标</button>
      <button class="btn" onclick="participate('contract','${id}')">加入队列</button>
    </td>
  </tr>`;
}

function showDetail(id) {
  const r = store.contracts[decodeURIComponent(id)];
  if (!r) return;
  const inds = r.indicators || [];
  $("contractDetail").innerHTML = `
    <div class="panel">
      <h3>${r.symbol} · ${escapeHtml(r.regime || "行情未知")} · ${escapeHtml(r.playbook || "")} · ${r.recommend ? "推荐" : "不推荐"}</h3>
      <p class="muted">${escapeHtml(r.regime_advice || "")} ${escapeHtml(r.regime_detail || "")}${r.raw_decision && r.raw_decision !== r.decision ? " · 模型原结论 " + r.raw_decision + " 已被过滤" : ""}</p>
      <h3>${r.symbol} 指标权重（${r.mode === "infer" ? "套用已拟合模型" : "本次校准"} · 校准 ${Number(r.n_sims||0).toLocaleString()} 次）</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>指标</th><th>信号</th><th>强度</th><th>期望</th><th>初始权重</th><th>优化权重</th><th>说明</th></tr></thead>
        <tbody>
          ${inds.map((i) => `<tr>
            <td>${i.name}</td>
            <td>${i.signal === 1 ? "涨" : i.signal === -1 ? "跌" : "观望"}</td>
            <td>${i.strength}</td><td>${i.expectancy}</td>
            <td>${i.weight_initial}</td><td>${i.weight_optimized}</td>
            <td>${escapeHtml(i.detail)}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>
    </div>`;
}

async function startAnalyze(mode) {
  if (analyzeStarting) return;
  analyzeStarting = true;
  const interval = $("klineInterval").value;
  const kind = mode === "fit" ? "fit" : "infer";
  setStatus(kind === "fit" ? "开始校准指标权重（10 亿次，只需偶尔做）…" : "套用已拟合模型出信号…");
  $("analyzeProgress").classList.remove("hidden");
  try {
    const job = await api("/api/contracts/analyze", { method: "POST", body: { interval, mode: kind } });
    analyzeJob = job.job_id;
    if (job.reused) setStatus(`已有任务在跑 ${job.done || 0}/${job.total || 0}，继续等待…`);
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
    const data = await api("/api/contracts/analyze/" + analyzeJob);
    const pct = data.total ? (data.done / data.total) * 100 : 0;
    $("analyzeProgress").querySelector("div").style.width = pct + "%";
    (data.results || []).forEach((r) => { if (r.symbol) store.contracts[r.symbol] = r; });
    const rows = (data.results || []).filter((r) => r.symbol && r.symbol !== "?");
    if (rows.length) renderContracts();
    const note = (data.results || []).find((r) => r.sim_note);
    if (note && $("simBadge")) $("simBadge").textContent = note.sim_note;
    const phase = data.phase ? " · " + data.phase : "";
    const kindLabel = data.kind === "fit" ? "校准权重" : "套用模型";
    setStatus(`${kindLabel} ${data.done}/${data.total} · ${data.status}${phase}` + (data.status === "done" ? " · 完成" : ""));
    if (data.status === "running") setTimeout(pollAnalyze, 1200);
    else if (data.status === "error") setStatus("任务失败：" + (data.error || "").slice(0, 180));
    else if (data.status === "done" && $("simBadge") && note) $("simBadge").textContent = note.sim_note;
  } catch (err) {
    setStatus("分析任务查询失败：" + err.message);
  }
}

async function addAmbassador() {
  const project = ($("ambProject") && $("ambProject").value || "").trim();
  if (!project) {
    setStatus("请填写项目名再加入观察");
    return;
  }
  await api("/api/ambassadors", { method: "POST", body: {
    project,
    url: ($("ambUrl") && $("ambUrl").value || "").trim(),
  }});
  $("ambProject").value = "";
  if ($("ambUrl")) $("ambUrl").value = "";
  await loadView("ambassador", true);
  setStatus("已加入观察：" + project);
}

function ageLabel(m) {
  const mins = m.age_minutes;
  if (mins == null || mins === "") return "";
  const n = Number(mins);
  if (Number.isNaN(n)) return "";
  if (n < 60) return `池龄 ${n.toFixed(0)} 分钟`;
  if (n < 60 * 24) return `池龄 ${(n / 60).toFixed(1)} 小时`;
  return `池龄 ${(n / 60 / 24).toFixed(1)} 天`;
}

function sourceBadge(item) {
  const kind = item.source_kind || (item.fallback ? "seed" : "live");
  const label = kind === "manual" ? "手动" : kind === "live" ? "实时" : "观察池";
  const cls = kind === "live" ? "live" : "seed";
  return `<span class="tag ${cls}">${label}</span>`;
}

function memeRow(m) {
  const id = encodeURIComponent(m.key);
  const g = m.grade || "观察";
  const cls = g === "可跟" ? "up" : g === "避开" ? "down" : "wait";
  const extra = [ageLabel(m)].concat(m.score_reasons || []).concat(m.reject_reasons || []).slice(0, 3).join(" · ");
  return `<tr>
    <td><span class="tag ${cls}">${escapeHtml(g)}</span></td>
    <td>${escapeHtml(m.chain)}</td>
    <td><strong>${escapeHtml(m.symbol)}</strong><div class="muted">${escapeHtml(extra)}</div></td>
    <td>${fmtUsd(m.price_usd)}</td>
    <td>${fmtUsd(m.liquidity_usd)}</td>
    <td>${m.buy_sell_ratio ?? "-"}</td>
    <td>${m.heat ?? "-"}</td>
    <td>${m.risk ?? "-"}</td>
    <td>${escapeHtml(m.source)}</td>
    <td class="row-actions">
      ${m.url ? `<a class="btn" href="${escapeHtml(m.url)}" target="_blank">打开</a>` : ""}
      <button class="btn" onclick="participate('meme','${id}')">手动队列</button>
    </td>
  </tr>`;
}

function ambassadorCard(a) {
  const id = encodeURIComponent(a.key);
  return `<article class="card">
    <h3>${sourceBadge(a)} ${escapeHtml(a.project || a.username || "项目")}</h3>
    <p>${escapeHtml((a.text || "").slice(0, 220))}</p>
    <p>优先级：<strong>${escapeHtml(a.priority)}</strong> · 期限：${escapeHtml(a.deadline)}</p>
    <p>状态：${markSelect("ambassador", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.twitter ? `<a class="btn" href="${escapeHtml(a.twitter)}" target="_blank">X</a>` : ""}
      ${a.url ? `<a class="btn" href="${escapeHtml(a.url)}" target="_blank">来源</a>` : ""}
      <button class="btn" onclick="mark('ambassador','${id}','applied')">标记已申请</button>
      <button class="btn primary" onclick="mark('ambassador','${id}','accepted')">标记已成功</button>
    </div>
  </article>`;
}

function launchCard(a) {
  const id = encodeURIComponent(a.key);
  const klass = a.alert ? "card alert-card" : "card";
  const when = a.launch_when_label || a.launch_when;
  const verified = !!a.verified_follow;
  const officialN = Number(a.official_follow_count || (a.followed_by || []).length || 0);
  const officialTotal = Number(a.official_follow_total || 3);
  const fans = Number(a.followers || 0);
  const countLine = verified
    ? `${escapeHtml(a.follow_count_label || ("官方关注 " + officialN + "/" + officialTotal))} · 粉丝 ${fans ? fans.toLocaleString() : "未知"}`
    : `${escapeHtml(a.follow_count_label || "不是官方关注 · 链上新开盘")}${a.liquidity_usd ? " · 池子 $" + Number(a.liquidity_usd).toLocaleString(undefined, {maximumFractionDigits: 0}) : ""}`;
  return `<article class="${klass}">
    <h3>${sourceBadge(a)} ${escapeHtml(a.name)}${a.username ? " <span class='muted'>@" + escapeHtml(a.username) + "</span>" : ""}</h3>
    <p>${escapeHtml(a.kind || "")} · ${escapeHtml(a.chain || "")} · ${escapeHtml(a.source || "")}</p>
    <p class="launch-when">${countLine}</p>
    ${a.follow_proof ? `<p>${escapeHtml(a.follow_proof)}</p>` : ""}
    ${verified && a.followed_by && a.followed_by.length ? `<p>${(a.followed_by || []).map((n) => `<span class="tag live">@${escapeHtml(n)} 关注</span>`).join(" ")}</p>` : ""}
    ${a.launch_status ? `<p><span class="tag ${a.alert ? "range" : "wait"}">${escapeHtml(a.launch_status)}</span>${a.new_follow ? " <span class='tag live'>新关注</span>" : ""}</p>` : ""}
    ${when ? `<p class="launch-when">${escapeHtml(when)}</p>` : ""}
    <p>${escapeHtml((a.analysis || a.text || "").slice(0, 220))}</p>
    ${a.analysis && a.text && a.alert ? `<p>${escapeHtml(a.text.slice(0, 160))}</p>` : ""}
    <p>标记：${markSelect("launch", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.twitter ? `<a class="btn" href="${escapeHtml(a.twitter)}" target="_blank">X</a>` : ""}
      ${a.url ? `<a class="btn" href="${escapeHtml(a.url)}" target="_blank">打开</a>` : ""}
      <button class="btn" onclick="participate('launch','${id}')">加入打新队列</button>
    </div>
  </article>`;
}

function pingLaunchAlerts(alerts) {
  if (!alerts || !alerts.length || !("Notification" in window)) return;
  const body = alerts.slice(0, 3).map((a) => `${a.name} · ${a.launch_when_label || a.launch_status || ""}`).join("；");
  const send = () => { try { new Notification("链上雷达 · Sol 发射提醒", { body }); } catch (e) {} };
  if (Notification.permission === "granted") send();
  else if (Notification.permission !== "denied") Notification.requestPermission().then((p) => { if (p === "granted") send(); });
}

function newsBiasClass(bias) {
  if (bias === "偏多") return "up";
  if (bias === "偏空") return "down";
  return "wait";
}

function renderNews() {
  const only = $("newsAlertOnly") && $("newsAlertOnly").checked;
  const bias = (($("newsBiasFilter") && $("newsBiasFilter").value) || "");
  const q = (($("newsFilter") && $("newsFilter").value) || "").toLowerCase();
  const stance = store.newsStance || {};
  const tag = stance.stance_tag || "观望";
  if ($("newsVerdict")) {
    $("newsVerdict").innerHTML = `
      <h3 class="verdict-title">消息面结论
        <span class="tag ${tagClass(tag)}">${escapeHtml(stance.stance || "观望")}</span>
        <span class="tag ${stance.confidence === "高" ? "live" : "wait"}">${escapeHtml(stance.confidence || "低")}把握</span>
      </h3>
      <p>${escapeHtml(stance.summary || "还没有足够消息形成方向。")}</p>
      <p>${escapeHtml(stance.playbook || "")}</p>
      <p class="muted">利多 ${stance.long_count || 0} · 利空 ${stance.short_count || 0} · 待公布/未定 ${stance.wait_count || 0}</p>`;
  }
  const groups = stance.groups || {};
  const cols = [
    ["long", "利多 · 偏多", "up"],
    ["short", "利空 · 偏空", "down"],
    ["wait", "待公布 / 方向未定", "wait"],
  ];
  if ($("newsGroups")) {
    $("newsGroups").innerHTML = cols.map(([key, label, cls]) => {
      const rows = (groups[key] || []).filter((r) => {
        if (only && !r.alert) return false;
        if (bias && r.bias !== bias) return false;
        if (!q) return true;
        return (r.headline + " " + (r.title || "") + " " + (r.category || "") + " " + (r.text || "")).toLowerCase().includes(q);
      });
      const body = rows.map(newsClusterCard).join("") || `<p class="muted">${only ? "这一侧暂时没有高影响提醒。" : "这一侧暂无催化剂。"}</p>`;
      return `<section class="panel"><h3><span class="tag ${cls}">${label}</span></h3>${body}</section>`;
    }).join("");
  }
}

function newsClusterCard(a) {
  const refs = (a.cluster || []).map((c) => {
    const title = escapeHtml(c.title || "");
    const when = c.when_label ? `<span class="muted"> · ${escapeHtml(c.when_label)}</span>` : "";
    if (c.url) return `<li><a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${title}</a>${when}</li>`;
    return `<li>${title}${when}</li>`;
  }).join("");
  return `<article class="${a.alert ? "card alert-card" : "card"}" style="margin-top:10px">
    <h3>${escapeHtml(a.headline || a.title || "")}</h3>
    <p>
      <span class="tag ${a.impact === "高" ? "range" : "wait"}">${escapeHtml(a.impact || "")}影响</span>
      <span class="tag ${newsBiasClass(a.bias)}">${escapeHtml(a.bias || "方向未定")}</span>
      <span class="tag macro">${escapeHtml(a.category || "")}</span>
      ${a.cluster_size > 1 ? `<span class="tag wait">${a.cluster_size}条依据</span>` : ""}
    </p>
    <p class="launch-when">${escapeHtml(a.when_label || a.when_status || "")}</p>
    <p>${escapeHtml(a.playbook || "")}</p>
    ${refs ? `<ul class="cluster-list">${refs}</ul>` : ""}
  </article>`;
}

function pingNewsAlerts(stance, alerts) {
  const call = (stance && stance.stance) ? stance.stance : "";
  const fresh = (alerts || []).filter((a) => a.key && !seenNewsAlerts.has(a.key));
  fresh.forEach((a) => seenNewsAlerts.add(a.key));
  if (!fresh.length && !call) return;
  if (!("Notification" in window)) return;
  const body = call
    ? `结论 ${call}（${(stance && stance.confidence) || "低"}把握）`
    : fresh.slice(0, 3).map((a) => a.title).join("；");
  const send = () => { try { new Notification("链上雷达 · 消息面结论", { body }); } catch (e) {} };
  if (!fresh.length) return;
  if (Notification.permission === "granted") send();
  else if (Notification.permission !== "denied") Notification.requestPermission().then((p) => { if (p === "granted") send(); });
}

function airdropRow(a) {
  const id = encodeURIComponent(a.key);
  return `<tr>
    <td><strong>${escapeHtml(a.name)}</strong><div class="muted">${escapeHtml((a.chains||[]).slice(0,3).join(", "))}</div></td>
    <td><span class="tag ${a.ecosystem === "bitcoin" ? "btc" : (a.ecosystem === "other" ? "mixed" : "eth")}">${escapeHtml(a.ecosystem_label || "")}</span></td>
    <td>${fmtUsd(a.total_funding_usd)}</td>
    <td>${a.famous_count} · ${escapeHtml((a.famous_investors||[]).slice(0,3).join(", "))}</td>
    <td>${escapeHtml(a.token_expect)}</td>
    <td>${escapeHtml(a.sector || "")}</td>
    <td>${a.score}</td>
    <td>${markSelect("airdrop", a.key, a.mark_status)}</td>
    <td class="row-actions">
      ${a.source ? `<a class="btn" href="${escapeHtml(a.source)}" target="_blank">来源</a>` : ""}
      <button class="btn" onclick="participate('airdrop','${id}')">加入交互队列</button>
    </td>
  </tr>`;
}

function markSelect(category, key, status) {
  const opts = {
    ambassador: [["none","未标记"],["watching","关注中"],["applied","已申请"],["accepted","已参与成功"],["rejected","未通过"]],
    airdrop: [["none","未标记"],["watching","关注中"],["applied","已交互"],["accepted","已参与成功"],["skipped","放弃"]],
    launch: [["none","未标记"],["watching","关注中"],["applied","已打新"],["accepted","已中签"],["skipped","放弃"]],
    news: [["none","未标记"],["watching","关注中"],["applied","已查看"],["skipped","忽略"]],
    meme: [["none","未标记"],["watching","关注中"],["applied","已买入"],["skipped","忽略"]],
  }[category] || [["none","未标记"],["watching","关注中"]];
  const id = encodeURIComponent(key);
  return `<select onchange="mark('${category}','${id}', this.value)">
    ${opts.map(([v,l]) => `<option value="${v}" ${status===v?"selected":""}>${l}</option>`).join("")}
  </select>`;
}

async function mark(category, key, status) {
  key = decodeURIComponent(key);
  await api("/api/marks", { method: "POST", body: { category, item_key: key, status } });
  setStatus("已标记 " + status);
  if (category === "ambassador") loadView("ambassador");
}

async function participate(category, key) {
  const bucket = category === "contract" ? "contracts" : category;
  const item = (store[bucket] || {})[decodeURIComponent(key)];
  if (!item) return;
  const task = await api("/api/wallet/participate", { method: "POST", body: { category, item, auto: false } });
  setStatus("已加入队列 #" + task.id + "，请到钱包页确认");
  showView("wallet");
}

async function loadCopytrade() {
  const c = await api("/api/copytrade");
  $("copyEnabled").checked = !!c.enabled;
  $("copyMode").value = c.mode || "paper";
  $("copySize").value = c.size_usd;
  $("copyEquity").textContent = fmtUsd(c.equity);
  $("copyRealized").textContent = fmtUsd(c.realized_pnl);
  $("copyUnreal").textContent = fmtUsd(c.unrealized_pnl);
  $("copyWin").textContent = ((c.win_rate || 0) * 100).toFixed(1) + "%";
  $("copyOpenN").textContent = c.open_count;
  $("copyActions").textContent = c.note || "";
  const rows = (c.open || []).concat(c.closed || []).slice(0, 40);
    $("copyPosRows").innerHTML = rows.map((p) => `<tr>
    <td>${escapeHtml(p.symbol)}</td>
    <td>${escapeHtml(p.chain)}</td>
    <td>${fmtPx(p.entry)}</td>
    <td>${fmtPx(p.last_price)}</td>
    <td>${fmtPx(p.sl)}</td>
    <td>${fmtPx(p.tp)}</td>
    <td>${fmtUsd(p.status === "open" ? p.unrealized_pnl : p.pnl_usd)}</td>
    <td>${escapeHtml(p.status)}${p.close_reason ? " · " + escapeHtml(p.close_reason) : ""}</td>
  </tr>`).join("") || emptyRow(8, "暂无持仓。点「刷新当前模块」或保存跟单规则后，会按「可跟」开模拟仓。");
  setStatus(`跟单 ${c.mode} · 持仓 ${c.open_count}`);
}

async function saveCopytrade() {
  await api("/api/copytrade/settings", { method: "POST", body: { settings: {
    copy_enabled: $("copyEnabled").checked,
    copy_mode: $("copyMode").value,
    copy_size_usd: Number($("copySize").value || 30),
  }}});
  await api("/api/meme?refresh=true");
  await loadCopytrade();
  setStatus("跟单规则已保存，并按最新妖币信号扫描");
}

async function loadWallet() {
  const w = await api("/api/wallet");
  $("walletAddr").textContent = w.address || "未连接";
  $("walletChip").textContent = w.connected ? ("已连接 " + w.address.slice(0, 6) + "…" + w.address.slice(-4)) : "钱包未连接";
  $("autoParticipate").checked = !!w.auto_participate;
  $("autoMaxSpend").value = w.auto_max_spend_usd;
  $("taskRows").innerHTML = (w.tasks || []).map((t) => `<tr>
    <td>${(t.created_at||"").replace("T"," ").slice(0,19)}</td>
    <td>${escapeHtml(t.category)}</td>
    <td>${escapeHtml(t.title)}</td>
    <td>${escapeHtml(t.status)}</td>
    <td>${escapeHtml(t.tx_hash || "-")}</td>
  </tr>`).join("") || emptyRow(5, "暂无任务");
  setStatus(w.connected ? "钱包已连接" : "钱包未连接");
}

async function persistWalletFlags() {
  await api("/api/settings", { method: "POST", body: { settings: {
    auto_participate: $("autoParticipate").checked,
    auto_max_spend_usd: Number($("autoMaxSpend").value || 50),
  }}});
}

async function fillLaunchTokenBox() {
  try {
    settingsCache = await api("/api/settings");
  } catch (e) {
    return;
  }
  const token = String(settingsCache.twitter_bearer_token || "");
  if ($("launch_twitter_bearer")) $("launch_twitter_bearer").value = token;
  if ($("launchTokenStatus")) {
    $("launchTokenStatus").textContent = token
      ? "已保存令牌。打新仍只显示官方关注列表里的账号。"
      : "可留空。不填也会去读公开关注页，读不到就空着。";
  }
}

async function saveLaunchToken() {
  const token = (($("launch_twitter_bearer") && $("launch_twitter_bearer").value) || "").trim();
  if (!token) {
    setStatus("请先粘贴 Bearer Token");
    if ($("launchTokenStatus")) $("launchTokenStatus").textContent = "空的。打开 developer.x.com → App → Keys and tokens → Bearer Token。";
    return;
  }
  await api("/api/settings", { method: "POST", body: { settings: { twitter_bearer_token: token } } });
  if ($("s_twitter_bearer_token")) $("s_twitter_bearer_token").value = token;
  if ($("launchTokenStatus")) $("launchTokenStatus").textContent = "已保存，正在用这串令牌跟踪 @solana…";
  setStatus("令牌已保存，正在拉 @solana 最近关注…");
  await loadView("launch", true);
}

async function loadSettingsForm() {
  settingsCache = await api("/api/settings");
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","meme_min_liquidity_usd","airdrop_min_funding_usd","airdrop_btc_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
    const el = $("s_" + k);
    if (el) el.value = settingsCache[k] ?? "";
  });
}

async function saveSettings() {
  const settings = {};
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","meme_min_liquidity_usd","airdrop_min_funding_usd","airdrop_btc_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
    const el = $("s_" + k);
    let v = el.value;
    if (el.type === "number") v = Number(v);
    settings[k] = v;
  });
  await api("/api/settings", { method: "POST", body: { settings } });
  setStatus("设置已保存");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
}

showView("contracts");
loadWallet().catch(() => {});
