const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function setStatus(t) { $("statusLine").textContent = t; }

let workspace = { projects: [], active_id: "" };
let templates = [];
let selectedTaskId = "";
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
  p.specialty = $("infoSpec").value.trim();
  p.contract_start = $("infoStart").value;
  p.contract_end = $("infoEnd").value;
  p.notes = $("infoNotes").value;
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => save().catch((e) => setStatus("保存失败：" + e.message)), 600);
}

async function save() {
  persistInfo();
  setStatus("正在保存…");
  workspace = await api("api/workspace", { method: "PUT", body: workspace });
  render();
  setStatus("已保存");
}

function renderProjects() {
  $("projectList").innerHTML = workspace.projects.map((p) => {
    const st = p.stats || {};
    return `<div class="proj ${p.id === workspace.active_id ? "on" : ""}" data-id="${p.id}">
      ${esc(p.name)}<small>进度 ${st.overall || 0}%　滞后 ${st.delayed_count || 0}</small>
    </div>`;
  }).join("");
  $("projectList").querySelectorAll(".proj").forEach((el) => {
    el.onclick = () => {
      persistInfo();
      workspace.active_id = el.dataset.id;
      render();
    };
  });
}

function renderStats() {
  const p = active();
  if (!p) { $("stats").innerHTML = ""; return; }
  const s = p.stats || {};
  const cards = [
    ["总进度", `${s.overall || 0}%`, ""],
    ["计划应完", `${s.planned_overall || 0}%`, ""],
    ["SPI", s.spi ?? "-", s.spi && s.spi < 0.95 ? "warn" : ""],
    ["滞后工作", s.delayed_count ?? 0, s.delayed_count ? "warn" : ""],
    ["关键工作", s.critical_count ?? 0, ""],
    ["剩余日历天", s.remaining_days ?? "-", ""],
  ];
  $("stats").innerHTML = cards.map(([k, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${k}</span></div>`).join("");
}

function renderInfo() {
  const p = active();
  if (!p) return;
  $("infoName").value = p.name || "";
  $("infoLoc").value = p.location || "";
  $("infoMgr").value = p.manager || "";
  $("infoSpec").value = p.specialty || "";
  $("infoStart").value = (p.contract_start || "").slice(0, 10);
  $("infoEnd").value = (p.contract_end || "").slice(0, 10);
  $("infoNotes").value = p.notes || "";
}

function statusChip(st) {
  const map = { 已完成: "ok", 延期完成: "ok", 进行中: "run", 滞后: "lag", 未开始: "wait" };
  return `<span class="st st-${map[st] || "wait"}">${esc(st || "")}</span>`;
}

function parseDate(s) {
  if (!s) return null;
  const d = new Date(s.slice(0, 10) + "T00:00:00");
  return Number.isNaN(d.getTime()) ? null : d;
}

function ganttRange(tasks) {
  const dates = [];
  tasks.forEach((t) => {
    const a = parseDate(t.planned_start);
    const b = parseDate(t.planned_end);
    if (a) dates.push(a);
    if (b) dates.push(b);
  });
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (!dates.length) return { start: today, end: new Date(today.getTime() + 30 * 86400000), today };
  let start = new Date(Math.min(...dates));
  let end = new Date(Math.max(...dates));
  start = new Date(start.getTime() - 2 * 86400000);
  end = new Date(end.getTime() + 2 * 86400000);
  return { start, end, today };
}

function daysBetween(a, b) {
  return Math.round((b - a) / 86400000);
}
function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderGrid() {
  const p = active();
  const pane = $("gridPane");
  if (!p) { pane.innerHTML = ""; return; }
  const tasks = p.tasks || [];
  const rows = tasks.map((t) => {
    const cls = [t.summary ? "summary" : "", t.critical && !t.summary ? "critical" : "", t.status === "滞后" ? "lag" : "", t.id === selectedTaskId ? "on" : ""].join(" ");
    return `<tr class="${cls}" data-id="${t.id}">
      <td><input data-k="wbs" value="${esc(t.wbs)}" /></td>
      <td><input data-k="name" value="${esc(t.name)}" /></td>
      <td><input data-k="owner" value="${esc(t.owner || "")}" /></td>
      <td><input data-k="planned_start" type="date" value="${esc((t.planned_start || "").slice(0,10))}" /></td>
      <td><input data-k="planned_end" type="date" value="${esc((t.planned_end || "").slice(0,10))}" /></td>
      <td><input data-k="duration" type="number" min="1" value="${esc(t.duration || 1)}" /></td>
      <td><input data-k="progress" type="number" min="0" max="100" value="${esc(t.progress || 0)}" /></td>
      <td>${statusChip(t.status)}</td>
    </tr>`;
  }).join("");
  pane.innerHTML = `<table class="tasks">
    <thead><tr><th>WBS</th><th>工作名称</th><th>责任人</th><th>计划开始</th><th>计划完成</th><th>工期</th><th>%</th><th>状态</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="8" style="padding:12px">暂无工作，请新增或从左侧模板生成。</td></tr>`}</tbody>
  </table>`;
  pane.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => { selectedTaskId = tr.dataset.id; });
    tr.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("change", () => {
        const task = tasks.find((x) => x.id === tr.dataset.id);
        if (!task) return;
        const k = inp.dataset.k;
        task[k] = inp.type === "number" ? Number(inp.value) : inp.value;
        if (k === "planned_start" || k === "planned_end") {
          const a = parseDate(task.planned_start);
          const b = parseDate(task.planned_end);
          if (a && b && b >= a) task.duration = daysBetween(a, b) + 1;
        }
        if (k === "duration") {
          const a = parseDate(task.planned_start);
          if (a && task.duration > 0) {
            const end = new Date(a.getTime() + (task.duration - 1) * 86400000);
            task.planned_end = ymd(end);
          }
        }
        scheduleSave();
      });
    });
  });
}

