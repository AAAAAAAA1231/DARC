from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .. import cache
from ..config import LEAGUES, League
from ..http_client import HttpError, fetch_json
from ..names import canonical_name, display_cn


ESPN_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/soccer"


def _espn(path: str, ttl: float) -> Any:
    url = f"{ESPN_BASE}/{path}"
    cached = cache.get_json(f"espn:{path}", ttl)
    if cached is not None:
        return cached
    data = fetch_json(url)
    cache.set_json(f"espn:{path}", data)
    return data


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def american_to_prob(ml: float | int | str | None) -> float | None:
    if ml is None:
        return None
    if isinstance(ml, str):
        text = ml.replace(",", "").strip()
        if not text:
            return None
        try:
            ml = float(text)
        except ValueError:
            return None
    try:
        ml = float(ml)
    except (TypeError, ValueError):
        return None
    if ml == 0:
        return None
    if ml > 0:
        p = 100.0 / (ml + 100.0)
    else:
        p = abs(ml) / (abs(ml) + 100.0)
    return max(0.01, min(0.98, p))


def _normalize_odds(h: float | None, d: float | None, a: float | None) -> tuple[float, float, float] | None:
    if h is None or d is None or a is None:
        return None
    s = h + d + a
    if s <= 0:
        return None
    return h / s, d / s, a / s


def _side_odds(block: Any) -> float | None:
    if not isinstance(block, dict):
        return american_to_prob(block)
    for key in ("close", "open", "current"):
        nested = block.get(key)
        if isinstance(nested, dict) and nested.get("odds") is not None:
            return american_to_prob(nested.get("odds"))
        if nested is not None and not isinstance(nested, dict):
            return american_to_prob(nested)
    return american_to_prob(block.get("moneyLine") or block.get("odds"))


def _extract_moneyline(odds: Any) -> tuple[float, float, float] | None:
    if not odds:
        return None
    items = odds if isinstance(odds, list) else [odds]
    for item in items:
        if not isinstance(item, dict):
            continue
        home_ml = away_ml = draw_ml = None
        # 旧结构
        home_ml = _side_odds(item.get("homeTeamOdds") or {})
        away_ml = _side_odds(item.get("awayTeamOdds") or {})
        draw_ml = _side_odds(item.get("drawOdds") or {})
        # ESPN soccer: moneyline.home.close.odds = "+180"
        ml = item.get("moneyline") or item.get("moneyLine") or {}
        if isinstance(ml, dict):
            home_ml = home_ml or _side_odds(ml.get("home") or {})
            away_ml = away_ml or _side_odds(ml.get("away") or {})
            draw_ml = draw_ml or _side_odds(ml.get("draw") or {})
        found = _normalize_odds(home_ml, draw_ml, away_ml)
        if found:
            return found
    return None


@dataclass
class Injury:
    team: str
    player: str
    status: str
    detail: str
    position: str = ""


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    published: str = ""
    url: str = ""


@dataclass
class Fixture:
    league: str
    espn_id: str
    date: datetime
    home: str
    away: str
    home_cn: str
    away_cn: str
    venue: str
    status: str
    home_score: int | None = None
    away_score: int | None = None
    home_form: str = ""
    away_form: str = ""
    market: tuple[float, float, float] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        kick = self.date.astimezone().strftime("%m-%d %H:%M") if self.date.tzinfo else self.date.strftime("%m-%d %H:%M")
        return f"{kick}  {self.home_cn} vs {self.away_cn}"


def list_teams(league: League) -> list[str]:
    data = _espn(f"{league.espn_slug}/teams", ttl=6 * 3600)
    teams = []
    try:
        items = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError, TypeError):
        return []
    for item in items:
        name = (item.get("team") or {}).get("displayName") or ""
        if name:
            teams.append(canonical_name(name))
    return teams


