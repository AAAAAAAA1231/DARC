export type HoldingOverlay = {
  held?: boolean;
  avg_cost?: string;
  quantity?: string;
  net_pnl?: string | null;
  unrealized_pnl?: string | null;
  current_price?: string | null;
  roi?: number | null;
  signal?: string;
  status?: string;
};

export function holdingFor(overlay: Record<string, HoldingOverlay> | undefined, symbol?: string | null): HoldingOverlay | undefined {
  if (!overlay || !symbol) return undefined;
  const u = symbol.toUpperCase();
  return overlay[u] || overlay[u.replace(/USDT$/, "")] || overlay[`${u}USDT`];
}
