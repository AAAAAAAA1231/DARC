"""CoinGecko markets and coin detail. Works without a key; Pro key is optional."""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_float, optional_str, parse_timestamp
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


class CoinGeckoProvider(DataProvider):
    name = "coingecko"

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.yaml_config.get("providers", {}).get("coingecko", {})
        self.base = str(cfg.get("base", "https://api.coingecko.com/api/v3")).rstrip("/")
        headers: dict[str, str] = {}
        if settings.coingecko_api_key:
            headers["x-cg-pro-api-key"] = settings.coingecko_api_key
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)), headers)

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/ping")

    async def markets(self, vs: str = "usd", per_page: int = 100, page: int = 1) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/coins/markets",
            params={
                "vs_currency": vs,
                "order": "volume_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "24h,7d,30d",
            },
            expect=list,
        )
        if not raw.ok:
            return raw
        parsed: list[dict[str, Any]] = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            coin_id = optional_str(item, "id")
            symbol = optional_str(item, "symbol")
            name = optional_str(item, "name")
            price = optional_float(item, "current_price")
            if not coin_id or not symbol or not name or price is None:
                continue
            parsed.append(
                {
                    "id": coin_id,
                    "symbol": symbol.upper(),
                    "name": name,
                    "image": optional_str(item, "image"),
                    "current_price": price,
                    "market_cap": optional_float(item, "market_cap"),
                    "fully_diluted_valuation": optional_float(item, "fully_diluted_valuation"),
                    "total_volume": optional_float(item, "total_volume"),
                    "circulating_supply": optional_float(item, "circulating_supply"),
                    "total_supply": optional_float(item, "total_supply"),
                    "max_supply": optional_float(item, "max_supply"),
                    "ath": optional_float(item, "ath"),
                    "atl": optional_float(item, "atl"),
                    "ath_change_percentage": optional_float(item, "ath_change_percentage"),
                    "price_change_percentage_24h": optional_float(item, "price_change_percentage_24h"),
                    "price_change_percentage_7d": optional_float(item, "price_change_percentage_7d_in_currency"),
                    "price_change_percentage_30d": optional_float(item, "price_change_percentage_30d_in_currency"),
                    "market_cap_rank": item.get("market_cap_rank"),
                    "last_updated": parse_timestamp(item.get("last_updated")).isoformat()
                    if parse_timestamp(item.get("last_updated"))
                    else None,
                }
            )
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.PARTIAL,
            confidence=1.0 if parsed else 0.2,
        )

    async def coin_detail(self, coin_id: str) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "true",
                "developer_data": "true",
            },
            expect=dict,
        )
        if not raw.ok:
            return raw
        item = raw.payload
        platforms = item.get("platforms") if isinstance(item.get("platforms"), dict) else {}
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        market = item.get("market_data") if isinstance(item.get("market_data"), dict) else {}
        community = item.get("community_data") if isinstance(item.get("community_data"), dict) else {}
        developer = item.get("developer_data") if isinstance(item.get("developer_data"), dict) else {}
        genesis = parse_timestamp(item.get("genesis_date"))
        categories = item.get("categories") if isinstance(item.get("categories"), list) else []
        homepage = None
        if isinstance(links.get("homepage"), list) and links["homepage"]:
            homepage = links["homepage"][0] or None
        twitter = optional_str(links, "twitter_screen_name")
        github_repos = []
        repos = links.get("repos_url") if isinstance(links.get("repos_url"), dict) else {}
        if isinstance(repos.get("github"), list):
            github_repos = [u for u in repos["github"] if u]
        parsed = {
            "id": optional_str(item, "id"),
            "symbol": (optional_str(item, "symbol") or "").upper(),
            "name": optional_str(item, "name"),
            "platforms": {k: v for k, v in platforms.items() if v},
            "categories": [c for c in categories if isinstance(c, str)],
            "genesis_date": genesis.isoformat() if genesis else None,
            "homepage": homepage,
            "twitter": twitter,
            "telegram": optional_str(links, "telegram_channel_identifier"),
            "subreddit": optional_str(links, "subreddit_url"),
            "github_repos": github_repos,
            "sentiment_votes_up_percentage": optional_float(item, "sentiment_votes_up_percentage"),
            "watchlist_portfolio_users": item.get("watchlist_portfolio_users"),
            "market_cap": (market.get("market_cap") or {}).get("usd") if isinstance(market.get("market_cap"), dict) else None,
            "fdv": (market.get("fully_diluted_valuation") or {}).get("usd")
            if isinstance(market.get("fully_diluted_valuation"), dict)
            else None,
            "total_volume": (market.get("total_volume") or {}).get("usd") if isinstance(market.get("total_volume"), dict) else None,
            "circulating_supply": market.get("circulating_supply"),
            "total_supply": market.get("total_supply"),
            "max_supply": market.get("max_supply"),
            "ath": (market.get("ath") or {}).get("usd") if isinstance(market.get("ath"), dict) else None,
            "atl": (market.get("atl") or {}).get("usd") if isinstance(market.get("atl"), dict) else None,
            "community": {
                "twitter_followers": community.get("twitter_followers"),
                "reddit_subscribers": community.get("reddit_subscribers"),
                "telegram_channel_user_count": community.get("telegram_channel_user_count"),
            },
            "developer": {
                "forks": developer.get("forks"),
                "stars": developer.get("stars"),
                "subscribers": developer.get("subscribers"),
                "commit_count_4_weeks": developer.get("commit_count_4_weeks"),
            },
            "description": ((item.get("description") or {}).get("en") if isinstance(item.get("description"), dict) else None),
        }
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK, confidence=1.0)
