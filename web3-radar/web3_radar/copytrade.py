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
    wanted = float(s.get("copy_size_usd") or 10)
    cap = equity * float(s.get("copy_max_size_pct") or 0.01)
    return round(max(0.0, min(wanted, cap)), 2)


def trail_stop(
    entry: float,
    current_sl: float,
    price: float,
    arm_pct: float = 0.50,
    lock_pct: float = 1.5,
    lock_mult: float = 1.5,
) -> float | None:
    """1.5 倍先把止损抬到成本；2.5 倍抬到 1.5 倍。先锁定胜率，再留月亮仓。"""
    if entry <= 0 or price <= 0:
        return None
    ret = (price - entry) / entry
    new_sl = current_sl
    if ret >= arm_pct:
        new_sl = max(new_sl, entry)
    if ret >= lock_pct:
        new_sl = max(new_sl, entry * lock_mult)
    if new_sl > current_sl + 1e-12:
        return round(new_sl, 10)
    return None


def apply_scale(pos: dict[str, Any], price: float, s: dict[str, Any]) -> dict[str, Any] | None:
    """1.5 倍卖掉约 55% 锁定胜利，2.5 倍再卖 20%，剩下博 5–10 倍。"""
    entry = float(pos.get("entry") or 0)
    qty = float(pos.get("qty") or 0)
    orig = float(pos.get("orig_qty") or qty)
    if entry <= 0 or orig <= 0 or price <= 0:
        return None
    multiple = price / entry
    stage = int(pos.get("scale_stage") or 0)
    s1 = float(s.get("copy_scale1_mult") or 1.5)
    s2 = float(s.get("copy_scale2_mult") or 2.5)
    frac1 = float(s.get("copy_scale_frac") or 0.55)
    frac2 = float(s.get("copy_scale2_frac") or 0.20)
    if stage < 1 and multiple >= s1:
        sell = min(orig * frac1, qty * 0.95)
        return {"stage": 1, "sell_qty": sell, "label": f"{s1:.1f}倍锁定"}
    if stage < 2 and multiple >= s2:
        sell = min(orig * frac2, qty * 0.95)
        return {"stage": 2, "sell_qty": sell, "label": f"{s2:.1f}倍减仓"}
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


def _settings() -> dict[str, Any]:
    s = load_settings()
    s.setdefault("copy_enabled", True)
    s.setdefault("copy_mode", "paper")  # paper | live_queue
    s.setdefault("copy_max_positions", 2)
    s.setdefault("copy_size_usd", 10)
    s.setdefault("copy_sl_pct", 0.18)
    s.setdefault("copy_tp_pct", 9.0)
    s.setdefault("copy_max_1h_change", 85)
    s.setdefault("copy_min_heat", 68)
    s.setdefault("copy_max_risk", 48)
    s.setdefault("copy_paper_equity", 1000)
    s.setdefault("copy_cooldown_minutes", 150)
    s.setdefault("copy_max_size_pct", 0.01)
    s.setdefault("copy_trail_arm_pct", 0.50)
    s.setdefault("copy_trail_lock_pct", 1.5)
    s.setdefault("copy_daily_loss_pct", 0.06)
    s.setdefault("copy_time_stop_minutes", 50)
    s.setdefault("copy_giveup_pct", 0.12)
    s.setdefault("copy_scale1_mult", 1.5)
    s.setdefault("copy_scale2_mult", 2.5)
    s.setdefault("copy_scale_frac", 0.55)
    s.setdefault("copy_scale2_frac", 0.20)
    s.setdefault("copy_fast_fail_minutes", 12)
    s.setdefault("copy_fast_fail_pct", 0.07)
    s.setdefault("copy_struct_m5_fail", -8)
    s.setdefault("copy_struct_h1_min", 25)
    s.setdefault("copy_require_multi_source", True)
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
        "max_positions": int(s.get("copy_max_positions") or 2),
        "sl_pct": float(s.get("copy_sl_pct") or 0.18),
        "tp_pct": float(s.get("copy_tp_pct") or 9.0),
        "min_heat": float(s.get("copy_min_heat") or 68),
        "max_risk": float(s.get("copy_max_risk") or 48),
        "cooldown_minutes": int(s.get("copy_cooldown_minutes") or 150),
        "open": open_pos,
        "closed": closed[:40],
        "open_count": len(open_pos),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unreal, 2),
        "win_rate": round(len(wins) / len(closed), 3) if closed else 0,
        "note": (
            "胜率优先：只买多源确认、1h 已启动、5m 回踩反弹的票。"
            "1.5 倍卖掉 55% 先锁定胜利并把止损抬到成本；2.5 倍再卖 20%。"
            "12 分钟内跌超 7% 快速止损。5m 结构破坏立刻走。50 分钟还没 +12% 当死票。"
            "单笔 1% 本金，最多 2 仓。剩下仓位继续博 5–10 倍。"
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
        "copy_time_stop_minutes",
        "copy_giveup_pct",
        "copy_scale1_mult",
        "copy_scale2_mult",
        "copy_scale_frac",
        "copy_scale2_frac",
        "copy_fast_fail_minutes",
        "copy_fast_fail_pct",
        "copy_struct_m5_fail",
        "copy_struct_h1_min",
        "copy_require_multi_source",
    }
    for k, v in fields.items():
        if k in allowed:
            s[k] = v
    save_settings(s)
    return await snapshot()