def _competitor_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    comps = (event.get("competitions") or [{}])[0]
    out = {}
    for c in comps.get("competitors") or []:
        side = c.get("homeAway") or ""
        out[side] = c
    return out


def _fixture_from_event(league_key: str, event: dict[str, Any]) -> Fixture | None:
    comps = (event.get("competitions") or [{}])[0]
    cmap = _competitor_map(event)
    home_c = cmap.get("home") or {}
    away_c = cmap.get("away") or {}
    home_name = canonical_name(((home_c.get("team") or {}).get("displayName")) or "")
    away_name = canonical_name(((away_c.get("team") or {}).get("displayName")) or "")
    if not home_name or not away_name:
        return None
    dt = _parse_iso(event.get("date") or comps.get("date")) or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    venue = ((event.get("venue") or comps.get("venue") or {}).get("displayName")) or ""
    status = ((event.get("status") or {}).get("type") or {}).get("state") or ""
    hs = home_c.get("score")
    as_ = away_c.get("score")
    market = _extract_moneyline(comps.get("odds"))
    return Fixture(
        league=league_key,
        espn_id=str(event.get("id") or ""),
        date=dt,
        home=home_name,
        away=away_name,
        home_cn=display_cn(home_name),
        away_cn=display_cn(away_name),
        venue=venue,
        status=status,
        home_score=int(hs) if str(hs).isdigit() else None,
        away_score=int(as_) if str(as_).isdigit() else None,
        home_form=str(home_c.get("form") or ""),
        away_form=str(away_c.get("form") or ""),
        market=market,
        raw=event,
    )


def list_fixtures(league: League, date_from: str, date_to: str, ttl: float = 15 * 60) -> list[Fixture]:
    path = f"{league.espn_slug}/scoreboard?dates={date_from}-{date_to}"
    data = _espn(path, ttl=ttl)
    fixtures: list[Fixture] = []
    for event in data.get("events") or []:
        fx = _fixture_from_event(league.key, event)
        if fx:
            fixtures.append(fx)
    fixtures.sort(key=lambda f: f.date)
    return fixtures


def list_injuries(league: League) -> list[Injury]:
    try:
        data = _espn(f"{league.espn_slug}/injuries", ttl=30 * 60)
    except HttpError:
        return []
    out: list[Injury] = []
    for block in data.get("injuries") or []:
        team_name = canonical_name(((block.get("team") or {}).get("displayName")) or "")
        for item in block.get("injuries") or []:
            athlete = item.get("athlete") or {}
            status = ((item.get("status") or {}).get("type") or "") if isinstance(item.get("status"), dict) else str(item.get("status") or "")
            out.append(
                Injury(
                    team=team_name,
                    player=athlete.get("displayName") or item.get("shortComment") or "未知球员",
                    status=status or str(item.get("type") or ""),
                    detail=item.get("longComment") or item.get("shortComment") or "",
                    position=(athlete.get("position") or {}).get("abbreviation") or "",
                )
            )
        # 某些赛季结构是扁平列表
        if "athlete" in block:
            athlete = block.get("athlete") or {}
            team_name = canonical_name(((block.get("team") or {}).get("displayName")) or team_name)
            out.append(
                Injury(
                    team=team_name,
                    player=athlete.get("displayName") or "未知球员",
                    status=str(block.get("status") or ""),
                    detail=str(block.get("comment") or block.get("details") or ""),
                    position="",
                )
            )
    return out


def list_news(league: League) -> list[NewsItem]:
    try:
        data = _espn(f"{league.espn_slug}/news", ttl=20 * 60)
    except HttpError:
        return []
    items: list[NewsItem] = []
    for art in data.get("articles") or []:
        items.append(
            NewsItem(
                title=art.get("headline") or art.get("title") or "",
                summary=art.get("description") or "",
                source="ESPN",
                published=str(art.get("published") or ""),
                url=((art.get("links") or {}).get("web") or {}).get("href") or "",
            )
        )
    return items
