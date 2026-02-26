#!/usr/bin/env python3
"""
Advanced Technical Indicators (continued)
==========================================
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum


class Signal(Enum):
    """Trading signal."""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


@dataclass
class IndicatorResult:
    """Result from a technical indicator."""
    name: str
    value: float
    signal: Signal
    description: str
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "signal": self.signal.value,
            "description": self.description,
            "details": self.details or {}
        }


class TechnicalIndicators:
    """Advanced technical indicator calculations."""
    
    def __init__(self, closes: List[float], highs: List[float] = None, 
                 lows: List[float] = None, volumes: List[float] = None,
                 opens: List[float] = None):
        self.closes = np.array(closes, dtype=float)
        self.highs = np.array(highs if highs else closes, dtype=float)
        self.lows = np.array(lows if lows else closes, dtype=float)
        self.volumes = np.array(volumes if volumes else [1]*len(closes), dtype=float)
        self.opens = np.array(opens if opens else closes, dtype=float)
        self.current_price = self.closes[-1] if len(self.closes) > 0 else 0
    
    # =========================================================================
    # Volatility Indicators
    # =========================================================================
    
    def bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> IndicatorResult:
        """Bollinger Bands - volatility bands around SMA."""
        if len(self.closes) < period:
            return IndicatorResult("Bollinger Bands", 0, Signal.HOLD, "Insufficient data")
        
        sma = self._sma(self.closes, period)
        std = np.array([np.std(self.closes[i:i+period]) for i in range(len(self.closes)-period+1)])
        
        middle = sma[-1]
        upper = middle + std_dev * std[-1]
        lower = middle - std_dev * std[-1]
        
        percent_b = (self.current_price - lower) / (upper - lower) if upper != lower else 0.5
        bandwidth = (upper - lower) / middle * 100 if middle > 0 else 0
        
        if percent_b < 0.2:
            signal = Signal.BUY
            desc = f"Price near lower band ({percent_b:.1%}), potential oversold"
        elif percent_b > 0.8:
            signal = Signal.SELL
            desc = f"Price near upper band ({percent_b:.1%}), potential overbought"
        else:
            signal = Signal.HOLD
            desc = f"Price within bands ({percent_b:.1%})"
        
        return IndicatorResult(
            name="Bollinger Bands",
            value=percent_b,
            signal=signal,
            description=desc,
            details={"upper": round(upper, 2), "middle": round(middle, 2), "lower": round(lower, 2),
                    "percent_b": round(percent_b, 4), "bandwidth": round(bandwidth, 2)}
        )
    
    def atr(self, period: int = 14) -> IndicatorResult:
        """Average True Range - volatility indicator."""
        if len(self.closes) < period:
            return IndicatorResult("ATR", 0, Signal.HOLD, "Insufficient data")
        
        tr = self._true_range()
        atr_values = self._ema(tr, period)
        current_atr = atr_values[-1]
        atr_pct = (current_atr / self.current_price * 100) if self.current_price > 0 else 0
        
        return IndicatorResult(
            name="ATR",
            value=current_atr,
            signal=Signal.HOLD,
            description=f"Volatility {atr_pct:.2f}%",
            details={"atr": round(current_atr, 2), "atr_pct": round(atr_pct, 2)}
        )
    
    def keltner_channels(self, ema_period: int = 20, atr_period: int = 10, 
                         multiplier: float = 2.0) -> IndicatorResult:
        """Keltner Channels - EMA with ATR-based bands."""
        if len(self.closes) < max(ema_period, atr_period):
            return IndicatorResult("Keltner Channels", 0, Signal.HOLD, "Insufficient data")
        
        ema = self._ema(self.closes, ema_period)[-1]
        tr = self._true_range()
        atr = self._ema(tr, atr_period)[-1]
        
        upper = ema + multiplier * atr
        lower = ema - multiplier * atr
        
        if self.current_price > upper:
            signal, desc = Signal.SELL, "Price above upper channel, overbought"
        elif self.current_price < lower:
            signal, desc = Signal.BUY, "Price below lower channel, oversold"
        else:
            signal, desc = Signal.HOLD, "Price within channels"
        
        return IndicatorResult(
            name="Keltner Channels",
            value=(self.current_price - lower) / (upper - lower) if upper != lower else 0.5,
            signal=signal, description=desc,
            details={"upper": round(upper, 2), "middle": round(ema, 2), "lower": round(lower, 2)}
        )
    
    def donchian_channels(self, period: int = 20) -> IndicatorResult:
        """Donchian Channels - highest high and lowest low."""
        if len(self.closes) < period:
            return IndicatorResult("Donchian Channels", 0, Signal.HOLD, "Insufficient data")
        
        upper = np.max(self.highs[-period:])
        lower = np.min(self.lows[-period:])
        middle = (upper + lower) / 2
        position = (self.current_price - lower) / (upper - lower) if upper != lower else 0.5
        
        if self.current_price >= upper:
            signal, desc = Signal.BUY, f"Breakout above {period}-day high"
        elif self.current_price <= lower:
            signal, desc = Signal.SELL, f"Breakdown below {period}-day low"
        else:
            signal, desc = Signal.HOLD, f"Within {period}-day range"
        
        return IndicatorResult(
            name="Donchian Channels", value=position, signal=signal, description=desc,
            details={"upper": round(upper, 2), "middle": round(middle, 2), "lower": round(lower, 2)}
        )
    
    # =========================================================================
    # Trend Indicators
    # =========================================================================
    
    def ichimoku_cloud(self, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> IndicatorResult:
        """Ichimoku Cloud - comprehensive trend indicator."""
        if len(self.closes) < senkou_b:
            return IndicatorResult("Ichimoku Cloud", 0, Signal.HOLD, "Insufficient data")
        
        tenkan_sen = (np.max(self.highs[-tenkan:]) + np.min(self.lows[-tenkan:])) / 2
        kijun_sen = (np.max(self.highs[-kijun:]) + np.min(self.lows[-kijun:])) / 2
        senkou_a = (tenkan_sen + kijun_sen) / 2
        senkou_span_b = (np.max(self.highs[-senkou_b:]) + np.min(self.lows[-senkou_b:])) / 2
        
        cloud_top = max(senkou_a, senkou_span_b)
        cloud_bottom = min(senkou_a, senkou_span_b)
        
        signals = 0
        if self.current_price > cloud_top: signals += 2
        elif self.current_price < cloud_bottom: signals -= 2
        if tenkan_sen > kijun_sen: signals += 1
        else: signals -= 1
        
        if signals >= 2: signal, desc = Signal.STRONG_BUY, "Strong bullish"
        elif signals >= 1: signal, desc = Signal.BUY, "Bullish"
        elif signals <= -2: signal, desc = Signal.STRONG_SELL, "Strong bearish"
        elif signals <= -1: signal, desc = Signal.SELL, "Bearish"
        else: signal, desc = Signal.HOLD, "Neutral"
        
        return IndicatorResult(
            name="Ichimoku Cloud", value=signals, signal=signal, description=desc,
            details={"tenkan_sen": round(tenkan_sen, 2), "kijun_sen": round(kijun_sen, 2),
                    "cloud_top": round(cloud_top, 2), "cloud_bottom": round(cloud_bottom, 2)}
        )
    
    def parabolic_sar(self, af_start: float = 0.02, af_increment: float = 0.02, 
                      af_max: float = 0.2) -> IndicatorResult:
        """Parabolic SAR - trend following stop-and-reverse indicator."""
        if len(self.closes) < 5:
            return IndicatorResult("Parabolic SAR", 0, Signal.HOLD, "Insufficient data")
        
        n = len(self.closes)
        sar = np.zeros(n)
        af = af_start
        ep = self.highs[0]
        uptrend = True
        sar[0] = self.lows[0]
        
        for i in range(1, n):
            if uptrend:
                sar[i] = sar[i-1] + af * (ep - sar[i-1])
                sar[i] = min(sar[i], self.lows[i-1], self.lows[i-2] if i > 1 else self.lows[i-1])
                if self.lows[i] < sar[i]:
                    uptrend, sar[i], ep, af = False, ep, self.lows[i], af_start
                elif self.highs[i] > ep:
                    ep, af = self.highs[i], min(af + af_increment, af_max)
            else:
                sar[i] = sar[i-1] + af * (ep - sar[i-1])
                sar[i] = max(sar[i], self.highs[i-1], self.highs[i-2] if i > 1 else self.highs[i-1])
                if self.highs[i] > sar[i]:
                    uptrend, sar[i], ep, af = True, ep, self.highs[i], af_start
                elif self.lows[i] < ep:
                    ep, af = self.lows[i], min(af + af_increment, af_max)
        
        current_sar = sar[-1]
        is_uptrend = self.current_price > current_sar
        
        return IndicatorResult(
            name="Parabolic SAR", value=current_sar,
            signal=Signal.BUY if is_uptrend else Signal.SELL,
            description=f"{'Up' if is_uptrend else 'Down'}trend - SAR at ${current_sar:.2f}",
            details={"sar": round(current_sar, 2), "trend": "up" if is_uptrend else "down"}
        )
    
    def adx(self, period: int = 14) -> IndicatorResult:
        """Average Directional Index - trend strength indicator."""
        if len(self.closes) < period * 2:
            return IndicatorResult("ADX", 0, Signal.HOLD, "Insufficient data")
        
        up_move = self.highs[1:] - self.highs[:-1]
        down_move = self.lows[:-1] - self.lows[1:]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        tr = self._true_range()[1:]
        tr_smooth = self._ema(tr, period)
        plus_dm_smooth = self._ema(plus_dm, period)
        minus_dm_smooth = self._ema(minus_dm, period)
        
        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx_values = self._ema(dx, period)
        
        current_adx = adx_values[-1]
        
        if current_adx > 25:
            signal = Signal.BUY if plus_di[-1] > minus_di[-1] else Signal.SELL
            desc = f"Strong {'up' if plus_di[-1] > minus_di[-1] else 'down'}trend (ADX={current_adx:.1f})"
        else:
            signal, desc = Signal.HOLD, f"Weak trend (ADX={current_adx:.1f})"
        
        return IndicatorResult(
            name="ADX", value=current_adx, signal=signal, description=desc,
            details={"adx": round(current_adx, 2), "plus_di": round(plus_di[-1], 2), "minus_di": round(minus_di[-1], 2)}
        )
    
    # =========================================================================
    # Momentum Indicators
    # =========================================================================
    
    def cci(self, period: int = 20) -> IndicatorResult:
        """Commodity Channel Index - momentum oscillator."""
        if len(self.closes) < period:
            return IndicatorResult("CCI", 0, Signal.HOLD, "Insufficient data")
        
        typical_price = (self.highs + self.lows + self.closes) / 3
        sma = self._sma(typical_price, period)[-1]
        mean_dev = np.mean(np.abs(typical_price[-period:] - sma))
        cci = (typical_price[-1] - sma) / (0.015 * mean_dev) if mean_dev > 0 else 0
        
        if cci > 100: signal, desc = Signal.SELL, f"Overbought (CCI={cci:.0f})"
        elif cci < -100: signal, desc = Signal.BUY, f"Oversold (CCI={cci:.0f})"
        else: signal, desc = Signal.HOLD, f"Neutral (CCI={cci:.0f})"
        
        return IndicatorResult(name="CCI", value=cci, signal=signal, description=desc, details={"cci": round(cci, 2)})
    
    def williams_r(self, period: int = 14) -> IndicatorResult:
        """Williams %R - momentum indicator."""
        if len(self.closes) < period:
            return IndicatorResult("Williams %R", 0, Signal.HOLD, "Insufficient data")
        
        highest_high = np.max(self.highs[-period:])
        lowest_low = np.min(self.lows[-period:])
        williams_r = -100 * (highest_high - self.current_price) / (highest_high - lowest_low) if highest_high != lowest_low else -50
        
        if williams_r > -20: signal, desc = Signal.SELL, f"Overbought (%R={williams_r:.0f})"
        elif williams_r < -80: signal, desc = Signal.BUY, f"Oversold (%R={williams_r:.0f})"
        else: signal, desc = Signal.HOLD, f"Neutral (%R={williams_r:.0f})"
        
        return IndicatorResult(name="Williams %R", value=williams_r, signal=signal, description=desc, details={"williams_r": round(williams_r, 2)})
        self.opens = np.array(opens if opens else closes, dtype=float)
        self.current_price = self.closes[-1] if len(self.closes) > 0 else 0
    
    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        if len(data) < period:
            return np.full(len(data), np.nan)
        return np.convolve(data, np.ones(period)/period, mode='valid')
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        if len(data) < period:
            return np.full(len(data), np.nan)
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        return ema
    
    def _true_range(self) -> np.ndarray:
        """Calculate True Range."""
        high_low = self.highs - self.lows
        high_close = np.abs(self.highs[1:] - self.closes[:-1])
        low_close = np.abs(self.lows[1:] - self.closes[:-1])
        tr = np.zeros(len(self.closes))
        tr[0] = high_low[0]
        tr[1:] = np.maximum(high_low[1:], np.maximum(high_close, low_close))
        return tr

    # =========================================================================
    # Volume Indicators
    # =========================================================================
    
    def obv(self) -> IndicatorResult:
        """
        On-Balance Volume - cumulative volume indicator.
        Rising OBV = accumulation, Falling OBV = distribution
        """
        if len(self.closes) < 2:
            return IndicatorResult("OBV", 0, Signal.HOLD, "Insufficient data")
        
        obv = np.zeros(len(self.closes))
        obv[0] = self.volumes[0]
        
        for i in range(1, len(self.closes)):
            if self.closes[i] > self.closes[i-1]:
                obv[i] = obv[i-1] + self.volumes[i]
            elif self.closes[i] < self.closes[i-1]:
                obv[i] = obv[i-1] - self.volumes[i]
            else:
                obv[i] = obv[i-1]
        
        # OBV trend (compare to 20-day average)
        if len(obv) >= 20:
            obv_sma = np.mean(obv[-20:])
            current_obv = obv[-1]
            
            if current_obv > obv_sma * 1.05:
                signal = Signal.BUY
                desc = "OBV rising - accumulation"
            elif current_obv < obv_sma * 0.95:
                signal = Signal.SELL
                desc = "OBV falling - distribution"
            else:
                signal = Signal.HOLD
                desc = "OBV neutral"
        else:
            signal = Signal.HOLD
            desc = "OBV neutral"
            current_obv = obv[-1]
        
        return IndicatorResult(
            name="OBV",
            value=current_obv,
            signal=signal,
            description=desc,
            details={"obv": round(current_obv, 0)}
        )
    
    def vwap(self) -> IndicatorResult:
        """
        Volume Weighted Average Price.
        Price above VWAP = bullish, below = bearish
        """
        if len(self.closes) < 1:
            return IndicatorResult("VWAP", 0, Signal.HOLD, "Insufficient data")
        
        typical_price = (self.highs + self.lows + self.closes) / 3
        vwap = np.cumsum(typical_price * self.volumes) / np.cumsum(self.volumes)
        
        current_vwap = vwap[-1]
        distance_pct = (self.current_price - current_vwap) / current_vwap * 100
        
        if self.current_price > current_vwap * 1.02:
            signal = Signal.BUY
            desc = f"Price {distance_pct:.1f}% above VWAP - bullish"
        elif self.current_price < current_vwap * 0.98:
            signal = Signal.SELL
            desc = f"Price {abs(distance_pct):.1f}% below VWAP - bearish"
        else:
            signal = Signal.HOLD
            desc = f"Price near VWAP"
        
        return IndicatorResult(
            name="VWAP",
            value=current_vwap,
            signal=signal,
            description=desc,
            details={
                "vwap": round(current_vwap, 2),
                "distance_pct": round(distance_pct, 2)
            }
        )
    
    def chaikin_money_flow(self, period: int = 20) -> IndicatorResult:
        """
        Chaikin Money Flow - buying/selling pressure.
        CMF > 0: Buying pressure, CMF < 0: Selling pressure
        """
        if len(self.closes) < period:
            return IndicatorResult("CMF", 0, Signal.HOLD, "Insufficient data")
        
        # Money Flow Multiplier
        mfm = ((self.closes - self.lows) - (self.highs - self.closes)) / (self.highs - self.lows + 1e-10)
        
        # Money Flow Volume
        mfv = mfm * self.volumes
        
        # CMF
        cmf = np.sum(mfv[-period:]) / np.sum(self.volumes[-period:])
        
        if cmf > 0.1:
            signal = Signal.BUY
            desc = f"Strong buying pressure (CMF={cmf:.2f})"
        elif cmf > 0:
            signal = Signal.BUY
            desc = f"Mild buying pressure (CMF={cmf:.2f})"
        elif cmf < -0.1:
            signal = Signal.SELL
            desc = f"Strong selling pressure (CMF={cmf:.2f})"
        elif cmf < 0:
            signal = Signal.SELL
            desc = f"Mild selling pressure (CMF={cmf:.2f})"
        else:
            signal = Signal.HOLD
            desc = "Neutral"
        
        return IndicatorResult(
            name="Chaikin Money Flow",
            value=cmf,
            signal=signal,
            description=desc,
            details={"cmf": round(cmf, 4)}
        )
    
    def accumulation_distribution(self) -> IndicatorResult:
        """
        Accumulation/Distribution Line.
        """
        if len(self.closes) < 2:
            return IndicatorResult("A/D Line", 0, Signal.HOLD, "Insufficient data")
        
        mfm = ((self.closes - self.lows) - (self.highs - self.closes)) / (self.highs - self.lows + 1e-10)
        mfv = mfm * self.volumes
        ad = np.cumsum(mfv)
        
        # Trend
        if len(ad) >= 20:
            ad_sma = np.mean(ad[-20:])
            if ad[-1] > ad_sma:
                signal = Signal.BUY
                desc = "A/D rising - accumulation"
            else:
                signal = Signal.SELL
                desc = "A/D falling - distribution"
        else:
            signal = Signal.HOLD
            desc = "A/D neutral"
        
        return IndicatorResult(
            name="A/D Line",
            value=ad[-1],
            signal=signal,
            description=desc,
            details={"ad": round(ad[-1], 0)}
        )
    
    # =========================================================================
    # Support/Resistance
    # =========================================================================
    
    def fibonacci_retracements(self) -> IndicatorResult:
        """
        Fibonacci Retracement Levels based on recent swing.
        """
        if len(self.closes) < 20:
            return IndicatorResult("Fibonacci", 0, Signal.HOLD, "Insufficient data")
        
        # Find recent high and low
        high = np.max(self.highs[-50:]) if len(self.highs) >= 50 else np.max(self.highs)
        low = np.min(self.lows[-50:]) if len(self.lows) >= 50 else np.min(self.lows)
        
        diff = high - low
        
        # Fibonacci levels
        levels = {
            "0.0": high,
            "0.236": high - diff * 0.236,
            "0.382": high - diff * 0.382,
            "0.5": high - diff * 0.5,
            "0.618": high - diff * 0.618,
            "0.786": high - diff * 0.786,
            "1.0": low
        }
        
        # Find nearest level
        nearest_level = None
        nearest_distance = float('inf')
        for name, level in levels.items():
            distance = abs(self.current_price - level)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_level = (name, level)
        
        # Determine position
        price_position = (high - self.current_price) / diff if diff > 0 else 0.5
        
        if price_position < 0.382:
            signal = Signal.BUY
            desc = f"Near Fib support at 0.382 (${levels['0.382']:.2f})"
        elif price_position > 0.618:
            signal = Signal.SELL
            desc = f"Near Fib resistance at 0.618 (${levels['0.618']:.2f})"
        else:
            signal = Signal.HOLD
            desc = f"Between Fib levels"
        
        return IndicatorResult(
            name="Fibonacci Retracements",
            value=price_position,
            signal=signal,
            description=desc,
            details={
                "levels": {k: round(v, 2) for k, v in levels.items()},
                "nearest": nearest_level[0] if nearest_level else None,
                "swing_high": round(high, 2),
                "swing_low": round(low, 2)
            }
        )
    
    def pivot_points(self) -> IndicatorResult:
        """
        Pivot Points - classic support/resistance levels.
        """
        if len(self.closes) < 2:
            return IndicatorResult("Pivot Points", 0, Signal.HOLD, "Insufficient data")
        
        # Use previous day's data
        high = self.highs[-2] if len(self.highs) > 1 else self.highs[-1]
        low = self.lows[-2] if len(self.lows) > 1 else self.lows[-1]
        close = self.closes[-2] if len(self.closes) > 1 else self.closes[-1]
        
        # Calculate pivot point
        pivot = (high + low + close) / 3
        
        # Support and Resistance levels
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        levels = {
            "R3": r3, "R2": r2, "R1": r1,
            "Pivot": pivot,
            "S1": s1, "S2": s2, "S3": s3
        }
        
        # Determine signal based on position
        if self.current_price > r1:
            signal = Signal.SELL
            desc = f"Above R1 (${r1:.2f}), watch R2 at ${r2:.2f}"
        elif self.current_price < s1:
            signal = Signal.BUY
            desc = f"Below S1 (${s1:.2f}), watch S2 at ${s2:.2f}"
        elif self.current_price > pivot:
            signal = Signal.BUY
            desc = f"Above pivot (${pivot:.2f}), bullish bias"
        else:
            signal = Signal.SELL
            desc = f"Below pivot (${pivot:.2f}), bearish bias"
        
        return IndicatorResult(
            name="Pivot Points",
            value=pivot,
            signal=signal,
            description=desc,
            details={k: round(v, 2) for k, v in levels.items()}
        )
    
    # =========================================================================
    # Calculate All
    # =========================================================================
    
    def calculate_all(self) -> List[IndicatorResult]:
        """Calculate all available indicators."""
        results = []
        
        # Volatility
        try:
            results.append(self.bollinger_bands())
        except Exception:
            pass
        try:
            results.append(self.atr())
        except Exception:
            pass
        try:
            results.append(self.keltner_channels())
        except Exception:
            pass
        try:
            results.append(self.donchian_channels())
        except Exception:
            pass
        
        # Trend
        try:
            results.append(self.ichimoku_cloud())
        except Exception:
            pass
        try:
            results.append(self.parabolic_sar())
        except Exception:
            pass
        try:
            results.append(self.adx())
        except Exception:
            pass
        try:
            results.append(self.supertrend())
        except Exception:
            pass
        try:
            results.append(self.aroon())
        except Exception:
            pass
        
        # Momentum
        try:
            results.append(self.cci())
        except Exception:
            pass
        try:
            results.append(self.williams_r())
        except Exception:
            pass
        try:
            results.append(self.stochastic_rsi())
        except Exception:
            pass
        
        # Volume
        try:
            results.append(self.obv())
        except Exception:
            pass
        try:
            results.append(self.vwap())
        except Exception:
            pass
        try:
            results.append(self.chaikin_money_flow())
        except Exception:
            pass
        
        # Support/Resistance
        try:
            results.append(self.fibonacci_retracements())
        except Exception:
            pass
        try:
            results.append(self.pivot_points())
        except Exception:
            pass
        
        return results
    
    def get_summary(self) -> Dict:
        """Get summary of all indicators."""
        results = self.calculate_all()
        
        buy_count = sum(1 for r in results if r.signal in [Signal.BUY, Signal.STRONG_BUY])
        sell_count = sum(1 for r in results if r.signal in [Signal.SELL, Signal.STRONG_SELL])
        hold_count = sum(1 for r in results if r.signal == Signal.HOLD)
        
        if buy_count > sell_count * 1.5:
            overall = Signal.BUY
        elif sell_count > buy_count * 1.5:
            overall = Signal.SELL
        else:
            overall = Signal.HOLD
        
        return {
            "overall_signal": overall.value,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "hold_signals": hold_count,
            "total_indicators": len(results),
            "indicators": [r.to_dict() for r in results]
        }


if __name__ == "__main__":
    # Demo with sample data
    import random
    
    # Generate sample price data
    np.random.seed(42)
    n = 100
    base_price = 150
    closes = [base_price]
    for _ in range(n-1):
        closes.append(closes[-1] * (1 + np.random.randn() * 0.02))
    
    highs = [c * (1 + abs(np.random.randn() * 0.01)) for c in closes]
    lows = [c * (1 - abs(np.random.randn() * 0.01)) for c in closes]
    volumes = [int(1000000 * (1 + np.random.rand())) for _ in closes]
    
    # Calculate indicators
    ti = TechnicalIndicators(closes, highs, lows, volumes)
    
    print("="*60)
    print("ADVANCED TECHNICAL INDICATORS")
    print("="*60)
    print(f"Current Price: ${closes[-1]:.2f}")
    print()
    
    summary = ti.get_summary()
    print(f"Overall Signal: {summary['overall_signal']}")
    print(f"Buy Signals: {summary['buy_signals']}")
    print(f"Sell Signals: {summary['sell_signals']}")
    print(f"Hold Signals: {summary['hold_signals']}")
    print()
    
    print("Individual Indicators:")
    print("-"*60)
    for ind in summary['indicators']:
        print(f"  {ind['name']}: {ind['signal']} - {ind['description']}")
