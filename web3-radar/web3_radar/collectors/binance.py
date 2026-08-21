from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pandas as pd

COINGECKO = "https://api.coingecko.com/api/v3"
COINCAP_ASSETS = "https://api.coincap.io/v2/assets"
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


def builtin_markets() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (cid, symbol) in enumerate(SYMBOL_OVERRIDES.items()):
        base = symbol.replace("USDT", "").replace("1000", "")
        out.append(
            {
                "id": cid,
                "symbol": base.lower(),
                "name": cid.replace("-", " ").title(),
                "market_cap": max(1, 2_000_000_000_000 - i * 10_000_000),
                "market_cap_rank": i + 1,
                "current_price": None,
            }
        )
    return out


def markets_from_coincap(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        try:
            cap = float(row.get("marketCapUsd") or 0)
            price = float(row.get("priceUsd") or 0)
            rank = int(float(row.get("rank") or i + 1))
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "id": str(row.get("id") or "").lower(),
                "symbol": str(row.get("symbol") or "").lower(),
                "name": row.get("name") or row.get("symbol"),
                "market_cap": cap,
                "market_cap_rank": rank,
                "current_price": price,
            }
        )
    return out


def markets_from_binance_tickers(tickers: Any, perps: set[str] | None = None) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in tickers or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol.endswith("USDT") or "_" in symbol:
            continue
        if perps and symbol not in perps:
            continue
        try:
            vol = float(row.get("quoteVolume") or 0)
        except (TypeError, ValueError):
            vol = 0.0
        ranked.append((vol, row))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(ranked[:150]):
        symbol = str(row.get("symbol") or "")
        base = symbol.replace("USDT", "").replace("1000", "")
        try:
            price = float(row.get("lastPrice") or row.get("last") or 0)
        except (TypeError, ValueError):
            price = 0.0
        out.append(
            {
                "id": base.lower(),
                "symbol": base.lower(),
                "name": base,
                "market_cap": ranked[i][0],
                "market_cap_rank": i + 1,
                "current_price": price,
            }
        )
    return out


def select_perp_universe(
    markets: list[dict[str, Any]],
    perps: set[str],
    okx_bases: set[str],
    limit: int = 100,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    venue_default = "binance" if perps else ("okx" if okx_bases else "spot")
    for coin in markets or []:
        cid = str(coin.get("id") or "")
        raw_sym = str(coin.get("symbol") or "").upper()
        if not raw_sym:
            continue
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
                "id": cid or raw_sym.lower(),
                "name": coin.get("name") or raw_sym,
                "coingecko_symbol": coin.get("symbol"),
                "binance_symbol": symbol,
                "okx_inst": f"{raw_sym}-USDT-SWAP",
                "venue": venue,
                "market_cap": coin.get("market_cap") or 0,
                "market_cap_rank": coin.get("market_cap_rank") or len(selected) + 1,
                "price": coin.get("current_price"),
                "image": coin.get("image"),
            }
        )
        if len(selected) >= limit:
            break
    return selected


class BinanceClient:
    """Market-cap universe + klines. Prefers Binance USDT-M, falls back to OKX SWAP
    and Binance Vision spot when the futures API is geo-blocked (HTTP 451).
    """

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.klines_source = "binance-fapi"

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=HEADERS) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("Retry-After") or ""
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = 0.8 * (2 ** attempt)
                        await asyncio.sleep(min(max(delay, 0.4), 2.5))
                        last_exc = httpx.HTTPStatusError(
                            f"429 Too Many Requests for {url}",
                            request=resp.request,
                            response=resp,
                        )
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code == 429 and attempt < 1:
                    await asyncio.sleep(min(0.8 * (2 ** attempt), 2.5))
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < 1:
                    await asyncio.sleep(0.3)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError(f"request failed: {url}")

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
        perps = await self.exchange_symbols()
        okx_bases = await self.okx_swap_bases()
        markets: list[dict[str, Any]] | None = None
        source = "builtin"
        try:
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
            source = "coingecko"
        except Exception:
            markets = None
        if not markets:
            cap = await self._get_allow_fail(COINCAP_ASSETS, {"limit": 150})
            if cap:
                markets = markets_from_coincap(cap)
                source = "coincap"
        if not markets:
            tickers = await self._get_allow_fail(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr")
            if tickers:
                markets = markets_from_binance_tickers(tickers, perps)
                source = "binance-volume"
        if not markets:
            markets = builtin_markets()
            source = "builtin"
        selected = select_perp_universe(markets, perps, okx_bases)
        for row in selected:
            row["universe_source"] = source
        venues = {str(r.get("venue") or "") for r in selected}
        if "binance" in venues:
            self.klines_source = "binance-fapi"
        elif "okx" in venues:
            self.klines_source = "okx-swap"
        else:
            self.klines_source = "binance-vision"
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
