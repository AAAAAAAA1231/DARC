from __future__ import annotations

from dataclasses import dataclass
import re

from .config import LEAGUES
from .names import TeamInfo, all_team_infos, display_cn


_LEAGUE_WORDS = {
    "laliga": ("西甲", "laliga", "la liga", "西班牙甲"),
    "bundesliga": ("德甲", "bundesliga", "德国甲"),
    "seriea": ("意甲", "serie a", "seriea", "意大利甲"),
}


@dataclass
class SearchQuery:
    raw: str
    teams: list[str]
    league: str | None
    want_next: bool

    def describe(self) -> str:
        bits = []
        if self.want_next:
            bits.append("下一场")
        if self.league:
            bits.append(LEAGUES[self.league].name_cn)
        bits.extend(display_cn(t) for t in self.teams)
        return " ".join(bits) if bits else self.raw


def _keyword_map() -> list[tuple[str, TeamInfo]]:
    pairs: list[tuple[str, TeamInfo]] = []
    for info in all_team_infos():
        for kw in (info.canonical, info.name_cn, *info.aliases):
            k = kw.strip()
            if len(k) >= 2:
                pairs.append((k, info))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


_KEYWORDS = _keyword_map()


def _detect_league(text: str) -> str | None:
    low = text.lower()
    for key, words in _LEAGUE_WORDS.items():
        for w in words:
            if w.lower() in low:
                return key
    return None


def extract_teams(text: str) -> list[str]:
    remaining = text
    found: list[TeamInfo] = []
    seen: set[str] = set()
    for kw, info in _KEYWORDS:
        if info.canonical in seen:
            continue
        pattern = re.escape(kw)
        flags = re.I if kw.isascii() else 0
        needle = rf"\b{pattern}\b" if (kw.isascii() and len(kw) <= 3) else pattern
        if not re.search(needle, remaining, flags):
            continue
        found.append(info)
        seen.add(info.canonical)
        remaining = re.sub(pattern, " ", remaining, count=1, flags=flags)
    return [info.canonical for info in found]


def parse_query(text: str) -> SearchQuery:
    raw = (text or "").strip()
    want_next = bool(re.search(r"下一场|下场|最近一场|next\s+match|next\s+game", raw, re.I))
    league = _detect_league(raw)
    teams = extract_teams(raw)
    return SearchQuery(raw=raw, teams=teams, league=league, want_next=want_next)
