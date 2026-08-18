const $ = (id) => document.getElementById(id);
const status = (t) => { $("statusLine").textContent = t; };

async function api(url, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body instanceof FormData) {
    init.body = opts.body;
  } else if (opts.body) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || JSON.stringify(j);
    } catch (_) {
      msg = await res.text();
    }
    throw new Error(msg);
  }
  if (opts.blob) return res.blob();
  return res.json();
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.add("hidden"));
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $("tab-" + name).classList.remove("hidden");
}

document.querySelectorAll(".tabs button").forEach((b) => {
  b.addEventListener("click", () => showTab(b.dataset.tab));
});

function renderList(el, items, kind) {
  el.innerHTML = (items || []).map((b) => `
    <div class="item">
      <div><strong>${b.name}</strong><div class="muted">${b.filename}</div></div>
      <button class="btn danger" data-del="${kind}" data-id="${b.id}">移除</button>
    </div>`).join("") || `<div class="muted">还没有上传，至少需要 3 家。</div>`;
}

function renderFindings(tbody, rows) {
  tbody.innerHTML = (rows || []).map((f) => `
    <tr>
      <td>${f.bidder || (f.bidders || []).join(" / ") || ""}</td>
      <td>${f.category || ""}</td>
      <td class="sev-${f.severity || ""}">${f.severity || ""}</td>
      <td>${f.item_code || ""}</td>
      <td>${f.item_name || ""}</td>
      <td>${f.detail || ""}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="muted">暂无</td></tr>`;
}

function renderSimple(tbody, rows) {
  tbody.innerHTML = (rows || []).map((f) => `
    <tr>
      <td>${f.bidder || ""}</td>
      <td>${f.category || ""}</td>
      <td class="sev-${f.severity || ""}">${f.severity || ""}</td>
      <td>${f.detail || ""}</td>
    </tr>`).join("") || `<tr><td colspan="4" class="muted">暂无</td></tr>`;
}

async function refresh() {
  const s = await api("/api/session");
  const p = s.project || {};
  ["name", "floors", "area", "structure", "foundation", "seismic", "notes"].forEach((k) => {
    if ($(k)) $(k).value = p[k] ?? "";
  });
  if (s.settings) {
    $("similar_price_pct").value = s.settings.similar_price_pct ?? 0.5;
    $("text_similar_pct").value = s.settings.text_similar_pct ?? 86;
  }
  $("limitName").textContent = (s.economic && s.economic.limit && s.economic.limit.filename) || "尚未上传";
  renderList($("ecoList"), s.economic.bidders, "eco");
  renderList($("techList"), s.technical.bidders, "tech");
  const eco = (s.results || {}).economic;
  if (eco) {
    $("ecoSummary").textContent = `限价清单 ${eco.limit_items || 0} 项；` +
      (eco.parsed || []).map((x) => `${x.bidder} ${x.items} 项`).join("；");
    renderFindings($("ecoRows"), [].concat(eco.findings || [], eco.metadata || []));
  }
  const tech = (s.results || {}).technical;
  if (tech) {
    renderSimple($("techSingleRows"), tech.single);
    renderSimple($("techCrossRows"), [].concat(tech.cross || [], tech.metadata || []));
  }
}

$("saveProject").onclick = async () => {
  try {
    await api("/api/project", {
      method: "POST",
      body: {
        name: $("name").value,
        floors: $("floors").value,
        area: $("area").value,
        structure: $("structure").value,
        foundation: $("foundation").value,
        seismic: $("seismic").value,
        notes: $("notes").value,
        settings: {
          similar_price_pct: Number($("similar_price_pct").value || 0.5),
          text_similar_pct: Number($("text_similar_pct").value || 86),
        },
      },
    });
    status("概况已保存（仅本机）");
  } catch (e) { status(e.message); }
};

$("resetAll").onclick = async () => {
  if (!confirm("确定清空本机这次清标的上传和分析结果？")) return;
  await api("/api/reset", { method: "POST" });
  await refresh();
  status("已清空");
};

$("uploadLimit").onclick = async () => {
  const f = $("limitFile").files[0];
  if (!f) return status("请选择最高投标限价 Excel");
  const fd = new FormData();
  fd.append("file", f);
  try {
    await api("/api/economic/limit", { method: "POST", body: fd });
    await refresh();
    status("限价已上传");
  } catch (e) { status(e.message); }
};

$("uploadEco").onclick = async () => {
  const f = $("ecoFile").files[0];
  const name = $("ecoName").value.trim();
  if (!name || !f) return status("请填写投标人名称并选择 Excel");
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", f);
  try {
    await api("/api/economic/bidder", { method: "POST", body: fd });
    $("ecoName").value = "";
    $("ecoFile").value = "";
    await refresh();
    status("已加入一家经济标");
  } catch (e) { status(e.message); }
};

$("uploadTech").onclick = async () => {
  const f = $("techFile").files[0];
  const name = $("techName").value.trim();
  if (!name || !f) return status("请填写投标人名称并选择技术标文件");
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", f);
  try {
    await api("/api/technical/bidder", { method: "POST", body: fd });
    $("techName").value = "";
    $("techFile").value = "";
    await refresh();
    status("已加入一家技术标");
  } catch (e) { status(e.message); }
};

document.body.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-del]");
  if (!btn) return;
  const kind = btn.dataset.del;
  const id = btn.dataset.id;
  const url = kind === "eco" ? `/api/economic/bidder/${id}` : `/api/technical/bidder/${id}`;
  await fetch(url, { method: "DELETE" });
  await refresh();
});

$("runEco").onclick = async () => {
  status("正在清经济标…");
  try {
    const r = await api("/api/economic/analyze", { method: "POST" });
    await refresh();
    status(`经济标完成，问题 ${(r.findings || []).length + (r.metadata || []).length} 条`);
  } catch (e) { status(e.message); }
};

$("runTech").onclick = async () => {
  status("正在清技术标…");
  try {
    const r = await api("/api/technical/analyze", { method: "POST" });
    await refresh();
    status(`技术标完成，单份 ${(r.single || []).length} 条，横向 ${(r.cross || []).length} 条`);
  } catch (e) { status(e.message); }
};

$("makeReport").onclick = async () => {
  status("正在生成 Word 报告…");
  try {
    const r = await api("/api/report", { method: "POST" });
    $("reportMsg").textContent = "已生成 " + r.filename + "，点击下载。文件只保存在本机 data 目录。";
    status("报告已生成");
  } catch (e) { status(e.message); }
};

refresh().catch((e) => status(e.message));