function renderGantt() {
  const p = active();
  const pane = $("ganttPane");
  if (!p) { pane.innerHTML = ""; return; }
  const tasks = p.tasks || [];
  const { start, end, today } = ganttRange(tasks);
  const span = Math.max(daysBetween(start, end) + 1, 1);
  const colW = span > 240 ? 4 : span > 120 ? 7 : 14;
  const rowH = 32;
  const headH = 46;
  const width = span * colW + 8;
  const height = headH + tasks.length * rowH;
  const months = [];
  let cur = new Date(start);
  while (cur <= end) {
    const m0 = new Date(cur.getFullYear(), cur.getMonth(), 1);
    const m1 = new Date(cur.getFullYear(), cur.getMonth() + 1, 0);
    const a = cur < start ? start : cur;
    const b = m1 > end ? end : m1;
    months.push({ label: `${a.getFullYear()}-${String(a.getMonth() + 1).padStart(2, "0")}`, x: daysBetween(start, a) * colW, w: (daysBetween(a, b) + 1) * colW });
    cur = new Date(m1.getTime() + 86400000);
  }
  const monthRects = months.map((m) => `<rect x="${m.x}" y="0" width="${m.w}" height="${headH}" fill="#12365f" stroke="#2b5080"/><text x="${m.x + 6}" y="18" fill="#fff" font-size="11">${m.label}</text>`).join("");
  const ticks = [];
  if (colW >= 10) {
    for (let i = 0; i < span; i += 7) {
      const d = new Date(start.getTime() + i * 86400000);
      ticks.push(`<text x="${i * colW + 2}" y="38" fill="#dbe7f6" font-size="9">${d.getMonth() + 1}/${d.getDate()}</text>`);
    }
  }
  const bars = tasks.map((t, i) => {
    const a = parseDate(t.planned_start);
    const b = parseDate(t.planned_end);
    if (!a || !b) return "";
    const x = daysBetween(start, a) * colW;
    const w = Math.max((daysBetween(a, b) + 1) * colW - 2, 3);
    const y = headH + i * rowH + 8;
    const prog = Math.max(0, Math.min(100, Number(t.progress) || 0));
    let color = "#93c5fd";
    if (t.status === "已完成" || t.status === "延期完成") color = "#15803d";
    else if (t.status === "滞后") color = "#ea580c";
    else if (t.status === "进行中") color = "#3b82f6";
    const pw = Math.max(w * prog / 100, prog ? 2 : 0);
    return `<rect x="${x}" y="${y}" width="${w}" height="16" rx="3" fill="${color}" opacity="0.35"/>
      <rect x="${x}" y="${y}" width="${pw}" height="16" rx="3" fill="${color}"/>
      <text x="${x + 4}" y="${y + 12}" font-size="10" fill="#0f172a">${prog}%</text>`;
  }).join("");
  const tx = daysBetween(start, today) * colW;
  const todayLine = (tx >= 0 && tx <= width)
    ? `<line x1="${tx}" y1="${headH}" x2="${tx}" y2="${height}" stroke="#dc2626" stroke-width="2"/><text x="${tx + 4}" y="${headH + 12}" fill="#dc2626" font-size="10">今日</text>`
    : "";
  const weekBg = [];
  for (let i = 0; i < span; i++) {
    const d = new Date(start.getTime() + i * 86400000);
    if (d.getDay() === 0 || d.getDay() === 6) {
      weekBg.push(`<rect x="${i * colW}" y="${headH}" width="${colW}" height="${height - headH}" fill="#f1f5f9"/>`);
    }
  }
  const rowLines = tasks.map((_, i) => `<line x1="0" y1="${headH + (i + 1) * rowH}" x2="${width}" y2="${headH + (i + 1) * rowH}" stroke="#e2e8f0"/>`).join("");
  pane.innerHTML = `<svg class="gantt-svg" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">${monthRects}${ticks.join("")}${weekBg.join("")}${rowLines}${bars}${todayLine}</svg>`;
  $("scaleHint").textContent = `${ymd(start)} ～ ${ymd(end)}　${span} 日历天`;
  syncScroll();
}

