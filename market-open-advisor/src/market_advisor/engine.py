"""Fetch → fit → 10B-limit stats → verify MC → advice cards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .advice import Advice, DISCLAIMER, build_advice
from .model import DEFAULT_VERIFY_SIMS, fit_model, verify_against_limit
from .quotes import BarSeries, HttpGet, QuoteError, http_get_json, load_all


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


def analyze_series(
    series: BarSeries,
    opened_at: datetime,
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
) -> Advice:
    model = fit_model(series.closes, series.dates)
    limit, verify, err = verify_against_limit(model.returns, n_sims=n_verify, seed=seed)
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
    )


def run_report(
    http_get: HttpGet = http_get_json,
    now: datetime | None = None,
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
    progress: Callable[[str], None] | None = None,
) -> Report:
    opened_at = now or datetime.now(timezone.utc).astimezone()
    if progress:
        progress("正在拉取各交易场所公开行情…")
    series_list = load_all(http_get=http_get, now=opened_at)
    items: list[Advice] = []
    errors: list[str] = []
    for series in series_list:
        if progress:
            progress(f"正在拟合 {series.market.name} 并做 100 亿次模拟极限 + 蒙特卡洛核验…")
        try:
            items.append(analyze_series(series, opened_at, n_verify=n_verify, seed=seed))
        except Exception as exc:  # noqa: BLE001 — surface per-venue failure in the report
            errors.append(f"{series.market.name}: {exc}")
    if not items:
        raise QuoteError("没有生成任何场所的建议：" + "；".join(errors))
    return Report(
        opened_at=opened_at.isoformat(timespec="seconds"),
        disclaimer=DISCLAIMER,
        items=items,
        errors=errors,
    )
