import { HoldingOverlay } from "../holdings";

export default function HoldingBadge({ overlay }: { overlay?: HoldingOverlay }) {
  if (!overlay?.held) return null;
  const pnl = overlay.net_pnl;
  const pnlNum = pnl != null ? Number(pnl) : null;
  const color = pnlNum == null ? "text-[#f5c542]" : pnlNum >= 0 ? "text-[#3ee0b4]" : "text-[#ff5d73]";
  return (
    <div className={`text-[11px] ${color}`}>
      HELD qty {overlay.quantity} @ {overlay.avg_cost} · PnL {pnl ?? "UNKNOWN"} · {overlay.signal || "HOLD"}
    </div>
  );
}
