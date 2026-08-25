from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
import csv
import io

from .. import cache
from ..config import LEAGUES, SEASONS, SECOND_DIV_SEASONS, League
from ..http_client import HttpError, fetch_text
from ..names import canonical_name


FD_BASE = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"


@dataclass
class Match:
    league: str
    date: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    ht_home: int | None = None
    ht_away: int | None = None
    hxg: float | None = None
    axg: float | None = None
    market_h: float | None = None
    market_d: float | None = None
    market_a: float | None = None
    division: str = ""

    @property
    def result(self) -> str:
        if self.home_goals > self.away_goals:
            return "H"
        if self.home_goals < self.away_goals:
            return "A"
        return "D"


def _parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _to_int(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_csv(text: str, league_key: str, division: str) -> list[Match]:
    rows = list(csv.DictReader(io.StringIO(text)))
    matches: list[Match] = []
    for row in rows:
        date = _parse_date(row.get("Date") or "")
        home = canonical_name(row.get("HomeTeam") or "")
        away = canonical_name(row.get("AwayTeam") or "")
        hg = _to_int(row.get("FTHG"))
        ag = _to_int(row.get("FTAG"))
        if not date or not home or not away or hg is None or ag is None:
            continue
        matches.append(
            Match(
                league=league_key,
                date=date,
                home=home,
                away=away,
                home_goals=hg,
                away_goals=ag,
                ht_home=_to_int(row.get("HTHG")),
                ht_away=_to_int(row.get("HTAG")),
                hxg=_to_float(row.get("HxG")),
                axg=_to_float(row.get("AxG")),
                market_h=_to_float(row.get("AvgH") or row.get("B365H") or row.get("PSH")),
                market_d=_to_float(row.get("AvgD") or row.get("B365D") or row.get("PSD")),
                market_a=_to_float(row.get("AvgA") or row.get("B365A") or row.get("PSA")),
                division=division,
            )
        )
    return matches


def _download(season: str, code: str) -> str | None:
    url = FD_BASE.format(season=season, code=code)
    cache_key = f"fd:{season}:{code}"
    cached = cache.get_json(cache_key, ttl_seconds=12 * 3600)
    if isinstance(cached, str) and cached:
        return cached
    try:
        text = fetch_text(url, timeout=25)
    except HttpError:
        return None
    if "Div" not in text.split("\n", 1)[0]:
        return None
    cache.set_json(cache_key, text)
    return text


def load_league_history(league: League, include_second_div: bool = True) -> list[Match]:
    matches: list[Match] = []
    for season in SEASONS:
        text = _download(season, league.fd_code)
        if text:
            matches.extend(_parse_csv(text, league.key, league.fd_code))
    if include_second_div:
        for season in SECOND_DIV_SEASONS:
            text = _download(season, league.fd_code_2)
            if text:
                matches.extend(_parse_csv(text, league.key, league.fd_code_2))
    matches.sort(key=lambda m: m.date)
    # 去重：同一天同对阵
    uniq: dict[tuple, Match] = {}
    for m in matches:
        uniq[(m.date.date().isoformat(), m.home, m.away)] = m
    return sorted(uniq.values(), key=lambda m: m.date)


def load_all_history() -> dict[str, list[Match]]:
    return {key: load_league_history(league) for key, league in LEAGUES.items()}


def matches_to_dicts(matches: list[Match]) -> list[dict[str, Any]]:
    out = []
    for m in matches:
        d = asdict(m)
        d["date"] = m.date.isoformat()
        out.append(d)
    return out