function syncScroll() {
  const a = $("gridPane");
  const b = $("ganttPane");
  a.onscroll = () => { if (Math.abs(b.scrollTop - a.scrollTop) > 1) b.scrollTop = a.scrollTop; };
  b.onscroll = () => { if (Math.abs(a.scrollTop - b.scrollTop) > 1) a.scrollTop = b.scrollTop; };
}

function renderLogs() {
  const p = active();
  if (!p) return;
  $("logAuthor").value = $("logAuthor").value || p.manager || "";
  $("logList").innerHTML = (p.logs || []).map((l) => `<div class="log-item">
    <h3>${esc(l.date)}　${esc(l.weather)}　${esc(l.temperature || "")}　人数 ${esc(l.manpower || "-")}　${esc(l.author || "")}</h3>
    <p><strong>完成：</strong>${esc(l.work)}</p>
    <p><strong>问题：</strong>${esc(l.issues || "无")}</p>
    <p><strong>明日：</strong>${esc(l.tomorrow || "")}</p>
  </div>`).join("") || `<p class="muted">还没有日志。每天收工填一笔即可。</p>`;
}

function render() {
  renderProjects();
  renderStats();
  renderInfo();
  renderGrid();
  renderGantt();
  renderLogs();
}

async function boot() {
  const today = new Date().toISOString().slice(0, 10);
  $("logDate").value = today;
  $("tplStart").value = today;
  const [ws, tpl] = await Promise.all([api("api/workspace"), api("api/templates")]);
  workspace = ws;
  templates = tpl.templates || [];
  $("tplSelect").innerHTML = templates.map((t) => `<option value="${t.id}">${esc(t.name)}（${t.task_count} 项）</option>`).join("");
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b === btn));
      document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "tab-" + btn.dataset.tab));
    };
  });
  $("btnSave").onclick = () => save().catch((e) => setStatus(e.message));
  $("btnEmpty").onclick = async () => {
    workspace = await api("api/projects/empty", { method: "POST", body: {} });
    render();
  };
  $("btnTpl").onclick = async () => {
    workspace = await api("api/projects/from-template", {
      method: "POST",
      body: {
        template_id: $("tplSelect").value,
        name: $("tplName").value.trim(),
        location: $("tplLoc").value.trim(),
        manager: $("tplMgr").value.trim(),
        contract_start: $("tplStart").value,
      },
    });
    render();
    setStatus("已按模板生成计划");
  };
  $("btnAdd").onclick = async () => {
    const p = active();
    workspace = await api(`api/projects/${p.id}/tasks`, { method: "POST", body: { name: "新工作", duration: 7 } });
    render();
  };
  $("btnCascade").onclick = async () => {
    if (!confirm("将按完成-开始（FS）关系和合同开工日期重排计划开始/完成时间。已填的实际进度不会丢。继续？")) return;
    const p = active();
    workspace = await api(`api/projects/${p.id}/reschedule`, { method: "POST", body: {} });
    render();
    setStatus("已按 FS 重排");
  };
  $("btnXlsx").onclick = () => { window.location.href = `api/projects/${active().id}/export.xlsx`; };
  $("btnPng").onclick = () => { window.location.href = `api/projects/${active().id}/export.png`; };
  $("btnDel").onclick = async () => {
    if (!confirm("删除当前工程？不可恢复。")) return;
    workspace = await api(`api/projects/${active().id}`, { method: "DELETE" });
    render();
  };
  $("btnLog").onclick = async () => {
    const p = active();
    workspace = await api(`api/projects/${p.id}/logs`, {
      method: "POST",
      body: {
        date: $("logDate").value,
        weather: $("logWeather").value,
        temperature: $("logTemp").value,
        manpower: $("logMan").value,
        author: $("logAuthor").value,
        work: $("logWork").value,
        issues: $("logIssues").value,
        tomorrow: $("logTomorrow").value,
      },
    });
    $("logWork").value = "";
    $("logIssues").value = "";
    $("logTomorrow").value = "";
    render();
    setStatus("日志已写入");
  };
  ["infoName", "infoLoc", "infoMgr", "infoSpec", "infoStart", "infoEnd", "infoNotes"].forEach((id) => {
    $(id).addEventListener("change", scheduleSave);
  });
  render();
  setStatus("就绪 · 本机 127.0.0.1:8793");
}

boot().catch((e) => setStatus("启动失败：" + e.message));
