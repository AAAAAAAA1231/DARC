const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
let catalog = { specialties: [], structures: [], codes: [] };
let lastCodes = [];

function setStatus(t) { $("statusLine").textContent = t; }

async function api(path, opt) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opt,
    body: opt && opt.body ? JSON.stringify(opt.body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function selectedCodes() {
  return [...document.querySelectorAll("#codeBox input:checked")].map((el) => el.value);
}

function renderCodeChecks(specialty, structure, buildingType) {
  const tags = new Set(["all", specialty, structure, buildingType === "住宅" ? "住宅" : ""]);
  if (structure.includes("框") || structure.includes("剪") || structure.includes("混凝土")) tags.add("混凝土");
  const box = $("codeBox");
  box.innerHTML = catalog.codes.map((c) => {
    const hit = (c.tags || []).some((t) => tags.has(t));
    return `<label><input type="checkbox" value="${c.code}" ${hit ? "checked" : ""} /> ${c.code}　${c.name}　<span class="muted">${c.kind || ""}</span></label>`;
  }).join("");
}

function payload() {
  const include = selectedCodes();
  const all = catalog.codes.map((c) => c.code);
  const exclude = all.filter((c) => !include.includes(c));
  return {
    name: $("name").value.trim(),
    location: $("location").value.trim(),
    owner: $("owner").value.trim(),
    bidder: $("bidder").value.trim(),
    specialty: $("specialty").value,
    structure: $("structure").value,
    building_type: $("building_type").value,
    residential: $("building_type").value === "住宅",
    area: $("area").value.trim(),
    floors: $("floors").value.trim(),
    duration: $("duration").value.trim(),
    seismic: $("seismic").value.trim(),
    foundation: $("foundation").value.trim(),
    cost: $("cost").value.trim(),
    quality_goal: $("quality_goal").value.trim(),
    safety_goal: $("safety_goal").value.trim(),
    tender_text: $("tender_text").value,
    include_codes: include,
    exclude_codes: exclude,
  };
}

async function generate() {
  setStatus("正在按规范生成…");
  const data = await api("api/generate", { method: "POST", body: payload() });
  $("resultBox").style.display = "block";
  $("warnBox").innerHTML = (data.warnings || []).map((w) => `<p class="warn">${w}</p>`).join("");
  $("codeRows").innerHTML = (data.codes || []).map((c) => `<tr><td>${c.code}</td><td>${c.name}</td><td>${c.kind || ""}</td></tr>`).join("");
  $("preview").innerHTML = (data.chapters || []).map((ch) => {
    const secs = (ch.sections || []).map((s) => `<h4>${esc(s.heading)}</h4>${esc(s.body).split("\n").map((p) => `<p>${p}</p>`).join("")}`).join("");
    return `<h3>${esc(ch.title)}</h3>${secs}`;
  }).join("");
  setStatus(`已生成 ${data.toc.length} 章 · 引用规范 ${data.codes.length} 项`);
}

async function boot() {
  catalog = await api("api/catalog");
  $("specialty").innerHTML = catalog.specialties.map((s) => `<option>${s.name}</option>`).join("");
  $("structure").innerHTML = catalog.structures.map((s) => `<option>${s.name}</option>`).join("");
  $("structure").value = "框剪";
  renderCodeChecks($("specialty").value, $("structure").value, $("building_type").value);
  ["specialty", "structure", "building_type"].forEach((id) => {
    $(id).addEventListener("change", () => renderCodeChecks($("specialty").value, $("structure").value, $("building_type").value));
  });
  $("specialty").addEventListener("change", () => {
    const sp = $("specialty").value;
    if (["市政道路", "市政给排水", "公路工程"].includes(sp)) {
      $("structure").value = "不适用（市政/公路）";
      $("building_type").value = "市政";
    } else if (sp === "钢结构厂房") {
      $("structure").value = "钢结构";
    }
    renderCodeChecks($("specialty").value, $("structure").value, $("building_type").value);
  });
  $("run").addEventListener("click", () => generate().catch((e) => setStatus("错误：" + e.message)));
  setStatus("就绪 · 本机 127.0.0.1:8792");
}

boot().catch((e) => setStatus("启动失败：" + e.message));
