const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function setStatus(t) { $("statusLine").textContent = t; }

let workspace = { projects: [], active_id: "" };
let catalog = { defects: [], specialties: [], statuses: [], inspect_types: [] };
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
  p.qc_lead = $("infoQc").value.trim();
  p.supervisor = $("infoSup").value.trim();
  p.specialty = $("infoSpec").value.trim();
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
      ${esc(p.name)}<small>未闭合 ${s.open_count || 0}　超期 ${s.overdue_count || 0}</small>
    </div>`;
  }).join("");
  $("projectList").querySelectorAll(".proj").forEach((el) => {
    el.onclick = () => {
      persistInfo();
      workspace.active_id = el.dataset.id;
      selectedId = "";
      render();
    };
  });
}

function renderStats() {
  const p = active();
  if (!p) { $("stats").innerHTML = ""; return; }
  const s = p.stats || {};
  const cards = [
    ["未闭合", s.open_count ?? 0, s.open_count ? "" : ""],
    ["超期", s.overdue_count ?? 0, s.overdue_count ? "warn" : ""],
    ["重大未闭合", s.major_open ?? 0, s.major_open ? "bad" : ""],
    ["本周新增", s.new_week ?? 0, ""],
    ["本周闭合", s.closed_week ?? 0, ""],
    ["闭合率", `${s.close_rate ?? 0}%`, ""],
  ];
  $("stats").innerHTML = cards.map(([k, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${k}</span></div>`).join("");
}

function renderInfo() {
  const p = active();
  if (!p) return;
  $("infoName").value = p.name || "";
  $("infoLoc").value = p.location || "";
  $("infoMgr").value = p.manager || "";
  $("infoQc").value = p.qc_lead || "";
  $("infoSup").value = p.supervisor || "";
  $("infoSpec").value = p.specialty || "";
  $("infoNotes").value = p.notes || "";
}

function filteredIssues() {
  const p = active();
  let list = (p && p.issues) || [];
  const st = $("fStatus").value;
  const sp = $("fSpec").value;
  const ov = $("fOverdue").checked;
  if (st) list = list.filter((i) => i.status === st);
  if (sp) list = list.filter((i) => i.specialty === sp);
  if (ov) list = list.filter((i) => i.overdue);
  return list;
}

