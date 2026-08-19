import { mount, apply, capturePng } from "/static/js/render.js";

const $ = (id) => document.getElementById(id);
let MODE = "exterior";
let LAST = null;
let CAT = null;

mount($("viewport"));

function body() {
  return {
    mode: MODE,
    name: $("name").value,
    building_type: $("building_type").value,
    floors: Number($("floors").value),
    floor_h: Number($("floor_h").value),
    length: Number($("length").value),
    width: Number($("width").value),
    facade: $("facade").value,
    interior_room: $("interior_room").value,
    interior_style: $("interior_style").value,
    time: $("time").value,
    lens_mm: Number($("lens_mm").value),
    camera_h: Number($("camera_h").value),
    output: $("output").value,
    quality: $("quality").value,
    two_point: $("two_point").checked,
    entourage: $("entourage").checked,
    bloom: $("bloom").checked,
    renderer: "V-Ray 6",
  };
}

function fillSelect(id, items, get = (x) => [x, x]) {
  const el = $(id);
  el.innerHTML = items.map((x) => {
    const [v, lab] = get(x);
    return `<option value="${v}">${lab}</option>`;
  }).join("");
}

function applyDefaults(modeId) {
  const d = CAT.defaults;
  // rebuild defaults client-side from mode
  const map = {
    interior: { lens: 35, cam: 1.6, time: "上午", bloom: false },
    exterior: { lens: 24, cam: 1.7, time: "上午", bloom: false },
    siteplan: { lens: 50, cam: 90, time: "上午", bloom: false },
    aerial: { lens: 24, cam: 80, time: "上午", bloom: false },
    night: { lens: 24, cam: 1.7, time: "夜晚", bloom: true },
  };
  const m = map[modeId] || map.exterior;
  $("lens_mm").value = String(m.lens);
  $("camera_h").value = m.cam;
  $("time").value = m.time;
  $("bloom").checked = m.bloom;
}

async function boot() {
  CAT = await (await fetch("/api/catalog")).json();
  $("modes").innerHTML = CAT.modes
    .map(
      (m) =>
        `<button class="mode${m.id === MODE ? " on" : ""}" data-id="${m.id}"><b>${m.name}</b><span>${m.desc}</span></button>`
    )
    .join("");
  $("modes").querySelectorAll(".mode").forEach((btn) => {
    btn.onclick = () => {
      MODE = btn.dataset.id;
      $("modes").querySelectorAll(".mode").forEach((x) => x.classList.toggle("on", x === btn));
      applyDefaults(MODE);
      generate();
    };
  });
  fillSelect("building_type", CAT.building_types);
  fillSelect("facade", CAT.facades);
  fillSelect("interior_room", CAT.interiors);
  fillSelect("interior_style", CAT.styles);
  fillSelect("time", CAT.times);
  fillSelect("quality", CAT.quality);
  fillSelect("output", CAT.outputs, (o) => [o.id, o.label]);
  $("building_type").value = "办公楼";
  $("facade").value = "玻璃幕墙";
  $("output").value = "1080p";
  $("quality").value = "成图 High";
  applyDefaults(MODE);
  $("building_type").onchange = () => {
    const t = $("building_type").value;
    const preset = {
      办公楼: [18, 3.6, 48, 24, "玻璃幕墙", "办公室"],
      住宅: [11, 2.9, 36, 15, "涂料", "客厅"],
      商业: [6, 4.5, 60, 32, "石材", "大堂"],
      酒店: [22, 3.3, 42, 22, "玻璃幕墙", "大堂"],
      学校: [6, 3.6, 72, 18, "涂料", "教室"],
      医院: [12, 3.6, 54, 28, "石材", "门厅"],
    }[t];
    if (preset) {
      $("floors").value = preset[0];
      $("floor_h").value = preset[1];
      $("length").value = preset[2];
      $("width").value = preset[3];
      $("facade").value = preset[4];
      $("interior_room").value = preset[5];
      $("name").value = `××${t}效果图`;
    }
  };
  await generate();
}

async function generate() {
  $("run").disabled = true;
  $("statusLine").textContent = "出图中…";
  try {
    const res = await fetch("/api/scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body()),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    LAST = data.scene;
    apply(LAST);
    $("sheet").textContent = LAST.max_sheet;
    $("camLabel").textContent = `${LAST.mode.name} · ${LAST.camera.name} · ${LAST.camera.lens_mm}mm`;
    $("sizeLabel").textContent = `${LAST.output.width}×${LAST.output.height} · ${LAST.sun.time} · ${LAST.quality}`;
    $("statusLine").textContent = "完成";
  } catch (e) {
    $("statusLine").textContent = "失败";
    alert("生成失败：" + e);
  } finally {
    $("run").disabled = false;
  }
}

$("run").onclick = generate;
$("shot").onclick = () => {
  if (!LAST) return generate().then(shot);
  shot();
};
function shot() {
  const w = LAST.output.width;
  const h = LAST.output.height;
  capturePng(w, h, `${LAST.name}_${LAST.mode.name}.png`);
}

boot();
