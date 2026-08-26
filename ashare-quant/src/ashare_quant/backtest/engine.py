"""Close-signal / next-open execution backtest with A-share constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from ..calendar import next_trading_day
from ..config import Action, AppConfig, Board, LimitStatus
from ..ensemble.weighting import compute_ensemble_panel
from ..indicators import atr
from ..market.costs import apply_slippage_price, slippage_rate, trade_cost
from ..market.rules import classify_limit, fill_probability, limit_ratio, round_lot
from ..market.t_plus_one import Book
from ..risk.atr_stops import atr_bands
from ..risk.position import BookState, size_long
from ..universe.filter import filter_universe
from .metrics import summarize_equity


@dataclass
class OpenPos:
    symbol: str
    qty: int
    entry: float
    stop: float
    take: float
    board: str
    entry_date: date
    costs: float = 0.0


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: pd.DataFrame
    daily: pd.DataFrame
    metrics: dict
    weights_last: dict[str, float] = field(default_factory=dict)
    ideas_last: pd.DataFrame = field(default_factory=pd.DataFrame)
    panel: pd.DataFrame = field(default_factory=pd.DataFrame)
    selected_symbols: list[str] = field(default_factory=list)


def _index_bars(bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for sym, g in bars.groupby("symbol", sort=False):
        gg = g.sort_values("date").copy()
        gg["date"] = pd.to_datetime(gg["date"]).dt.normalize()
        out[sym] = gg.set_index("date")
    return out


def _session_row(by_sym: dict[str, pd.DataFrame], symbol: str, ts: pd.Timestamp) -> pd.Series | None:
    g = by_sym.get(symbol)
    if g is None or ts not in g.index:
        return None
    return g.loc[ts]


def _limit_status_row(row: pd.Series, cfg: AppConfig) -> LimitStatus:
    raw = row.get("limit_status")
    if isinstance(raw, str) and raw in LimitStatus._value2member_map_:
        return LimitStatus(raw)
    board = Board(row["board"]) if "board" in row and pd.notna(row["board"]) else Board.SSE_MAIN
    listing = pd.Timestamp(row["listing_date"]).date() if pd.notna(row.get("listing_date")) else None
    listing_days = (row.name.date() - listing).days if listing else 1000
    ratio = limit_ratio(board, is_st=bool(row.get("is_st", False)), listing_days=listing_days, cfg=cfg.market)
    prev = float(row["close"])  # fallback
    return classify_limit(float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), prev, ratio)


def run_backtest(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    *,
    params: dict | None = None,
    symbols: list[str] | None = None,
    start=None,
    end=None,
    slippage_mult: float = 1.0,
    fill_jitter: float = 0.0,
    rng: np.random.Generator | None = None,
    rebalance_universe_every: int = 21,
) -> BacktestResult:
    rng = rng or np.random.default_rng(cfg.seed)
    work = bars.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    if start is not None:
        work = work[work["date"] >= pd.Timestamp(start)]
    if end is not None:
        work = work[work["date"] <= pd.Timestamp(end)]
    sessions = list(pd.to_datetime(work["date"].drop_duplicates().sort_values()))
    if len(sessions) < 40:
        empty_eq = pd.Series(dtype=float)
        return BacktestResult(empty_eq, pd.DataFrame(), pd.DataFrame(), summarize_equity(empty_eq))

    # Freeze universe at first eligible date then refresh periodically (no daily full scan).
    selected: list[str] = list(symbols) if symbols else []
    uni_asof = sessions[min(len(sessions) - 1, cfg.signals.lookback)]
    if not selected:
        uni = filter_universe(bars, meta, uni_asof, cfg)
        selected = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni else []
        if not selected:
            selected = uni.loc[uni["eligible"] == True, "symbol"].head(cfg.universe.max_names).tolist() if "eligible" in uni else []
    if not selected:
        empty_eq = pd.Series([cfg.risk.initial_cash], index=sessions[:1])
        return BacktestResult(empty_eq, pd.DataFrame(), pd.DataFrame(), summarize_equity(empty_eq))

    pool = work[work["symbol"].isin(selected)].copy()
    panel = compute_ensemble_panel(pool, cfg, params)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    score_map: dict[tuple[str, pd.Timestamp], float] = {}
    weight_cols = [c for c in panel.columns if c.startswith("w_")]
    last_w = {c[2:]: float(panel.iloc[-1][c]) for c in weight_cols} if len(panel) else {}
    for row in panel.itertuples(index=False):
        score_map[(row.symbol, row.date)] = float(row.ensemble)

    by_sym = _index_bars(pool)
    book = Book()
    cash = float(cfg.risk.initial_cash)
    positions: dict[str, OpenPos] = {}
    pending_buys: dict[str, dict] = {}
    pending_exits: dict[str, str] = {}
    trades: list[dict] = []
    equity_pts = []
    nav = cash

    warmup = max(cfg.signals.lookback, 40)

    def mark_nav(ts: pd.Timestamp) -> float:
        mtm = cash
        for sym, pos in positions.items():
            row = _session_row(by_sym, sym, ts)
            px = float(row["close"]) if row is not None else pos.entry
            mtm += pos.qty * px
        return mtm

    def current_book_state(ts: pd.Timestamp) -> BookState:
        mtm = mark_nav(ts)
        gross = 0.0
        board_exp: dict[str, float] = {}
        weights: dict[str, float] = {}
        for sym, pos in positions.items():
            row = _session_row(by_sym, sym, ts)
            px = float(row["close"]) if row is not None else pos.entry
            val = pos.qty * px
            gross += val
            board_exp[pos.board] = board_exp.get(pos.board, 0.0) + val
            weights[sym] = val / mtm if mtm else 0.0
        return BookState(nav=mtm, gross_exposure=gross, names_held=len(positions), board_exposure=board_exp, weight_by_symbol=weights)

    def execute_sell(sym: str, pos: OpenPos, session: date, ts: pd.Timestamp, row: pd.Series, reason: str) -> None:
        nonlocal cash
        avail = book.available_qty(sym, session)
        qty = min(pos.qty, avail)
        if qty <= 0:
            pending_exits[sym] = reason
            return
        status = _limit_status_row(row, cfg)
        if status in (LimitStatus.SEALED_DOWN, LimitStatus.TOUCH_DOWN) and reason != "forced":
            fp = fill_probability("sell", status, cfg=cfg.market, order_volume=qty, day_volume=float(row["volume"]))
            fp = float(np.clip(fp + rng.normal(0, fill_jitter), 0, 1))
            if rng.random() > fp:
                pending_exits[sym] = reason
                return
        atr_pct = None
        g = by_sym[sym]
        hist = g.loc[:ts]
        if len(hist) > 5:
            a = float(atr(hist["high"], hist["low"], hist["close"], cfg.risk.atr_window).iloc[-1])
            atr_pct = a / float(row["open"]) if row["open"] else None
        rate = slippage_rate(atr_pct, cfg.costs, slippage_mult)
        px = apply_slippage_price(float(row["open"]), "sell", rate)
        if reason == "stop":
            px = min(px, pos.stop)
        if reason == "take":
            px = max(px, pos.take)
        px = max(0.01, px)
        filled = book.sell(sym, qty, session)
        if filled <= 0:
            pending_exits[sym] = reason
            return
        notional = filled * px
        cost = trade_cost(notional, "sell", cfg.costs, atr_pct=atr_pct, slippage_mult=slippage_mult)
        cash += notional - cost["total"]
        pnl = (px - pos.entry) * filled - cost["total"] - pos.costs * (filled / pos.qty)
        trades.append(
            {
                "date": session,
                "symbol": sym,
                "side": "sell",
                "qty": filled,
                "price": px,
                "notional": notional,
                "pnl": pnl,
                "reason": reason,
                "cost": cost["total"],
            }
        )
        pos.qty -= filled
        if pos.qty <= 0:
            positions.pop(sym, None)
            pending_exits.pop(sym, None)
        else:
            pending_exits.pop(sym, None)

    ideas_last = pd.DataFrame()

    for i, ts in enumerate(sessions):
        session = ts.date()
        if i > 0 and i % rebalance_universe_every == 0 and symbols is None:
            uni = filter_universe(bars, meta, ts, cfg)
            new_sel = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni else selected
            if new_sel:
                selected = sorted(set(selected) | set(new_sel))

        # Exits first (open of session), T+1 respected via available_qty
        for sym in list(positions.keys()):
            pos = positions[sym]
            row = _session_row(by_sym, sym, ts)
            if row is None or bool(row.get("suspended", False)):
                continue
            reason = None
            if pending_exits.get(sym):
                reason = pending_exits[sym]
            elif float(row["low"]) <= pos.stop:
                reason = "stop"
            elif float(row["high"]) >= pos.take:
                reason = "take"
            else:
                sc = score_map.get((sym, ts), score_map.get((sym, sessions[i - 1] if i else ts), 0.0))
                if sc <= cfg.signals.exit_threshold:
                    reason = "signal_exit"
            if reason:
                execute_sell(sym, pos, session, ts, row, reason)

        # Pending buys from prior close (T+1 execution)
        for sym, order in list(pending_buys.items()):
            row = _session_row(by_sym, sym, ts)
            pending_buys.pop(sym, None)
            if row is None or bool(row.get("suspended", False)):
                continue
            status = _limit_status_row(row, cfg)
            qty = int(order["qty"])
            fp = fill_probability("buy", status, cfg=cfg.market, order_volume=qty, day_volume=float(row["volume"]))
            fp = float(np.clip(fp + rng.normal(0, fill_jitter), 0, 1))
            if rng.random() > fp:
                continue
            hist = by_sym[sym].loc[:ts]
            atr_pct = None
            if len(hist) > 5:
                a = float(atr(hist["high"], hist["low"], hist["close"], cfg.risk.atr_window).iloc[-1])
                atr_pct = a / float(row["open"]) if row["open"] else None
            rate = slippage_rate(atr_pct, cfg.costs, slippage_mult)
            px = apply_slippage_price(float(row["open"]), "buy", rate)
            notional = qty * px
            cost = trade_cost(notional, "buy", cfg.costs, atr_pct=atr_pct, slippage_mult=slippage_mult)
            if cash < notional + cost["total"]:
                continue
            cash -= notional + cost["total"]
            sellable = next_trading_day(session)
            book.buy(sym, qty, session, sellable)
            bands = atr_bands(hist["high"], hist["low"], hist["close"], cfg.risk, entry=px)
            positions[sym] = OpenPos(
                symbol=sym,
                qty=qty,
                entry=px,
                stop=bands["stop_loss"],
                take=bands["take_profit"],
                board=str(row.get("board", "sse_main")),
                entry_date=session,
                costs=cost["total"],
            )
            trades.append(
                {
                    "date": session,
                    "symbol": sym,
                    "side": "buy",
                    "qty": qty,
                    "price": px,
                    "notional": notional,
                    "pnl": 0.0,
                    "reason": "signal",
                    "cost": cost["total"],
                    "stop": bands["stop_loss"],
                    "take": bands["take_profit"],
                    "earliest_exit": sellable,
                }
            )

        nav = mark_nav(ts)
        equity_pts.append({"date": ts, "equity": nav, "cash": cash, "n_pos": len(positions)})

        # After close: new ideas (no lookahead: scores at ts use data <= ts)
        if i < warmup or i >= len(sessions) - 1:
            continue
        state = current_book_state(ts)
        ranked: list[tuple[float, str]] = []
        for sym in selected:
            sc = score_map.get((sym, ts))
            if sc is None:
                continue
            ranked.append((sc, sym))
        ranked.sort(reverse=True)
        new_ideas = []
        for sc, sym in ranked:
            row = _session_row(by_sym, sym, ts)
            if row is None or bool(row.get("suspended", False)):
                continue
            hist = by_sym[sym].loc[:ts]
            if len(hist) < warmup:
                continue
            status = _limit_status_row(row, cfg)
            action = Action.NO_TRADE
            note = []
            if status == LimitStatus.SEALED_UP:
                note.append("涨停封板无法买入")
            if sc >= cfg.signals.long_threshold and sym not in positions and sym not in pending_buys:
                bands = atr_bands(hist["high"], hist["low"], hist["close"], cfg.risk)
                sized = size_long(
                    cfg=cfg,
                    nav=state.nav,
                    price=float(row["close"]),
                    stop_distance_pct=bands["stop_distance_pct"],
                    adv_shares=float(hist["volume"].tail(20).mean()),
                    board=str(row.get("board", "sse_main")),
                    book=state,
                    already_held=False,
                )
                if sized.action == Action.BUY and status != LimitStatus.SEALED_UP:
                    pending_buys[sym] = {"qty": sized.shares, "signal_date": session}
                    # reserve cash/exposure so subsequent names see the cap
                    state.gross_exposure += sized.notional
                    state.names_held += 1
                    bk = str(row.get("board", "sse_main"))
                    state.board_exposure[bk] = state.board_exposure.get(bk, 0.0) + sized.notional
                    action = Action.BUY
                    note.append("T日收盘信号，T+1开盘委托")
                else:
                    note.extend(sized.reasons)
            elif sc <= cfg.signals.exit_threshold and sym in positions:
                pending_exits[sym] = "signal_exit"
                action = Action.EXIT
            elif sym in positions:
                action = Action.HOLD
            new_ideas.append(
                {
                    "symbol": sym,
                    "date": session,
                    "score": sc,
                    "action": action.value,
                    "note": ";".join(note),
                }
            )
        ideas_last = pd.DataFrame(new_ideas)

    equity = pd.Series({r["date"]: r["equity"] for r in equity_pts}, name="equity").sort_index()
    trades_df = pd.DataFrame(trades)
    daily = pd.DataFrame(equity_pts)
    metrics = summarize_equity(equity, trades_df)
    return BacktestResult(
        equity=equity,
        trades=trades_df,
        daily=daily,
        metrics=metrics,
        weights_last=last_w,
        ideas_last=ideas_last,
        panel=panel,
        selected_symbols=selected,
    )
