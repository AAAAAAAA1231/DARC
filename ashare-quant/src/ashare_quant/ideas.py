"""T-close idea sheet: ensemble score, ATR bands, confidence interval, T+1 calendar."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .calendar import next_trading_day
from .config import Action, AppConfig, Board, LimitStatus
from .ensemble.weighting import blend, compute_ensemble_panel, default_equal_weights
from .market.costs import trade_cost
from .market.rules import classify_limit, limit_ratio
from .risk.atr_stops import atr_bands
from .risk.confidence import residual_bootstrap_ci
from .risk.position import BookState, size_long
from .universe.boards import board_cn
from .universe.filter import filter_universe


def generate_ideas(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    asof,
    *,
    panel: pd.DataFrame | None = None,
    book: BookState | None = None,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    asof_ts = pd.Timestamp(asof).normalize()
    asof_d = asof_ts.date()
    uni = filter_universe(bars, meta, asof_ts, cfg)
    picked = uni[uni.get("selected", False) == True] if "selected" in uni.columns else uni[uni.get("eligible", False) == True]
    symbols = picked["symbol"].tolist()
    if not symbols:
        return pd.DataFrame()

    pool = bars[(bars["symbol"].isin(symbols)) & (pd.to_datetime(bars["date"]) <= asof_ts)].copy()
    if panel is None:
        panel = compute_ensemble_panel(pool, cfg)
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    today = panel[panel["date"] == asof_ts]
    if today.empty:
        last = panel["date"].max()
        today = panel[panel["date"] == last]
        asof_d = pd.Timestamp(last).date()

    exec_d = next_trading_day(asof_d)
    earliest_exit = next_trading_day(exec_d)  # buy T+1, sell T+2

    if book is None:
        book = BookState(
            nav=cfg.risk.initial_cash,
            gross_exposure=0.0,
            names_held=0,
            board_exposure={},
            weight_by_symbol={},
        )
    w_cols = [c for c in today.columns if c.startswith("w_")]
    rows = []
    for rec in today.itertuples(index=False):
        sym = rec.symbol
        hist = pool[pool["symbol"] == sym].sort_values("date")
        if hist.empty:
            continue
        last = hist.iloc[-1]
        board = Board(str(last.get("board", "sse_main")))
        scores = {m.value: float(getattr(rec, m.value, 0.0)) for m in cfg.ensemble.methods}
        if weights is None and w_cols:
            w = {c[2:]: float(getattr(rec, c)) for c in w_cols}
        else:
            w = weights or default_equal_weights(cfg)
        score = float(rec.ensemble) if hasattr(rec, "ensemble") else blend(scores, w)
        bands = atr_bands(hist["high"], hist["low"], hist["close"], cfg.risk)
        listing = pd.Timestamp(last["listing_date"]).date() if pd.notna(last.get("listing_date")) else asof_d
        ratio = limit_ratio(board, is_st=bool(last.get("is_st", False)), listing_days=(asof_d - listing).days, cfg=cfg.market)
        prev = float(hist["close"].iloc[-2]) if len(hist) > 1 else float(last["close"])
        status = last.get("limit_status") or classify_limit(
            float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"]), prev, ratio
        )
        if not isinstance(status, LimitStatus):
            status = LimitStatus(str(status)) if str(status) in LimitStatus._value2member_map_ else LimitStatus.NORMAL

        flags: list[str] = []
        action = Action.NO_TRADE
        sized_shares = 0
        notional = 0.0
        if bool(last.get("suspended", False)):
            flags.append("停牌")
        if status == LimitStatus.SEALED_UP:
            flags.append("一字涨停，买入成交概率≈0")
        if status == LimitStatus.SEALED_DOWN:
            flags.append("一字跌停，卖出成交概率≈0")

        if score >= cfg.signals.long_threshold and not flags:
            sized = size_long(
                cfg=cfg,
                nav=book.nav,
                price=float(last["close"]),
                stop_distance_pct=float(bands["stop_distance_pct"]),
                adv_shares=float(hist["volume"].tail(20).mean()),
                board=board,
                book=book,
                already_held=False,
            )
            if sized.action == Action.BUY:
                action = Action.BUY
                sized_shares = sized.shares
                notional = sized.notional
                book.gross_exposure += notional
                book.names_held += 1
                book.board_exposure[board.value] = book.board_exposure.get(board.value, 0.0) + notional
                flags.extend(sized.reasons)
            else:
                flags.extend(sized.reasons)
        elif score <= cfg.signals.exit_threshold:
            action = Action.EXIT
            flags.append("集成分低于退出阈值")
        elif abs(score) < cfg.signals.long_threshold:
            flags.append("分值未达开仓阈值，观望")

        cost = trade_cost(notional or float(last["close"]) * cfg.market.lot_size, "buy", cfg.costs, atr_pct=bands["atr_pct"])
        sub = panel[panel["symbol"] == sym]
        ci = residual_bootstrap_ci(
            sub["fwd_ret"] if "fwd_ret" in sub.columns else pd.Series(dtype=float),
            sub["ensemble"] if "ensemble" in sub.columns else pd.Series(dtype=float),
            score,
            levels=cfg.risk.ci_levels,
            n_paths=cfg.risk.bootstrap_paths,
            seed=cfg.seed + (int(sym) % 1000 if str(sym).isdigit() else 0),
        )
        rows.append(
            {
                "symbol": sym,
                "name": last.get("name", ""),
                "board": board.value,
                "board_cn": board_cn(board),
                "signal_date": asof_d.isoformat(),
                "execute_date": exec_d.isoformat(),
                "earliest_exit_date": earliest_exit.isoformat(),
                "close": float(last["close"]),
                "score": round(score, 4),
                "action": action.value,
                "shares": sized_shares,
                "notional": round(notional, 2),
                "stop_loss": bands["stop_loss"],
                "take_profit": bands["take_profit"],
                "atr": round(bands["atr"], 3),
                "stop_k": round(bands["stop_k"], 3),
                "take_k": round(bands["take_k"], 3),
                "ci_p10": round(ci.get("p10", 0.0), 4),
                "ci_p50": round(ci.get("p50", ci.get("expected", 0.0)), 4),
                "ci_p90": round(ci.get("p90", 0.0), 4),
                "cost_bps": round(cost["cost_bps"], 2),
                "limit_status": status.value,
                "flags": ";".join(flags),
                **{f"s_{k}": round(v, 4) for k, v in scores.items()},
                **{f"w_{k}": round(w.get(k, 0.0), 4) for k in scores},
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["action", "score"], ascending=[True, False]).reset_index(drop=True)
