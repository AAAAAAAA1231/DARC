export function fmtNum(value: unknown, digits = 4): string {
  if (value == null || value === "") return "未知";
  const n = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

export function fmtPct(value: unknown, digits = 2): string {
  if (value == null || value === "") return "未知";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "未知";
  const pct = Math.abs(n) <= 1 && Math.abs(n) !== 0 ? n * 100 : n;
  return `${pct.toFixed(digits)}%`;
}

export function fmtUsd(value: unknown): string {
  if (value == null || value === "" || value === "UNKNOWN") return "未知";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
  return `$${n.toLocaleString("zh-CN", { maximumFractionDigits: 4 })}`;
}
