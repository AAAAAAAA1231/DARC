"""Fetch → fit → 10B-limit stats → verify MC → per-venue and per-stock advice."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .advice import Advice, DISCLAIMER, build_advice
from .model import DEFAULT_VERIFY_SIMS, SimulationStats, fit_model, infinite_bootstrap_stats, verify_against_limit
from .quotes import BarSeries, HttpGet, QuoteError, fetch_by_ids, http_get_json, load_all
from .universe import DEFAULT_PER_MARKET, Instrument, list_instruments


@dataclass
class Report:
    opened_at: str
    disclaimer: str
    items: list[Advice]
    errors: list[str]

    def to_dict(self) -> dict:
        return {
            "opened_at": self.opened_at,
            "disclaimer": self.disclaimer,
            "items": [item.to_dict() for item in self.items],
            "errors": self.errors,
        }


def _skipped_verify() -> SimulationStats:
    return SimulationStats(
        expected_return=0.0,
        p_up=0.0,
        p05=0.0,
        p50=0.0,
        p95=0.0,
        sigma=0.0,
        n_sims=0,
        source="skipped",
    )


def analyze_series(
    series: BarSeries,
    opened_at: datetime,
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
    is_index: bool = True,
) -> Advice:
    model = fit_model(series.closes, series.dates)
    if n_verify and n_verify > 0:
        limit, verify, err = verify_against_limit(model.returns, n_sims=n_verify, seed=seed)
    else:
        limit = infinite_bootstrap_stats(model.returns)
        verify = _skipped_verify()
        err = 0.0
    return build_advice(
        market=series.market,
        index_name=series.name,
        model=model,
        limit=limit,
        verify=verify,
        verify_error=err,
        opened_at=opened_at,
        spot=series.spot,
        change_pct=series.change_pct,
        data_source=series.source,
        symbol=series.symbol,
        is_index=is_index,
    )


def _fetch_one(inst: Instrument, http_get: HttpGet) -> BarSeries:
    return fetch_by_ids(
        inst.market,
        inst.name,
        inst.symbol,
        inst.sina,
        inst.tencent,
        inst.yahoo,
        http_get=http_get,
    )


def load_stock_series(
    instruments: list[Instrument],
    http_get: HttpGet,
    workers: int = 12,
) -> tuple[list[BarSeries], list[str]]:
    series: list[BarSeries] = []
    errors: list[str] = []
    if not instruments:
        return series, errors
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(_fetch_one, inst, http_get): inst for inst in instruments}
        for fut in as_completed(futs):
            inst = futs[fut]
            try:
                series.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{inst.market.name} {inst.symbol} {inst.name}: {exc}")
    series.sort(key=lambda item: (item.market.key, item.symbol))
    return series, errors


def run_report(
    http_get: HttpGet = http_get_json,
    now: datetime | None = None,
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
    progress: Callable[[str], None] | None = None,
    per_market: int = DEFAULT_PER_MARKET,
    stock_verify: int = 0,
) -> Report:
    opened_at = now or datetime.now(timezone.utc).astimezone()
    if progress:
        progress("正在拉取各交易场所公开行情…")
    series_list = load_all(http_get=http_get, now=opened_at)
    items: list[Advice] = []
    errors: list[str] = []
    for series in series_list:
        if progress:
            progress(f"正在拟合 {series.market.name} 指数并计算 100 亿次模拟极限…")
        try:
            venue = analyze_series(series, opened_at, n_verify=n_verify, seed=seed, is_index=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{series.market.name}: {exc}")
            continue
        if progress:
            progress(f"正在拉取 {series.market.name} 成分/活跃个股列表…")
        instruments = list_instruments(series.market, http_get=http_get, limit=per_market)
        if progress:
            progress(f"{series.market.name} 共 {len(instruments)} 只股票，正在拉取K线并逐只计算建议…")
        stock_series, stock_errors = load_stock_series(instruments, http_get=http_get)
        errors.extend(stock_errors)
        stocks: list[Advice] = []
        for bars in stock_series:
            try:
                stocks.append(
                    analyze_series(
                        bars,
                        opened_at,
                        n_verify=stock_verify,
                        seed=seed,
                        is_index=False,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{series.market.name} {bars.symbol} {bars.name}: {exc}")
        rank = {"偏多": 0, "观望": 1, "偏空": 2}
        stocks.sort(key=lambda row: (rank.get(row.action, 9), -row.expected_return))
        venue.stocks = stocks
        items.append(venue)
    if not items:
        raise QuoteError("没有生成任何场所的建议：" + "；".join(errors))
    return Report(
        opened_at=opened_at.isoformat(timespec="seconds"),
        disclaimer=DISCLAIMER,
        items=items,
        errors=errors,
    )
