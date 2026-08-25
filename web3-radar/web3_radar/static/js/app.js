const views = {
  contracts: ["合约分析", "涨跌、挂单建仓、止损、止盈。仅供参考，不构成投资建议。"],
  news: ["单边快讯", "过去 24 小时的做多 / 做空 / 观望。仅供参考，不构成投资建议。"],
  meme: ["妖币监控", "可跟 / 观察 / 避开，附 CA 与链。仅供参考，不构成投资建议。"],
  copytrade: ["自动跟单", "跟随「可跟」信号。模拟盘默认开启，实盘需钱包确认。"],
  ambassador: ["大使招募", "项目方发布的招募窗口。可标记申请与结果。"],
  launch: ["打新监测", "只看 @solana 或 @toly 最近一个月关注、尚未发币的 Web3 项目。个人账号不显示。"],
  airdrop: ["空投雷达", "比特币与 ETH 生态未发币项目。"],
  wallet: ["钱包执行", "连接钱包后，将任务加入确认队列。不会索取助记词。"],
  settings: ["设置", "接口令牌、钱包接口与过滤条件。"],
};

const $ = (id) => document.getElementById(id);
const store = { contracts: {}, meme: {}, ambassador: {}, launch: {}, airdrop: {}, news: {} };
const fmtUsd = (n) => n == null || Number.isNaN(Number(n)) ? "-" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const fmtPx = (n) => n == null || n === "" ? "-" : Number(n).toPrecision(6);
const tagClass = (d) => d === "涨" ? "up" : d === "跌" ? "down" : "wait";
const regimeClass = (r) => r === "单边" ? "trend" : r === "震荡" ? "range" : "mixed";

function fmtWinRate(r) {
  if (r == null || r.win_rate == null || r.win_rate === "") return "-";
  const n = Number(r.win_rate);
  if (Number.isNaN(n)) return "-";
  return (n * 100).toFixed(0) + "%";
}

function resultBadge() {
  const n = Object.values(store.contracts).filter((r) => r && r.recommend).length;
  const el = $("simBadge");
  if (!el) return;
  if (!n) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.classList.remove("hidden");
  el.textContent = "推荐 " + n + " 个";
}

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
if ($("analyzeAll")) $("analyzeAll").addEventListener("click", () => startAnalyze("infer"));
if ($("refitWeights")) $("refitWeights").addEventListener("click", () => startAnalyze("fit"));
$("saveSettings").addEventListener("click", saveSettings);
$("disconnectWallet").addEventListener("click", async () => {
  await api("/api/wallet/disconnect", { method: "POST" });
  loadWallet();
});
$("contractFilter").addEventListener("input", () => renderContracts());
$("contractFilter").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    ev.preventDefault();
    analyzeOneCoin();
  }
});
if ($("analyzeOne")) $("analyzeOne").addEventListener("click", () => analyzeOneCoin());
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
      setStatus("正在更新…");
      const last = await api("/api/contracts/status");
      if (last.running && last.job_id) {
        analyzeJob = last.job_id;
        $("analyzeProgress").classList.remove("hidden");
        if (last.results && last.results.length) {
          last.results.forEach((r) => { store.contracts[r.symbol] = r; });
          renderContracts();
        }
        pollAnalyze();
        return;
      }
      if (last.results && last.results.length) {
        last.results.forEach((r) => { store.contracts[r.symbol] = r; });
        renderContracts();
        setStatus("已更新");
        if (refresh && last.fitted) {
          startAnalyze("infer");
        }
        return;
      }
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
      if (!analyzeJob && uni.items.length) startAnalyze(last.fitted ? "infer" : "fit");
    } else if (name === "meme") {
      setStatus("正在更新…");
      if ($("memeRows")) $("memeRows").innerHTML = emptyRow(7, "加载中…");
      const data = await api("/api/meme" + q);
      store.meme = {};
      $("memeRows").innerHTML = (data.items || []).map((m) => {
        store.meme[m.key] = m;
        return memeRow(m);
      }).join("") || emptyRow(7, "暂无过线标的");
      setStatus(`可跟 ${data.followable_count || 0} · 名人喊单 ${data.kol_count || 0}`);
    } else if (name === "ambassador") {
      setStatus("正在更新…");
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
      }).join("") || "<p class='muted'>" + (want === "rejected" ? "没有标记为未通过的大使。" : "暂无新的项目方招募。") + "</p>";
      setStatus(`招募 ${items.length} 条`);
    } else if (name === "launch") {
      setStatus("正在更新…");
      $("launchCards").innerHTML = "<p class='muted'>加载中…</p>";
      if ($("launchAlerts")) $("launchAlerts").innerHTML = "";
      const data = await api("/api/launches" + q);
      store.launch = {};
      const alerts = data.alerts || (data.items || []).filter((x) => x.alert);
      if ($("launchAlerts")) {
        $("launchAlerts").innerHTML = alerts.slice(0, 6).map((a) => `
          <div class="alert-banner">
            <strong>官方 · 未发币 · ${escapeHtml(a.launch_status || "")}</strong>
            <div>${escapeHtml(a.name)} ${a.username ? "(@" + escapeHtml(a.username) + ")" : ""}</div>
            <div class="launch-when">${escapeHtml(a.launch_when_label || a.launch_when || "时间待确认")}</div>
          </div>`).join("");
      }
      const launchItems = (data.items || []).filter((x) => x.verified_follow && (x.followed_by || []).length);
      $("launchCards").innerHTML = launchItems.map((a) => {
        store.launch[a.key] = a;
        return launchCard(a);
      }).join("") || "<p class='muted'>暂无未发币项目。</p>";
      const bits = [];
      if (data.sol_count) bits.push(`Solana ${data.sol_count}`);
      if (data.bsc_count) bits.push(`BSC ${data.bsc_count}`);
      if (data.alert_count) bits.push(`提醒 ${data.alert_count}`);
      setStatus(bits.join(" · ") || "已更新");
      pingLaunchAlerts(alerts);
    } else if (name === "news") {
      setStatus("正在更新…");
      if ($("newsVerdict")) $("newsVerdict").innerHTML = "<p class='muted'>加载中…</p>";
      if ($("newsGroups")) $("newsGroups").innerHTML = "";
      const data = await api("/api/news" + q);
      store.news = {};
      store.newsStance = data.stance || {};
      (data.items || []).forEach((x) => { if (x.key) store.news[x.key] = x; });
      renderNews();
      const alerts = data.alerts || (data.items || []).filter((x) => x.alert);
      pingNewsAlerts(data.stance, alerts);
      setStatus(`${((data.stance || {}).stance) || "观望"} · 利多 ${(data.stance || {}).long_count || 0} · 利空 ${(data.stance || {}).short_count || 0}`);
      if (!newsTimer) newsTimer = setInterval(() => { if (currentView === "news") loadView("news", false); }, 90 * 1000);
    } else if (name === "airdrop") {
      setStatus("正在更新…");
      $("airdropRows").innerHTML = emptyRow(8, "加载中…");
      const data = await api("/api/airdrops" + q);
      const want = $("airdropStatusFilter").value;
      const items = (data.items || []).filter((x) => !want || x.mark_status === want);
      store.airdrop = {};
      $("airdropRows").innerHTML = items.map((a) => {
        store.airdrop[a.key] = a;
        return airdropRow(a);
      }).join("") || emptyRow(8, "暂无候选");
      setStatus(`空投 ${items.length}`);
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
  $("contractRows").innerHTML = shown.map(contractRow).join("") || emptyRow(9, only ? "暂无推荐" : "暂无标的");
  resultBadge();
}

