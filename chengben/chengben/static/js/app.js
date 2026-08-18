const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function setStatus(t) { $("statusLine").textContent = t; }
function yuan(n) {
  const v = Number(n || 0);
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function wan(n) {
  const v = Number(n || 0) / 10000;
  const t = Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1);
  return t.replace(/\.0$/, "") + "万";
}
function pct(r) {
  return `${((Number(r) || 0) * 100).toFixed(1)}%`;
}

let workspace = { projects: [], active_id: "" };
let catalog = { templates: [], categories: [], log_kinds: [], corr_kinds: [], corr_statuses: [] };
let selectedId = "";
let saveTimer = 0;

async function api(path, opt = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opt,
    body: opt.body ? JSON.stringify(opt.body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

function active() {
  return workspace.projects.find((p) => p.id === workspace.active_id) || workspace.projects[0];
}

function persistInfo() {
  const p = active();
  if (!p) return;
  p.name = $("infoName").value.trim() || p.name;
  p.location = $("infoLoc").value.trim();
  p.manager = $("infoMgr").value.trim();
  p.cost_lead = $("infoCost").value.trim();
  p.specialty = $("infoSpec").value.trim();
  p.contract_amount = Number($("infoContract").value || 0);
  p.notes = $("infoNotes").value;
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => save().catch((e) => setStatus("保存失败：" + e.message)), 700);
}

async function save() {
  persistInfo();
  setStatus("正在保存…");
  workspace = await api("/api/workspace", { method: "PUT", body: workspace });
  render();
  setStatus("已保存");
}

function renderProjects() {
  $("projectList").innerHTML = workspace.projects.map((p) => {
    const s = p.stats || {};
    return `<div class="proj ${p.id === workspace.active_id ? "on" : ""}" data-id="${p.id}">
      ${esc(p.name)}<small>节超 ${wan(s.deviation)}　超支 ${s.over_count || 0} 项</small>
    </div>`;
  }).join("");
  $("projectList").querySelectorAll(".proj").forEach((el) => {
    el.onclick = () => { persistInfo(); workspace.active_id = el.dataset.id; selectedId = ""; render(); };
  });
}

function renderStats() {
  const p = active();
  if (!p) { $("stats").innerHTML = ""; return; }
  const s = p.stats || {};
  const d = Number(s.deviation || 0);
  const cards = [
    ["目标成本", wan(s.budget), ""],
    ["动态成本", wan(s.target), ""],
    ["已发生", wan(s.actual), ""],
    ["预计总成本", wan(s.forecast), ""],
    ["节超", wan(s.deviation), d > 0 ? "bad" : d < 0 ? "ok" : ""],
    ["节超率", pct(s.deviation_rate), d > 0 ? "bad" : ""],
    ["超支科目", s.over_count ?? 0, s.over_count ? "bad" : ""],
    ["纠偏未闭合", s.open_corr ?? 0, s.open_corr ? "warn" : ""],
  ];
  $("stats").innerHTML = cards.map(([k, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${k}</span></div>`).join("");
}

function renderInfo() {
  const p = active();
  if (!p) return;
  $("infoName").value = p.name || "";
  $("infoLoc").value = p.location || "";
  $("infoMgr").value = p.manager || "";
  $("infoCost").value = p.cost_lead || "";
  $("infoSpec").value = p.specialty || "";
  $("infoContract").value = p.contract_amount || 0;
  $("infoNotes").value = p.notes || "";
}

function itemOpts(selectId) {
  const p = active();
  const items = (p && p.items) || [];
  $(selectId).innerHTML = items.map((i) => `<option value="${i.id}">${esc(i.code)} ${esc(i.name)}</option>`).join("");
}

function filteredItems() {
  const p = active();
  let list = (p && p.items) || [];
  const cat = $("fCat").value;
  const flag = $("fFlag").value;
  if (cat) list = list.filter((i) => i.category === cat);
  if (flag) list = list.filter((i) => i.flag === flag);
  return list;
}

function renderItems() {
  const rows = filteredItems().map((i) => `<tr class="${esc(i.flag)} ${i.id === selectedId ? "on" : ""}" data-id="${i.id}">
    <td>${esc(i.code)}</td><td>${esc(i.name)}</td><td>${esc(i.category)}</td>
    <td class="num">${yuan(i.target)}</td><td class="num">${yuan(i.actual_amount)}</td>
    <td class="num">${yuan(i.remain_amount)}</td><td class="num">${yuan(i.forecast)}</td>
    <td class="num">${yuan(i.deviation)}</td><td>${pct(i.deviation_rate)}</td>
    <td><span class="st st-${esc(i.flag)}">${esc(i.flag)}</span></td>
  </tr>`).join("");
  $("itemTable").innerHTML = `<table>
    <thead><tr><th>编码</th><th>科目</th><th>类别</th><th>动态</th><th>已发生</th><th>待发生</th><th>预计</th><th>节超</th><th>率</th><th>状态</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="10" style="padding:12px">暂无科目，请用左侧模板生成。</td></tr>`}</tbody>
  </table>`;
  $("itemTable").querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.onclick = () => { selectedId = tr.dataset.id; renderItemDetail(); renderItems(); };
  });
}

function itemById(id) {
  return ((active() && active().items) || []).find((x) => x.id === id);
}

function renderItemDetail() {
  const box = $("itemDetail");
  const i = itemById(selectedId);
  if (!i) { box.style.display = "none"; box.innerHTML = ""; return; }
  box.style.display = "block";
  const cats = catalog.categories.map((s) => `<option ${s === i.category ? "selected" : ""}>${s}</option>`).join("");
  box.innerHTML = `<h2>${esc(i.code)}　${esc(i.name)}　<span class="st st-${esc(i.flag)}">${esc(i.flag)}</span></h2>
    <p class="muted">动态 ${yuan(i.target)}　预计 ${yuan(i.forecast)}　节超 ${yuan(i.deviation)}（${pct(i.deviation_rate)}）　量差 ${i.qty_diff || 0}　价差 ${i.price_diff || 0}</p>
    <div class="grid">
      <label>名称 <input data-k="name" value="${esc(i.name)}" /></label>
      <label>类别 <select data-k="category">${cats}</select></label>
      <label>单位 <input data-k="unit" value="${esc(i.unit || "")}" /></label>
      <label>责任人 <input data-k="owner" value="${esc(i.owner || "")}" /></label>
      <label>目标量 <input data-k="budget_qty" type="number" step="0.01" value="${esc(i.budget_qty || 0)}" /></label>
      <label>目标单价 <input data-k="budget_price" type="number" step="0.01" value="${esc(i.budget_price || 0)}" /></label>
      <label>目标金额 <input data-k="budget_amount" type="number" step="0.01" value="${esc(i.budget_amount || 0)}" /></label>
      <label>变更金额 <input data-k="change_amount" type="number" step="0.01" value="${esc(i.change_amount || 0)}" /></label>
      <label>已发生量 <input data-k="actual_qty" type="number" step="0.01" value="${esc(i.actual_qty || 0)}" /></label>
      <label>已发生金额 <input data-k="actual_amount" type="number" step="0.01" value="${esc(i.actual_amount || 0)}" /></label>
      <label>待发生 <input data-k="remain_amount" type="number" step="0.01" value="${esc(i.remain_amount || 0)}" /></label>
    </div>
    <label>备注 <textarea data-k="notes">${esc(i.notes || "")}</textarea></label>
    <button class="btn" id="btnCorrFromItem">按本科目开纠偏</button>`;
  box.querySelectorAll("[data-k]").forEach((el) => {
    el.addEventListener("change", () => {
      const k = el.dataset.k;
      i[k] = el.type === "number" ? Number(el.value || 0) : el.value;
      if (k === "budget_qty" || k === "budget_price") {
        if (Number(i.budget_qty) && Number(i.budget_price)) i.budget_amount = Math.round(Number(i.budget_qty) * Number(i.budget_price) * 100) / 100;
      }
      scheduleSave();
    });
  });
  $("btnCorrFromItem").onclick = () => {
    $("cItem").value = i.id;
    $("cAmt").value = Math.max(0, Number(i.deviation) || 0);
    $("cTitle").value = `${i.name}节超纠偏`;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === "corr"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "tab-corr"));
  };
}

