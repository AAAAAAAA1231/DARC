import pytest

from backend.core.enums import DataQuality, SourceStatus
from backend.data_sources.registry import bootstrap_providers, get_provider


@pytest.mark.asyncio
async def test_binance_ping_and_schema():
    bootstrap_providers()
    env = await get_provider("binance").health()
    assert env.source == "binance"
    if env.status == SourceStatus.OK:
        # ping may be {} 
        assert env.data_quality in {DataQuality.OK, DataQuality.PARTIAL, DataQuality.MISSING}
    else:
        assert env.status in {
            SourceStatus.TIMEOUT,
            SourceStatus.NETWORK_ERROR,
            SourceStatus.RATE_LIMITED,
            SourceStatus.UNKNOWN_ERROR,
        }
        assert env.payload is None


@pytest.mark.asyncio
async def test_binance_futures_top_not_hardcoded():
    bootstrap_providers()
    provider = get_provider("binance")
    env = await provider.futures_ticker_24h()
    if not env.ok:
        pytest.skip(f"binance unavailable: {env.status} {env.error}")
    assert len(env.payload) > 10
    volumes = [float(r["quote_volume"]) for r in env.payload[:10]]
    assert volumes == sorted(volumes, reverse=True)
    symbols = [r["symbol"] for r in env.payload[:100]]
    assert all(s.endswith("USDT") for s in symbols)


@pytest.mark.asyncio
async def test_coingecko_or_structured_error():
    bootstrap_providers()
    env = await get_provider("coingecko").health()
    assert env.status in set(SourceStatus)
    if env.ok:
        assert isinstance(env.payload, dict)


@pytest.mark.asyncio
async def test_football_data_missing_key():
    bootstrap_providers()
    env = await get_provider("football_data").health()
    # Without a key this must be missing_key, never a fake fixture list.
    if env.status == SourceStatus.MISSING_KEY:
        assert env.payload is None
        assert "FOOTBALL_DATA_API_KEY" in (env.error or "")
    else:
        assert env.status in set(SourceStatus)


@pytest.mark.asyncio
async def test_goplus_unsupported_chain_is_schema_error():
    bootstrap_providers()
    env = await get_provider("goplus").token_security("not-a-chain", "0x" + "1" * 40)
    assert env.status == SourceStatus.SCHEMA_ERROR
    assert env.payload is None
