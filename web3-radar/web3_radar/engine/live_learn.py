from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np

from web3_radar.config import INITIAL_INDICATOR_SHARES
from web3_radar.engine.monte_carlo import composite_score, decision_from_score
from web3_radar.engine.signals import mark_top_recommendations, resolve_weights

LEDGER_KEY = "recommendation_ledger_v1"
LEDGER_TTL = 365 * 24 * 3600
FEE_BUFFER = 0.0008
HALF_LIFE_HOURS = 48.0
LEARNING_RATE = 0.10
MAX_PENDING = 30
MAX_CLOSED = 200
PENDING_EXPIRE_HOURS = 7 * 24
SKIP_LOSER_HOURS = 24.0
MIN_HOLD_HOURS = 1.0

INTERVAL_HOURS = {
    "1m": 1 / 60,
    "3m": 3 / 60,
    "5m": 5 / 60,
    "15m": 0.25,
    "30m": 0.5,
    "1h": 1.0,
    "2h": 2.0,
    "4h": 4.0,
    "6h": 6.0,
    "8h": 8.0,
    "12h": 12.0,
    "1d": 24.0,
    "3d": 72.0,
    "1w": 168.0,
}


def parse_dt(value: Any) -> datetime | None:
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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hours_between(start: Any, end: datetime) -> float:
    dt = parse_dt(start)
    if not dt:
        return 0.0
    return max(0.0, (end - dt).total_seconds() / 3600.0)


def recency_weight(age_hours: float, half_life: float = HALF_LIFE_HOURS) -> float:
    if age_hours <= 0:
        return 1.0
    return float(math.exp(-math.log(2.0) * age_hours / max(half_life, 1e-6)))


def hold_hours_for(interval: str | None) -> float:
    mapped = INTERVAL_HOURS.get(str(interval or "").strip().lower(), 4.0)
    return max(MIN_HOLD_HOURS, float(mapped))


def side_sign(side: str) -> int:
    if side == "涨":
        return 1
    if side == "跌":
        return -1
    return 0


def pnl_pct(side: str, entry: float, exit_px: float) -> float:
    if entry <= 0 or exit_px <= 0:
        return 0.0
    ret = (exit_px - entry) / entry
    if side == "跌":
        return float(-ret)
    return float(ret)


