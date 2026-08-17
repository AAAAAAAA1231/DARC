const views = {
  contracts: ["合约分析", "市值前 100 · TD13/谐波等 · 每标的 100 万次权重模拟。未拟合前不要把「观望」当成信号。"],
  meme: ["妖币监控", "只保留池子≥$20k、短期买压、持币在增加、且不像接盘的币。可跟才会进入自动跟单。"],
  copytrade: ["自动跟单", "跟随妖币「可跟」信号。默认模拟盘，带止盈止损和最大持仓限制。"],
  ambassador: ["大使招募", "Twitter / 镜像检索一周内大使计划，并支持申请与参与成功标记"],
  launch: ["打新监测", "关键词：打新、新平台、launch、presale、IDO 等"],
  airdrop: ["空投雷达", "知名机构投资、融资 > $2000 万、优先未发币，可标记交互状态"],
  wallet: ["钱包执行", "连接 OKX 等钱包，将空投 / 打新 / 妖币 / 合约加入确认队列"],
  settings: ["设置", "权重模拟次数、阈值、API Token 与自动参加上限"],
};

const $ = (id) => document.getElementById(id);
const store = { contracts: {}, meme: {}, ambassador: {}, launch: {}, airdrop: {} };
const fmtUsd = (n) => n == null || Number.isNaN(Number(n)) ? "-" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const fmtPx = (n) => n == null || n === "" ? "-" : Number(n).toPrecision(6);
const tagClass = (d) => d === "涨" ? "up" : d === "跌" ? "down" : "wait";

let currentView = "contracts";
let analyzeJob = null;
let settingsCache = {};

