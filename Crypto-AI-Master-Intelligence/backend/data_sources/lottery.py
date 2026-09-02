"""Chinese lottery historical draws. Architecture supports extra games later."""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_str, parse_timestamp
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient

SUPPORTED_GAMES = ("ssq", "dlt", "pl3", "pl5", "3d", "qxc")


class LotteryProvider(DataProvider):
    name = "lottery"

    def __init__(self) -> None:
        cfg = get_settings().yaml_config.get("providers", {})
        ssq = cfg.get("lottery_ssq", {})
        dlt = cfg.get("lottery_dlt", {})
        self.ssq_base = str(ssq.get("base", "https://www.cwl.gov.cn")).rstrip("/")
        self.dlt_base = str(dlt.get("base", "https://webapi.sporttery.cn")).rstrip("/")
        self.http = HttpClient(self.name, 20.0, {"User-Agent": "Crypto-AI-Master-Intelligence/1.0"})

    async def health(self) -> QualityEnvelope:
        return await self.ssq_history(count=1)

    async def history(self, game: str, count: int = 50) -> QualityEnvelope:
        game_n = game.lower()
        if game_n == "ssq":
            return await self.ssq_history(count=count)
        if game_n == "dlt":
            return await self.dlt_history(count=count)
        if game_n in SUPPORTED_GAMES:
            return envelope(
                self.name,
                status=SourceStatus.OK,
                payload=[],
                data_quality=DataQuality.MISSING,
                confidence=0.0,
                error=f"game {game_n} is architected but no live source is configured",
                meta={"supported": list(SUPPORTED_GAMES)},
            )
        return envelope(
            self.name,
            status=SourceStatus.SCHEMA_ERROR,
            data_quality=DataQuality.INVALID,
            error=f"unknown game {game}",
        )

    async def ssq_history(self, count: int = 50) -> QualityEnvelope:
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
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.MISSING,
            confidence=1.0 if parsed else 0.0,
        )

    async def dlt_history(self, count: int = 50) -> QualityEnvelope:
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
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.MISSING,
            confidence=1.0 if parsed else 0.0,
        )
