from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

COINGECKO = "https://api.coingecko.com/api/v3"
BINANCE_FAPI = "https://fapi.binance.com"
BINANCE_VISION = "https://data-api.binance.vision"
OKX = "https://www.okx.com"

SYMBOL_OVERRIDES = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "dogecoin": "DOGEUSDT",
    "cardano": "ADAUSDT",
    "tron": "TRXUSDT",
    "avalanche-2": "AVAXUSDT",
    "shiba-inu": "1000SHIBUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT",
    "bitcoin-cash": "BCHUSDT",
    "near": "NEARUSDT",
    "uniswap": "UNIUSDT",
    "litecoin": "LTCUSDT",
    "pepe": "1000PEPEUSDT",
    "internet-computer": "ICPUSDT",
    "aptos": "APTUSDT",
    "hedera-hashgraph": "HBARUSDT",
    "ethereum-classic": "ETCUSDT",
    "render-token": "RENDERUSDT",
    "mantle": "MANTLEUSDT",
    "cosmos": "ATOMUSDT",
    "filecoin": "FILUSDT",
    "arbitrum": "ARBUSDT",
    "optimism": "OPUSDT",
    "injective-protocol": "INJUSDT",
    "stellar": "XLMUSDT",
    "aave": "AAVEUSDT",
    "lido-dao": "LDOUSDT",
    "worldcoin-wld": "WLDUSDT",
    "sui": "SUIUSDT",
    "bittensor": "TAOUSDT",
    "fetch-ai": "FETUSDT",
    "bonk": "1000BONKUSDT",
    "sei-network": "SEIUSDT",
    "celestia": "TIAUSDT",
    "jupiter-exchange-solana": "JUPUSDT",
    "ondo-finance": "ONDOUSDT",
    "ethena": "ENAUSDT",
}

INTERVAL_OKX = {"15m": "15m", "4h": "4H", "1d": "1D", "1h": "1H"}
HEADERS = {"User-Agent": "ChainRadar/1.0", "Accept": "application/json"}


class BinanceClient:
    """Market-cap universe + klines. Prefers Binance USDT-M, falls back to OKX SWAP
    and Binance Vision spot when the futures API is geo-blocked (HTTP 451).
    """

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.klines_source = "binance-fapi"

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout, headers=HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _get_allow_fail(self, url: str, params: dict[str, Any] | None = None) -> Any | None:
        try:
            return await self._get(url, params)
        except Exception:
            return None

    async def exchange_symbols(self) -> set[str]:
        data = await self._get_allow_fail(f"{BINANCE_FAPI}/fapi/v1/exchangeInfo")
        if not data:
            return set()
        out = set()
        for s in data.get("symbols", []):
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                out.add(s["symbol"])
        return out

    async def okx_swap_bases(self) -> set[str]:
        data = await self._get_allow_fail(f"{OKX}/api/v5/public/instruments", params={"instType": "SWAP"})
        if not data:
            return set()
        bases = set()
        for row in data.get("data") or []:
            inst = row.get("instId") or ""
            if inst.endswith("-USDT-SWAP") and row.get("state") == "live":
                bases.add(inst.split("-")[0])
        return bases

    async def top100_perp_by_market_cap(self) -> list[dict[str, Any]]:
        markets = await self._get(
            f"{COINGECKO}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 150,
                "page": 1,
                "sparkline": "false",
            },
        )
        perps = await self.exchange_symbols()
        okx_bases = await self.okx_swap_bases()
        selected: list[dict[str, Any]] = []
        used = set()
        venue_default = "binance" if perps else ("okx" if okx_bases else "spot")
        self.klines_source = {"binance": "binance-fapi", "okx": "okx-swap", "spot": "binance-vision"}[venue_default]

        for coin in markets:
            cid = coin.get("id", "")
            raw_sym = str(coin.get("symbol", "")).upper()
            symbol = SYMBOL_OVERRIDES.get(cid) or f"{raw_sym}USDT"
            venue = venue_default
            if perps:
                if symbol not in perps:
                    alt = f"1000{raw_sym}USDT"
                    if alt in perps:
                        symbol = alt
                    elif okx_bases and raw_sym in okx_bases:
                        venue = "okx"
                        symbol = f"{raw_sym}USDT"
                    else:
                        venue = "spot"
                        symbol = f"{raw_sym}USDT"
            elif okx_bases and raw_sym in okx_bases:
                venue = "okx"
                symbol = f"{raw_sym}USDT"
            else:
                venue = "spot"
                symbol = f"{raw_sym}USDT"
            if symbol in used:
                continue
            used.add(symbol)
            selected.append(
                {
                    "id": cid,
                    "name": coin.get("name"),
                    "coingecko_symbol": coin.get("symbol"),
                    "binance_symbol": symbol,
                    "okx_inst": f"{raw_sym}-USDT-SWAP",
                    "venue": venue,
                    "market_cap": coin.get("market_cap") or 0,
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "price": coin.get("current_price"),
                    "image": coin.get("image"),
                }
            )
            if len(selected) >= 100:
                break
        return selected

    async def klines(self, symbol: str, interval: str = "4h", limit: int = 500) -> pd.DataFrame:
        fapi = await self._get_allow_fail(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        if fapi:
            return _klines_binance(fapi)
        inst = f"{symbol.replace('USDT', '').replace('1000', '')}-USDT-SWAP"
        okx = await self._get_allow_fail(
            f"{OKX}/api/v5/market/candles",
            params={"instId": inst, "bar": INTERVAL_OKX.get(interval, "4H"), "limit": str(min(limit, 300))},
        )
        if okx and okx.get("data"):
            return _klines_okx(okx["data"])
        vision = await self._get(
            f"{BINANCE_VISION}/api/v3/klines",
            params={"symbol": symbol.replace("1000", ""), "interval": interval, "limit": limit},
        )
        return _klines_binance(vision)

    async def last_price(self, symbol: str) -> float:
        data = await self._get_allow_fail(f"{BINANCE_FAPI}/fapi/v1/ticker/price", params={"symbol": symbol})
        if data and data.get("price"):
            return float(data["price"])
        inst = f"{symbol.replace('USDT', '').replace('1000', '')}-USDT-SWAP"
        okx = await self._get_allow_fail(f"{OKX}/api/v5/market/ticker", params={"instId": inst})
        if okx and okx.get("data"):
            return float(okx["data"][0]["last"])
        vision = await self._get(f"{BINANCE_VISION}/api/v3/ticker/price", params={"symbol": symbol.replace("1000", "")})
        return float(vision["price"])


def _klines_binance(raw: list[Any]) -> pd.DataFrame:
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_base",
        "taker_quote",
        "ignore",
    ]
    df = pd.DataFrame(raw, columns=cols[: len(raw[0])])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def _klines_okx(raw: list[Any]) -> pd.DataFrame:
    # OKX returns newest first: ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm
    rows = list(reversed(raw))
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume", "vol_ccy", "vol_quote", "confirm"][: len(rows[0])])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"].astype(float), unit="ms", utc=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]
