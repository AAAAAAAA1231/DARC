import ReactECharts from "echarts-for-react";

type Candle = {
  open_time?: string;
  open: string | number;
  close: string | number;
  low: string | number;
  high: string | number;
};

export default function CandleChart({ candles, height = 280 }: { candles?: Candle[] | null; height?: number }) {
  if (!candles?.length) {
    return <div className="text-sm text-[#8aa0c2]">暂无K线 — 数据源不可用或为空。不会编造价格。</div>;
  }
  const option = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: { trigger: "axis" },
    grid: { left: 56, right: 12, top: 16, bottom: 28 },
    xAxis: {
      type: "category",
      data: candles.map((c) => (c.open_time || "").slice(0, 10)),
      axisLabel: { color: "#8aa0c2", fontSize: 10 },
    },
    yAxis: { scale: true, axisLabel: { color: "#8aa0c2", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e2a44" } } },
    series: [
      {
        type: "candlestick",
        data: candles.map((c) => [Number(c.open), Number(c.close), Number(c.low), Number(c.high)]),
        itemStyle: { color: "#3ee0b4", color0: "#ff5d73", borderColor: "#3ee0b4", borderColor0: "#ff5d73" },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}