def _should_enter(item: dict[str, Any], s: dict[str, Any]) -> tuple[bool, str]:
    scored = enrich_and_score(item, float(s.get("meme_min_liquidity_usd") or 50_000))
    if scored.get("grade") != "可跟":
        return False, f"评级 {scored.get('grade')}，不自动跟"
    if scored.get("action") == "禁止买入":
        return False, "禁止买入"
    if not scored.get("dip_in_trend"):
        return False, "不是 1h 启动 + 5m 回踩，胜率不够"
    if s.get("copy_require_multi_source", True) and not scored.get("multi_source"):
        return False, "只有单源报价，交叉确认不够"
    if not scored.get("crowd_ok"):
        return False, "买盘人数不够"
    if float(scored.get("heat") or 0) < float(s.get("copy_min_heat") or 68):
        return False, "热度不够"
    if float(scored.get("risk") or 100) > float(s.get("copy_max_risk") or 48):
        return False, "风险过高"
    chg_h1 = float(scored.get("price_change_h1") or 0)
    chg_m5 = float(scored.get("price_change_m5") or 0)
    chg_h24 = float(scored.get("price_change_h24") or 0)
    if chg_h1 >= float(s.get("copy_max_1h_change") or 85):
        return False, "1h 已经翻太倍，大头过了"
    if chg_m5 >= float(s.get("meme_max_m5_change") or 18):
        return False, "5m 太陡，回踩后再买"
    if chg_m5 < 4:
        return False, "5m 还没确认反弹"
    if chg_h1 < 32:
        return False, "1h 还没启动，胜率不够"
    if chg_h24 >= max(80.0, chg_h1 * 2.2):
        return False, "24h 已经见顶回落"
    fdv = float(scored.get("fdv") or 0)
    if fdv >= 8_000_000:
        return False, "盘太大，不是小妖"
    px = float(scored.get("price_usd") or 0)
    if px <= 0:
        return False, "无有效价格"
    return True, "可跟：多源确认回踩，小仓博倍数"


