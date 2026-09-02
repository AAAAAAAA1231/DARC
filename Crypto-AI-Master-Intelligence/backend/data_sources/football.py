"""Football providers: football-data.org (key) and TheSportsDB (public demo key)."""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_str, parse_timestamp
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient

FOOTBALL_DATA_COMPETITIONS = {
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "PD": "La Liga",
}

THESPORTSDB_LEAGUES = {
    "4331": "Bundesliga",
    "4332": "Serie A",
    "4335": "La Liga",
}


class FootballDataProvider(DataProvider):
    name = "football_data"

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.yaml_config.get("providers", {}).get("football_data", {})
        self.base = str(cfg.get("base", "https://api.football-data.org/v4")).rstrip("/")
        self.api_key = settings.football_data_api_key
        headers = {"X-Auth-Token": self.api_key} if self.api_key else {}
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)), headers)

    def required_keys(self) -> list[str]:
        return ["FOOTBALL_DATA_API_KEY"]

    async def health(self) -> QualityEnvelope:
        if not self.api_key:
            return envelope(
                self.name,
                status=SourceStatus.MISSING_KEY,
                data_quality=DataQuality.MISSING,
                error="FOOTBALL_DATA_API_KEY is not set",
            )
        return await self.http.get_json(f"{self.base}/competitions", expect=dict)

    async def matches(self, code: str) -> QualityEnvelope:
        if not self.api_key:
            return envelope(
                self.name,
                status=SourceStatus.MISSING_KEY,
                data_quality=DataQuality.MISSING,
                error="FOOTBALL_DATA_API_KEY is not set",
            )
        raw = await self.http.get_json(f"{self.base}/competitions/{code}/matches", expect=dict)
        if not raw.ok:
            return raw
        matches = raw.payload.get("matches")
        if not isinstance(matches, list):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="matches missing")
        parsed = []
        for item in matches:
            if not isinstance(item, dict):
                continue
            home = (item.get("homeTeam") or {}).get("name") if isinstance(item.get("homeTeam"), dict) else None
            away = (item.get("awayTeam") or {}).get("name") if isinstance(item.get("awayTeam"), dict) else None
            score = item.get("score") if isinstance(item.get("score"), dict) else {}
            full = score.get("fullTime") if isinstance(score.get("fullTime"), dict) else {}
            kickoff = parse_timestamp(item.get("utcDate"))
            if not home or not away or not item.get("id"):
                continue
            parsed.append(
                {
                    "external_id": f"fd-{item['id']}",
                    "competition": FOOTBALL_DATA_COMPETITIONS.get(code, code),
                    "home": home,
                    "away": away,
                    "kickoff": kickoff.isoformat() if kickoff else None,
                    "status": optional_str(item, "status") or "SCHEDULED",
                    "home_goals": full.get("home"),
                    "away_goals": full.get("away"),
                    "source": self.name,
                }
            )
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK, confidence=1.0)


class TheSportsDbProvider(DataProvider):
    name = "thesportsdb"

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.yaml_config.get("providers", {}).get("thesportsdb", {})
        self.base = str(cfg.get("base", "https://www.thesportsdb.com/api/v1/json")).rstrip("/")
        self.api_key = settings.thesportsdb_api_key or "3"
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)))

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/{self.api_key}/lookup_all_teams.php", params={"id": 4331}, expect=dict)

    async def next_events(self, league_id: str) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/{self.api_key}/eventsnextleague.php",
            params={"id": league_id},
            expect=dict,
        )
        if not raw.ok:
            return raw
        events = raw.payload.get("events")
        if events is None:
            return envelope(
                self.name,
                status=SourceStatus.OK,
                payload=[],
                data_quality=DataQuality.MISSING,
                confidence=0.0,
                error="no events in response",
            )
        if not isinstance(events, list):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="events not list")
        return envelope(self.name, status=SourceStatus.OK, payload=_parse_tsdb(events, league_id), data_quality=DataQuality.OK, confidence=0.8)

    async def past_events(self, league_id: str) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/{self.api_key}/eventspastleague.php",
            params={"id": league_id},
            expect=dict,
        )
        if not raw.ok:
            return raw
        events = raw.payload.get("events")
        if not isinstance(events, list):
            return envelope(self.name, status=SourceStatus.OK, payload=[], data_quality=DataQuality.MISSING, confidence=0.0)
        return envelope(self.name, status=SourceStatus.OK, payload=_parse_tsdb(events, league_id), data_quality=DataQuality.OK, confidence=0.8)

    async def last_results(self, team_id: str) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/{self.api_key}/eventslast.php",
            params={"id": team_id},
            expect=dict,
        )
        if not raw.ok:
            return raw
        results = raw.payload.get("results")
        if not isinstance(results, list):
            return envelope(self.name, status=SourceStatus.OK, payload=[], data_quality=DataQuality.MISSING, confidence=0.0)
        return envelope(self.name, status=SourceStatus.OK, payload=_parse_tsdb(results, ""), data_quality=DataQuality.OK, confidence=0.8)


def _parse_tsdb(events: list[Any], league_id: str) -> list[dict[str, Any]]:
    competition = THESPORTSDB_LEAGUES.get(str(league_id), "UNKNOWN")
    parsed: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        home = optional_str(item, "strHomeTeam")
        away = optional_str(item, "strAwayTeam")
        eid = optional_str(item, "idEvent")
        if not home or not away or not eid:
            continue
        date = optional_str(item, "dateEvent")
        time = optional_str(item, "strTime") or "00:00:00"
        kickoff = parse_timestamp(f"{date}T{time}Z") if date else None
        home_goals = item.get("intHomeScore")
        away_goals = item.get("intAwayScore")
        try:
            home_goals_i = int(home_goals) if home_goals not in (None, "") else None
            away_goals_i = int(away_goals) if away_goals not in (None, "") else None
        except (TypeError, ValueError):
            home_goals_i = None
            away_goals_i = None
        parsed.append(
            {
                "external_id": f"tsdb-{eid}",
                "competition": optional_str(item, "strLeague") or competition,
                "home": home,
                "away": away,
                "kickoff": kickoff.isoformat() if kickoff else None,
                "status": "FINISHED" if home_goals_i is not None else "SCHEDULED",
                "home_goals": home_goals_i,
                "away_goals": away_goals_i,
                "home_id": optional_str(item, "idHomeTeam"),
                "away_id": optional_str(item, "idAwayTeam"),
                "source": "thesportsdb",
            }
        )
    return parsed