function renderLogs() {
  const p = active();
  const items = (p && p.items) || [];
  $("logList").innerHTML = ((p && p.logs) || []).map((l) => {
    const it = items.find((x) => x.id === l.item_id);
    return `<div class="log-item"><h3>${esc(l.date)}　${esc(l.kind)}　${esc(it ? it.name : "")}　${yuan(l.amount)} 元</h3>
      <p class="muted">数量 ${esc(l.qty || "-")}　单据 ${esc(l.voucher || "-")}　${esc(l.notes || "")}</p></div>`;
  }).join("") || `<p class="muted">还没有发生记录。</p>`;
}

function renderCorr() {
  const p = active();
  const items = (p && p.items) || [];
  $("corrList").innerHTML = ((p && p.corrections) || []).map((c) => {
    const it = items.find((x) => x.id === c.item_id);
    return `<div class="fix-item">
      <h3>${esc(c.no)}　${esc(c.title)}　<span class="st st-${esc(c.status)}">${esc(c.status)}</span>${c.overdue ? "　超期" : ""}</h3>
      <p class="muted">${esc(it ? it.name : "")}　${esc(c.kind)}　${yuan(c.deviation_amount)} 元　责任人 ${esc(c.owner || "-")}　期限 ${esc(c.deadline || "")}</p>
      <p><strong>原因：</strong>${esc(c.cause || "")}</p>
      <p><strong>措施：</strong>${esc(c.action || "")}</p>
      <div class="toolbar">
        <button class="btn" data-id="${c.id}" data-st="落实中">落实中</button>
        <button class="btn" data-id="${c.id}" data-st="已验证">已验证</button>
        <button class="btn primary" data-id="${c.id}" data-st="已闭合">闭合</button>
      </div>
    </div>`;
  }).join("") || `<p class="muted">还没有纠偏。超支科目点开后可一键带入。</p>`;
  $("corrList").querySelectorAll("[data-st]").forEach((btn) => {
    btn.onclick = async () => {
      workspace = await api(`/api/projects/${active().id}/corrections/${btn.dataset.id}/status`, { method: "POST", body: { status: btn.dataset.st } });
      render();
      setStatus("纠偏状态：" + btn.dataset.st);
    };
  });
}