function contractRow(r) {
  const id = encodeURIComponent(r.symbol);
  return `<tr>
    <td><strong>${r.symbol}</strong><div class="muted">${r.name || ""} ${r.venue ? "· " + r.venue : ""}</div></td>
    <td><span class="tag ${tagClass(r.decision)}">${r.decision || "观望"}</span>${r.recommend ? " <span class='tag live'>推荐</span>" : ""}</td>
    <td><span class="tag ${regimeClass(r.regime)}">${r.regime || "-"}</span></td>
    <td>${fmtWinRate(r)}</td>
    <td>${fmtPx(r.price)}</td>
    <td>${fmtPx(r.entry)}</td>
    <td>${fmtPx(r.stop_loss)}</td>
    <td>${fmtPx(r.take_profit)}</td>
    <td class="row-actions">
      <button class="btn" onclick="showDetail('${id}')">详情</button>
      <button class="btn" onclick="participate('contract','${id}')">加入队列</button>
    </td>
  </tr>`;
}

function showDetail(id) {
  const r = store.contracts[decodeURIComponent(id)];
  if (!r) return;
  $("contractDetail").innerHTML = `
    <div class="panel">
      <h3>${r.symbol}
        <span class="tag ${tagClass(r.decision)}">${r.decision || "观望"}</span>
        ${r.recommend ? " <span class='tag live'>推荐</span>" : ""}
      </h3>
      <p>胜率 <strong>${fmtWinRate(r)}</strong> · 行情 ${escapeHtml(r.regime || "-")}</p>
      <p>现价 ${fmtPx(r.price)} · 挂单 ${fmtPx(r.entry)} · 止损 ${fmtPx(r.stop_loss)} · 止盈 ${fmtPx(r.take_profit)}</p>
    </div>`;
}

