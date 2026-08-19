const $ = (id) => document.getElementById(id);
let TASK = "floor";
let CAT = null;

$("tasks").querySelectorAll(".mode").forEach((btn) => {
  btn.onclick = () => {
    TASK = btn.dataset.t;
    $("tasks").querySelectorAll(".mode").forEach((x) => x.classList.toggle("on", x === btn));
  };
});

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
  };
}

function fill(id, items) {
  $(id).innerHTML = items.map((t) => `<option value="${t.name}">${t.name}</option>`).join("");
}

async function boot() {
  CAT = await (await fetch("/api/catalog")).json();
  fill("floor_tile", CAT.tile_floors);
  fill("wall_tile", CAT.tile_walls);
  fill("ceiling", CAT.ceilings);
  await run();
}

async function run() {
  $("run").disabled = true;
  $("statusLine").textContent = "排版中…";
  try {
    const f = $("file").files[0];
    let data;
    if (f) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("task", TASK);
      fd.append("text", $("text").value);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      data = await res.json();
    } else {
      const res = await fetch("/api/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body()),
      });
      if (!res.ok) throw new Error(await res.text());
      data = await res.json();
    }
    $("preview").innerHTML = data.svg;
    $("titleLine").textContent = `${data.room.name} · ${{floor:"地砖",wall:"墙砖",ceiling:"吊顶",furniture:"家具"}[data.task] || data.task}`;
    $("srcLine").textContent = `${data.room.width}×${data.room.depth}×${data.room.height}m · 来源 ${data.room.source}`;
    $("checks").innerHTML = (data.checks || [])
      .map((c) => `<div class="chk ${c.ok ? "ok" : "bad"}">${c.ok ? "符合" : "注意"} · ${c.code} · ${c.msg}</div>`)
      .join("");
    $("qty").innerHTML =
      "<tr><th>项目</th><th>数量</th><th>单位</th></tr>" +
      (data.qty || []).map((r) => `<tr><td>${r.name}</td><td>${r.qty}</td><td>${r.unit}</td></tr>`).join("");
    $("statusLine").textContent = data.pass ? "校核通过" : "有提示，请看规范校核";
    if (!$("width").value) $("width").value = data.room.width;
    if (!$("depth").value) $("depth").value = data.room.depth;
  } catch (e) {
    $("statusLine").textContent = "失败";
    alert("排版失败：" + e);
  } finally {
    $("run").disabled = false;
  }
}

$("run").onclick = run;
boot();
