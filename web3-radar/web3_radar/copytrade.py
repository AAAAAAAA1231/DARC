from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar import db
from web3_radar.config import load_settings, save_settings
from web3_radar.engine.meme_score import enrich_and_score
from web3_radar.wallet import enqueue_participate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings() -> dict[str, Any]:
    s = load_settings()
    s.setdefault("copy_enabled", True)
    s.setdefault("copy_mode", "paper")  # paper | live_queue
    s.setdefault("copy_max_positions", 5)
    s.setdefault("copy_size_usd", 30)
    s.setdefault("copy_sl_pct", 0.18)
    s.setdefault("copy_tp_pct", 0.40)
    s.setdefault("copy_max_1h_change", 80)
    s.setdefault("copy_min_heat", 65)
    s.setdefault("copy_max_risk", 45)
    s.setdefault("copy_paper_equity", 1000)
    return s


async def snapshot() -> dict[str, Any]:
    s = _settings()
    positions = await db.list_copy_positions()
    open_pos = [p for p in positions if p["status"] == "open"]
    closed = [p for p in positions if p["status"] == "closed"]
    realized = sum(float(p.get("pnl_usd") or 0) for p in closed)
    unreal = sum(float(p.get("unrealized_pnl") or 0) for p in open_pos)
    wins = [p for p in closed if float(p.get("pnl_usd") or 0) > 0]
    return {
        "enabled": bool(s.get("copy_enabled")),
        "mode": s.get("copy_mode") or "paper",
        "equity": float(s.get("copy_paper_equity") or 1000),
        "size_usd": float(s.get("copy_size_usd") or 30),
        "max_positions": int(s.get("copy_max_positions") or 5),
        "sl_pct": float(s.get("copy_sl_pct") or 0.18),
        "tp_pct": float(s.get("copy_tp_pct") or 0.40),
        "min_heat": float(s.get("copy_min_heat") or 65),
        "max_risk": float(s.get("copy_max_risk") or 45),
        "open": open_pos,
        "closed": closed[:40],
        "open_count": len(open_pos),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unreal, 2),
        "win_rate": round(len(wins) / len(closed), 3) if closed else 0,
        "note": "默认模拟跟单：按妖币「可跟」信号开仓，止损 18%、止盈 40%。实盘只进钱包确认队列，不代签私钥。",
    }


async def update_settings(fields: dict[str, Any]) -> dict[str, Any]:
    s = load_settings()
    allowed = {
        "copy_enabled",
        "copy_mode",
        "copy_max_positions",
        "copy_size_usd",
        "copy_sl_pct",
        "copy_tp_pct",
        "copy_max_1h_change",
        "copy_min_heat",
        "copy_max_risk",
        "copy_paper_equity",
    }
    for k, v in fields.items():
        if k in allowed:
            s[k] = v
    save_settings(s)
    return await snapshot()


def _should_enter(item: dict[str, Any], s: dict[str, Any]) -> tuple[bool, str]:
    scored = item if "grade" in item else enrich_and_score(item, float(s.get("meme_min_liquidity_usd") or 20_000))
    if scored.get("grade") != "可跟":
        return False, f"评级 {scored.get('grade')}，不自动跟"
    if float(scored.get("heat") or 0) < float(s.get("copy_min_heat") or 65):
        return False, "热度不够"
    if float(scored.get("risk") or 100) > float(s.get("copy_max_risk") or 45):
        return False, "风险过高"
    chg = float(scored.get("price_change_m5") or scored.get("price_change_h1") or 0)
    if chg >= float(s.get("copy_max_1h_change") or 80):
        return False, "涨幅过大，不追高"
    px = float(scored.get("price_usd") or 0)
    if px <= 0:
        return False, "无有效价格"
    return True, "可跟：多人买入+持币增加+池子够深+涨幅未失控"


async def evaluate_memes(items: list[dict[str, Any]]) -> dict[str, Any]:
    s = _settings()
    actions: list[str] = []
    prices = {it.get("key"): float(it.get("price_usd") or 0) for it in items if it.get("key")}
    open_pos = await db.list_copy_positions("open")

    for pos in open_pos:
        px = prices.get(pos["item_key"]) or float(pos.get("last_price") or pos["entry"])
        await db.update_copy_position(pos["id"], last_price=px, unrealized_pnl=_pnl(pos, px))
        hit = _exit_reason(pos, px, s)
        if hit:
            pnl = _pnl(pos, px)
            await db.update_copy_position(
                pos["id"],
                status="closed",
                exit_price=px,
                pnl_usd=pnl,
                closed_at=_now(),
                unrealized_pnl=0,
                close_reason=hit,
            )
            s["copy_paper_equity"] = float(s.get("copy_paper_equity") or 1000) + pnl
            actions.append(f"平仓 {pos['symbol']} @ {px} ({hit}) PnL {pnl:.2f}")
    save_settings(s)

    if not s.get("copy_enabled"):
        snap = await snapshot()
        snap["actions"] = actions + ["跟单未开启"]
        return snap

    open_pos = await db.list_copy_positions("open")
    open_keys = {p["item_key"] for p in open_pos}
    max_n = int(s.get("copy_max_positions") or 5)
    size = float(s.get("copy_size_usd") or 30)

    candidates = []
    for it in items:
        ok, why = _should_enter(it, s)
        if ok:
            candidates.append((it, why))
    candidates.sort(key=lambda x: float(x[0].get("heat") or 0) - float(x[0].get("risk") or 0), reverse=True)

    for it, why in candidates:
        if len(open_pos) >= max_n:
            actions.append("已达最大持仓数")
            break
        key = str(it.get("key"))
        if key in open_keys:
            continue
        px = float(it.get("price_usd") or 0)
        sl = px * (1 - float(s.get("copy_sl_pct") or 0.18))
        tp = px * (1 + float(s.get("copy_tp_pct") or 0.40))
        qty = size / px
        pos = await db.add_copy_position(
            {
                "item_key": key,
                "symbol": it.get("symbol") or "?",
                "chain": it.get("chain") or "",
                "url": it.get("url") or "",
                "entry": px,
                "qty": qty,
                "sl": sl,
                "tp": tp,
                "last_price": px,
                "reason": why,
                "mode": s.get("copy_mode") or "paper",
                "heat": it.get("heat"),
                "risk": it.get("risk"),
            }
        )
        open_pos.append(pos)
        open_keys.add(key)
        actions.append(f"开仓 {pos['symbol']} {pos['chain']} @ {px} 仓位 ${size}")
        if (s.get("copy_mode") or "paper") == "live_queue":
            await enqueue_participate("meme", it, auto=False)

    snap = await snapshot()
    snap["actions"] = actions
    return snap


def _pnl(pos: dict[str, Any], price: float) -> float:
    entry = float(pos.get("entry") or 0)
    qty = float(pos.get("qty") or 0)
    return round((price - entry) * qty, 4)


def _exit_reason(pos: dict[str, Any], price: float, s: dict[str, Any]) -> str | None:
    sl = float(pos.get("sl") or 0)
    tp = float(pos.get("tp") or 0)
    if sl and price <= sl:
        return "止损"
    if tp and price >= tp:
        return "止盈"
    return None