function renderIssueTable() {
  const rows = filteredIssues().map((i) => {
    const cls = [
      i.id === selectedId ? "on" : "",
      i.status === "已闭合" ? "done" : "open",
      i.overdue ? "lag" : "",
      i.severity === "重大" && !i.closed ? "major" : "",
    ].join(" ");
    return `<tr class="${cls}" data-id="${i.id}">
      <td>${esc(i.no)}</td>
      <td>${esc(i.title)}</td>
      <td>${esc(i.location)}</td>
      <td>${esc(i.specialty)}</td>
      <td>${esc(i.severity)}</td>
      <td>${esc(i.owner)}</td>
      <td>${esc(i.deadline)}</td>
      <td><span class="st st-${esc(i.status)}">${esc(i.status)}</span>${i.overdue ? " 超期" + i.overdue_days + "天" : ""}</td>
    </tr>`;
  }).join("");
  $("issueTable").innerHTML = `<table>
    <thead><tr><th>编号</th><th>问题</th><th>部位</th><th>专业</th><th>等级</th><th>责任人</th><th>期限</th><th>状态</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="8" style="padding:12px">暂无问题。用上方模板入账。</td></tr>`}</tbody>
  </table>`;
  $("issueTable").querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.onclick = () => { selectedId = tr.dataset.id; renderIssueDetail(); renderIssueTable(); };
  });
}

function loopHtml(step) {
  return ["发现", "整改", "复查", "闭合"].map((n, i) => `<span class="${i <= step ? "on" : ""}">${n}</span>`).join("");
}

function issueById(id) {
  const p = active();
  return ((p && p.issues) || []).find((x) => x.id === id);
}

function renderIssueDetail() {
  const box = $("issueDetail");
  const i = issueById(selectedId);
  if (!i) { box.style.display = "none"; box.innerHTML = ""; return; }
  box.style.display = "block";
  const specs = catalog.specialties.map((s) => `<option ${s === i.specialty ? "selected" : ""}>${esc(s)}</option>`).join("");
  box.innerHTML = `
    <h2>${esc(i.no)}　${esc(i.title)}</h2>
    <div class="loop">${loopHtml(i.loop_step || 0)}</div>
    <div class="grid">
      <label>问题 <input data-k="title" value="${esc(i.title)}" /></label>
      <label>部位 <input data-k="location" value="${esc(i.location || "")}" /></label>
      <label>专业 <select data-k="specialty">${specs}</select></label>
      <label>等级 <select data-k="severity">${["一般","较大","重大"].map((s) => `<option ${s === i.severity ? "selected" : ""}>${s}</option>`).join("")}</select></label>
      <label>来源 <input data-k="source" value="${esc(i.source || "")}" /></label>
      <label>发现日期 <input data-k="found_date" type="date" value="${esc((i.found_date || "").slice(0,10))}" /></label>
      <label>整改期限 <input data-k="deadline" type="date" value="${esc((i.deadline || "").slice(0,10))}" /></label>
      <label>检查人 <input data-k="inspector" value="${esc(i.inspector || "")}" /></label>
      <label>责任人 <input data-k="owner" value="${esc(i.owner || "")}" /></label>
      <label>实测 <input data-k="actual" value="${esc(i.actual || "")}" /></label>
      <label>允许值 <input data-k="allowed" value="${esc(i.allowed || "")}" /></label>
      <label>偏差 <input data-k="deviation" value="${esc(i.deviation || "")}" /></label>
    </div>
    <label>问题描述 <textarea data-k="description">${esc(i.description || "")}</textarea></label>
    <label>规范/标准 <textarea data-k="standard">${esc(i.standard || "")}</textarea></label>
    <label>整改要求 <textarea data-k="rectify_plan">${esc(i.rectify_plan || "")}</textarea></label>
    <label>已完成整改情况 <textarea data-k="rectify_desc">${esc(i.rectify_desc || "")}</textarea></label>
    <div class="toolbar">
      <button class="btn" data-st="整改中">开始整改</button>
      <button class="btn" data-st="待复查">提交复查</button>
      <button class="btn primary" data-st="已闭合">复查闭合</button>
      <button class="btn danger" id="btnDelIssue">删除此条</button>
    </div>
  `;
  box.querySelectorAll("[data-k]").forEach((el) => {
    el.addEventListener("change", () => {
      i[el.dataset.k] = el.value;
      scheduleSave();
    });
  });
  box.querySelectorAll("[data-st]").forEach((btn) => {
    btn.onclick = async () => {
      const p = active();
      workspace = await api(`/api/projects/${p.id}/issues/${i.id}/status`, {
        method: "POST",
        body: {
          status: btn.dataset.st,
          rectify_plan: i.rectify_plan,
          rectify_desc: i.rectify_desc,
          reviewer: p.qc_lead || "",
        },
      });
      render();
      setStatus("状态已更新：" + btn.dataset.st);
    };
  });
  $("btnDelIssue").onclick = async () => {
    if (!confirm("删除这条问题？")) return;
    const p = active();
    selectedId = "";
    workspace = await api(`/api/projects/${p.id}/issues/${i.id}`, { method: "DELETE" });
    render();
  };
}

function renderFix() {
  const p = active();
  const list = (p && p.issues) || [];
  $("fixList").innerHTML = list.map((i) => `
    <div class="fix-item" data-id="${i.id}">
      <h3>${esc(i.no)}　${esc(i.title)}　<span class="st st-${esc(i.status)}">${esc(i.status)}</span></h3>
      <p class="muted">${esc(i.location)}　标准：${esc(i.standard || "（补规范号）")}　实测 ${esc(i.actual || "-")}　允许 ${esc(i.allowed || "-")}　偏差 ${esc(i.deviation || "-")}</p>
      <div class="grid">
        <label>人 <input data-k="cause_man" value="${esc(i.cause_man || "")}" /></label>
        <label>机 <input data-k="cause_machine" value="${esc(i.cause_machine || "")}" /></label>
        <label>料 <input data-k="cause_material" value="${esc(i.cause_material || "")}" /></label>
        <label>法 <input data-k="cause_method" value="${esc(i.cause_method || "")}" /></label>
        <label>环 <input data-k="cause_env" value="${esc(i.cause_env || "")}" /></label>
      </div>
      <label>纠正措施（当下改掉） <textarea data-k="corrective">${esc(i.corrective || "")}</textarea></label>
      <label>预防措施（下次不再发生） <textarea data-k="preventive">${esc(i.preventive || "")}</textarea></label>
    </div>
  `).join("") || `<p class="muted">还没有问题，先在台账入账。</p>`;
  $("fixList").querySelectorAll(".fix-item").forEach((box) => {
    const i = issueById(box.dataset.id);
    box.querySelectorAll("[data-k]").forEach((el) => {
      el.addEventListener("change", () => { i[el.dataset.k] = el.value; scheduleSave(); });
    });
  });
}

function renderInspect() {
  const p = active();
  $("insWho").value = $("insWho").value || (p && p.qc_lead) || "";
  $("insList").innerHTML = ((p && p.inspections) || []).map((l) => `
    <div class="log-item">
      <h3>${esc(l.date)}　${esc(l.kind)}　${esc(l.area)}　${esc(l.result)}　${esc(l.inspector)}</h3>
      <p><strong>发现：</strong>${esc(l.findings || "无")}</p>
      <p><strong>后续：</strong>${esc(l.follow_up || "")}</p>
    </div>
  `).join("") || `<p class="muted">还没有巡检记录。</p>`;
}

function render() {
  renderProjects();
  renderStats();
  renderInfo();
  renderIssueTable();
  renderIssueDetail();
  renderFix();
  renderInspect();
}

async function boot() {
  const today = new Date().toISOString().slice(0, 10);
  $("insDate").value = today;
  const d = new Date();
  d.setDate(d.getDate() + 7);
  $("newDead").value = d.toISOString().slice(0, 10);
  const [ws, cat] = await Promise.all([api("/api/workspace"), api("/api/catalog")]);
  workspace = ws;
  catalog = cat;
  $("defectId").innerHTML = `<option value="">（不选模板，手写问题）</option>` + catalog.defects.map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join("");
  $("fStatus").innerHTML = `<option value="">全部</option>` + catalog.statuses.map((s) => `<option>${s}</option>`).join("");
  $("fSpec").innerHTML = `<option value="">全部</option>` + catalog.specialties.map((s) => `<option>${s}</option>`).join("");
  $("insKind").innerHTML = catalog.inspect_types.map((s) => `<option>${s}</option>`).join("");
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b === btn));
      document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "tab-" + btn.dataset.tab));
    };
  });
  ["fStatus", "fSpec", "fOverdue"].forEach((id) => $(id).addEventListener("change", renderIssueTable));
  $("btnSave").onclick = () => save().catch((e) => setStatus(e.message));
  $("btnEmpty").onclick = async () => {
    workspace = await api("/api/projects/empty", { method: "POST", body: {} });
    selectedId = "";
    render();
  };
  $("btnAddIssue").onclick = async () => {
    const p = active();
    workspace = await api(`/api/projects/${p.id}/issues`, {
      method: "POST",
      body: {
        defect_id: $("defectId").value,
        title: $("defectId").selectedOptions[0] && $("defectId").value ? $("defectId").selectedOptions[0].text : "质量问题",
        location: $("newLoc").value,
        owner: $("newOwner").value,
        deadline: $("newDead").value,
        inspector: p.qc_lead || "",
      },
    });
    $("newLoc").value = "";
    selectedId = (active().issues || [])[0]?.id || "";
    render();
    setStatus("已入账");
  };
  $("btnXlsx").onclick = () => { window.location.href = `/api/projects/${active().id}/export.xlsx`; };
  $("btnDel").onclick = async () => {
    if (!confirm("删除当前工程？")) return;
    workspace = await api(`/api/projects/${active().id}`, { method: "DELETE" });
    selectedId = "";
    render();
  };
  $("btnIns").onclick = async () => {
    const p = active();
    workspace = await api(`/api/projects/${p.id}/inspections`, {
      method: "POST",
      body: {
        date: $("insDate").value,
        kind: $("insKind").value,
        area: $("insArea").value,
        inspector: $("insWho").value,
        result: $("insResult").value,
        findings: $("insFind").value,
        follow_up: $("insFollow").value,
      },
    });
    $("insFind").value = "";
    $("insFollow").value = "";
    $("insArea").value = "";
    render();
    setStatus("巡检已写入");
  };
  ["infoName", "infoLoc", "infoMgr", "infoQc", "infoSup", "infoSpec", "infoNotes"].forEach((id) => {
    $(id).addEventListener("change", scheduleSave);
  });
  render();
  setStatus("就绪 · 本机 127.0.0.1:8794");
}

boot().catch((e) => setStatus("启动失败：" + e.message));
