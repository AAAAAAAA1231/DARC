const $ = (id) => document.getElementById(id);

async function loadCatalog() {
  const r = await fetch("/api/catalog");
  const data = await r.json();
  const roomSel = $("room_type");
  const fixSel = $("fixture_id");
  roomSel.innerHTML = data.rooms
    .map((x) => `<option value="${x.id}">${x.id} · ${x.E}lx / UGR${x.UGR} / Ra${x.Ra}</option>`)
    .join("");
  roomSel.value = "普通办公室";
  fixSel.innerHTML =
    `<option value="">自动推荐</option>` +
    data.fixtures.map((x) => `<option value="${x.id}">${x.name} ${x.P}W ${x.Phi}lm</option>`).join("");
}

function payload() {
  return {
    description: $("description").value,
    room_type: $("room_type").value,
    fixture_id: $("fixture_id").value,
    width_m: Number($("width_m").value || 0),
    depth_m: Number($("depth_m").value || 0),
    height_m: Number($("height_m").value || 0),
    illuminance_lx: Number($("illuminance_lx").value || 0),
    mf: Number($("mf").value || 0.8),
    work_plane_m: Number($("work_plane_m").value || 0.75),
    cct: Number($("cct").value || 4000),
    ra_min: Number($("ra_min").value || 0),
  };
}

function render(data) {
  if (!data.ok) {
    $("kpis").innerHTML = `<div class="kpi"><b>失败</b><span>${data.error || "未知错误"}</span></div>`;
    $("preview").innerHTML = "";
    return;
  }
  $("kpis").innerHTML = [
    ["数量", data.n + " 盏"],
    ["平均照度", data.e_avg + " lx"],
    ["LPD", data.lpd + " W/m²"],
    ["功率", data.power_w + " W"],
  ]
    .map(([k, v]) => `<div class="kpi"><b>${v}</b><span>${k}</span></div>`)
    .join("");
  const f = data.fixture;
  $("fixture").innerHTML = `<b>${f.name}</b> · ${f.P}W · ${f.Phi}lm · Ra${f.Ra} · ${f.CCT}K · ${data.nx}×${data.ny} 布置 · 间距 ${data.spacing_m} m · 房间 ${data.room.width_m}×${data.room.depth_m} m（${data.room.source}）`;
  $("checks").innerHTML = data.checks
    .map(
      (c) =>
        `<tr><td>${c.name}</td><td class="${c.ok ? "ok" : "bad"}">${c.ok ? "通过" : "未过"}</td><td>${c.detail}</td></tr>`
    )
    .join("");
  $("alts").innerHTML = (data.alternatives || [])
    .map((a) => `<li>${a.name} ${a.P}W ${a.Phi}lm ×${a.n} · ${a.e_avg}lx · LPD ${a.lpd}</li>`)
    .join("");
  $("preview").innerHTML = data.svg || "";
}

async function run() {
  const file = $("file").files[0];
  let data;
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    const p = payload();
    Object.entries(p).forEach(([k, v]) => fd.append(k, String(v)));
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    data = await r.json();
  } else {
    const r = await fetch("/api/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    data = await r.json();
  }
  render(data);
}

function dl(kind) {
  window.location = `/api/download/${kind}`;
}

$("btn-run").addEventListener("click", run);
$("btn-svg").addEventListener("click", () => dl("svg"));
$("btn-dxf").addEventListener("click", () => dl("dxf"));
$("btn-zip").addEventListener("click", () => dl("zip"));

loadCatalog().catch((e) => {
  $("kpis").innerHTML = `<div class="kpi"><b>目录失败</b><span>${e}</span></div>`;
});