def extract_votes(row: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ind in row.get("indicators") or []:
        name = str(ind.get("name") or "").strip()
        if not name:
            continue
        sig = int(np.sign(float(ind.get("signal") or 0)))
        out[name] = sig
    return out


def price_map(results: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in results or []:
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym or sym == "?":
            continue
        px = float(row.get("price") or row.get("entry") or 0)
        if px > 0:
            out[sym] = px
    return out


def settle_recommendations(
    pending: list[dict[str, Any]],
    results: list[dict[str, Any]],
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = now or utcnow()
    prices = price_map(results)
    still: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    for rec in pending or []:
        ts = rec.get("ts")
        age = hours_between(ts, now)
        if age >= PENDING_EXPIRE_HOURS:
            continue
        symbol = str(rec.get("symbol") or "").strip().upper()
        px = prices.get(symbol)
        needed = hold_hours_for(rec.get("interval"))
        if px is None or age < needed:
            still.append(rec)
            continue
        entry = float(rec.get("entry") or 0)
        side = str(rec.get("side") or "")
        change = pnl_pct(side, entry, px)
        hit = change > FEE_BUFFER
        closed.append(
            {
                **rec,
                "symbol": symbol,
                "exit": px,
                "pnl_pct": round(change, 6),
                "hit": hit,
                "closed_at": now.isoformat(),
                "hold_hours": round(age, 4),
            }
        )
    return still, closed


def update_weights_from_trades(
    weights: dict[str, float],
    trades: list[dict[str, Any]],
    now: datetime | None = None,
    lr: float = LEARNING_RATE,
    half_life: float = HALF_LIFE_HOURS,
) -> dict[str, float]:
    now = now or utcnow()
    names = [n for n in (weights or {}) if n]
    if not names or not trades:
        return dict(weights or {})
    updated = {n: max(float(weights.get(n) or 0), 1e-9) for n in names}
    for trade in trades:
        age = hours_between(trade.get("ts") or trade.get("closed_at"), now)
        recency = recency_weight(age, half_life)
        change = float(trade.get("pnl_pct") or 0)
        outcome = 1.0 if change > FEE_BUFFER else -1.0
        magnitude = min(max(abs(change) / 0.01, 0.25), 3.0)
        scale = lr * recency * outcome * magnitude
        side = side_sign(str(trade.get("side") or ""))
        if side == 0:
            continue
        votes = trade.get("signals") or {}
        for name, vote in votes.items():
            if name not in updated:
                continue
            vote_i = int(np.sign(float(vote or 0)))
            if vote_i == 0:
                continue
            agreed = 1.0 if vote_i == side else -1.0
            factor = 1.0 + max(-0.35, min(0.40, scale * agreed))
            updated[name] *= factor
    raw = np.array([updated[n] for n in names], dtype=np.float64)
    raw = np.clip(raw, 1e-9, None)
    raw = raw / raw.sum()
    cap = max(0.18, 3.0 / max(len(names), 1))
    floor = min(0.002, 0.25 / max(len(names), 1))
    raw = np.clip(raw, floor, cap)
    raw = raw / raw.sum()
    return {n: float(raw[i]) for i, n in enumerate(names)}


def regime_threshold(regime: str, threshold: float) -> float:
    if regime == "震荡":
        return threshold * 1.8
    if regime == "过渡":
        return threshold * 1.35
    return float(threshold)


def rescore_row(row: dict[str, Any], weights: dict[str, float], threshold: float = 0.18) -> dict[str, Any]:
    inds = list(row.get("indicators") or [])
    if not inds or row.get("error"):
        return row
    names = [str(i.get("name") or "") for i in inds]
    resolved = resolve_weights(names, weights, INITIAL_INDICATOR_SHARES)
    signals = np.array([float(i.get("signal") or 0) for i in inds], dtype=np.float64)
    strengths = np.array([float(i.get("strength") or 0) for i in inds], dtype=np.float64)
    w = np.array([resolved[n] for n in names], dtype=np.float64)
    score = composite_score(signals, strengths, w)
    regime = str(row.get("regime") or "过渡")
    effective = regime_threshold(regime, threshold)
    raw_decision = decision_from_score(score, threshold)
    decision = decision_from_score(score, effective)
    row["score"] = round(score, 4)
    row["raw_decision"] = raw_decision
    row["decision"] = decision
    row["confidence"] = round(min(1.0, abs(score) / max(effective, 1e-6)), 4)
    if decision == "涨":
        row["side"] = "long"
    elif decision == "跌":
        row["side"] = "short"
    else:
        row["side"] = "flat"
    for ind in inds:
        name = str(ind.get("name") or "")
        if name in resolved:
            ind["weight_optimized"] = round(resolved[name], 4)
    row["indicators"] = inds
    return row


def skip_symbols(
    pending: list[dict[str, Any]],
    closed: list[dict[str, Any]],
    now: datetime | None = None,
    loser_hours: float = SKIP_LOSER_HOURS,
) -> set[str]:
    now = now or utcnow()
    skip: set[str] = set()
    for rec in pending or []:
        sym = str(rec.get("symbol") or "").strip().upper()
        if sym:
            skip.add(sym)
    for trade in closed or []:
        if trade.get("hit"):
            continue
        if hours_between(trade.get("closed_at"), now) > loser_hours:
            continue
        sym = str(trade.get("symbol") or "").strip().upper()
        if sym:
            skip.add(sym)
    return skip


def recommend_count(
    closed: list[dict[str, Any]],
    pending: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    default: int = 3,
) -> int:
    """How many 涨/跌 calls to flag. Unfinished paper trades no longer shrink this."""
    del closed, pending, now
    return max(0, int(default))


def live_symbol_stats(closed: list[dict[str, Any]] | None) -> dict[str, tuple[float, int]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for trade in closed or []:
        sym = str(trade.get("symbol") or "").strip().upper()
        if not sym:
            continue
        buckets.setdefault(sym, []).append(trade)
    out: dict[str, tuple[float, int]] = {}
    for sym, trades in buckets.items():
        recent = trades[-8:]
        if not recent:
            continue
        hits = sum(1 for t in recent if t.get("hit"))
        out[sym] = (hits / len(recent), len(recent))
    return out


def attach_win_rates(
    results: list[dict[str, Any]],
    closed: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    live = live_symbol_stats(closed)
    for row in results or []:
        if row.get("error"):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        live_wr, live_n = live.get(sym, (None, 0))
        hist = row.get("hist_win_rate")
        if hist is None:
            hist = 0.5
        if live_n >= 2:
            wr, src = float(live_wr), f"纸面{live_n}笔"
        else:
            wr, src = float(hist), "近期K线同向命中"
        row["win_rate"] = round(wr, 4)
        row["win_rate_n"] = int(live_n)
        row["win_rate_label"] = f"{wr:.0%} · {src}"
        row["hist_win_rate"] = round(float(hist), 4)
    return results


def record_recommendations(
    results: list[dict[str, Any]],
    weights: dict[str, float] | None,
    interval: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or utcnow()
    pending: list[dict[str, Any]] = []
    for row in results or []:
        if not row.get("recommend"):
            continue
        decision = str(row.get("decision") or "")
        if decision not in ("涨", "跌"):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol == "?":
            continue
        entry = float(row.get("entry") or row.get("price") or 0)
        if entry <= 0:
            continue
        pending.append(
            {
                "symbol": symbol,
                "side": decision,
                "entry": entry,
                "ts": now.isoformat(),
                "interval": interval,
                "score": float(row.get("score") or 0),
                "signals": extract_votes(row),
                "weights": dict(weights or {}),
            }
        )
    return pending


def _summary(
    newly_closed: list[dict[str, Any]],
    closed: list[dict[str, Any]],
    n: int,
    skip: set[str],
    weights_changed: bool,
    now: datetime,
) -> str:
    recent = sorted(closed or [], key=lambda t: str(t.get("closed_at") or ""), reverse=True)[:8]
    if recent:
        hits = sum(1 for t in recent if t.get("hit"))
        wr = hits / len(recent)
        wr_txt = f"近{len(recent)}笔纸面胜率 {wr:.0%}"
    else:
        wr_txt = "尚无纸面成交，按各币近期K线胜率排序推荐"
    closed_txt = ""
    if newly_closed:
        bits = []
        for t in newly_closed[:4]:
            mark = "盈" if t.get("hit") else "亏"
            bits.append(f"{t.get('symbol')}{mark}{float(t.get('pnl_pct') or 0):+.1%}")
        closed_txt = "；刚结算 " + "、".join(bits)
    learn_txt = "，已按时间衰减回写指标权重" if weights_changed else ""
    rec_txt = f"，按胜率最多推荐 {n} 个（不考虑未到期持仓）"
    return f"{wr_txt}{closed_txt}{learn_txt}{rec_txt}"


def apply_live_feedback(
    results: list[dict[str, Any]],
    ledger: dict[str, Any] | None,
    weights: dict[str, float] | None,
    interval: str = "4h",
    now: datetime | None = None,
    threshold: float = 0.18,
) -> dict[str, Any]:
    now = now or utcnow()
    ledger = ledger or {}
    pending, newly_closed = settle_recommendations(list(ledger.get("pending") or []), results, now)
    closed = (list(ledger.get("closed") or []) + newly_closed)[-MAX_CLOSED:]
    new_weights = dict(weights or {})
    weights_changed = False
    if newly_closed and new_weights:
        new_weights = update_weights_from_trades(new_weights, newly_closed, now)
        weights_changed = True
        for row in results:
            rescore_row(row, new_weights, threshold)
    skip: set[str] = set()
    n = recommend_count(closed, pending, now)
    attach_win_rates(results, closed)
    mark_top_recommendations(results, n)
    existing = {str(p.get("symbol") or "").upper() for p in pending}
    for rec in record_recommendations(results, new_weights, interval, now):
        if rec["symbol"] not in existing:
            pending.append(rec)
            existing.add(rec["symbol"])
    pending = pending[-MAX_PENDING:]
    summary = _summary(newly_closed, closed, n, skip, weights_changed, now)
    for row in results:
        note = str(row.get("sim_note") or "").strip()
        extra = f"实盘回写：{summary}"
        row["sim_note"] = f"{note} · {extra}" if note else extra
    return {
        "results": results,
        "weights": new_weights,
        "weights_changed": weights_changed,
        "ledger": {
            "pending": pending,
            "closed": closed,
            "updated_at": now.isoformat(),
            "summary": summary,
        },
        "recommend_n": n,
        "recommend_skip": sorted(skip),
        "summary": summary,
        "closed_now": newly_closed,
    }
