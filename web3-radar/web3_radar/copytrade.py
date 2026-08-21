from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar import db
from web3_radar.config import load_settings, save_settings
from web3_radar.engine.meme_score import enrich_and_score
from web3_radar.wallet import enqueue_participate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def token_id(item: dict[str, Any]) -> str:
    addr = str(item.get("token_address") or "").strip().lower()
    chain = str(item.get("chain_id") or item.get("chain") or "").strip().lower()
    if addr:
        return f"{chain}:{addr}"
    return str(item.get("item_key") or item.get("key") or "").strip().lower()


def position_size_usd(s: dict[str, Any]) -> float:
    equity = max(float(s.get("copy_paper_equity") or 1000), 1.0)
    wanted = float(s.get("copy_size_usd") or 30)
    cap = equity * float(s.get("copy_max_size_pct") or 0.05)
    return round(max(0.0, min(wanted, cap)), 2)


def trail_stop(entry: float, current_sl: float, price: float, arm_pct: float = 0.25, lock_pct: float = 0.50) -> float | None:
    """After +arm, lock breakeven; after +lock, trail SL to keep half of open profit."""
    if entry <= 0 or price <= 0:
        return None
    ret = (price - entry) / entry
    new_sl = current_sl
    if ret >= arm_pct:
        new_sl = max(new_sl, entry)
    if ret >= lock_pct:
        new_sl = max(new_sl, entry + (price - entry) * 0.5)
    if new_sl > current_sl + 1e-12:
        return round(new_sl, 10)
    return None


def recently_closed(closed: list[dict[str, Any]], tid: str, minutes: int, now: datetime | None = None) -> bool:
    if minutes <= 0 or not tid:
        return False
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)
    for pos in closed:
        if token_id(pos) != tid and str(pos.get("item_key") or "").lower() != tid:
            continue
        closed_at = _parse_dt(pos.get("closed_at"))
        if closed_at and closed_at >= cutoff:
            return True
    return False


def halt_new_entries(s: dict[str, Any], positions: list[dict[str, Any]], now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    day_pnl = 0.0
    for pos in positions:
        if pos.get("status") != "closed":
            continue
        closed_at = _parse_dt(pos.get("closed_at"))
        if closed_at and closed_at.date() == today:
            day_pnl += float(pos.get("pnl_usd") or 0)
    unreal = sum(float(p.get("unrealized_pnl") or 0) for p in positions if p.get("status") == "open")
    equity = float(s.get("copy_paper_equity") or 1000)
    start_eq = max(equity - day_pnl, 1.0)
    limit = float(s.get("copy_daily_loss_pct") or 0.15)
    if day_pnl + unreal <= -abs(start_eq) * limit:
        return f"当日回撤超过 {limit:.0%}，停止新开仓"
    return None


def closed_by_time(closed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [p for p in closed or [] if p.get("closed_at") or p.get("status") == "closed"],
        key=lambda p: str(p.get("closed_at") or ""),
    )


def consecutive_closed_losses(closed: list[dict[str, Any]], n: int = 3) -> bool:
    last = closed_by_time(closed)[-max(int(n), 1) :]
    return len(last) >= n and all(float(p.get("pnl_usd") or 0) < 0 for p in last)


def size_after_losses(size: float, closed: list[dict[str, Any]], lookback: int = 5) -> float:
    recent = closed_by_time(closed)[-lookback:]
    if len(recent) < 3:
        return float(size)
    net = sum(float(p.get("pnl_usd") or 0) for p in recent)
    if net < 0:
        return round(max(float(size) * 0.5, 0.0), 2)
    return float(size)


def cooldown_minutes_for(
    closed: list[dict[str, Any]],
    tid: str,
    key: str,
    base: int,
) -> int:
    minutes = max(int(base or 0), 0)
    recent = closed_by_time(closed)
    for pos in reversed(recent):
        same = token_id(pos) == tid or str(pos.get("item_key") or "").lower() == str(key or "").lower()
        if not same:
            continue
        if str(pos.get("close_reason") or "") == "止损":
            return minutes * 2
        return minutes
    return minutes


def max_new_entries(s: dict[str, Any], closed: list[dict[str, Any]]) -> tuple[int, str | None]:
    cap = max(0, int(s.get("copy_max_new_per_refresh") or 1))
    if consecutive_closed_losses(closed, 3):
        return 0, "近3笔跟单连亏，本次不开新仓"
    return cap, None


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
    s.setdefault("copy_cooldown_minutes", 60)
    s.setdefault("copy_max_size_pct", 0.05)
    s.setdefault("copy_trail_arm_pct", 0.25)
    s.setdefault("copy_trail_lock_pct", 0.50)
    s.setdefault("copy_daily_loss_pct", 0.15)
    s.setdefault("copy_max_new_per_refresh", 1)
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
        "size_usd": position_size_usd(s),
        "max_positions": int(s.get("copy_max_positions") or 5),
        "sl_pct": float(s.get("copy_sl_pct") or 0.18),
        "tp_pct": float(s.get("copy_tp_pct") or 0.40),
        "min_heat": float(s.get("copy_min_heat") or 65),
        "max_risk": float(s.get("copy_max_risk") or 45),
        "cooldown_minutes": int(s.get("copy_cooldown_minutes") or 60),
        "open": open_pos,
        "closed": closed[:40],
        "open_count": len(open_pos),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unreal, 2),
        "win_rate": round(len(wins) / len(closed), 3) if closed else 0,
        "note": (
            "默认模拟跟单：只在刷新妖币时最多新开 1 笔；缓存刷新只做盯市与平仓。"
            "止损 18%、止盈 40%，浮盈 25% 保本、50% 追踪锁一半利润。"
            "同币冷却 60 分钟（止损后加倍），单笔不超过权益 5%。近 3 笔连亏或当日回撤过大则停开。"
            "实盘只进钱包确认队列，不代签私钥。"
        ),
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
        "copy_cooldown_minutes",
        "copy_max_size_pct",
        "copy_trail_arm_pct",
        "copy_trail_lock_pct",
        "copy_daily_loss_pct",
        "copy_max_new_per_refresh",
    }
    for k, v in fields.items():
        if k in allowed:
            s[k] = v
    save_settings(s)
    return await snapshot()


