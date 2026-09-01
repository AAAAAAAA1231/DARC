const views = {
  contracts: ["合约分析", "100 万次只用于校准指标权重。校准完成后，刷新信号会直接套用模型告诉你涨/跌/观望。"],
  meme: ["妖币监控", "只保留池子≥$20k、短期买压、持币在增加、且不像接盘的币。可跟才会进入自动跟单。"],
  copytrade: ["自动跟单", "跟随妖币「可跟」信号。缓存页只盯市；刷新才开新仓。带追踪止盈、冷却和仓位上限。"],
  ambassador: ["大使招募", "新 Web3 项目在 X / 招聘页上的大使计划，不是 OKX、币安校园大使。可标记申请与成功。"],
  launch: ["打新监测", "新项目白名单 / Presale / TGE / 新协议上线，不是交易所上新。"],
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
$("contractFilter").addEventListener("input", () => filterTable("contractRows", $("contractFilter").value));
$("memeFilter").addEventListener("input", () => filterTable("memeRows", $("memeFilter").value));
$("ambStatusFilter").addEventListener("change", () => loadView("ambassador"));
$("airdropStatusFilter").addEventListener("change", () => loadView("airdrop"));
$("autoParticipate").addEventListener("change", persistWalletFlags);
$("autoMaxSpend").addEventListener("change", persistWalletFlags);
if ($("copySave")) $("copySave").addEventListener("click", saveCopytrade);
if ($("ambAdd")) $("ambAdd").addEventListener("click", addAmbassador);

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
          $("contractRows").innerHTML = last.results.map(contractRow).join("");
        }
        if ($("simBadge")) $("simBadge").textContent = last.fitted_note;
        setStatus(last.fitted_note);
        pollAnalyze();
        return;
      }
      if (last.results && last.results.length) {
        last.results.forEach((r) => { store.contracts[r.symbol] = r; });
        $("contractRows").innerHTML = last.results.map(contractRow).join("");
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
        $("contractRows").innerHTML = uni.items.map((u) => {
          const row = {
            key: u.binance_symbol, symbol: u.binance_symbol, name: u.name, venue: u.venue,
            market_cap_rank: u.market_cap_rank, decision: "观望", score: 0,
            price: u.price, entry: u.price, stop_loss: "", take_profit: "", n_sims: 0, mode: "",
          };
          store.contracts[row.symbol] = row;
          return contractRow(row);
        }).join("");
      }
      if (last.fitted) {
        setStatus(`标的 ${uni.items.length} 个。权重已校准，正在套用模型出信号…`);
        if (!analyzeJob && uni.items.length) startAnalyze("infer");
      } else {
        setStatus(`标的 ${uni.items.length} 个。首次需要校准指标权重（100 万次，只需一次）…`);
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
      }).join("") || "<p class='muted'>暂无新项目大使。可填 Twitter Bearer 拉 X 动态，或手动添加。</p>";
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
      if ($("launchMsg")) $("launchMsg").textContent = data.note || "";
      setStatus(`新项目打新 ${data.count} 条` + (data.live_count ? ` · 实时 ${data.live_count}` : "") + (data.social_skipped ? " · 未配置 X Token" : ""));
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
  const tradable = !!r.tradable;
  const note = r.filter_note ? `<div class="muted">${escapeHtml(r.filter_note)}</div>` : "";
  const size = tradable && r.suggested_notional_pct ? `${Number(r.suggested_notional_pct).toFixed(1)}% 权益` : "-";
  const manage = tradable ? `${fmtPx(r.partial_tp)} / ${fmtPx(r.breakeven)}` : "-";
  return `<tr>
    <td><strong>${r.symbol}</strong><div class="muted">${r.name || ""} ${r.venue ? "· " + r.venue : ""}</div>${note}</td>
    <td>${r.market_cap_rank || "-"}</td>
    <td><span class="tag ${tagClass(r.decision)}">${r.decision || "观望"}</span>${tradable ? ' <span class="tag seed">可做</span>' : ""}</td>
    <td>${r.quality ?? "-"}</td>
    <td>${r.score ?? "-"}</td>
    <td>${fmtPx(r.price)}</td>
    <td>${fmtPx(r.entry)}</td>
    <td>${fmtPx(r.stop_loss)}</td>
    <td>${manage}</td>
    <td>${fmtPx(r.take_profit)}</td>
    <td>${size}</td>
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
      <h3>${r.symbol} 指标权重（${r.mode === "infer" ? "套用已拟合模型" : "本次校准"} · 校准 ${Number(r.n_sims||0).toLocaleString()} 次）</h3>
      <p class="muted">${escapeHtml(r.plan_note || r.filter_note || "")}</p>
      <p class="muted">原始结论 ${escapeHtml(r.raw_decision || r.decision || "观望")} · 趋势一致度 ${r.agreement ?? "-"} · ATR% ${(r.atr_pct!=null ? (Number(r.atr_pct)*100).toFixed(2)+"%" : "-")} · 止损 ${r.sl_mult ?? "-"} ATR</p>
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
  setStatus(kind === "fit" ? "开始校准指标权重（100 万次，只需偶尔做）…" : "套用已拟合模型出信号…");
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
    if (rows.length) $("contractRows").innerHTML = rows.map(contractRow).join("");
    const note = (data.results || []).find((r) => r.sim_note);
    if (note && $("simBadge")) $("simBadge").textContent = note.sim_note;
    const phase = data.phase ? " · " + data.phase : "";
    const kindLabel = data.kind === "fit" ? "校准权重" : "套用模型";
    const book = data.tradable_count != null ? ` · 可做 ${data.tradable_count}` : "";
    setStatus(`${kindLabel} ${data.done}/${data.total} · ${data.status}${phase}${book}` + (data.status === "done" ? " · 完成" : ""));
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
  return `<article class="card">
    <h3>${sourceBadge(a)} ${escapeHtml(a.name)}</h3>
    <p>${escapeHtml(a.kind)} · ${escapeHtml(a.chain || "")} · ${escapeHtml(a.source || "")}</p>
    <p>${escapeHtml((a.text || "").slice(0, 200))}</p>
    <p>${a.price_usd != null ? "价格 " + fmtUsd(a.price_usd) : ""}</p>
    <p>标记：${markSelect("launch", a.key, a.mark_status)}</p>
    <div class="card-actions">
      ${a.twitter ? `<a class="btn" href="${escapeHtml(a.twitter)}" target="_blank">X</a>` : ""}
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

async function loadSettingsForm() {
  settingsCache = await api("/api/settings");
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","risk_per_trade_pct","max_contract_positions","meme_min_liquidity_usd","airdrop_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
    const el = $("s_" + k);
    if (el) el.value = settingsCache[k] ?? "";
  });
}

async function saveSettings() {
  const settings = {};
  ["monte_carlo_sims","signal_threshold","atr_sl_mult","atr_tp_mult","risk_per_trade_pct","max_contract_positions","meme_min_liquidity_usd","airdrop_min_funding_usd","twitter_bearer_token","okx_api_key","okx_api_secret","okx_passphrase"].forEach((k) => {
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