document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
$("refreshBtn").addEventListener("click", () => loadView(currentView, true));
$("analyzeAll").addEventListener("click", startAnalyze);
$("saveSettings").addEventListener("click", saveSettings);
$("disconnectWallet").addEventListener("click", async () => {
  await api("/api/wallet/disconnect", { method: "POST" });
  loadWallet();
});
$("contractFilter").addEventListener("input", () => filterTable("contractRows", $("contractFilter").value));
$("memeFilter").addEventListener("input", () => filterTable("memeRows", $("memeFilter").value));
$("ambStatusFilter").addEventListener("change", () => loadView("ambassador"));
$("airdropStatusFilter").addEventListener("change", () => loadView("airdrop"));
$("autoParticipate").addEventListener("change", persistWalletFlags);
$("autoMaxSpend").addEventListener("change", persistWalletFlags);
if ($("copySave")) $("copySave").addEventListener("click", saveCopytrade);

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
      if (last.fitted && last.results && last.results.length) {
        last.results.forEach((r) => { store.contracts[r.symbol] = r; });
        $("contractRows").innerHTML = last.results.map(contractRow).join("");
        if ($("simBadge")) $("simBadge").textContent = last.fitted_note;
        setStatus(last.fitted_note);
        return;
      }
      if ($("simBadge")) $("simBadge").textContent = last.fitted_note || "尚未拟合";
      const uni = await api("/api/contracts/universe");
      if (!$("contractRows").children.length) {
        $("contractRows").innerHTML = uni.items.map((u) => {
          const row = {
            key: u.binance_symbol, symbol: u.binance_symbol, name: u.name, venue: u.venue,
            market_cap_rank: u.market_cap_rank, decision: "观望", score: 0,
            price: u.price, entry: u.price, stop_loss: "", take_profit: "", n_sims: 0,
          };
          store.contracts[row.symbol] = row;
          return contractRow(row);
        }).join("");
      }
      setStatus(`标的 ${uni.items.length} 个。模型未拟合，正在启动 100 万次模拟…`);
      if (!analyzeJob && uni.items.length) startAnalyze();
    } else if (name === "meme") {
      setStatus("正在拉取妖币（可能需要十几秒）…");
      if ($("memeRows")) $("memeRows").innerHTML = emptyRow(9, "加载中…");
      const data = await api("/api/meme" + q);
      store.meme = {};
      $("memeRows").innerHTML = (data.items || []).map((m) => {
        store.meme[m.key] = m;
        return memeRow(m);
      }).join("") || emptyRow(10, "暂无过线妖币（需要池子≥20k且短期买压）");
      if ($("memeMsg")) $("memeMsg").textContent = (data.method || "") + ((data.errors || []).length ? "；部分源失败：" + data.errors.slice(0,2).join("；") : "");
      setStatus(`监控 ${data.count} · 可跟 ${data.followable_count || 0}`);
    } else if (name === "ambassador") {
      setStatus("正在加载大使计划…");
      $("ambassadorCards").innerHTML = "<p class='muted'>加载中…</p>";
      const data = await api("/api/ambassadors" + q);
      const want = $("ambStatusFilter").value;
      const items = (data.items || []).filter((x) => !want || (x.mark_status || "none") === want);
      store.ambassador = {};
      $("ambassadorCards").innerHTML = items.map((a) => {
        store.ambassador[a.key] = a;
        return ambassadorCard(a);
      }).join("") || "<p class='muted'>未检索到帖文。国内访问 Twitter 常失败，已尽量给出观察池。</p>";
      setStatus(`招募信息 ${items.length} 条` + ((data.note && " · " + data.note) || ""));
    } else if (name === "launch") {
      setStatus("正在监测打新…");
      $("launchCards").innerHTML = "<p class='muted'>加载中…</p>";
      const data = await api("/api/launches" + q);
      store.launch = {};
      $("launchCards").innerHTML = (data.items || []).map((a) => {
        store.launch[a.key] = a;
        return launchCard(a);
      }).join("") || "<p class='muted'>暂无打新信息</p>";
      setStatus(`打新 ${data.count} 条`);
    } else if (name === "airdrop") {
      setStatus("正在扫描高融资未发币项目…");
      $("airdropRows").innerHTML = emptyRow(8, "加载中…");
      const data = await api("/api/airdrops" + q);
      const want = $("airdropStatusFilter").value;
      const items = (data.items || []).filter((x) => !want || x.mark_status === want);
      store.airdrop = {};
      $("airdropRows").innerHTML = items.map((a) => {
        store.airdrop[a.key] = a;
        return airdropRow(a);
      }).join("") || emptyRow(8, "暂无命中项目");
      setStatus(`空投候选 ${items.length}` + ((data.errors && data.errors.length) ? " · 部分数据源失败已用观察池补齐" : ""));
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

function contractRow(r) {
  const id = encodeURIComponent(r.symbol);
  return `<tr>
    <td><strong>${r.symbol}</strong><div class="muted">${r.name || ""} ${r.venue ? "· " + r.venue : ""}</div></td>
    <td>${r.market_cap_rank || "-"}</td>
    <td><span class="tag ${tagClass(r.decision)}">${r.decision || "观望"}</span></td>
    <td>${r.score ?? "-"}</td>
    <td>${fmtPx(r.price)}</td>
    <td>${fmtPx(r.entry)}</td>
    <td>${fmtPx(r.stop_loss)}</td>
    <td>${fmtPx(r.take_profit)}</td>
    <td>${r.n_sims ? Number(r.n_sims).toLocaleString() : "未模拟"}</td>
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
      <h3>${r.symbol} 指标权重（初始份额 → ${Number(r.n_sims||0).toLocaleString()} 次模拟后）</h3>
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

async function startAnalyze() {
  const interval = $("klineInterval").value;
  setStatus("启动分析任务…");
  $("analyzeProgress").classList.remove("hidden");
  const job = await api("/api/contracts/analyze", { method: "POST", body: { interval } });
  analyzeJob = job.job_id;
  pollAnalyze();
}

async function pollAnalyze() {
  if (!analyzeJob) return;
  const data = await api("/api/contracts/analyze/" + analyzeJob);
  const pct = data.total ? (data.done / data.total) * 100 : 0;
  $("analyzeProgress").querySelector("div").style.width = pct + "%";
  (data.results || []).forEach((r) => { store.contracts[r.symbol] = r; });
  $("contractRows").innerHTML = (data.results || []).map(contractRow).join("");
  const doneSims = (data.results || []).find((r) => r.n_sims);
  if (doneSims && $("simBadge")) {
    $("simBadge").textContent = (doneSims.sim_note || `已完成 ${Number(doneSims.n_sims).toLocaleString()} 次模拟并修正权重`);
  }
  setStatus(`分析进度 ${data.done}/${data.total} · ${data.status}` + (data.status === "done" ? " · 权重已按模拟结果修正" : ""));
  if (data.status === "running") setTimeout(pollAnalyze, 1200);
}

function memeRow(m) {
  const id = encodeURIComponent(m.key);
  const g = m.grade || "观察";
  const cls = g === "可跟" ? "up" : g === "避开" ? "down" : "wait";
  return `<tr>
    <td><span class="tag ${cls}">${escapeHtml(g)}</span></td>
    <td>${escapeHtml(m.chain)}</td>
    <td><strong>${escapeHtml(m.symbol)}</strong><div class="muted">${escapeHtml((m.score_reasons||[]).slice(0,2).join(" · "))}</div></td>
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
    <h3>${escapeHtml(a.project || a.username || "项目")}</h3>
    <p>${escapeHtml((a.text || "").slice(0, 220))}</p>
    <p>优先级：<strong>${escapeHtml(a.priority)}</strong> · 期限：${escapeHtml(a.deadline)}</p>
    <p>状态：${markSelect("ambassador", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.url ? `<a class="btn" href="${escapeHtml(a.url)}" target="_blank">来源</a>` : ""}
      <button class="btn" onclick="mark('ambassador','${id}','applied')">标记已申请</button>
      <button class="btn primary" onclick="mark('ambassador','${id}','accepted')">标记已成功</button>
    </div>
  </article>`;
}

function launchCard(a) {
  const id = encodeURIComponent(a.key);
  return `<article class="card">
    <h3>${escapeHtml(a.name)}</h3>
    <p>${escapeHtml(a.kind)} · ${escapeHtml(a.chain || "")}</p>
    <p>${escapeHtml((a.text || "").slice(0, 200))}</p>
    <p>${a.price_usd != null ? "价格 " + fmtUsd(a.price_usd) : ""}</p>
    <p>标记：${markSelect("launch", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.url ? `<a class="btn" href="${escapeHtml(a.url)}" target="_blank">打开</a>` : ""}
      <button class="btn" onclick="participate('launch','${id}')">加入打新队列</button>
    </div>
  </article>`;
}

function airdropRow(a) {
  const id = encodeURIComponent(a.key);
  return `<tr>
    <td><strong>${escapeHtml(a.name)}</strong><div class="muted">${escapeHtml((a.chains||[]).slice(0,3).join(", "))}</div></td>
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
  </tr>`).join("") || emptyRow(8, "暂无持仓。打开妖币监控后会按「可跟」自动开模拟仓。");
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

async function loadSettingsForm() {
  settingsCache = await api("/api/settings");
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","meme_min_liquidity_usd","airdrop_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
    const el = $("s_" + k);
    if (el) el.value = settingsCache[k] ?? "";
  });
}

async function saveSettings() {
  const settings = {};
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","meme_min_liquidity_usd","airdrop_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
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