def _should_enter(item: dict[str, Any], s: dict[str, Any]) -> tuple[bool, str]:
    scored = item if "grade" in item else enrich_and_score(item, float(s.get("meme_min_liquidity_usd") or 1_000_000))
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


async def evaluate_memes(items: list[dict[str, Any]], open_new: bool = True) -> dict[str, Any]:
    s = _settings()
    actions: list[str] = []
    prices = {it.get("key"): float(it.get("price_usd") or 0) for it in items if it.get("key")}
    # also index by token id so MTM still works if source key changed
    for it in items:
        tid = token_id(it)
        px = float(it.get("price_usd") or 0)
        if tid and px > 0:
            prices.setdefault(tid, px)
    open_pos = await db.list_copy_positions("open")

    for pos in open_pos:
        px = prices.get(pos["item_key"]) or prices.get(token_id(pos)) or float(pos.get("last_price") or pos["entry"])
        await db.update_copy_position(pos["id"], last_price=px, unrealized_pnl=_pnl(pos, px))
        pos["last_price"] = px
        pos["unrealized_pnl"] = _pnl(pos, px)
        new_sl = trail_stop(
            float(pos.get("entry") or 0),
            float(pos.get("sl") or 0),
            px,
            float(s.get("copy_trail_arm_pct") or 0.25),
            float(s.get("copy_trail_lock_pct") or 0.50),
        )
        if new_sl is not None:
            await db.update_copy_position(pos["id"], sl=new_sl)
            pos["sl"] = new_sl
            actions.append(f"追踪止损 {pos['symbol']} → {new_sl}")
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
        snap["opened_new"] = False
        return snap

    if not open_new:
        snap = await snapshot()
        snap["actions"] = actions + ["缓存刷新：只盯市/平仓，不开新仓"]
        snap["opened_new"] = False
        return snap

    all_pos = await db.list_copy_positions()
    halt = halt_new_entries(s, all_pos)
    if halt:
        snap = await snapshot()
        snap["actions"] = actions + [halt]
        snap["opened_new"] = False
        return snap

    open_pos = await db.list_copy_positions("open")
    closed = [p for p in all_pos if p.get("status") == "closed"]
    open_keys = {str(p["item_key"]).lower() for p in open_pos}
    open_tids = {token_id(p) for p in open_pos}
    max_n = int(s.get("copy_max_positions") or 5)
    size = size_after_losses(position_size_usd(s), closed)
    cooldown = int(s.get("copy_cooldown_minutes") or 60)
    max_new, streak_halt = max_new_entries(s, closed)

    if size < 5 or max_new <= 0:
        snap = await snapshot()
        why = "权益过低，单笔不足 $5，停止开仓" if size < 5 else (streak_halt or "本次不开新仓")
        snap["actions"] = actions + [why]
        snap["opened_new"] = False
        return snap

    candidates = []
    for it in items:
        ok, why = _should_enter(it, s)
        if ok:
            candidates.append((it, why))
    candidates.sort(key=lambda x: float(x[0].get("heat") or 0) - float(x[0].get("risk") or 0), reverse=True)

    opened = 0
    for it, why in candidates:
        if opened >= max_new:
            actions.append(f"本次最多新开 {max_new} 笔，其余可跟下次再看")
            break
        if len(open_pos) >= max_n:
            actions.append("已达最大持仓数")
            break
        key = str(it.get("key"))
        tid = token_id(it)
        if key.lower() in open_keys or tid in open_tids:
            continue
        wait = cooldown_minutes_for(closed, tid, key.lower(), cooldown)
        if recently_closed(closed, tid, wait) or recently_closed(closed, key.lower(), wait):
            actions.append(f"冷却中，跳过 {it.get('symbol')}")
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
                "token_address": it.get("token_address") or "",
            }
        )
        open_pos.append(pos)
        open_keys.add(key.lower())
        open_tids.add(tid)
        opened += 1
        actions.append(f"开仓 {pos['symbol']} {pos['chain']} @ {px} 仓位 ${size}")
        if (s.get("copy_mode") or "paper") == "live_queue":
            await enqueue_participate("meme", it, auto=False)

    snap = await snapshot()
    snap["actions"] = actions
    snap["opened_new"] = opened > 0
    return snap


def _pnl(pos: dict[str, Any], price: float) -> float:
    entry = float(pos.get("entry") or 0)
    qty = float(pos.get("qty") or 0)
    return round((price - entry) * qty, 4)


def _exit_reason(pos: dict[str, Any], price: float, s: dict[str, Any]) -> str | None:
    sl = float(pos.get("sl") or 0)
    tp = float(pos.get("tp") or 0)
    if sl and price <= sl:
        if price >= float(pos.get("entry") or 0):
            return "追踪止盈"
        return "止损"
    if tp and price >= tp:
        return "止盈"
    return None