async function analyzeOneCoin() {
  const q = (($("contractFilter") && $("contractFilter").value) || "").trim();
  if (!q) {
    setStatus("请先在搜索框输入币种，例如 BTC 或 ETHUSDT");
    return;
  }
  const interval = $("klineInterval").value;
  setStatus("正在分析 " + q + "…");
  try {
    const row = await api("/api/contracts/analyze-one", { method: "POST", body: { symbol: q, interval } });
    if (row && row.symbol) {
      store.contracts[row.symbol] = row;
      if ($("onlyRecommend")) $("onlyRecommend").checked = false;
      renderContracts();
      showDetail(encodeURIComponent(row.symbol));
      setStatus(
        row.symbol + " · " + (row.decision || "观望")
        + " · 胜率 " + fmtWinRate(row)
        + " · 挂单 " + fmtPx(row.entry)
        + " / 止损 " + fmtPx(row.stop_loss)
        + " / 止盈 " + fmtPx(row.take_profit)
      );
    }
  } catch (err) {
    setStatus("分析失败：" + err.message);
  }
}

async function startAnalyze(mode) {
  if (analyzeStarting) return;
  analyzeStarting = true;
  const interval = $("klineInterval").value;
  const kind = mode === "fit" ? "fit" : "infer";
  setStatus("正在更新…");
  $("analyzeProgress").classList.remove("hidden");
  try {
    const job = await api("/api/contracts/analyze", { method: "POST", body: { interval, mode: kind } });
    analyzeJob = job.job_id;
    if (job.reused) setStatus(`正在更新 ${job.done || 0}/${job.total || 0}`);
    pollAnalyze();
  } catch (err) {
    setStatus("无法启动：" + err.message);
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
    if (data.status === "running") {
      setStatus(`正在更新 ${data.done}/${data.total}`);
      setTimeout(pollAnalyze, 1200);
    } else if (data.status === "error") {
      setStatus("更新失败");
    } else if (data.status === "done") {
      setStatus("已更新");
      if ($("analyzeProgress")) $("analyzeProgress").classList.add("hidden");
    }
  } catch (err) {
    setStatus("更新失败：" + err.message);
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

function sourceBadge(item) {
  const kind = item.source_kind || (item.fallback ? "seed" : "live");
  if (kind !== "manual") return "";
  return `<span class="tag seed">手动</span>`;
}

function memeRow(m) {
  const id = encodeURIComponent(m.key);
  const g = m.grade || "观察";
  const cls = g === "可跟" ? "up" : g === "避开" ? "down" : "wait";
  const ca = m.token_address || "";
  const shortCa = ca ? (ca.slice(0, 6) + "…" + ca.slice(-4)) : "-";
  const kol = m.kol_call
    ? `<div><span class="tag kol">名人喊单</span> ${escapeHtml(m.kol || "")}</div>`
    : "";
  return `<tr>
    <td><span class="tag ${cls}">${escapeHtml(g)}</span>${m.kol_call ? " <span class='tag kol'>名人</span>" : ""}</td>
    <td>${escapeHtml(m.chain)}</td>
    <td><strong>${escapeHtml(m.symbol)}</strong>${kol}</td>
    <td class="ca" title="${escapeHtml(ca)}">${escapeHtml(shortCa)}</td>
    <td>${fmtUsd(m.price_usd)}</td>
    <td>${fmtUsd(m.liquidity_usd)}</td>
    <td class="row-actions">
      ${m.url ? `<a class="btn" href="${escapeHtml(m.url)}" target="_blank">打开</a>` : ""}
      ${m.call_url ? `<a class="btn" href="${escapeHtml(m.call_url)}" target="_blank">喊单</a>` : ""}
      <button class="btn" onclick="participate('meme','${id}')">加入队列</button>
    </td>
  </tr>`;
}

function ambassadorCard(a) {
  const id = encodeURIComponent(a.key);
  return `<article class="card">
    <h3>${sourceBadge(a)} ${escapeHtml(a.project || a.username || "项目")}</h3>
    <p>${escapeHtml((a.text || "").slice(0, 220))}</p>
    <p>期限：${escapeHtml(a.deadline || "-")}</p>
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
  const badge = `<span class="tag live">官方</span> <span class="tag wait">未发币</span>`;
  const who = (a.followed_by || []).map((n) => `<span class="tag live">@${escapeHtml(n)}</span>`).join(" ");
  return `<article class="${klass}">
    <h3>${badge} ${escapeHtml(a.name)}${a.username ? " <span class='muted'>@" + escapeHtml(a.username) + "</span>" : ""}</h3>
    <p>${escapeHtml(a.chain || "")}</p>
    ${who ? `<p>${who}</p>` : ""}
    ${a.launch_status ? `<p><span class="tag ${a.alert ? "range" : "wait"}">${escapeHtml(a.launch_status)}</span></p>` : ""}
    ${when ? `<p class="launch-when">${escapeHtml(when)}</p>` : ""}
    <p>标记：${markSelect("launch", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.twitter ? `<a class="btn" href="${escapeHtml(a.twitter)}" target="_blank">X</a>` : ""}
      ${a.url ? `<a class="btn" href="${escapeHtml(a.url)}" target="_blank">打开</a>` : ""}
      <button class="btn" onclick="participate('launch','${id}')">加入队列</button>
    </div>
  </article>`;
}

function pingLaunchAlerts(alerts) {
  if (!alerts || !alerts.length || !("Notification" in window)) return;
  const body = alerts.slice(0, 3).map((a) => `${a.name} · ${a.launch_when_label || a.launch_status || ""}`).join("；");
  const send = () => { try { new Notification("链上雷达 · 打新提醒", { body }); } catch (e) {} };
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
      <h3 class="verdict-title">结论
        <span class="tag ${tagClass(tag)}">${escapeHtml(stance.stance || "观望")}</span>
      </h3>
      <p>${escapeHtml(stance.summary || "暂无方向。")}</p>
      <p class="muted">利多 ${stance.long_count || 0} · 利空 ${stance.short_count || 0} · 待公布 ${stance.wait_count || 0}</p>`;
  }
  const groups = stance.groups || {};
  const cols = [
    ["long", "利多", "up"],
    ["short", "利空", "down"],
    ["wait", "待公布", "wait"],
  ];
  if ($("newsGroups")) {
    $("newsGroups").innerHTML = cols.map(([key, label, cls]) => {
      const rows = (groups[key] || []).filter((r) => {
        if (only && !r.alert) return false;
        if (bias && r.bias !== bias) return false;
        if (!q) return true;
        return (r.headline + " " + (r.title || "") + " " + (r.category || "") + " " + (r.text || "")).toLowerCase().includes(q);
      });
      const body = rows.map(newsClusterCard).join("") || `<p class="muted">${only ? "这一侧暂时没有高影响提醒。" : "这一侧暂无消息。"}</p>`;
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
      <span class="tag ${newsBiasClass(a.bias)}">${escapeHtml(a.bias || "方向未定")}</span>
      ${a.impact === "高" ? `<span class="tag range">高影响</span>` : ""}
    </p>
    <p class="launch-when">${escapeHtml(a.when_label || a.when_status || "")}</p>
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
    ? `结论 ${call}`
    : fresh.slice(0, 3).map((a) => a.title).join("；");
  const send = () => { try { new Notification("链上雷达 · 快讯", { body }); } catch (e) {} };
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
    <td>${escapeHtml((a.famous_investors||[]).slice(0,3).join(", ") || "-")}</td>
    <td>${escapeHtml(a.token_expect)}</td>
    <td>${escapeHtml(a.sector || "")}</td>
    <td>${markSelect("airdrop", a.key, a.mark_status)}</td>
    <td class="row-actions">
      ${a.source ? `<a class="btn" href="${escapeHtml(a.source)}" target="_blank">来源</a>` : ""}
      <button class="btn" onclick="participate('airdrop','${id}')">加入队列</button>
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
  setStatus("已标记");
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
  const rows = (c.open || []).concat(c.closed || []).slice(0, 40);
  $("copyPosRows").innerHTML = rows.map((p) => `<tr>
    <td>${escapeHtml(p.symbol)}</td>
    <td>${escapeHtml(p.chain)}</td>
    <td>${fmtPx(p.entry)}</td>
    <td>${fmtPx(p.last_price)}</td>
    <td>${fmtPx(p.sl)}</td>
    <td>${fmtPx(p.tp)}</td>
    <td>${fmtUsd(p.status === "open" ? p.unrealized_pnl : p.pnl_usd)}</td>
    <td>${escapeHtml(p.status === "open" ? "持仓" : (p.status === "closed" ? "已平" : p.status))}</td>
  </tr>`).join("") || emptyRow(8, "暂无持仓");
  setStatus(`持仓 ${c.open_count}`);
}

async function saveCopytrade() {
  await api("/api/copytrade/settings", { method: "POST", body: { settings: {
    copy_enabled: $("copyEnabled").checked,
    copy_mode: $("copyMode").value,
    copy_size_usd: Number($("copySize").value || 30),
  }}});
  await api("/api/meme?refresh=true");
  await loadCopytrade();
  setStatus("已保存");
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
}

async function saveLaunchToken() {
  const token = (($("launch_twitter_bearer") && $("launch_twitter_bearer").value) || "").trim();
  if (!token) {
    setStatus("请先粘贴令牌");
    return;
  }
  await api("/api/settings", { method: "POST", body: { settings: { twitter_bearer_token: token } } });
  if ($("s_twitter_bearer_token")) $("s_twitter_bearer_token").value = token;
  setStatus("已保存");
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
    if (!el) return;
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
