from backend.core.enums import SourceStatus
from backend.data_sources.http import HttpClient


async def test_http_maps_timeout_and_schema():
    client = HttpClient("unit", timeout_sec=0.01)
    env = await client.get_json("https://10.255.255.1/", expect=dict)
    assert env.status in {SourceStatus.TIMEOUT, SourceStatus.NETWORK_ERROR}
    assert env.payload is None