function renderChg() {
  const p = active();
  const items = (p && p.items) || [];
  $("chgList").innerHTML = ((p && p.changes) || []).map((z) => {
    const it = items.find((x) => x.id === z.item_id);
    return `<div class="log-item"><h3>${esc(z.no)}　${esc(z.title)}　${yuan(z.amount)} 元</h3>
      <p class="muted">${esc(z.date)}　科目 ${esc(it ? it.name : "")}　${z.approved ? "已纳入动态成本" : "未批准"}　${esc(z.notes || "")}</p></div>`;
  }).join("") || `<p class="muted">还没有签证变更。</p>`;
}

function render() {
  renderProjects();
  renderStats();
  renderInfo();
  renderItems();
  renderItemDetail();
  itemOpts("logItem");
  itemOpts("cItem");
  itemOpts("zItem");
  renderLogs();
  renderCorr();
  renderChg();
}

async function boot() {
  const today = new Date();
  const ymd = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  $("logDate").value = ymd;
  $("zDate").value = ymd;
  const d7 = new Date(today.getTime() + 7 * 86400000);
  $("cDead").value = `${d7.getFullYear()}-${String(d7.getMonth() + 1).padStart(2, "0")}-${String(d7.getDate()).padStart(2, "0")}`;
  const [ws, cat] = await Promise.all([api("/api/workspace"), api("/api/catalog")]);
  workspace = ws;
  catalog = cat;
  $("tplSelect").innerHTML = catalog.templates.map((t) => `<option value="${t.id}">${esc(t.name)}（${t.item_count} 项）</option>`).join("");
  $("fCat").innerHTML = `<option value="">全部</option>` + catalog.categories.map((s) => `<option>${s}</option>`).join("");
  $("logKind").innerHTML = catalog.log_kinds.map((s) => `<option>${s}</option>`).join("");
  $("cKind").innerHTML = catalog.corr_kinds.map((s) => `<option>${s}</option>`).join("");
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b === btn));
      document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "tab-" + btn.dataset.tab));
    };
  });
  ["fCat", "fFlag"].forEach((id) => $(id).addEventListener("change", renderItems));
  $("btnSave").onclick = () => save().catch((e) => setStatus(e.message));
  $("btnEmpty").onclick = async () => { workspace = await api("/api/projects/empty", { method: "POST", body: {} }); selectedId = ""; render(); };
  $("btnTpl").onclick = async () => {
    workspace = await api("/api/projects/from-template", {
      method: "POST",
      body: { template_id: $("tplSelect").value, name: $("tplName").value.trim(), location: $("tplLoc").value.trim(), manager: $("tplMgr").value.trim(), cost_lead: $("tplCost").value.trim() },
    });
    selectedId = "";
    render();
    setStatus("已按模板生成科目");
  };
  $("btnAddItem").onclick = async () => {
    workspace = await api(`/api/projects/${active().id}/items`, { method: "POST", body: { name: "新科目", category: "材料费", budget_amount: 0 } });
    render();
  };
  $("btnXlsx").onclick = () => { window.location.href = `/api/projects/${active().id}/export.xlsx`; };
  $("btnDel").onclick = async () => {
    if (!confirm("删除当前工程？")) return;
    workspace = await api(`/api/projects/${active().id}`, { method: "DELETE" });
    selectedId = "";
    render();
  };
  $("btnLog").onclick = async () => {
    workspace = await api(`/api/projects/${active().id}/logs`, {
      method: "POST",
      body: { date: $("logDate").value, item_id: $("logItem").value, kind: $("logKind").value, qty: Number($("logQty").value || 0), amount: Number($("logAmt").value || 0), voucher: $("logVou").value, notes: $("logNotes").value },
    });
    $("logAmt").value = ""; $("logQty").value = ""; $("logVou").value = ""; $("logNotes").value = "";
    render();
    setStatus("已计入发生");
  };
  $("btnCorr").onclick = async () => {
    workspace = await api(`/api/projects/${active().id}/corrections`, {
      method: "POST",
      body: { item_id: $("cItem").value, kind: $("cKind").value, deviation_amount: Number($("cAmt").value || 0), owner: $("cOwner").value, deadline: $("cDead").value, title: $("cTitle").value, cause: $("cCause").value, action: $("cAction").value },
    });
    $("cCause").value = ""; $("cAction").value = ""; $("cTitle").value = "";
    render();
    setStatus("纠偏已写入");
  };
  $("btnChg").onclick = async () => {
    workspace = await api(`/api/projects/${active().id}/changes`, {
      method: "POST",
      body: { date: $("zDate").value, item_id: $("zItem").value, amount: Number($("zAmt").value || 0), title: $("zTitle").value, notes: $("zNotes").value, approved: true },
    });
    $("zTitle").value = ""; $("zAmt").value = ""; $("zNotes").value = "";
    render();
    setStatus("变更已计入动态成本");
  };
  ["infoName", "infoLoc", "infoMgr", "infoCost", "infoSpec", "infoContract", "infoNotes"].forEach((id) => $(id).addEventListener("change", scheduleSave));
  render();
  setStatus("就绪 · 本机 127.0.0.1:8795");
}

boot().catch((e) => setStatus("启动失败：" + e.message));
