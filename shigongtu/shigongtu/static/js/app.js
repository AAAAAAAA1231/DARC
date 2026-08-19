const PRESET_FILL = {
  办公楼: { floors: 6, basement: 1, floor_area: 1200, floor_height: 3.6, span_x: 8.4, span_y: 8.4, structure: "框架" },
  住宅: { floors: 11, basement: 1, floor_area: 640, floor_height: 2.9, span_x: 4.2, span_y: 3.9, structure: "框剪" },
  商业: { floors: 4, basement: 1, floor_area: 1800, floor_height: 4.5, span_x: 8.4, span_y: 8.4, structure: "框架" },
  厂房: { floors: 1, basement: 0, floor_area: 3600, floor_height: 8.0, span_x: 12, span_y: 9, structure: "钢结构" },
  学校: { floors: 5, basement: 0, floor_area: 1600, floor_height: 3.6, span_x: 9, span_y: 8.4, structure: "框架" },
  医院: { floors: 8, basement: 1, floor_area: 2000, floor_height: 3.6, span_x: 8.1, span_y: 8.1, structure: "框剪" },
  酒店: { floors: 12, basement: 1, floor_area: 900, floor_height: 3.3, span_x: 8.0, span_y: 4.2, structure: "框剪" },
};

const $ = (id) => document.getElementById(id);
const statusLine = $("statusLine");
let LAST = null;
let FILTER = "全部";

$("building_type").addEventListener("change", () => {
  const t = $("building_type").value;
  const p = PRESET_FILL[t];
  if (!p) return;
  for (const [k, v] of Object.entries(p)) {
    if ($(k)) $(k).value = v;
  }
  $("name").value = `××${t}工程`;
});

function body() {
  const num = (id) => {
    const v = $(id).value;
    return v === "" ? 0 : Number(v);
  };
  return {
    name: $("name").value,
    location: $("location").value,
    client: $("client").value,
    designer: $("designer").value,
    building_type: $("building_type").value,
    floors: Number($("floors").value || 1),
    basement: Number($("basement").value || 0),
    floor_area: num("floor_area"),
    total_area: num("total_area"),
    floor_height: num("floor_height"),
    length: num("length"),
    width: num("width"),
    span_x: num("span_x"),
    span_y: num("span_y"),
    structure: $("structure").value,
    seismic: $("seismic").value,
    fire_rating: $("fire_rating").value,
    climate: $("climate").value,
    foundation: $("foundation").value,
    notes: $("notes").value,
  };
}

$("run").addEventListener("click", async () => {
  $("run").disabled = true;
  statusLine.textContent = "正在出图…";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body()),
    });
    if (!res.ok) throw new Error(await res.text());
    LAST = await res.json();
    render(LAST);
    statusLine.textContent = `已生成 ${LAST.count} 张`;
  } catch (err) {
    statusLine.textContent = "失败";
    alert("生成失败：" + err);
  } finally {
    $("run").disabled = false;
  }
});

function render(doc) {
  $("resultBox").style.display = "block";
  const s = doc.summary;
  $("summaryBox").innerHTML = `<div class="kpis">
    <div class="kpi"><b>${s.building_type}</b>性质</div>
    <div class="kpi"><b>${s.floors}F${s.basement ? "/-"+s.basement : ""}</b>层数</div>
    <div class="kpi"><b>${s.floor_area}㎡</b>单层</div>
    <div class="kpi"><b>${s.total_area}㎡</b>总面积</div>
    <div class="kpi"><b>${s.length}×${s.width}m</b>平面</div>
    <div class="kpi"><b>${s.height}m</b>高度</div>
    <div class="kpi"><b>${s.structure}</b>结构</div>
    <div class="kpi"><b>${doc.count}</b>图纸</div>
  </div>`;
  $("warnBox").innerHTML = (doc.warnings || []).map((w) => `<div class="warn">${w}</div>`).join("");
  const discs = ["全部", ...Array.from(new Set(doc.drawings.map((d) => d.discipline)))];
  $("tabs").innerHTML = discs.map((x) => `<button class="tab${x === FILTER ? " on" : ""}" data-d="${x}">${x}</button>`).join("");
  $("tabs").querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => {
      FILTER = btn.dataset.d;
      render(LAST);
    };
  });
  const items = doc.drawings.filter((d) => FILTER === "全部" || d.discipline === FILTER);
  $("list").innerHTML = items
    .map(
      (d, i) =>
        `<div class="item${i === 0 ? " on" : ""}" data-id="${d.id}"><span class="no">${d.number}</span>${d.name}</div>`
    )
    .join("");
  $("list").querySelectorAll(".item").forEach((el) => {
    el.onclick = () => {
      $("list").querySelectorAll(".item").forEach((x) => x.classList.remove("on"));
      el.classList.add("on");
      show(Number(el.dataset.id));
    };
  });
  if (items.length) show(items[0].id);
}

function show(id) {
  const svg = `/api/drawing/${id}/svg?t=${Date.now()}`;
  const dxf = `/api/drawing/${id}/dxf`;
  $("frame").src = svg;
  $("openSvg").href = svg;
  $("openDxf").href = dxf;
}

fetch("/api/health").then((r) => r.json()).then((h) => {
  if (h.ok) statusLine.textContent = "本机就绪";
}).catch(() => {
  statusLine.textContent = "服务未连接";
});
