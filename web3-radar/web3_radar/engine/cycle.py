from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

LAST_HALVING = datetime(2024, 4, 20, tzinfo=timezone.utc)
CYCLE_LEN_DAYS = 1461  # ~4 years
CN = timezone(timedelta(hours=8))


def _now(now: datetime | None = None) -> datetime:
    n = now or datetime.now(timezone.utc)
    return n if n.tzinfo else n.replace(tzinfo=timezone.utc)


def days_into_cycle(now: datetime | None = None) -> int:
    n = _now(now)
    days = int((n - LAST_HALVING).total_seconds() // 86400)
    if days < 0:
        return CYCLE_LEN_DAYS + days
    return days


def cycle_clock(now: datetime | None = None) -> dict[str, Any]:
    """Map the 4-year Bitcoin halving clock to a coarse bull/bear phase."""
    days = days_into_cycle(now)
    pos = days % CYCLE_LEN_DAYS
    if pos < 270:
        phase, market, cash = "减半后早期", "偏牛", "偏持币"
        bottom, top = False, False
        hold_days = 180
        note = "减半后常见积累转主升。适合分批持币，合约以大周期多单为主。"
    elif pos < 540:
        phase, market, cash = "主升浪", "牛市", "持币"
        bottom, top = False, False
        hold_days = 120
        note = "历史主升窗口。这一轮更适合拿高胜率多单，少做抄底。"
    elif pos < 750:
        phase, market, cash = "过热窗口", "牛末/转换", "减币持U"
        bottom, top = False, True
        hold_days = 30
        note = "减半后约 18–24 个月，历史上容易见顶。给出逃顶提示，合约缩短持仓。"
    elif pos < 1100:
        phase, market, cash = "熊市", "熊市", "持U"
        bottom, top = False, False
        hold_days = 45
        note = "主升过后进入熊段。优先持 U，合约以顺势空单或观望为主。"
    else:
        phase, market, cash = "熊末积累", "偏熊转牛", "分批持币"
        bottom, top = True, False
        hold_days = 150
        note = "接近下一轮减半。可研究抄底，但仓位要分批。"
    return {
        "days_into_cycle": days,
        "cycle_pos_days": pos,
        "phase": phase,
        "market": market,
        "cash_bias": cash,
        "bottom_signal": bottom,
        "top_signal": top,
        "hold_days": hold_days,
        "clock_note": note,
        "halving_at": LAST_HALVING.isoformat(),
        "next_halving_est": (LAST_HALVING + timedelta(days=CYCLE_LEN_DAYS)).date().isoformat(),
    }


def _ma_overlay(df: pd.DataFrame | None) -> dict[str, Any]:
    empty = {"price": None, "ma50": None, "ma200": None, "ret_90d": None, "trend": "数据不足"}
    if df is None or "close" not in df.columns or len(df) < 60:
        return empty
    close = df["close"].astype(float)
    px = float(close.iloc[-1])
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else px
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
    ret = None
    if len(close) >= 90 and close.iloc[-90] > 0:
        ret = float(close.iloc[-1] / close.iloc[-90] - 1)
    if px >= ma200 and ma50 >= ma200:
        trend = "均线偏多"
    elif px < ma200 and ma50 < ma200:
        trend = "均线偏空"
    else:
        trend = "均线纠缠"
    return {
        "price": round(px, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "ret_90d": None if ret is None else round(ret, 4),
        "trend": trend,
        "stretched_down": bool(ma200 and px < ma200 * 0.80),
        "stretched_up": bool(ret is not None and ret >= 0.80),
    }


def assess_cycle(df: pd.DataFrame | None = None, now: datetime | None = None) -> dict[str, Any]:
    clock = cycle_clock(now)
    ma = _ma_overlay(df)
    market = clock["market"]
    if ma.get("trend") == "均线偏空" and market in {"牛市", "偏牛"}:
        market = "转换偏空"
    elif ma.get("trend") == "均线偏多" and market in {"熊市", "偏熊转牛"}:
        market = "转换偏多"
    bottom = bool(clock["bottom_signal"] or (clock["market"] == "熊市" and ma.get("stretched_down")))
    top = bool(clock["top_signal"] or (clock["market"] in {"牛市", "牛末/转换"} and ma.get("stretched_up")))
    if bottom and top:
        bottom, top = False, True
    if top:
        action, cash = "逃顶", "持U"
        display, conversion = "牛熊转换", "逃顶：时钟/涨幅显示由牛转熊"
    elif bottom:
        action, cash = "抄底", "分批持币"
        display, conversion = "牛熊转换", "抄底：时钟/跌幅显示由熊转牛"
    elif "转换" in market:
        action, cash = "减仓观察", "减币持U" if "空" in market or "熊" in market else "分批持币"
        display, conversion = "牛熊转换", f"均线与四年时钟不一致（{market}）"
    elif "熊" in market:
        action, cash = "观望", "持U"
        display, conversion = "熊市", "四年减半时钟处于熊段，尚未给出转换信号"
    else:
        action, cash = "顺势持有", clock["cash_bias"]
        display, conversion = "牛市", "四年减半时钟处于牛段，尚未给出转换信号"
    side = "空" if ("熊" in display or "转熊" in conversion or top) and not bottom else "多"
    return {
        **clock,
        **ma,
        "market": display,
        "phase_market": market,
        "action": action,
        "cash_bias": cash,
        "preferred_side": side,
        "bottom_signal": bottom,
        "top_signal": top,
        "conversion_signal": conversion,
        "updated_at": _now(now).astimezone(CN).strftime("%Y-%m-%d %H:%M") + " 北京时间",
        "disclaimer": "四年减半周期叠加均线，仅供研究参考，不构成投资建议。",
        "summary": f"当前{display} · {clock['phase']} · {action} · 建议{cash}",
    }


def expected_yield(row: dict[str, Any]) -> float:
    try:
        entry = float(row.get("entry") or row.get("price") or 0)
        tp = float(row.get("take_profit") or 0)
        wr = float(row.get("win_rate") if row.get("win_rate") is not None else 0.5)
    except (TypeError, ValueError):
        return 0.0
    if entry <= 0 or tp <= 0:
        return 0.0
    return abs(tp - entry) / entry * max(0.0, min(wr, 1.0))


def pick_cycle_trade(cycle: dict[str, Any], rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Pick the contract whose side matches the cycle and whose expected yield is highest."""
    want = cycle.get("preferred_side")
    want_dec = "涨" if want == "多" else ("跌" if want == "空" else "")
    ranked: list[dict[str, Any]] = []
    for row in rows or []:
        if row.get("error") or str(row.get("decision") or "") not in {"涨", "跌"}:
            continue
        if want_dec and row.get("decision") != want_dec:
            continue
        y = expected_yield(row)
        if y <= 0:
            continue
        ranked.append({**row, "expected_yield": y})
    ranked.sort(key=lambda r: (float(r.get("expected_yield") or 0), abs(float(r.get("score") or 0))), reverse=True)
    if not ranked:
        return None
    best = ranked[0]
    hold = int(cycle.get("hold_days") or 30)
    if cycle.get("action") == "逃顶":
        hold = min(hold, 21)
    if cycle.get("action") == "抄底":
        hold = max(hold, 60)
    side_cn = "做多" if best.get("decision") == "涨" else "做空"
    return {
        "symbol": best.get("symbol"),
        "name": best.get("name") or "",
        "decision": best.get("decision"),
        "side": side_cn,
        "entry": best.get("entry"),
        "stop_loss": best.get("stop_loss"),
        "take_profit": best.get("take_profit"),
        "win_rate": best.get("win_rate"),
        "expected_yield": round(float(best["expected_yield"]), 4),
        "hold_days": hold,
        "how": f"{side_cn} {best.get('symbol')}，挂单 {best.get('entry')}，止损 {best.get('stop_loss')}，止盈 {best.get('take_profit')}",
        "why": f"本轮周期偏{cycle.get('market')}，在已分析合约里按预计收益率最高选出。预计持仓约 {hold} 天。",
    }


def fallback_btc_trade(cycle: dict[str, Any]) -> dict[str, Any]:
    """If contract analysis has not run, still give a cycle vehicle on BTCUSDT."""
    px = cycle.get("price")
    side = cycle.get("preferred_side") or "多"
    hold = int(cycle.get("hold_days") or 45)
    long_ = side != "空"
    entry = sl = tp = None
    if px:
        entry = round(float(px), 2)
        sl = round(entry * (0.92 if long_ else 1.08), 2)
        tp = round(entry * (1.28 if long_ else 0.78), 2)
    side_cn = "做多" if long_ else "做空"
    return {
        "symbol": "BTCUSDT",
        "name": "Bitcoin",
        "decision": "涨" if long_ else "跌",
        "side": side_cn,
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "win_rate": None,
        "expected_yield": None,
        "hold_days": hold,
        "how": f"{side_cn} BTCUSDT"
        + (f"，挂单 {entry}，止损 {sl}，止盈 {tp}" if entry else "（先看现价再挂单）"),
        "why": f"合约分析尚未给出更高收益标的，先按四年周期用 BTC 作为这一轮长持合约。预计持仓约 {hold} 天。",
    }


def attach_cycle_trade(cycle: dict[str, Any], rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    return pick_cycle_trade(cycle, rows) or fallback_btc_trade(cycle)
