"""Fourteen independent strategy plugins. Each uses only the provided OHLCV."""

from __future__ import annotations

import numpy as np

from backend.strategies.base import StrategyPlugin, StrategySignal
from backend.strategies.indicators import adx, atr, ema, macd, obv, rsi, sma, swing_points, vwap


def _dir_from_score(score: float) -> tuple[str, str]:
    if score >= 60:
        return "LONG", "BUY"
    if score <= 40:
        return "SHORT", "SELL"
    return "NEUTRAL", "HOLD"


class TdSequentialStrategy(StrategyPlugin):
    name = "td_sequential"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 20:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        countdown = 0
        direction = 0
        for i in range(4, len(close)):
            if close[i] > close[i - 4]:
                countdown = countdown + 1 if direction == 1 else 1
                direction = 1
            elif close[i] < close[i - 4]:
                countdown = countdown + 1 if direction == -1 else 1
                direction = -1
            else:
                countdown = 0
                direction = 0
        score = 50
        reasons, against = [], []
        if direction == 1 and countdown >= 9:
            score = 28
            reasons.append(f"TD buy setup countdown={countdown}")
        elif direction == -1 and countdown >= 9:
            score = 72
            reasons.append(f"TD sell setup countdown={countdown}")
        else:
            against.append(f"TD countdown incomplete ({countdown})")
            score = 50 + 4 * direction
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, min(0.9, 0.3 + countdown / 20), s, reasons, against)


class ChanlunStrategy(StrategyPlugin):
    name = "chanlun"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        high, low, close = ohlcv["high"], ohlcv["low"], ohlcv["close"]
        if len(close) < 30:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        sh, sl = swing_points(close, 4, 4)
        reasons, against = [], []
        score = 50
        if sh and sl:
            last_high = high[sh[-1]]
            last_low = low[sl[-1]]
            if sh[-1] > sl[-1] and close[-1] > last_high:
                score = 70
                reasons.append("break of last fractal high (potential 3rd buy)")
            elif sl[-1] > sh[-1] and close[-1] < last_low:
                score = 30
                reasons.append("break of last fractal low (potential 3rd sell)")
            else:
                against.append("price inside last bi range")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.45, s, reasons, against)


class HarmonicStrategy(StrategyPlugin):
    name = "harmonic"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 40:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        sh, sl = swing_points(close, 3, 3)
        points = sorted([(i, close[i]) for i in sh[-3:] + sl[-3:]])
        reasons, against = [], []
        score = 50
        if len(points) >= 4:
            xa = points[-3][1] - points[-4][1]
            ab = points[-2][1] - points[-3][1]
            if xa != 0:
                retr = abs(ab / xa)
                if 0.5 <= retr <= 0.886:
                    score = 62 if ab < 0 else 38
                    reasons.append(f"ABCD retracement {retr:.2f} near harmonic zone")
                else:
                    against.append(f"retracement {retr:.2f} outside harmonic bands")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.35, s, reasons, against)


class ElliottStrategy(StrategyPlugin):
    name = "elliott"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 50:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        sh, sl = swing_points(close, 5, 5)
        score = 50
        reasons, against = [], []
        if len(sh) >= 3 and len(sl) >= 2:
            impulse = sh[-1] > sh[-2] > sh[-3] if sh[-3:] else False
            if impulse and close[-1] > close[-20:].mean():
                score = 66
                reasons.append("higher swing highs consistent with impulse")
            else:
                against.append("no clear 5-wave impulse")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.3, s, reasons, against)


class WyckoffStrategy(StrategyPlugin):
    name = "wyckoff"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close, volume = ohlcv["close"], ohlcv["volume"]
        if len(close) < 40:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        rng = close[-40:]
        vol = volume[-40:]
        hi, lo = rng.max(), rng.min()
        mid = (hi + lo) / 2
        score = 50
        reasons, against = [], []
        if close[-1] > mid and vol[-5:].mean() > vol[-20:].mean():
            score = 68
            reasons.append("range high + rising volume (SOS-like)")
        elif close[-1] < mid and vol[-5:].mean() > vol[-20:].mean():
            score = 32
            reasons.append("range low + rising volume (SOW-like)")
        else:
            against.append("no volume confirmation in range")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.4, s, reasons, against)


class SmcStrategy(StrategyPlugin):
    name = "smc"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        high, low, close = ohlcv["high"], ohlcv["low"], ohlcv["close"]
        sh, sl = swing_points(close, 3, 3)
        score = 50
        reasons, against = [], []
        if sh and sl:
            if close[-1] > high[sh[-1]]:
                score = 74
                reasons.append("BOS above last swing high")
            elif close[-1] < low[sl[-1]]:
                score = 26
                reasons.append("BOS below last swing low")
            else:
                against.append("no BOS/CHoCH")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.5, s, reasons, against)


class IctStrategy(StrategyPlugin):
    name = "ict"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        high, low, close = ohlcv["high"], ohlcv["low"], ohlcv["close"]
        if len(close) < 10:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        reasons, against = [], []
        score = 50
        fvg_up = high[-3] < low[-1]
        fvg_down = low[-3] > high[-1]
        if fvg_up:
            score = 64
            reasons.append("bullish FVG between bar-3 and last bar")
        elif fvg_down:
            score = 36
            reasons.append("bearish FVG between bar-3 and last bar")
        else:
            against.append("no fresh FVG")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.35, s, reasons, against)


