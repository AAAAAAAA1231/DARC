const $ = (id) => document.getElementById(id);
const status = (t) => { $("statusLine").textContent = t; };
const yuan = (n) => Number(n || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });

const PRICE_FIELDS = [
  ["cpu_per_node", "每节点 CPU 颗数"],
  ["cpu_price", "CPU 单价"],
  ["cpu_tdp_w", "CPU TDP(W)"],
  ["ram_tb_per_node", "每节点内存 TB"],
  ["ram_price_per_tb", "内存 元/TB"],
  ["nvme_tb_per_node", "每节点 NVMe TB"],
  ["nvme_price_per_tb", "NVMe 元/TB"],
  ["nic_price", "高速网卡单价"],
  ["ib_switch_price", "交换机单价"],
  ["ib_ports_per_switch", "交换机口数"],
  ["cable_price", "线缆单价"],
  ["nodes_per_rack", "每柜节点数"],
  ["rack_price_liquid", "液冷机柜"],
  ["rack_price_air", "风冷机柜"],
  ["pdu_price", "PDU"],
  ["ups_cny_per_kva", "UPS 元/kVA"],
  ["cooling_liquid_cny_per_kw", "液冷 元/kW"],
  ["cooling_air_cny_per_kw", "风冷 元/kW"],
  ["fitout_cny_per_m2", "装修 元/㎡"],
  ["m2_per_rack", "每柜占地㎡"],
  ["pue_liquid", "液冷 PUE"],
  ["pue_air", "风冷 PUE"],
  ["electricity_cny_per_kwh", "电价 元/kWh"],
  ["hours_per_year", "年利用小时"],
  ["install_pct", "安装费 %"],
  ["software_pct", "软件费 %"],
  ["contingency_pct", "预备费 %"],
  ["vat_pct", "增值税 %"],
];

let catalog = { gpus: [], defaults: {} };

function fillPrices(d) {
  $("priceGrid").innerHTML = PRICE_FIELDS.map(([k, lab]) =>
    `<label>${lab} <input id="p_${k}" type="number" step="any" value="${d[k] ?? ""}" /></label>`
  ).join("");
}

function applyGpu() {
  const g = catalog.gpus.find((x) => x.id === $("gpu_id").value);
  if (!g) return;
  $("fp16_tflops").value = g.fp16_tflops;
  $("tdp_w").value = g.tdp_w;
  $("cards_per_node").value = g.cards_per_node;
  $("price_mode").value = g.price_mode;
  $("node_price").value = g.node_price;
  $("card_price").value = g.card_price;
}

function payload() {
  const prices = {};
  PRICE_FIELDS.forEach(([k]) => { prices[k] = Number($("p_" + k).value); });
  return {
    project: $("project").value,
    location: $("location").value,
    mode: $("mode").value,
    target_pflops: Number($("target_pflops").value),
    gpu_count: Number($("gpu_count").value),
    gpu_id: $("gpu_id").value,
    cooling: $("cooling").value,
    include_cpu_ram: $("include_cpu_ram").checked,
    gpu: {
      fp16_tflops: Number($("fp16_tflops").value),
      tdp_w: Number($("tdp_w").value),
      cards_per_node: Number($("cards_per_node").value),
      price_mode: $("price_mode").value,
      node_price: Number($("node_price").value),
      card_price: Number($("card_price").value),
      name: ($("gpu_id").selectedOptions[0] || {}).text,
    },
    prices,
  };
}

function render(b) {
  const s = b.scale, t = b.totals;
  $("kpis").innerHTML = [
    ["采购 GPU", s.gpu_buy + " 卡 / " + s.nodes + " 台"],
    ["标称 FP16", s.pflops_fp16 + " PFLOPS"],
    ["IT / 进线", s.it_kw + " / " + s.facility_kw + " kW"],
    ["机柜 / 面积", s.racks + " 套 / " + s.area_m2 + " ㎡"],
    ["含税总投资", yuan(t.total) + " 元"],
    ["约合万元", (t.total / 10000).toFixed(2) + " 万"],
    ["单卡含税", yuan(t.per_gpu) + " 元"],
    ["万元/PFLOPS", (t.per_pflops / 10000).toFixed(2)],
    ["年电费", yuan(t.opex_power_year) + " 元"],
  ].map(([k, v]) => `<div>${k}<b>${v}</b></div>`).join("");
  $("note").textContent = b.meta.price_note || "";
  const body = [];
  b.sections.forEach((sec) => {
    body.push(`<tr class="sec-title"><td colspan="5">${sec.title}</td><td>${yuan(sec.subtotal)}</td></tr>`);
    sec.rows.forEach((r) => {
      body.push(`<tr><td>${r.name}</td><td>${r.spec || ""}</td><td>${r.qty}</td><td>${r.unit}</td><td>${yuan(r.price)}</td><td>${yuan(r.amount)}</td></tr>`);
    });
  });
  body.push(`<tr class="sec-title"><td>预备费 ${t.contingency_pct}%</td><td colspan="4"></td><td>${yuan(t.contingency)}</td></tr>`);
  body.push(`<tr><td>不含税合计</td><td colspan="4"></td><td>${yuan(t.pretax)}</td></tr>`);
  body.push(`<tr><td>增值税 ${t.vat_pct}%</td><td colspan="4"></td><td>${yuan(t.vat)}</td></tr>`);
  body.push(`<tr class="sec-title"><td>含税总投资</td><td colspan="4"></td><td>${yuan(t.total)}</td></tr>`);
  $("rows").innerHTML = body.join("");
}

async function boot() {
  const res = await fetch("/api/catalog");
  catalog = await res.json();
  $("gpu_id").innerHTML = catalog.gpus.map((g) => `<option value="${g.id}">${g.name}</option>`).join("");
  fillPrices(catalog.defaults);
  applyGpu();
}

$("gpu_id").addEventListener("change", applyGpu);
$("run").onclick = async () => {
  status("正在汇总预算…");
  try {
    const res = await fetch("/api/budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "失败");
    render(data);
    status("预算已生成，可下载 Excel / Word");
  } catch (e) { status(String(e.message || e)); }
};

boot().catch((e) => status(String(e)));
