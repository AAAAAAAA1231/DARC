from __future__ import annotations

from dataclasses import dataclass

from .. import cache
from ..http_client import HttpError, fetch_json


@dataclass
class Weather:
    temperature_c: float | None
    precipitation_mm: float | None
    wind_kmh: float | None
    summary: str


def fetch_weather(lat: float, lon: float) -> Weather | None:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.3f}&longitude={lon:.3f}"
        "&current=temperature_2m,precipitation,wind_speed_10m,weather_code"
    )
    key = f"wx:{lat:.2f}:{lon:.2f}"
    cached = cache.get_json(key, ttl_seconds=30 * 60)
    if isinstance(cached, dict) and cached:
        return Weather(**cached)
    try:
        data = fetch_json(url, timeout=12)
    except HttpError:
        return None
    cur = data.get("current") or {}
    temp = cur.get("temperature_2m")
    rain = cur.get("precipitation")
    wind = cur.get("wind_speed_10m")
    code = int(cur.get("weather_code") or 0)
    bits = []
    if temp is not None:
        bits.append(f"{temp:.0f}°C")
    if rain:
        bits.append(f"降水 {rain}mm")
    if wind:
        bits.append(f"风速 {wind:.0f}km/h")
    if code >= 80:
        bits.append("强降水/雷暴")
    elif code >= 60:
        bits.append("降雨")
    elif code >= 40:
        bits.append("雾或霾")
    summary = "，".join(bits) if bits else "天气数据有限"
    wx = Weather(
        temperature_c=float(temp) if temp is not None else None,
        precipitation_mm=float(rain) if rain is not None else None,
        wind_kmh=float(wind) if wind is not None else None,
        summary=summary,
    )
    cache.set_json(
        key,
        {
            "temperature_c": wx.temperature_c,
            "precipitation_mm": wx.precipitation_mm,
            "wind_kmh": wx.wind_kmh,
            "summary": wx.summary,
        },
    )
    return wx
