const $ = (id) => document.getElementById(id);
const NAMES = { floor: "地砖", wall: "墙砖", ceiling: "吊顶", furniture: "家具" };
const SAMPLES = {
  floor: "客厅 4.8x6.2 层高2.8米，铺 800x800 抛光砖，正铺十字缝。",
  wall: "客厅 4.8x6.2 层高2.8米，墙砖 300x600，门洞套割，阴角收头。",
  ceiling: "客厅 4.8x6.2 层高2.8米，吊顶石膏板满吊。",
  furniture: "客厅 4.8x6.2 层高2.8米，家具布置。",
};
const SAMPLE_SET = new Set(Object.values(SAMPLES));

let TASK = "floor";
let CAT = null;
let seq = 0;

$("tasks").querySelectorAll(".mode").forEach((btn) => {
  btn.onclick = () => setMode(btn.dataset.t, true);
});

function setMode(task, refresh) {
  TASK = task;
  $("tasks").querySelectorAll(".mode").forEach((x) => x.classList.toggle("on", x.dataset.t === task));
  const cur = ($("text").value || "").trim();
  if (!cur || SAMPLE_SET.has(cur)) {
    $("text").value = SAMPLES[task];
  }
  if ($("modeHint")) {
    $("modeHint").textContent = `当前：${NAMES[task]}排版。点上方四个按钮立刻出图，不必再点「开始排版」。`;
  }
  if (refresh) run();
}

function body() {
  const n = (id) => {
    const v = $(id).value;
    return v === "" ? 0 : Number(v);
  };
  return {
    text: $("text").value,
    task: TASK,
    room_kind: $("room_kind").value,
    width: n("width"),
    depth: n("depth"),
    height: n("height"),
    floor_tile: $("floor_tile").value,
    wall_tile: $("wall_tile").value,
    ceiling: $("ceiling").value,
    pattern: $("pattern").value,
    project_type: $("project_type").value,
  };
}

function fill(id, items) {
  $(id).innerHTML = (items || []).map((t) => `<option value="${t.name}">${t.name}</option>`).join("");
}

function chkClass(c) {
  if (c.kind === "site") return "site";
  if (c.kind === "note") return "note";
  if (c.kind === "craft" && c.ok) return "note";
  return c.ok ? "ok" : "bad";
}

function chkLabel(c) {
  if (c.kind === "site") return "现场验收";
  if (c.kind === "note") return "说明";
  if (c.kind === "craft") return c.ok ? "工艺" : "工艺注意";
  return c.ok ? "符合" : "不符合";
}

function showError(msg) {
  $("statusLine").textContent = "失败";
  $("titleLine").textContent = `${NAMES[TASK] || TASK}排版失败`;
  $("preview").innerHTML = `<div class="errbox">排版失败：${String(msg || "未知错误")}</div>`;
}

function fileLabel() {
  const f = $("file").files[0];
  if ($("fileName")) $("fileName").textContent = f ? `已选图纸：${f.name}` : "未选择图纸，用左侧文字描述";
}

async function boot() {
  try {
    CAT = await (await fetch("/api/catalog")).json();
    fill("floor_tile", CAT.tile_floors);
    fill("wall_tile", CAT.tile_walls);
    fill("ceiling", CAT.ceilings);
  } catch (e) {
    showError("目录加载失败：" + e);
    return;
  }
  fileLabel();
  setMode("floor", false);
  ["floor_tile", "wall_tile", "ceiling", "pattern", "project_type", "room_kind"].forEach((id) => {
    const el = $(id);
    if (el) el.onchange = () => run();
  });
  await run();
}

async function parseRes(res) {
  const raw = await res.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error(raw.slice(0, 400) || `HTTP ${res.status}`);
  }
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || data.detail || raw.slice(0, 400) || `HTTP ${res.status}`);
  }
  return data;
}

async function run() {
  const mine = ++seq;
  const want = TASK;
  $("run").disabled = true;
  $("statusLine").textContent = `正在生成${NAMES[want]}…`;
  $("preview").innerHTML = `<p class="wait">正在生成${NAMES[want]}排版…</p>`;
  try {
    const f = $("file").files[0];
    const b = body();
    b.task = want;
    let data;
    if (f) {
      const fd = new FormData();
      fd.append("file", f);
      Object.entries(b).forEach(([k, v]) => fd.append(k, v));
      data = await parseRes(await fetch("/api/upload", { method: "POST", body: fd }));
    } else {
      data = await parseRes(
        await fetch("/api/layout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(b),
        })
      );
    }
    if (mine !== seq) return;
    if (data.task && data.task !== want) {
      throw new Error(`请求的是${NAMES[want]}，返回却是${NAMES[data.task] || data.task}`);
    }
    $("preview").innerHTML = data.svg || "<p class='wait'>没有图画出来</p>";
    $("titleLine").textContent = `${data.room.name} · ${NAMES[data.task] || data.task}`;
    $("srcLine").textContent = `${data.room.width}×${data.room.depth}×${data.room.height}m · ${data.project_type || ""} · 来源 ${data.room.source}`;
    $("checks").innerHTML = (data.checks || [])
      .map((c) => `<div class="chk ${chkClass(c)}">${chkLabel(c)} · ${c.code} · ${c.msg}</div>`)
      .join("");
    $("qty").innerHTML =
      "<tr><th>项目</th><th>数量</th><th>单位</th></tr>" +
      (data.qty || []).map((r) => `<tr><td>${r.name}</td><td>${r.qty}</td><td>${r.unit}</td></tr>`).join("");
    $("statusLine").textContent = data.pass ? `${NAMES[data.task]} · 强制性条文校核通过` : `${NAMES[data.task]} · 有强制性条文未满足`;
    if (!$("width").value) $("width").value = data.room.width;
    if (!$("depth").value) $("depth").value = data.room.depth;
    if (!$("height").value && data.room.height) $("height").value = data.room.height;
  } catch (e) {
    if (mine !== seq) return;
    showError(e.message || e);
  } finally {
    if (mine === seq) $("run").disabled = false;
  }
}

$("run").onclick = run;
$("file").onchange = () => {
  fileLabel();
  run();
};
if ($("clearFile")) {
  $("clearFile").onclick = () => {
    $("file").value = "";
    fileLabel();
    run();
  };
}
boot();