async def evaluate_memes(items: list[dict[str, Any]], open_new: bool = True) -> dict[str, Any]:
    s = _settings()
    actions: list[str] = []
    prices = {it.get("key"): float(it.get("price_usd") or 0) for it in items if it.get("key")}
    tape_by_key: dict[str, dict[str, Any]] = {}
    tape_by_tid: dict[str, dict[str, Any]] = {}
    # also index by token id so MTM still works if source key changed
    for it in items:
        tid = token_id(it)
        px = float(it.get("price_usd") or 0)
        if it.get("key"):
            tape_by_key[str(it.get("key"))] = it
        if tid:
            tape_by_tid[tid] = it
        if tid and px > 0:
            prices.setdefault(tid, px)
    open_pos = await db.list_copy_positions("open")
    s1 = float(s.get("copy_scale1_mult") or 1.5)

    for pos in open_pos:
        px = prices.get(pos["item_key"]) or prices.get(token_id(pos)) or float(pos.get("last_price") or pos["entry"])
        peak = max(float(pos.get("peak") or 0), px, float(pos.get("entry") or 0))
        await db.update_copy_position(pos["id"], last_price=px, peak=peak, unrealized_pnl=_pnl(pos, px))
        pos["last_price"] = px
        pos["peak"] = peak
        pos["unrealized_pnl"] = _pnl(pos, px)
        scaled = apply_scale(pos, px, s)
        if scaled:
            sell_qty = float(scaled["sell_qty"])
            pnl = round((px - float(pos["entry"])) * sell_qty, 4)
            new_qty = max(0.0, float(pos["qty"]) - sell_qty)
            booked = float(pos.get("pnl_usd") or 0) + pnl
            sl = max(float(pos.get("sl") or 0), float(pos["entry"]) * (1.0 if scaled["stage"] == 1 else s1))
            await db.update_copy_position(
                pos["id"],
                qty=new_qty,
                scale_stage=scaled["stage"],
                sl=sl,
                pnl_usd=booked,
            )
            pos["qty"] = new_qty
            pos["scale_stage"] = scaled["stage"]
            pos["sl"] = sl
            pos["pnl_usd"] = booked
            s["copy_paper_equity"] = float(s.get("copy_paper_equity") or 1000) + pnl
            actions.append(f"{scaled['label']} {pos['symbol']} 卖 {sell_qty:.4f} PnL {pnl:.2f}")
        new_sl = trail_stop(
            float(pos.get("entry") or 0),
            float(pos.get("sl") or 0),
            px,
            float(s.get("copy_trail_arm_pct") or 0.50),
            float(s.get("copy_trail_lock_pct") or 1.5),
            s1,
        )
        if new_sl is not None:
            await db.update_copy_position(pos["id"], sl=new_sl)
            pos["sl"] = new_sl
            actions.append(f"追踪止损 {pos['symbol']} → {new_sl}")
        live = tape_by_key.get(str(pos.get("item_key") or "")) or tape_by_tid.get(token_id(pos))
        hit = _exit_reason(pos, px, s, tape=live)
        if hit:
            remain = _pnl(pos, px)
            total = float(pos.get("pnl_usd") or 0) + remain
            await db.update_copy_position(
                pos["id"],
                status="closed",
                exit_price=px,
                pnl_usd=total,
                closed_at=_now(),
                unrealized_pnl=0,
                close_reason=hit,
            )
            s["copy_paper_equity"] = float(s.get("copy_paper_equity") or 1000) + remain
            actions.append(f"平仓 {pos['symbol']} @ {px} ({hit}) PnL {total:.2f}")
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
    max_n = int(s.get("copy_max_positions") or 2)
    size = position_size_usd(s)
    cooldown = int(s.get("copy_cooldown_minutes") or 180)

    if size < 5:
        snap = await snapshot()
        snap["actions"] = actions + ["权益过低，单笔不足 $5，停止开仓"]
        snap["opened_new"] = False
        return snap

    candidates = []
    for it in items:
        ok, why = _should_enter(it, s)
        if ok:
            candidates.append((it, why))
    candidates.sort(key=lambda x: float(x[0].get("expectancy") or 0) or (float(x[0].get("heat") or 0) - 1.5 * float(x[0].get("risk") or 0)), reverse=True)

    opened = 0
    for it, why in candidates:
        if len(open_pos) >= max_n:
            actions.append("已达最大持仓数")
            break
        key = str(it.get("key"))
        tid = token_id(it)
        if key.lower() in open_keys or tid in open_tids:
            continue
        if recently_closed(closed, tid, cooldown) or recently_closed(closed, key.lower(), cooldown):
            actions.append(f"冷却中，跳过 {it.get('symbol')}")
            continue
        px = float(it.get("price_usd") or 0)
        sl = px * (1 - float(s.get("copy_sl_pct") or 0.18))
        tp = px * (1 + float(s.get("copy_tp_pct") or 9.0))
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
        actions.append(f"开仓 {pos['symbol']} {pos['chain']} @ {px} 彩票 ${size}")
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


def _exit_reason(
    pos: dict[str, Any],
    price: float,
    s: dict[str, Any],
    now: datetime | None = None,
    tape: dict[str, Any] | None = None,
) -> str | None:
    sl = float(pos.get("sl") or 0)
    tp = float(pos.get("tp") or 0)
    entry = float(pos.get("entry") or 0)
    if sl and price <= sl:
        if price >= entry:
            return "追踪止盈"
        return "止损"
    if tp and price >= tp:
        return "月亮仓止盈"
    if entry > 0:
        ret = (price - entry) / entry
        opened = _parse_dt(pos.get("opened_at"))
        now = now or datetime.now(timezone.utc)
        if opened:
            age_min = (now - opened).total_seconds() / 60.0
            fast_m = int(s.get("copy_fast_fail_minutes") or 12)
            fast_p = float(s.get("copy_fast_fail_pct") or 0.07)
            if age_min <= fast_m and ret <= -abs(fast_p):
                return "快速止损"
            limit = int(s.get("copy_time_stop_minutes") or 50)
            giveup = float(s.get("copy_giveup_pct") or 0.12)
            if limit > 0 and age_min >= limit and ret < giveup:
                return "死票离场"
        if tape and int(pos.get("scale_stage") or 0) < 1:
            chg_m5 = float(tape.get("price_change_m5") or 0)
            chg_h1 = float(tape.get("price_change_h1") or 0)
            buys_m5 = float(tape.get("buys_m5") or 0)
            sells_m5 = float(tape.get("sells_m5") or 0)
            if chg_m5 <= float(s.get("copy_struct_m5_fail") or -8) and chg_h1 < float(s.get("copy_struct_h1_min") or 25):
                return "结构破坏"
            if sells_m5 >= max(buys_m5, 1.0) * 1.3 and chg_m5 < 0:
                return "结构破坏"
    return None
