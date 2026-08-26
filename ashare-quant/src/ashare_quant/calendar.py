"""A-share trading calendar (weekdays minus SSE/SZSE holidays)."""

from __future__ import annotations

from datetime import date, timedelta

# Major SSE/SZSE closed days 2022-2026. Weekend-only closures are handled separately.
# Source: exchange public holiday notices; keep conservative (closed if either exchange is closed).
_HOLIDAYS = {
    # 2022
    date(2022, 1, 3), date(2022, 1, 31), date(2022, 2, 1), date(2022, 2, 2),
    date(2022, 2, 3), date(2022, 2, 4), date(2022, 4, 4), date(2022, 4, 5),
    date(2022, 5, 2), date(2022, 5, 3), date(2022, 5, 4), date(2022, 6, 3),
    date(2022, 9, 12), date(2022, 10, 3), date(2022, 10, 4), date(2022, 10, 5),
    date(2022, 10, 6), date(2022, 10, 7),
    # 2023
    date(2023, 1, 2), date(2023, 1, 23), date(2023, 1, 24), date(2023, 1, 25),
    date(2023, 1, 26), date(2023, 1, 27), date(2023, 4, 5), date(2023, 5, 1),
    date(2023, 5, 2), date(2023, 5, 3), date(2023, 6, 22), date(2023, 6, 23),
    date(2023, 9, 29), date(2023, 10, 2), date(2023, 10, 3), date(2023, 10, 4),
    date(2023, 10, 5), date(2023, 10, 6),
    # 2024
    date(2024, 1, 1), date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
    date(2024, 2, 15), date(2024, 2, 16), date(2024, 4, 4), date(2024, 4, 5),
    date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3), date(2024, 6, 10),
    date(2024, 9, 16), date(2024, 9, 17), date(2024, 10, 1), date(2024, 10, 2),
    date(2024, 10, 3), date(2024, 10, 4), date(2024, 10, 7),
    # 2025
    date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 3), date(2025, 4, 4), date(2025, 5, 1),
    date(2025, 5, 2), date(2025, 5, 5), date(2025, 6, 2), date(2025, 10, 1),
    date(2025, 10, 2), date(2025, 10, 3), date(2025, 10, 6), date(2025, 10, 7),
    # 2026
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 2, 16), date(2026, 2, 17),
    date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20), date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 4), date(2026, 5, 5), date(2026, 6, 19),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 6),
    date(2026, 10, 7),
}


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in _HOLIDAYS


def next_trading_day(d: date) -> date:
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def shift_trading_days(d: date, n: int) -> date:
    """Shift n trading days. n>0 forward, n<0 backward. n=0 returns d if it is a session."""
    if n == 0:
        if is_trading_day(d):
            return d
        return next_trading_day(d) if n >= 0 else prev_trading_day(d)
    step = 1 if n > 0 else -1
    left = abs(n)
    cur = d
    while left:
        cur += timedelta(days=step)
        if is_trading_day(cur):
            left -= 1
    return cur


def prev_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    return cur


def trading_days(start: date, end: date) -> list[date]:
    out: list[date] = []
    cur = start
    while cur <= end:
        if is_trading_day(cur):
            out.append(cur)
        cur += timedelta(days=1)
    return out
