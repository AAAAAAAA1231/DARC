"""Lottery history. Official hosts first; 500.com XML and 17500 text as live failovers. Never invents draws."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_str, parse_timestamp
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient

SUPPORTED_GAMES = ("ssq", "dlt", "pl3", "pl5", "3d", "qxc")

# Public historical XML used when official WAF blocks cloud IPs. Still live draw records, not mocks.
XML_500 = {
    "ssq": "https://kaijiang.500.com/static/info/kaijiang/xml/ssq/list.xml",
    "dlt": "https://kaijiang.500.com/static/info/kaijiang/xml/dlt/list.xml",
    "3d": "https://kaijiang.500.com/static/info/kaijiang/xml/sd/list.xml",
    "pl3": "https://kaijiang.500.com/static/info/kaijiang/xml/pls/list.xml",
    "pl5": "https://kaijiang.500.com/static/info/kaijiang/xml/plw/list.xml",
    "qxc": "https://kaijiang.500.com/static/info/kaijiang/xml/qxc/list.xml",
}

TXT_17500 = {
    "ssq": "https://data.17500.cn/ssq_asc.txt",
    "dlt": "https://data.17500.cn/dlt_asc.txt",
}


def parse_500_xml(text: str, game: str, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    out: list[dict[str, Any]] = []
    for row in root.findall("row"):
        expect = row.attrib.get("expect")
        opencode = row.attrib.get("opencode")
        if not expect or not opencode:
            continue
        draw_time = parse_timestamp(row.attrib.get("opentime"))
        numbers = _split_opencode(game, opencode)
        if not numbers:
            continue
        out.append(
            {
                "game": game,
                "issue": expect,
                "draw_time": draw_time.isoformat() if draw_time else None,
                "numbers": numbers,
                "source": "kaijiang.500.com",
            }
        )
        if len(out) >= limit:
            break
    return out


def parse_17500_txt(text: str, game: str, limit: int) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # file is ascending; take the newest tail
    newest = list(reversed(lines))[:limit]
    out: list[dict[str, Any]] = []
    for ln in newest:
        parts = ln.split()
        if len(parts) < 4:
            continue
        issue, date = parts[0], parts[1]
        draw_time = parse_timestamp(date)
        if game == "ssq" and len(parts) >= 9:
            numbers = {"red": parts[2:8], "blue": [parts[8]]}
        elif game == "dlt" and len(parts) >= 9:
            numbers = {"front": parts[2:7], "back": parts[7:9]}
        else:
            continue
        out.append(
            {
                "game": game,
                "issue": issue,
                "draw_time": draw_time.isoformat() if draw_time else None,
                "numbers": numbers,
                "source": "data.17500.cn",
            }
        )
    return out


def _split_opencode(game: str, opencode: str) -> dict[str, Any] | None:
    if "|" in opencode:
        left, right = opencode.split("|", 1)
        a = [p.strip() for p in left.split(",") if p.strip()]
        b = [p.strip() for p in right.split(",") if p.strip()]
        if game == "ssq":
            return {"red": a, "blue": b}
        if game == "dlt":
            return {"front": a, "back": b}
        return {"main": a, "extra": b}
    nums = [p.strip() for p in opencode.replace("|", ",").split(",") if p.strip()]
    if game in {"3d", "pl3"}:
        return {"digits": nums}
    if game == "pl5":
        return {"digits": nums}
    if game == "qxc":
        return {"digits": nums}
    return {"numbers": nums}


class LotteryProvider(DataProvider):
    name = "lottery"

    def __init__(self) -> None:
        cfg = get_settings().yaml_config.get("providers", {})
        ssq = cfg.get("lottery_ssq", {})
        dlt = cfg.get("lottery_dlt", {})
        self.ssq_base = str(ssq.get("base", "https://www.cwl.gov.cn")).rstrip("/")
        self.dlt_base = str(dlt.get("base", "https://webapi.sporttery.cn")).rstrip("/")
        self.http = HttpClient(
            self.name,
            20.0,
            {"User-Agent": "Mozilla/5.0 Crypto-AI-Master-Intelligence/1.0", "Accept": "application/xml,text/plain,*/*"},
        )

    async def health(self) -> QualityEnvelope:
        return await self.history("ssq", count=1)

    async def history(self, game: str, count: int = 50) -> QualityEnvelope:
        game_n = game.lower()
        if game_n not in SUPPORTED_GAMES:
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error=f"unknown game {game}")

        errors: list[str] = []
        if game_n == "ssq":
            official = await self._ssq_official(count)
            if official.ok and official.payload:
                return official
            errors.append(f"cwl:{official.status.value}:{official.error}")
        if game_n == "dlt":
            official = await self._dlt_official(count)
            if official.ok and official.payload:
                return official
            errors.append(f"sporttery:{official.status.value}:{official.error}")

        xml_url = XML_500.get(game_n)
        if xml_url:
            raw = await self.http.get_text(xml_url)
            if raw.ok and isinstance(raw.payload, str):
                try:
                    parsed = parse_500_xml(raw.payload, game_n, count)
                except ET.ParseError as exc:
                    errors.append(f"500xml_parse:{exc}")
                    parsed = []
                if parsed:
                    return envelope(
                        self.name,
                        status=SourceStatus.OK,
                        payload=parsed,
                        data_quality=DataQuality.OK,
                        confidence=1.0,
                        meta={"failover": "kaijiang.500.com", "upstream_errors": errors},
                    )
            else:
                errors.append(f"500xml:{raw.status.value}:{raw.error}")

        txt_url = TXT_17500.get(game_n)
        if txt_url:
            raw = await self.http.get_text(txt_url)
            if raw.ok and isinstance(raw.payload, str):
                parsed = parse_17500_txt(raw.payload, game_n, count)
                if parsed:
                    return envelope(
                        self.name,
                        status=SourceStatus.OK,
                        payload=parsed,
                        data_quality=DataQuality.OK,
                        confidence=1.0,
                        meta={"failover": "data.17500.cn", "upstream_errors": errors},
                    )
            else:
                errors.append(f"17500:{raw.status.value}:{raw.error}")

        return envelope(
            self.name,
            status=SourceStatus.UNKNOWN_ERROR,
            payload=[],
            data_quality=DataQuality.ERROR,
            error="; ".join(errors) or "all lottery hosts failed",
            confidence=0.0,
        )

    async def _ssq_official(self, count: int) -> QualityEnvelope:
        url = f"{self.ssq_base}/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
        raw = await self.http.get_json(url, params={"name": "ssq", "issueCount": count}, expect=dict)
        if not raw.ok:
            return raw
        result = raw.payload.get("result")
        if not isinstance(result, list):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="ssq result missing")
        parsed = []
        for item in result:
            if not isinstance(item, dict):
                continue
            issue = optional_str(item, "code")
            red = optional_str(item, "red")
            blue = optional_str(item, "blue")
            if not issue or not red:
                continue
            draw_time = parse_timestamp(item.get("date"))
            parsed.append(
                {
                    "game": "ssq",
                    "issue": issue,
                    "draw_time": draw_time.isoformat() if draw_time else None,
                    "numbers": {"red": [p.strip() for p in red.split(",") if p.strip()], "blue": [blue] if blue else []},
                    "source": "cwl.gov.cn",
                }
            )
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK if parsed else DataQuality.MISSING, confidence=1.0 if parsed else 0.0)

    async def _dlt_official(self, count: int) -> QualityEnvelope:
        url = f"{self.dlt_base}/gateway/lottery/getHistoryPageListV1.qry"
        raw = await self.http.get_json(
            url,
            params={"gameNo": "85", "provinceId": "0", "pageSize": count, "isVerify": "1", "pageNo": "1"},
            expect=dict,
        )
        if not raw.ok:
            return raw
        value = raw.payload.get("value") if isinstance(raw.payload, dict) else None
        lst = value.get("list") if isinstance(value, dict) else None
        if not isinstance(lst, list):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="dlt list missing")
        parsed: list[dict[str, Any]] = []
        for item in lst:
            if not isinstance(item, dict):
                continue
            issue = optional_str(item, "lotteryDrawNum")
            result = optional_str(item, "lotteryDrawResult")
            if not issue or not result:
                continue
            parts = [p for p in result.replace("|", " ").split() if p]
            draw_time = parse_timestamp(item.get("lotteryDrawTime"))
            parsed.append(
                {
                    "game": "dlt",
                    "issue": issue,
                    "draw_time": draw_time.isoformat() if draw_time else None,
                    "numbers": {"front": parts[:5], "back": parts[5:7]},
                    "source": "sporttery.cn",
                }
            )
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK if parsed else DataQuality.MISSING, confidence=1.0 if parsed else 0.0)
