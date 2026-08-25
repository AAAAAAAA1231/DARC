const state = { page: 1, pageSize: 40, total: 0, selected: null };

const $ = (id) => document.getElementById(id);

function fmtPct(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "--";
  return `${n.toFixed(2)}%`;
}

function dirClass(d) {
  if (d === "上涨") return "dir-up";
  if (d === "下跌") return "dir-down";
  return "dir-flat";
}

async function loadMeta() {
  const meta = await (await fetch("/api/meta")).json();
  const cal = meta.calibration || {};
  const pred = meta.predictions || {};
  const n = cal.n_sims ? Number(cal.n_sims).toLocaleString("zh-CN") : "--";
  const markets = pred.markets || {};
  $("kpis").innerHTML = [
    kpi("模拟次数", n),
    kpi("上证", markets["上证"] ?? "--"),
    kpi("深证", markets["深证"] ?? "--"),
    kpi("科创板", markets["科创板"] ?? "--"),
    kpi("创业板", markets["创业板"] ?? "--"),
    kpi("股票数量", pred.count ?? "--"),
  ].join("");
  const labels = [
    ["", "全部市场"],
    ["上证", "上证"],
    ["深证", "深证"],
    ["科创板", "科创板"],
    ["创业板", "创业板"],
    ["北交所", "北交所"],
  ];
  $("board").innerHTML = labels
    .map(([value, name]) => {
      const extra = value && markets[name] != null ? ` (${markets[name]})` : "";
      return `<option value="${value}">${name}${extra}</option>`;
    })
    .join("");
  const methods = (cal.methods || []).slice().sort((a, b) => b.corrected - a.corrected);
  $("weights").innerHTML = methods
    .map((m) => {
      const pct = (m.corrected * 100).toFixed(2);
      return `<div class="bar"><span>${m.title}</span><div class="track"><div class="fill" style="width:${pct}%"></div></div><b>${pct}%</b></div>`;
    })
    .join("");
}

function kpi(label, value) {
  return `<div class="kpi"><b>${value}</b><span>${label}</span></div>`;
}

async function loadList() {
  const params = new URLSearchParams({
    q: $("q").value.trim(),
    direction: $("direction").value,
    board: $("board").value,
    page: String(state.page),
    page_size: String(state.pageSize),
    sort: $("sort").value,
  });
  const data = await (await fetch(`/api/stocks?${params}`)).json();
  state.total = data.total;
  const pages = Math.max(1, Math.ceil(data.total / state.pageSize));
  $("pageinfo").textContent = `${state.page} / ${pages} · ${data.total} 只`;
  $("rows").innerHTML = data.items
    .map(
      (x) => `<tr data-code="${x.code}">
        <td>${x.code}</td>
        <td>${x.name}</td>
        <td>${x.market || x.board}</td>
        <td>${x.last}</td>
        <td class="${x.change_pct >= 0 ? "dir-up" : "dir-down"}">${fmtPct(x.change_pct)}</td>
        <td class="${dirClass(x.direction)}">${x.direction}</td>
        <td>${Number(x.score).toFixed(3)}</td>
        <td>${(x.confidence * 100).toFixed(0)}%</td>
        <td class="dir-up">${x.take_profit}</td>
        <td class="dir-down">${x.stop_loss}</td>
        <td>${x.data_source === "live" ? "实盘K线" : "统计合成"}</td>
      </tr>`
    )
    .join("");
  document.querySelectorAll("tbody tr").forEach((tr) => {
    tr.addEventListener("click", () => showDetail(tr.dataset.code));
  });
}

function drawSpark(el, series) {
  const w = el.width;
  const h = el.height;
  const ctx = el.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  if (!series || series.length < 2) return;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min || 1;
  ctx.beginPath();
  series.forEach((v, i) => {
    const x = (i / (series.length - 1)) * (w - 4) + 2;
    const y = h - 6 - ((v - min) / span) * (h - 12);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = series[series.length - 1] >= series[0] ? "#ff5a6a" : "#22c55e";
  ctx.lineWidth = 2;
  ctx.stroke();
}

async function showDetail(code) {
  const x = await (await fetch(`/api/stocks/${code}`)).json();
  state.selected = x;
  $("detail").innerHTML = `
    <h2>${x.name} <span class="badge">${x.code}</span> <span class="badge">${x.market || x.board}</span> <span class="badge">${x.board}</span></h2>
    <p class="${dirClass(x.direction)}">${x.side} · ${x.direction} · 置信度 ${(x.confidence * 100).toFixed(0)}%</p>
    <canvas class="spark" id="spark" width="420" height="90"></canvas>
    <p>现价 <b>${x.last}</b>　止盈 <b class="dir-up">${x.take_profit}</b>　止损 <b class="dir-down">${x.stop_loss}</b>　盈亏比 ${x.reward_risk}</p>
    <p class="muted">${x.notes}</p>
    <div class="methods">
      ${(x.methods || [])
        .map(
          (m) => `<div class="method"><span>${m.title}</span><span>权重 ${(m.weight * 100).toFixed(2)}%</span><b class="${m.score >= 0 ? "dir-up" : "dir-down"}">${m.score.toFixed(3)}</b></div>`
        )
        .join("")}
    </div>
  `;
  drawSpark($("spark"), x.spark);
}

["q", "direction", "board", "sort"].forEach((id) => {
  $(id).addEventListener("input", () => {
    state.page = 1;
    loadList();
  });
  $(id).addEventListener("change", () => {
    state.page = 1;
    loadList();
  });
});
$("prev").addEventListener("click", () => {
  state.page = Math.max(1, state.page - 1);
  loadList();
});
$("next").addEventListener("click", () => {
  const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
  state.page = Math.min(pages, state.page + 1);
  loadList();
});

loadMeta().then(loadList).catch((err) => {
  $("rows").innerHTML = `<tr><td colspan="11">加载失败：${err.message}。请先运行 python -m a_share_trading run</td></tr>`;
});
