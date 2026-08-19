const $ = (id) => document.getElementById(id);

async function loadCatalog() {
  const r = await fetch("/api/catalog");
  const data = await r.json();
  $("space_type").innerHTML = data.spaces
    .map((x) => `<option value="${x.id}">${x.id} · ${x.purpose}</option>`)
    .join("");
  $("space_type").value = "办公室";
}

function payload() {
  return {
    description: $("description").value,
    space_type: $("space_type").value,
    purpose: $("purpose").value,
    width_m: Number($("width_m").value || 0),
    depth_m: Number($("depth_m").value || 0),
    height_m: Number($("height_m").value || 0),
    doors: Number($("doors").value || 0),
  };
}

function render(data) {
  if (!data.ok) {
    $("kpis").innerHTML = `<div class="kpi"><b>失败</b><span>${data.error || "未知错误"}</span></div>`;
    $("preview").innerHTML = "";
    return;
  }
  $("kpis").innerHTML = [
    ["摄像机", data.n + " 台"],
    ["覆盖率", data.cover + "%"],
    ["目标", data.purpose],
    ["校核", data.pass ? "通过" : "未过"],
  ]
    .map(([k, v]) => `<div class="kpi"><b>${v}</b><span>${k}</span></div>`)
    .join("");
  const room = data.room;
  $("summary").innerHTML = `<span class="${data.pass ? "ok" : "bad"}">${data.pass ? "校核通过" : "仍有未过项"}</span> · ${room.space_type} ${room.width_m}×${room.depth_m} m · ${room.doors} 个门 · ${room.source}`;
  $("checks").innerHTML = (data.checks || [])
    .map(
      (c) =>
        `<tr><td>${c.name}</td><td class="${c.ok ? "ok" : "bad"}">${c.ok ? "通过" : "未过"}</td><td>${c.detail}</td></tr>`
    )
    .join("");
  $("cams").innerHTML = (data.cameras || [])
    .map((c) => {
      const cam = c.camera;
      return `<tr><td>${c.id}</td><td>${c.x}, ${c.y}</td><td>${c.height_m} m</td><td>${c.role}</td><td>${cam.name} · ${cam.mp}MP · ${cam.lens_mm}mm · ${cam.hfov}°</td></tr>`;
    })
    .join("");
  $("qty").innerHTML = (data.qty || [])
    .map((q) => `<li>${q.name} ×${q.qty} ${q.unit}</li>`)
    .join("");
  $("preview").innerHTML = data.svg || "";
}

async function run() {
  const file = $("file").files[0];
  let data;
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(payload()).forEach(([k, v]) => fd.append(k, String(v)));
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    data = await r.json();
  } else {
    const r = await fetch("/api/layout", {
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
