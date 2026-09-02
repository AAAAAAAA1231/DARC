"""Provider registry. Services resolve vendors by name, never by import graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.data_sources.base import DataProvider

logger = get_logger("providers")

_PROVIDERS: dict[str, DataProvider] = {}


def register(provider: DataProvider) -> DataProvider:
    _PROVIDERS[provider.name] = provider
    logger.info("provider_registered name=%s", provider.name)
    return provider


def get_provider(name: str) -> DataProvider:
    if name not in _PROVIDERS:
        raise KeyError(f"unknown provider: {name}")
    return _PROVIDERS[name]


def all_providers() -> dict[str, DataProvider]:
    return dict(_PROVIDERS)


def bootstrap_providers() -> None:
    if _PROVIDERS:
        return
    from backend.data_sources.binance import BinanceProvider
    from backend.data_sources.coingecko import CoinGeckoProvider
    from backend.data_sources.defillama import DefiLlamaProvider
    from backend.data_sources.dexscreener import DexScreenerProvider
    from backend.data_sources.football import FootballDataProvider, TheSportsDbProvider
    from backend.data_sources.github import GitHubProvider
    from backend.data_sources.goplus import GoPlusProvider
    from backend.data_sources.lottery import LotteryProvider

    for provider in (
        BinanceProvider(),
        CoinGeckoProvider(),
        GoPlusProvider(),
        DexScreenerProvider(),
        DefiLlamaProvider(),
        GitHubProvider(),
        FootballDataProvider(),
        TheSportsDbProvider(),
        LotteryProvider(),
    ):
        register(provider)
