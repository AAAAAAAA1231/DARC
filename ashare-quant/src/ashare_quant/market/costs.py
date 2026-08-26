"""Commission, stamp tax, transfer fee, and slippage."""

from __future__ import annotations

from ..config import CostConfig


def commission(notional: float, cfg: CostConfig) -> float:
    if notional <= 0:
        return 0.0
    return max(cfg.commission_min, abs(notional) * cfg.commission_rate)


def stamp_tax(notional: float, side: str, cfg: CostConfig) -> float:
    if side.lower() != "sell" or notional <= 0:
        return 0.0
    return abs(notional) * cfg.stamp_tax_sell


def transfer_fee(notional: float, cfg: CostConfig) -> float:
    if notional <= 0:
        return 0.0
    return abs(notional) * cfg.transfer_fee


def slippage_rate(atr_pct: float | None, cfg: CostConfig, multiplier: float = 1.0) -> float:
    extra = 0.0 if atr_pct is None else max(0.0, float(atr_pct)) * cfg.atr_slippage_k
    return max(0.0, (cfg.base_slippage + extra) * multiplier)


def trade_cost(
    notional: float,
    side: str,
    cfg: CostConfig,
    *,
    atr_pct: float | None = None,
    slippage_mult: float = 1.0,
) -> dict[str, float]:
    """Total cost in CNY for one fill, including slippage as a cash drag."""
    notional = abs(float(notional))
    comm = commission(notional, cfg)
    stamp = stamp_tax(notional, side, cfg)
    fee = transfer_fee(notional, cfg)
    slip = notional * slippage_rate(atr_pct, cfg, slippage_mult)
    total = comm + stamp + fee + slip
    return {
        "commission": comm,
        "stamp_tax": stamp,
        "transfer_fee": fee,
        "slippage": slip,
        "total": total,
        "cost_bps": 0.0 if notional == 0 else 1e4 * total / notional,
    }


def apply_slippage_price(price: float, side: str, rate: float) -> float:
    if price <= 0:
        return price
    if side.lower() == "buy":
        return round(price * (1.0 + rate), 2)
    return round(price * (1.0 - rate), 2)