class PriceActionStrategy(StrategyPlugin):
    name = "price_action"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        o, h, l, c = ohlcv["open"], ohlcv["high"], ohlcv["low"], ohlcv["close"]
        reasons, against = [], []
        score = 50
        body = c[-1] - o[-1]
        rng = max(h[-1] - l[-1], 1e-12)
        if body > 0 and abs(body) / rng > 0.6 and c[-1] > o[-2] and o[-1] < c[-2]:
            score = 72
            reasons.append("bullish engulfing")
        elif body < 0 and abs(body) / rng > 0.6 and c[-1] < o[-2] and o[-1] > c[-2]:
            score = 28
            reasons.append("bearish engulfing")
        elif (min(o[-1], c[-1]) - l[-1]) / rng > 0.6:
            score = 63
            reasons.append("pin bar / rejection wick low")
        else:
            against.append("no clear PA candle")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.4, s, reasons, against)


class GannStrategy(StrategyPlugin):
    name = "gann"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 50:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        start = close[-50]
        slope = (close[-1] - start) / 50
        ideal = start + slope * np.arange(50)
        dist = (close[-50:] - ideal) / max(abs(start), 1e-9)
        score = 50 + float(np.clip(-dist[-1] * 100, -20, 20))
        reasons = [f"distance to 1x1 trend {dist[-1]:.3f}"]
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.25, s, reasons, [])


class DowStrategy(StrategyPlugin):
    name = "dow"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        sh, sl = swing_points(close, 4, 4)
        score = 50
        reasons, against = [], []
        if len(sh) >= 2 and len(sl) >= 2:
            hh = close[sh[-1]] > close[sh[-2]]
            hl = close[sl[-1]] > close[sl[-2]]
            if hh and hl:
                score = 74
                reasons.append("HH + HL (Dow uptrend)")
            elif (not hh) and (not hl):
                score = 26
                reasons.append("LH + LL (Dow downtrend)")
            else:
                against.append("mixed swing structure")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.5, s, reasons, against)


class VsaStrategy(StrategyPlugin):
    name = "vsa"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        o, h, l, c, v = ohlcv["open"], ohlcv["high"], ohlcv["low"], ohlcv["close"], ohlcv["volume"]
        spread = h[-1] - l[-1]
        avg_spread = np.mean(h[-20:] - l[-20:]) if len(c) >= 20 else spread
        avg_vol = np.mean(v[-20:]) if len(v) >= 20 else v[-1]
        score = 50
        reasons, against = [], []
        if spread < avg_spread * 0.6 and v[-1] > avg_vol * 1.4 and c[-1] > o[-1]:
            score = 70
            reasons.append("narrow spread + high volume on up bar (absorption)")
        elif spread > avg_spread * 1.4 and v[-1] > avg_vol * 1.4 and c[-1] < o[-1]:
            score = 30
            reasons.append("wide spread down + high volume (effort + result down)")
        else:
            against.append("no VSA climax/absorption")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.35, s, reasons, against)


class IchimokuStrategy(StrategyPlugin):
    name = "ichimoku"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        high, low, close = ohlcv["high"], ohlcv["low"], ohlcv["close"]
        if len(close) < 52:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        tenkan = (np.max(high[-9:]) + np.min(low[-9:])) / 2
        kijun = (np.max(high[-26:]) + np.min(low[-26:])) / 2
        span_a = (tenkan + kijun) / 2
        span_b = (np.max(high[-52:]) + np.min(low[-52:])) / 2
        cloud_top = max(span_a, span_b)
        cloud_bot = min(span_a, span_b)
        score = 50
        reasons, against = [], []
        if close[-1] > cloud_top and tenkan > kijun:
            score = 76
            reasons.append("price above cloud, tenkan > kijun")
        elif close[-1] < cloud_bot and tenkan < kijun:
            score = 24
            reasons.append("price below cloud, tenkan < kijun")
        else:
            against.append("price inside/around cloud")
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.55, s, reasons, against)


class MarketProfileStrategy(StrategyPlugin):
    name = "market_profile"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 30:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        bins = np.linspace(close[-30:].min(), close[-30:].max(), 12)
        idx = np.clip(np.digitize(close[-30:], bins) - 1, 0, 10)
        poc_bin = int(np.bincount(idx, minlength=11).argmax())
        poc = (bins[poc_bin] + bins[min(poc_bin + 1, 11)]) / 2
        score = 50
        reasons = [f"POC≈{poc:.6g} last={close[-1]:.6g}"]
        if close[-1] > poc:
            score = 60
        elif close[-1] < poc:
            score = 40
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.3, s, reasons, [])


class CycleStrategy(StrategyPlugin):
    name = "cycle"

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        close = ohlcv["close"]
        if len(close) < 64:
            return StrategySignal(self.name, "NEUTRAL", 50, 0.1, "HOLD", reasons=["insufficient bars"])
        x = close[-64:] - close[-64:].mean()
        spec = np.abs(np.fft.rfft(x))
        spec[0] = 0
        dominant = int(np.argmax(spec))
        phase = np.angle(np.fft.rfft(x)[dominant]) if dominant else 0
        score = 50 + float(np.clip(np.cos(phase) * 15, -15, 15))
        reasons = [f"dominant bin={dominant} phase={phase:.2f}"]
        d, s = _dir_from_score(score)
        return StrategySignal(self.name, d, score, 0.25, s, reasons, [])


ALL_STRATEGIES: list[StrategyPlugin] = [
    TdSequentialStrategy(),
    ChanlunStrategy(),
    HarmonicStrategy(),
    ElliottStrategy(),
    WyckoffStrategy(),
    SmcStrategy(),
    IctStrategy(),
    PriceActionStrategy(),
    GannStrategy(),
    DowStrategy(),
    VsaStrategy(),
    IchimokuStrategy(),
    MarketProfileStrategy(),
    CycleStrategy(),
]
