#!/usr/bin/env python3
"""
Stock Analyzer - Comprehensive Analysis & Recommendations
==========================================================
Multi-source analysis combining:
1. Technical Analysis (Alpaca/Yahoo/FMP) - Price patterns, indicators
2. Fundamental Analysis (FMP/Yahoo) - Valuation, financials
3. Analyst Data (FMP) - Price targets, DCF
4. Risk Analysis - VaR, volatility, drawdown

Supports global exchanges with professional format:
    python3 trade.py analyze NYSE:AAPL
    python3 trade.py analyze ASX:BHP
    python3 trade.py analyze BHP.AX
    python3 trade.py analyze LSE:VOD

Data Sources (in priority order):
- Alpaca: US stocks (most reliable)
- FMP: Global fundamentals + historical
- Yahoo Finance: Global backup
- Twelve Data: Additional backup

Usage:
    python3 trade.py analyze AAPL
    python3 trade.py analyze ASX:CBA --brief
    python3 trade.py analyze AAPL MSFT ASX:BHP --brief
"""

import os
import json
import math
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

ssl._create_default_https_context = ssl._create_unverified_context

# Import exchange mapper
try:
    from trading.exchanges import ExchangeMapper, ExchangeSymbol
except ImportError:
    ExchangeMapper = None
    ExchangeSymbol = None

# Import multi-source data fetcher
try:
    from trading.data_sources import DataFetcher
    DATA_FETCHER_AVAILABLE = True
except ImportError:
    DataFetcher = None
    DATA_FETCHER_AVAILABLE = False


class Signal(Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK BUY"
    HOLD = "HOLD"
    WEAK_SELL = "WEAK SELL"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


class Trend(Enum):
    STRONG_UP = "Strong Uptrend"
    UP = "Uptrend"
    SIDEWAYS = "Sideways"
    DOWN = "Downtrend"
    STRONG_DOWN = "Strong Downtrend"


@dataclass
class TechnicalSignal:
    name: str
    value: float
    signal: str
    strength: float
    description: str


@dataclass
class FundamentalSignal:
    name: str
    value: Optional[float]
    signal: str
    strength: float
    description: str


@dataclass
class AnalystSignal:
    name: str
    value: Optional[float]
    signal: str
    strength: float
    description: str


@dataclass 
class RiskMetrics:
    volatility_annual: float
    volatility_rating: str
    var_95: float
    max_drawdown: float
    sharpe_ratio: float
    risk_score: float


@dataclass
class AnalysisResult:
    symbol: str
    exchange: str
    display_symbol: str  # EXCHANGE:SYMBOL format
    company_name: str
    sector: str
    industry: str
    country: str
    currency: str
    currency_symbol: str  # $, £, €, etc.
    price_divisor: float  # For GBp -> GBP conversion (100)
    current_price: float
    prev_close: float
    change: float
    change_pct: float
    market_cap: float
    beta: float
    pe_ratio: float
    timestamp: datetime
    
    technical_signals: List[TechnicalSignal]
    fundamental_signals: List[FundamentalSignal]
    analyst_signals: List[AnalystSignal]
    risk_metrics: RiskMetrics
    
    technical_score: float
    fundamental_score: float
    analyst_score: float
    risk_score: float
    overall_score: float
    
    recommendation: Signal
    confidence: float
    trend: Trend
    
    support_levels: List[float]
    resistance_levels: List[float]
    
    target_low: float
    target_mid: float  
    target_high: float
    dcf_value: Optional[float]
    
    week_52_high: float
    week_52_low: float
    week_52_position: float
    
    summary: str
    key_factors: List[str]


# ============================================================================
# Data Fetchers
# ============================================================================

class AlpacaFetcher:
    """Alpaca API - US stocks only."""
    
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.url = "https://data.alpaca.markets"
        if not self.api_key:
            raise ValueError("ALPACA_API_KEY not set")
    
    def _request(self, endpoint: str) -> Dict:
        headers = {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}
        req = urllib.request.Request(f"{self.url}{endpoint}", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    
    def get_bars(self, symbol: str, days: int = 400) -> List[Dict]:
        end = datetime.now()
        start = end - timedelta(days=days)
        endpoint = (f"/v2/stocks/{symbol}/bars?timeframe=1Day"
                   f"&start={start.strftime('%Y-%m-%d')}&end={end.strftime('%Y-%m-%d')}"
                   f"&limit=1000&feed=iex")
        data = self._request(endpoint)
        return [{"date": b["t"], "open": b["o"], "high": b["h"], 
                 "low": b["l"], "close": b["c"], "volume": b["v"]} 
                for b in data.get("bars", [])]


class YahooFetcher:
    """Yahoo Finance - International stocks."""
    
    def __init__(self):
        pass
    
    def get_bars(self, symbol: str, days: int = 400) -> List[Dict]:
        """Fetch historical bars from Yahoo Finance."""
        try:
            # Yahoo uses range parameter (1y, 2y, 5y, max) or period1/period2
            # Using range is more reliable
            range_map = {400: "2y", 252: "1y", 100: "6mo", 30: "1mo"}
            range_val = "2y"
            for d, r in sorted(range_map.items()):
                if days <= d:
                    range_val = r
                    break
            
            # URL encode the symbol (handles . in symbol)
            import urllib.parse
            encoded_symbol = urllib.parse.quote(symbol)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?interval=1d&range={range_val}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            
            result = data.get("chart", {}).get("result", [])
            if not result:
                # Try alternative API
                return self._try_alternative(symbol, days)
            
            quotes = result[0]
            timestamps = quotes.get("timestamp", [])
            ohlc = quotes.get("indicators", {}).get("quote", [{}])[0]
            
            if not timestamps:
                return self._try_alternative(symbol, days)
            
            bars = []
            for i, ts in enumerate(timestamps):
                close = ohlc.get("close", [None])[i]
                if close is not None:
                    bars.append({
                        "date": datetime.fromtimestamp(ts).isoformat(),
                        "open": ohlc.get("open", [0])[i] or close,
                        "high": ohlc.get("high", [0])[i] or close,
                        "low": ohlc.get("low", [0])[i] or close,
                        "close": close,
                        "volume": ohlc.get("volume", [0])[i] or 0,
                    })
            return bars
            
        except urllib.error.HTTPError as e:
            print(f"  [WARN] Yahoo Finance HTTP error: {e.code} - trying alternative...")
            return self._try_alternative(symbol, days)
        except Exception as e:
            print(f"  [WARN] Yahoo Finance error: {e}")
            return self._try_alternative(symbol, days)
    
    def _try_alternative(self, symbol: str, days: int) -> List[Dict]:
        """Try alternative Yahoo Finance endpoint."""
        try:
            import urllib.parse
            encoded_symbol = urllib.parse.quote(symbol)
            
            # Try the v7 download endpoint
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=days)).timestamp())
            
            url = f"https://query1.finance.yahoo.com/v7/finance/download/{encoded_symbol}?period1={start}&period2={end}&interval=1d&events=history"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                csv_data = resp.read().decode()
            
            bars = []
            lines = csv_data.strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split(',')
                if len(parts) >= 6 and parts[4] != 'null':
                    try:
                        bars.append({
                            "date": parts[0],
                            "open": float(parts[1]) if parts[1] != 'null' else 0,
                            "high": float(parts[2]) if parts[2] != 'null' else 0,
                            "low": float(parts[3]) if parts[3] != 'null' else 0,
                            "close": float(parts[4]) if parts[4] != 'null' else 0,
                            "volume": int(float(parts[6])) if len(parts) > 6 and parts[6] != 'null' else 0,
                        })
                    except (ValueError, IndexError):
                        continue
            return bars
            
        except Exception as e:
            print(f"  [WARN] Yahoo alternative also failed: {e}")
            return []


class FMPFetcher:
    """Financial Modeling Prep API - uses STABLE endpoints."""
    
    def __init__(self):
        self.api_key = os.getenv("FMP_API_KEY", "")
        self.url = "https://financialmodelingprep.com/stable"
        if not self.api_key:
            print("  [WARN] FMP_API_KEY not set - fundamentals limited")
    
    def _request(self, endpoint: str) -> any:
        if not self.api_key:
            return None
        try:
            url = f"{self.url}/{endpoint}&apikey={self.api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list) and data:
                    return data[0]
                return data
        except Exception as e:
            return None
    
    def get_profile(self, symbol: str) -> Dict:
        return self._request(f"profile?symbol={symbol}") or {}
    
    def get_quote(self, symbol: str) -> Dict:
        return self._request(f"quote?symbol={symbol}") or {}
    
    def get_ratios(self, symbol: str) -> Dict:
        return self._request(f"ratios-ttm?symbol={symbol}") or {}
    
    def get_key_metrics(self, symbol: str) -> Dict:
        return self._request(f"key-metrics-ttm?symbol={symbol}") or {}
    
    def get_growth(self, symbol: str) -> Dict:
        return self._request(f"financial-growth?symbol={symbol}") or {}
    
    def get_dcf(self, symbol: str) -> Optional[float]:
        data = self._request(f"discounted-cash-flow?symbol={symbol}")
        if data:
            return data.get("dcf")
        return None
    
    def get_price_target(self, symbol: str) -> Dict:
        return self._request(f"price-target-consensus?symbol={symbol}") or {}
    
    def get_dividends(self, symbol: str) -> List[Dict]:
        """Get dividend history for a symbol."""
        try:
            # Use v3 API endpoint for historical dividends
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{symbol}?apikey={self.api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            
            if data and 'historical' in data:
                return data['historical'][:50]  # Return last 50 dividends
            return []
        except Exception:
            return []


# ============================================================================
# Technical Analysis
# ============================================================================

class TechnicalAnalyzer:
    def __init__(self, bars: List[Dict]):
        self.closes = [b["close"] for b in bars]
        self.highs = [b["high"] for b in bars]
        self.lows = [b["low"] for b in bars]
        self.volumes = [b["volume"] for b in bars]
    
    def sma(self, period: int) -> float:
        if len(self.closes) < period: return self.closes[-1]
        return sum(self.closes[-period:]) / period
    
    def rsi(self, period: int = 14) -> float:
        if len(self.closes) < period + 1: return 50
        gains, losses = [], []
        for i in range(1, len(self.closes)):
            chg = self.closes[i] - self.closes[i-1]
            gains.append(max(0, chg))
            losses.append(max(0, -chg))
        avg_g = sum(gains[-period:]) / period
        avg_l = sum(losses[-period:]) / period
        if avg_l == 0: return 100
        return 100 - (100 / (1 + avg_g / avg_l))
    
    def macd(self) -> Tuple[float, float, float]:
        if len(self.closes) < 26: return 0, 0, 0
        def ema(data, p):
            m = 2/(p+1)
            e = data[0]
            for v in data[1:]: e = (v-e)*m + e
            return e
        ema12, ema26 = ema(self.closes, 12), ema(self.closes, 26)
        macd_val = ema12 - ema26
        
        ema12_h, ema26_h = [self.closes[0]], [self.closes[0]]
        for p in self.closes[1:]:
            ema12_h.append((p - ema12_h[-1]) * 2/13 + ema12_h[-1])
            ema26_h.append((p - ema26_h[-1]) * 2/27 + ema26_h[-1])
        macd_h = [ema12_h[i] - ema26_h[i] for i in range(25, len(self.closes))]
        if len(macd_h) < 9: return macd_val, macd_val, 0
        sig = macd_h[0]
        for m in macd_h[1:]: sig = (m - sig) * 2/10 + sig
        return macd_val, sig, macd_val - sig
    
    def bollinger(self, p=20) -> Tuple[float, float, float]:
        if len(self.closes) < p: return self.closes[-1]*1.02, self.closes[-1], self.closes[-1]*0.98
        sma = sum(self.closes[-p:]) / p
        std = math.sqrt(sum((x-sma)**2 for x in self.closes[-p:]) / p)
        return sma + 2*std, sma, sma - 2*std
    
    def stochastic(self, p=14) -> float:
        if len(self.closes) < p: return 50
        h, l = max(self.highs[-p:]), min(self.lows[-p:])
        if h == l: return 50
        return ((self.closes[-1] - l) / (h - l)) * 100
    
    def atr(self, p=14) -> float:
        if len(self.closes) < p + 1: return 0
        tr = [max(self.highs[i]-self.lows[i], abs(self.highs[i]-self.closes[i-1]), 
                  abs(self.lows[i]-self.closes[i-1])) for i in range(1, len(self.closes))]
        return sum(tr[-p:]) / p
    
    def trend(self) -> Trend:
        if len(self.closes) < 50: return Trend.SIDEWAYS
        sma20, sma50 = sum(self.closes[-20:])/20, sum(self.closes[-50:])/50
        curr = self.closes[-1]
        mom = (curr - self.closes[-20]) / self.closes[-20] * 100
        if curr > sma20 > sma50 and mom > 5: return Trend.STRONG_UP
        if curr > sma20 and curr > sma50: return Trend.UP
        if curr < sma20 < sma50 and mom < -5: return Trend.STRONG_DOWN
        if curr < sma20 and curr < sma50: return Trend.DOWN
        return Trend.SIDEWAYS
    
    def support_resistance(self) -> Tuple[List[float], List[float]]:
        if len(self.closes) < 20: return [], []
        sups, ress = [], []
        w = min(10, len(self.closes)//4)
        for i in range(w, len(self.closes)-w):
            if self.lows[i] == min(self.lows[i-w:i+w+1]): sups.append(self.lows[i])
            if self.highs[i] == max(self.highs[i-w:i+w+1]): ress.append(self.highs[i])
        curr = self.closes[-1]
        return sorted(set(round(s,2) for s in sups if s < curr))[-3:], sorted(set(round(r,2) for r in ress if r > curr))[:3]
    
    def generate_signals(self) -> List[TechnicalSignal]:
        sigs = []
        curr = self.closes[-1]
        
        # RSI
        rsi = self.rsi()
        if rsi < 30: sigs.append(TechnicalSignal("RSI (14)", rsi, "BUY", 0.8, f"Oversold at {rsi:.1f}"))
        elif rsi < 40: sigs.append(TechnicalSignal("RSI (14)", rsi, "BUY", 0.5, f"Near oversold at {rsi:.1f}"))
        elif rsi > 70: sigs.append(TechnicalSignal("RSI (14)", rsi, "SELL", 0.8, f"Overbought at {rsi:.1f}"))
        elif rsi > 60: sigs.append(TechnicalSignal("RSI (14)", rsi, "SELL", 0.5, f"Near overbought at {rsi:.1f}"))
        else: sigs.append(TechnicalSignal("RSI (14)", rsi, "NEUTRAL", 0.3, f"Neutral at {rsi:.1f}"))
        
        # MACD
        macd, sig, hist = self.macd()
        if hist > 0 and macd > 0: sigs.append(TechnicalSignal("MACD", hist, "BUY", 0.7, "Bullish above zero line"))
        elif hist > 0: sigs.append(TechnicalSignal("MACD", hist, "BUY", 0.5, "Bullish crossover"))
        elif hist < 0 and macd < 0: sigs.append(TechnicalSignal("MACD", hist, "SELL", 0.7, "Bearish below zero line"))
        elif hist < 0: sigs.append(TechnicalSignal("MACD", hist, "SELL", 0.5, "Bearish crossover"))
        else: sigs.append(TechnicalSignal("MACD", hist, "NEUTRAL", 0.3, "Neutral"))
        
        # Moving Averages
        if len(self.closes) >= 50:
            sma20, sma50 = self.sma(20), self.sma(50)
            pct = (curr - sma20) / sma20 * 100
            if curr > sma20 > sma50: sigs.append(TechnicalSignal("Moving Avgs", pct, "BUY", 0.7, f"Bullish alignment ({pct:+.1f}% from 20d)"))
            elif curr > sma20: sigs.append(TechnicalSignal("Moving Avgs", pct, "BUY", 0.4, f"Above 20-day SMA ({pct:+.1f}%)"))
            elif curr < sma20 < sma50: sigs.append(TechnicalSignal("Moving Avgs", pct, "SELL", 0.7, f"Bearish alignment ({pct:+.1f}% from 20d)"))
            elif curr < sma20: sigs.append(TechnicalSignal("Moving Avgs", pct, "SELL", 0.4, f"Below 20-day SMA ({pct:+.1f}%)"))
            else: sigs.append(TechnicalSignal("Moving Avgs", pct, "NEUTRAL", 0.3, "Mixed signals"))
        
        # Bollinger
        up, mid, lo = self.bollinger()
        if curr < lo: sigs.append(TechnicalSignal("Bollinger", curr, "BUY", 0.7, "Below lower band - oversold"))
        elif curr > up: sigs.append(TechnicalSignal("Bollinger", curr, "SELL", 0.7, "Above upper band - overbought"))
        else:
            pos = (curr - lo) / (up - lo) * 100 if up != lo else 50
            if pos < 30: sigs.append(TechnicalSignal("Bollinger", pos, "BUY", 0.4, f"Near lower band ({pos:.0f}%)"))
            elif pos > 70: sigs.append(TechnicalSignal("Bollinger", pos, "SELL", 0.4, f"Near upper band ({pos:.0f}%)"))
            else: sigs.append(TechnicalSignal("Bollinger", pos, "NEUTRAL", 0.3, f"Mid-band ({pos:.0f}%)"))
        
        # Stochastic
        stoch = self.stochastic()
        if stoch < 20: sigs.append(TechnicalSignal("Stochastic", stoch, "BUY", 0.7, f"Oversold at {stoch:.1f}"))
        elif stoch > 80: sigs.append(TechnicalSignal("Stochastic", stoch, "SELL", 0.7, f"Overbought at {stoch:.1f}"))
        else: sigs.append(TechnicalSignal("Stochastic", stoch, "NEUTRAL", 0.3, f"Neutral at {stoch:.1f}"))
        
        # Momentum
        if len(self.closes) >= 20:
            mom = (curr - self.closes[-20]) / self.closes[-20] * 100
            if mom > 10: sigs.append(TechnicalSignal("Momentum", mom, "BUY", 0.6, f"Strong momentum +{mom:.1f}% (20d)"))
            elif mom > 5: sigs.append(TechnicalSignal("Momentum", mom, "BUY", 0.4, f"Positive momentum +{mom:.1f}% (20d)"))
            elif mom < -10: sigs.append(TechnicalSignal("Momentum", mom, "SELL", 0.6, f"Weak momentum {mom:.1f}% (20d)"))
            elif mom < -5: sigs.append(TechnicalSignal("Momentum", mom, "SELL", 0.4, f"Negative momentum {mom:.1f}% (20d)"))
            else: sigs.append(TechnicalSignal("Momentum", mom, "NEUTRAL", 0.2, f"Flat momentum {mom:+.1f}% (20d)"))
        
        # Volume
        if len(self.volumes) >= 20:
            avg, rec = sum(self.volumes[-20:])/20, sum(self.volumes[-5:])/5
            ratio = rec / avg if avg > 0 else 1
            up = self.closes[-1] > self.closes[-5]
            if ratio > 1.5 and up: sigs.append(TechnicalSignal("Volume", ratio, "BUY", 0.5, f"High volume buying ({ratio:.1f}x avg)"))
            elif ratio > 1.5: sigs.append(TechnicalSignal("Volume", ratio, "SELL", 0.5, f"High volume selling ({ratio:.1f}x avg)"))
            else: sigs.append(TechnicalSignal("Volume", ratio, "NEUTRAL", 0.2, f"Normal volume ({ratio:.1f}x avg)"))
        
        return sigs


# ============================================================================
# Fundamental Analysis (using correct FMP field names)
# ============================================================================

class FundamentalAnalyzer:
    def __init__(self, profile: Dict, quote: Dict, ratios: Dict, metrics: Dict, growth: Dict):
        self.profile = profile
        self.quote = quote
        self.ratios = ratios
        self.metrics = metrics
        self.growth = growth
    
    def generate_signals(self) -> List[FundamentalSignal]:
        sigs = []
        
        # P/E Ratio (correct field: priceToEarningsRatioTTM)
        pe = self.ratios.get("priceToEarningsRatioTTM")
        if pe and pe > 0:
            if pe < 12: sigs.append(FundamentalSignal("P/E Ratio", pe, "BUY", 0.7, f"Cheap valuation (P/E: {pe:.1f})"))
            elif pe < 20: sigs.append(FundamentalSignal("P/E Ratio", pe, "BUY", 0.4, f"Fair value (P/E: {pe:.1f})"))
            elif pe < 30: sigs.append(FundamentalSignal("P/E Ratio", pe, "NEUTRAL", 0.3, f"Moderate valuation (P/E: {pe:.1f})"))
            elif pe < 50: sigs.append(FundamentalSignal("P/E Ratio", pe, "SELL", 0.4, f"Expensive (P/E: {pe:.1f})"))
            else: sigs.append(FundamentalSignal("P/E Ratio", pe, "SELL", 0.6, f"Very expensive (P/E: {pe:.1f})"))
        
        # PEG Ratio (correct field: priceToEarningsGrowthRatioTTM)
        peg = self.ratios.get("priceToEarningsGrowthRatioTTM")
        if peg and peg > 0:
            if peg < 1: sigs.append(FundamentalSignal("PEG Ratio", peg, "BUY", 0.7, f"Undervalued vs growth (PEG: {peg:.2f})"))
            elif peg < 1.5: sigs.append(FundamentalSignal("PEG Ratio", peg, "BUY", 0.4, f"Fair for growth (PEG: {peg:.2f})"))
            elif peg < 2: sigs.append(FundamentalSignal("PEG Ratio", peg, "NEUTRAL", 0.3, f"Fairly valued (PEG: {peg:.2f})"))
            elif peg < 3: sigs.append(FundamentalSignal("PEG Ratio", peg, "SELL", 0.4, f"Pricey vs growth (PEG: {peg:.2f})"))
            else: sigs.append(FundamentalSignal("PEG Ratio", peg, "SELL", 0.6, f"Overvalued vs growth (PEG: {peg:.2f})"))
        
        # Price to Book (correct field: priceToBookRatioTTM)
        pb = self.ratios.get("priceToBookRatioTTM")
        if pb:
            if pb < 1: sigs.append(FundamentalSignal("Price/Book", pb, "BUY", 0.7, f"Below book value (P/B: {pb:.2f})"))
            elif pb < 3: sigs.append(FundamentalSignal("Price/Book", pb, "BUY", 0.3, f"Fair value (P/B: {pb:.2f})"))
            elif pb < 10: sigs.append(FundamentalSignal("Price/Book", pb, "NEUTRAL", 0.2, f"Premium to book (P/B: {pb:.1f})"))
            else: sigs.append(FundamentalSignal("Price/Book", pb, "SELL", 0.4, f"High premium (P/B: {pb:.1f})"))
        
        # ROE (correct field: returnOnEquityTTM - already decimal)
        roe = self.metrics.get("returnOnEquityTTM")
        if roe:
            rp = roe * 100  # Convert to percentage
            if rp > 100: sigs.append(FundamentalSignal("ROE", rp, "BUY", 0.5, f"Very high ROE ({rp:.0f}%) - likely buybacks"))
            elif rp > 25: sigs.append(FundamentalSignal("ROE", rp, "BUY", 0.6, f"Excellent returns ({rp:.1f}%)"))
            elif rp > 15: sigs.append(FundamentalSignal("ROE", rp, "BUY", 0.4, f"Good returns ({rp:.1f}%)"))
            elif rp > 10: sigs.append(FundamentalSignal("ROE", rp, "NEUTRAL", 0.3, f"Average returns ({rp:.1f}%)"))
            elif rp > 0: sigs.append(FundamentalSignal("ROE", rp, "SELL", 0.3, f"Low returns ({rp:.1f}%)"))
            else: sigs.append(FundamentalSignal("ROE", rp, "SELL", 0.6, f"Negative returns ({rp:.1f}%)"))
        
        # Profit Margin (correct field: netProfitMarginTTM)
        margin = self.ratios.get("netProfitMarginTTM")
        if margin:
            mp = margin * 100
            if mp > 20: sigs.append(FundamentalSignal("Profit Margin", mp, "BUY", 0.5, f"High profitability ({mp:.1f}%)"))
            elif mp > 10: sigs.append(FundamentalSignal("Profit Margin", mp, "BUY", 0.3, f"Good profitability ({mp:.1f}%)"))
            elif mp > 5: sigs.append(FundamentalSignal("Profit Margin", mp, "NEUTRAL", 0.2, f"Moderate margin ({mp:.1f}%)"))
            elif mp > 0: sigs.append(FundamentalSignal("Profit Margin", mp, "SELL", 0.3, f"Thin margin ({mp:.1f}%)"))
            else: sigs.append(FundamentalSignal("Profit Margin", mp, "SELL", 0.6, f"Unprofitable ({mp:.1f}%)"))
        
        # Revenue Growth (correct field: revenueGrowth)
        rg = self.growth.get("revenueGrowth")
        if rg:
            rgp = rg * 100
            if rgp > 25: sigs.append(FundamentalSignal("Revenue Growth", rgp, "BUY", 0.7, f"High growth ({rgp:.1f}% YoY)"))
            elif rgp > 10: sigs.append(FundamentalSignal("Revenue Growth", rgp, "BUY", 0.5, f"Good growth ({rgp:.1f}% YoY)"))
            elif rgp > 0: sigs.append(FundamentalSignal("Revenue Growth", rgp, "NEUTRAL", 0.3, f"Positive growth ({rgp:.1f}% YoY)"))
            else: sigs.append(FundamentalSignal("Revenue Growth", rgp, "SELL", 0.5, f"Declining revenue ({rgp:.1f}% YoY)"))
        
        # EPS Growth (correct field: epsgrowth)
        eg = self.growth.get("epsgrowth")
        if eg:
            egp = eg * 100
            if egp > 25: sigs.append(FundamentalSignal("EPS Growth", egp, "BUY", 0.6, f"Strong earnings growth ({egp:.1f}% YoY)"))
            elif egp > 10: sigs.append(FundamentalSignal("EPS Growth", egp, "BUY", 0.4, f"Good earnings growth ({egp:.1f}% YoY)"))
            elif egp > 0: sigs.append(FundamentalSignal("EPS Growth", egp, "NEUTRAL", 0.3, f"Positive EPS ({egp:.1f}% YoY)"))
            else: sigs.append(FundamentalSignal("EPS Growth", egp, "SELL", 0.5, f"Declining EPS ({egp:.1f}% YoY)"))
        
        # Debt to Equity (correct field: debtToEquityRatioTTM)
        de = self.ratios.get("debtToEquityRatioTTM")
        if de is not None:
            if de < 0.3: sigs.append(FundamentalSignal("Debt/Equity", de, "BUY", 0.5, f"Low leverage ({de:.2f}x)"))
            elif de < 1: sigs.append(FundamentalSignal("Debt/Equity", de, "NEUTRAL", 0.3, f"Moderate leverage ({de:.2f}x)"))
            elif de < 2: sigs.append(FundamentalSignal("Debt/Equity", de, "SELL", 0.3, f"High leverage ({de:.2f}x)"))
            else: sigs.append(FundamentalSignal("Debt/Equity", de, "SELL", 0.5, f"Very high leverage ({de:.2f}x)"))
        
        # Current Ratio (correct field: currentRatioTTM)
        cr = self.ratios.get("currentRatioTTM")
        if cr:
            if cr > 2: sigs.append(FundamentalSignal("Current Ratio", cr, "BUY", 0.4, f"Strong liquidity ({cr:.2f}x)"))
            elif cr > 1.5: sigs.append(FundamentalSignal("Current Ratio", cr, "BUY", 0.2, f"Good liquidity ({cr:.2f}x)"))
            elif cr > 1: sigs.append(FundamentalSignal("Current Ratio", cr, "NEUTRAL", 0.2, f"Adequate liquidity ({cr:.2f}x)"))
            else: sigs.append(FundamentalSignal("Current Ratio", cr, "SELL", 0.4, f"Liquidity concern ({cr:.2f}x)"))
        
        # Free Cash Flow Yield (correct field: freeCashFlowYieldTTM)
        fcfy = self.metrics.get("freeCashFlowYieldTTM")
        if fcfy:
            fcfp = fcfy * 100
            if fcfp > 8: sigs.append(FundamentalSignal("FCF Yield", fcfp, "BUY", 0.6, f"High cash generation ({fcfp:.1f}%)"))
            elif fcfp > 5: sigs.append(FundamentalSignal("FCF Yield", fcfp, "BUY", 0.4, f"Good cash generation ({fcfp:.1f}%)"))
            elif fcfp > 2: sigs.append(FundamentalSignal("FCF Yield", fcfp, "NEUTRAL", 0.2, f"Moderate FCF ({fcfp:.1f}%)"))
            elif fcfp > 0: sigs.append(FundamentalSignal("FCF Yield", fcfp, "SELL", 0.3, f"Low FCF ({fcfp:.1f}%)"))
            else: sigs.append(FundamentalSignal("FCF Yield", fcfp, "SELL", 0.5, f"Negative FCF ({fcfp:.1f}%)"))
        
        # EV/EBITDA (correct field: evToEBITDATTM from metrics)
        ev_ebitda = self.metrics.get("evToEBITDATTM")
        if ev_ebitda and ev_ebitda > 0:
            if ev_ebitda < 8: sigs.append(FundamentalSignal("EV/EBITDA", ev_ebitda, "BUY", 0.5, f"Cheap ({ev_ebitda:.1f}x)"))
            elif ev_ebitda < 12: sigs.append(FundamentalSignal("EV/EBITDA", ev_ebitda, "BUY", 0.3, f"Fair value ({ev_ebitda:.1f}x)"))
            elif ev_ebitda < 18: sigs.append(FundamentalSignal("EV/EBITDA", ev_ebitda, "NEUTRAL", 0.2, f"Moderate ({ev_ebitda:.1f}x)"))
            elif ev_ebitda < 25: sigs.append(FundamentalSignal("EV/EBITDA", ev_ebitda, "SELL", 0.3, f"Expensive ({ev_ebitda:.1f}x)"))
            else: sigs.append(FundamentalSignal("EV/EBITDA", ev_ebitda, "SELL", 0.5, f"Very expensive ({ev_ebitda:.1f}x)"))
        
        # Dividend Yield (correct field: dividendYieldTTM)
        div = self.ratios.get("dividendYieldTTM")
        if div and div > 0:
            dp = div * 100
            if dp > 4: sigs.append(FundamentalSignal("Dividend", dp, "BUY", 0.4, f"High yield ({dp:.2f}%)"))
            elif dp > 2: sigs.append(FundamentalSignal("Dividend", dp, "BUY", 0.2, f"Moderate yield ({dp:.2f}%)"))
            else: sigs.append(FundamentalSignal("Dividend", dp, "NEUTRAL", 0.1, f"Low yield ({dp:.2f}%)"))
        
        return sigs


# ============================================================================
# Analyst Analysis
# ============================================================================

class AnalystAnalyzer:
    def __init__(self, price_target: Dict, dcf: Optional[float], current_price: float):
        self.target = price_target
        self.dcf = dcf
        self.price = current_price
    
    def generate_signals(self) -> List[AnalystSignal]:
        sigs = []
        
        # Price Target
        t_avg = self.target.get("targetConsensus")
        if t_avg and self.price:
            up = (t_avg - self.price) / self.price * 100
            if up > 30: sigs.append(AnalystSignal("Price Target", up, "BUY", 0.8, f"${t_avg:.0f} target ({up:+.1f}% upside)"))
            elif up > 15: sigs.append(AnalystSignal("Price Target", up, "BUY", 0.6, f"${t_avg:.0f} target ({up:+.1f}% upside)"))
            elif up > 5: sigs.append(AnalystSignal("Price Target", up, "BUY", 0.4, f"${t_avg:.0f} target ({up:+.1f}% upside)"))
            elif up > -5: sigs.append(AnalystSignal("Price Target", up, "NEUTRAL", 0.3, f"${t_avg:.0f} target ({up:+.1f}%)"))
            elif up > -15: sigs.append(AnalystSignal("Price Target", up, "SELL", 0.4, f"${t_avg:.0f} target ({up:+.1f}% downside)"))
            else: sigs.append(AnalystSignal("Price Target", up, "SELL", 0.6, f"${t_avg:.0f} target ({up:+.1f}% downside)"))
        
        # DCF Valuation
        if self.dcf and self.price:
            up = (self.dcf - self.price) / self.price * 100
            if up > 30: sigs.append(AnalystSignal("DCF Value", self.dcf, "BUY", 0.7, f"${self.dcf:.0f} fair value ({up:+.1f}% upside)"))
            elif up > 10: sigs.append(AnalystSignal("DCF Value", self.dcf, "BUY", 0.5, f"${self.dcf:.0f} fair value ({up:+.1f}% upside)"))
            elif up > -10: sigs.append(AnalystSignal("DCF Value", self.dcf, "NEUTRAL", 0.3, f"${self.dcf:.0f} fair value ({up:+.1f}%)"))
            elif up > -30: sigs.append(AnalystSignal("DCF Value", self.dcf, "SELL", 0.5, f"${self.dcf:.0f} fair value ({up:+.1f}% overvalued)"))
            else: sigs.append(AnalystSignal("DCF Value", self.dcf, "SELL", 0.7, f"${self.dcf:.0f} fair value ({up:+.1f}% overvalued)"))
        
        return sigs


# ============================================================================
# Risk Analysis
# ============================================================================

class RiskAnalyzer:
    def __init__(self, bars: List[Dict], beta: float = 1.0):
        self.closes = [b["close"] for b in bars]
        self.returns = [(self.closes[i] - self.closes[i-1]) / self.closes[i-1] for i in range(1, len(self.closes))]
        self.beta = beta
    
    def calculate(self) -> RiskMetrics:
        if len(self.returns) < 20:
            return RiskMetrics(0, "Unknown", 0, 0, 0, 5)
        
        mean = sum(self.returns) / len(self.returns)
        var = sum((r - mean)**2 for r in self.returns) / len(self.returns)
        daily_vol = math.sqrt(var)
        annual_vol = daily_vol * math.sqrt(252) * 100
        
        if annual_vol < 15: rating = "Low"
        elif annual_vol < 25: rating = "Medium"
        elif annual_vol < 40: rating = "High"
        else: rating = "Very High"
        
        sorted_ret = sorted(self.returns)
        var_idx = int(len(sorted_ret) * 0.05)
        var_95 = abs(sorted_ret[var_idx]) * 100 if var_idx < len(sorted_ret) else 0
        
        peak, max_dd = self.closes[0], 0
        for p in self.closes:
            if p > peak: peak = p
            dd = (peak - p) / peak
            max_dd = max(max_dd, dd)
        
        sharpe = ((mean * 252) - 0.02) / (daily_vol * math.sqrt(252)) if daily_vol > 0 else 0
        
        risk_score = 5
        if annual_vol > 40: risk_score += 2
        elif annual_vol > 25: risk_score += 1
        elif annual_vol < 15: risk_score -= 1
        if max_dd > 0.30: risk_score += 2
        elif max_dd > 0.20: risk_score += 1
        if self.beta > 1.5: risk_score += 1
        elif self.beta < 0.8: risk_score -= 1
        
        return RiskMetrics(annual_vol, rating, var_95, max_dd * 100, sharpe, max(1, min(10, risk_score)))


# ============================================================================
# Main Analyzer
# ============================================================================

class StockAnalyzer:
    def __init__(self):
        # Use multi-source data fetcher if available
        if DATA_FETCHER_AVAILABLE:
            self.data_fetcher = DataFetcher(verbose=True)
        else:
            self.data_fetcher = None
            self.alpaca = AlpacaFetcher()
            self.yahoo = YahooFetcher()
        
        self.fmp = FMPFetcher()
        self.exchange_mapper = ExchangeMapper() if ExchangeMapper else None
    
    def analyze(self, input_symbol: str) -> AnalysisResult:
        """
        Analyze a stock with exchange support.
        
        Supported formats:
            AAPL          - US stock (default)
            NYSE:AAPL     - Professional format
            ASX:BHP       - Australian stock
            BHP.AX        - Yahoo suffix format
        """
        # Parse the symbol
        if self.exchange_mapper:
            parsed = self.exchange_mapper.parse(input_symbol)
            symbol = parsed.symbol
            exchange = parsed.exchange
            display = parsed.display
            fmp_symbol = parsed.fmp_symbol
            yahoo_symbol = parsed.yahoo_symbol
            is_us = parsed.is_us
            country = parsed.country
            currency = parsed.currency
        else:
            # Fallback without exchange mapper
            symbol = input_symbol.upper()
            exchange = "NYSE"
            display = f"NYSE:{symbol}"
            fmp_symbol = symbol
            yahoo_symbol = symbol
            is_us = True
            country = "US"
            currency = "USD"
        
        # Fetch price data using multi-source fetcher
        print(f"  Fetching price data for {display}...")
        
        if self.data_fetcher:
            # Use multi-source fetcher with automatic fallback
            bars, price_source = self.data_fetcher.get_bars(
                symbol if is_us else yahoo_symbol
            )
            if bars:
                print(f"    [OK] Price data from {price_source}")
        else:
            # Fallback to individual sources
            if is_us:
                bars = self.alpaca.get_bars(symbol)
                price_source = "Alpaca" if bars else ""
            else:
                bars = self.yahoo.get_bars(yahoo_symbol)
                price_source = "Yahoo" if bars else ""
        
        if not bars:
            raise ValueError(f"No price data available for {display}")
        
        # Fetch fundamentals
        print(f"  Fetching fundamentals...")
        
        profile = {}
        quote = {}
        ratios = {}
        metrics = {}
        growth = {}
        fund_source = ""
        
        if self.data_fetcher:
            fund_data, fund_source = self.data_fetcher.get_fundamentals(fmp_symbol)
            if fund_data and fund_source:
                print(f"    [OK] Fundamentals from {fund_source}")
                # data_fetcher returns flat structure, need to also fetch raw ratios/metrics
                profile = fund_data
                quote = {}
                
                # Fetch raw ratios and metrics for signal generation
                if hasattr(self.fmp, 'get_ratios'):
                    ratios = self.fmp.get_ratios(fmp_symbol) or {}
                else:
                    ratios = {}
                if hasattr(self.fmp, 'get_key_metrics'):
                    metrics = self.fmp.get_key_metrics(fmp_symbol) or {}
                else:
                    metrics = {}
                if hasattr(self.fmp, 'get_growth'):
                    growth = self.fmp.get_growth(fmp_symbol) or {}
                else:
                    growth = {}
            else:
                # Fallback - fetch directly
                profile = self.fmp.get_profile(fmp_symbol) if self.fmp else {}
                quote = self.fmp.get_quote(fmp_symbol) if self.fmp else {}
                ratios = self.fmp.get_ratios(fmp_symbol) if self.fmp else {}
                metrics = self.fmp.get_key_metrics(fmp_symbol) if self.fmp else {}
                growth = self.fmp.get_growth(fmp_symbol) if self.fmp else {}
                fund_source = "FMP" if profile else ""
        else:
            profile = self.fmp.get_profile(fmp_symbol)
            quote = self.fmp.get_quote(fmp_symbol)
            ratios = self.fmp.get_ratios(fmp_symbol)
            metrics = self.fmp.get_key_metrics(fmp_symbol)
            growth = self.fmp.get_growth(fmp_symbol)
            fund_source = "FMP" if profile else ""
        
        # Fetch analyst data
        print(f"  Fetching analyst data...")
        
        price_target = {}
        dcf = {}
        analyst_source = ""
        
        # Try to get analyst data from FMP if available
        if self.fmp:
            try:
                price_target = self.fmp.get_price_target(fmp_symbol) or {}
                dcf = self.fmp.get_dcf(fmp_symbol) or {}
                if price_target or dcf:
                    analyst_source = "FMP"
                    print(f"    [OK] Analyst data from {analyst_source}")
                else:
                    print(f"    ⚠ No analyst data available")
            except Exception:
                print(f"    ⚠ No analyst data available")
        else:
            print(f"    ⚠ No analyst data available")
        
        # Get price from fundamentals or price data
        curr = quote.get("price") or profile.get("price") or bars[-1]["close"]
        prev = quote.get("previousClose") or bars[-2]["close"] if len(bars) > 1 else curr
        
        print(f"  Running technical analysis...")
        tech = TechnicalAnalyzer(bars)
        tech_sigs = tech.generate_signals()
        sups, ress = tech.support_resistance()
        trend = tech.trend()
        
        print(f"  Running fundamental analysis...")
        fund_sigs = FundamentalAnalyzer(profile, quote, ratios, metrics, growth).generate_signals()
        
        print(f"  Analyzing analyst opinions...")
        analyst_sigs = AnalystAnalyzer(price_target, dcf, curr).generate_signals()
        
        print(f"  Calculating risk...")
        beta = profile.get("beta") or 1.0
        risk = RiskAnalyzer(bars, beta).calculate()
        
        # Calculate scores
        tech_sc = self._calc_score(tech_sigs)
        fund_sc = self._calc_score(fund_sigs) if fund_sigs else 50
        analyst_sc = self._calc_score(analyst_sigs) if analyst_sigs else 50
        risk_adj = (10 - risk.risk_score) * 10
        
        # Weighted overall
        if fund_sigs and analyst_sigs:
            overall = tech_sc * 0.30 + fund_sc * 0.35 + analyst_sc * 0.20 + risk_adj * 0.15
        elif fund_sigs:
            overall = tech_sc * 0.45 + fund_sc * 0.40 + risk_adj * 0.15
        else:
            overall = tech_sc * 0.70 + risk_adj * 0.30
        
        rec = self._get_rec(overall)
        conf = self._calc_conf(tech_sigs + fund_sigs + analyst_sigs)
        
        # Price targets
        atr = tech.atr()
        t_low = price_target.get("targetLow") or (sups[0] if sups else curr - atr * 3)
        t_mid = price_target.get("targetConsensus") or (ress[0] if ress else curr + atr * 2)
        t_high = price_target.get("targetHigh") or (ress[-1] if len(ress) > 1 else curr + atr * 5)
        
        summary, factors = self._summary(display, rec, tech_sigs, fund_sigs, analyst_sigs, risk, trend)
        
        # 52-week range
        w52_high = quote.get("yearHigh") or profile.get("range", "0-0").split("-")[-1]
        w52_low = quote.get("yearLow") or profile.get("range", "0-0").split("-")[0]
        try:
            w52_high = float(w52_high)
            w52_low = float(w52_low)
        except Exception:
            w52_high = max(b["high"] for b in bars[-252:]) if len(bars) >= 252 else max(b["high"] for b in bars)
            w52_low = min(b["low"] for b in bars[-252:]) if len(bars) >= 252 else min(b["low"] for b in bars)
        
        # Position in 52-week range
        w52_pos = (curr - w52_low) / (w52_high - w52_low) * 100 if w52_high != w52_low else 50
        
        # Get P/E from ratios
        pe_ratio = ratios.get("priceToEarningsRatioTTM") or 0
        
        # Get country/currency from profile or parsed
        actual_country = profile.get("country") or country
        actual_currency = profile.get("currency") or currency
        
        # Get currency symbol and divisor
        if self.exchange_mapper:
            curr_info = {'symbol': '$', 'divisor': 1}
            try:
                from trading.exchanges import CURRENCY_INFO
                curr_info = CURRENCY_INFO.get(actual_currency, {'symbol': '$', 'divisor': 1})
            except Exception:
                pass
            currency_symbol = curr_info['symbol']
            price_divisor = curr_info['divisor']
        else:
            currency_symbol = '$'
            price_divisor = 1
        
        return AnalysisResult(
            symbol=symbol,
            exchange=exchange,
            display_symbol=display,
            company_name=profile.get("companyName") or quote.get("name") or symbol,
            sector=profile.get("sector") or "Unknown",
            industry=profile.get("industry") or "Unknown",
            country=actual_country,
            currency=actual_currency,
            currency_symbol=currency_symbol,
            price_divisor=price_divisor,
            current_price=curr,
            prev_close=prev,
            change=curr - prev,
            change_pct=(curr - prev) / prev * 100 if prev else 0,
            market_cap=profile.get("marketCap") or quote.get("marketCap") or 0,
            beta=beta,
            pe_ratio=pe_ratio,
            timestamp=datetime.now(),
            technical_signals=tech_sigs,
            fundamental_signals=fund_sigs,
            analyst_signals=analyst_sigs,
            risk_metrics=risk,
            technical_score=tech_sc,
            fundamental_score=fund_sc,
            analyst_score=analyst_sc,
            risk_score=risk_adj,
            overall_score=overall,
            recommendation=rec,
            confidence=conf,
            trend=trend,
            support_levels=sups,
            resistance_levels=ress,
            target_low=t_low,
            target_mid=t_mid,
            target_high=t_high,
            dcf_value=dcf,
            week_52_high=w52_high,
            week_52_low=w52_low,
            week_52_position=w52_pos,
            summary=summary,
            key_factors=factors
        )
    
    def _calc_score(self, sigs) -> float:
        if not sigs: return 50
        tw, ws = 0, 0
        for s in sigs:
            w = s.strength
            sc = 50 + s.strength * 50 if s.signal == "BUY" else 50 - s.strength * 50 if s.signal == "SELL" else 50
            ws += sc * w
            tw += w
        return ws / tw if tw > 0 else 50
    
    def _get_rec(self, sc: float) -> Signal:
        if sc >= 75: return Signal.STRONG_BUY
        if sc >= 65: return Signal.BUY
        if sc >= 55: return Signal.WEAK_BUY
        if sc >= 45: return Signal.HOLD
        if sc >= 35: return Signal.WEAK_SELL
        if sc >= 25: return Signal.SELL
        return Signal.STRONG_SELL
    
    def _calc_conf(self, sigs) -> float:
        if not sigs: return 50
        buy = sum(1 for s in sigs if s.signal == "BUY")
        sell = sum(1 for s in sigs if s.signal == "SELL")
        return min(95, max(buy, sell) / len(sigs) * 100)
    
    def _summary(self, sym, rec, tech, fund, analyst, risk, trend):
        all_sigs = tech + fund + analyst
        buy_f = [s.description for s in sorted(all_sigs, key=lambda x: x.strength, reverse=True) if s.signal == "BUY"][:4]
        sell_f = [s.description for s in sorted(all_sigs, key=lambda x: x.strength, reverse=True) if s.signal == "SELL"][:4]
        
        risk_str = f"Volatility: {risk.volatility_rating}"
        
        if rec in [Signal.STRONG_BUY, Signal.BUY]:
            key = buy_f[0][:30] if buy_f else 'Multiple positives'
            summary = f"{sym}: Bullish. Key: {key}. {risk_str}."
        elif rec in [Signal.STRONG_SELL, Signal.SELL]:
            key = sell_f[0][:30] if sell_f else 'Multiple negatives'
            summary = f"{sym}: Bearish. Key: {key}. {risk_str}."
        else:
            summary = f"{sym}: Mixed signals - conflicting indicators. Wait for clearer direction. {risk_str}."
        
        return summary, buy_f + sell_f


# ============================================================================
# Display
# ============================================================================

def fmt_cap(mc: float) -> str:
    if mc >= 1e12: return f"${mc/1e12:.2f}T"
    if mc >= 1e9: return f"${mc/1e9:.2f}B"
    if mc >= 1e6: return f"${mc/1e6:.2f}M"
    return f"${mc:,.0f}"


def print_analysis(r: AnalysisResult):
    icons = {Signal.STRONG_BUY: "[++]", Signal.BUY: "[+]", Signal.WEAK_BUY: "[~][+]",
             Signal.HOLD: "[~]", Signal.WEAK_SELL: "[~-]", Signal.SELL: "[-]", Signal.STRONG_SELL: "[--]"}
    w = 80  # Total width inside box
    
    def pad(text, width, emoji_count=0):
        """Pad text accounting for emoji width (each emoji = 2 display chars but 1 len)"""
        return text + " " * (width - len(text) - emoji_count)
    
    # Get currency symbol from result, handling GBp (pence)
    curr_sym = getattr(r, 'currency_symbol', '$')
    divisor = getattr(r, 'price_divisor', 1)
    
    # For GBp (pence), convert to pounds for display
    if r.currency == 'GBp':
        curr_sym = '£'
        display_price = r.current_price / 100
        display_change = r.change / 100
        w52_low = r.week_52_low / 100
        w52_high = r.week_52_high / 100
    else:
        display_price = r.current_price
        display_change = r.change
        w52_low = r.week_52_low
        w52_high = r.week_52_high
    
    print()
    print("╔" + "═" * w + "╗")
    print("║" + "COMPREHENSIVE STOCK ANALYSIS".center(w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Header with exchange
    display_sym = getattr(r, 'display_symbol', f"{r.exchange}:{r.symbol}" if hasattr(r, 'exchange') else r.symbol)
    name = (r.company_name[:25] if r.company_name else r.symbol)
    chg = f"{display_change:+.2f} ({r.change_pct:+.2f}%)"
    line1 = f"  {name:<25} {curr_sym}{display_price:<10.2f} {chg}"
    print("║" + pad(line1, w) + "║")
    
    # Exchange and sector line
    exchange_info = f"{display_sym} ({r.country})" if hasattr(r, 'country') else display_sym
    sec_ind = f"{r.sector} | {r.industry}"[:38]
    line2 = f"  {exchange_info:<20} {sec_ind}"
    print("║" + pad(line2, w) + "║")
    
    # Market cap line - show actual currency for display
    display_currency = "GBP" if r.currency == "GBp" else r.currency
    line2b = f"  Market Cap: {fmt_cap(r.market_cap):<15} Currency: {display_currency}"
    print("║" + pad(line2b, w) + "║")
    
    pe_str = f"P/E: {r.pe_ratio:.1f}" if r.pe_ratio else "P/E: N/A"
    pos_bar = "▓" * int(r.week_52_position / 10) + "░" * (10 - int(r.week_52_position / 10))
    line3 = f"  Beta: {r.beta:.2f}  |  {pe_str}  |  52w: {curr_sym}{w52_low:.0f} [{pos_bar}] {curr_sym}{w52_high:.0f}"
    print("║" + pad(line3, w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Recommendation
    print("║" + "RECOMMENDATION".center(w) + "║")
    print("╠" + "═" * w + "╣")
    icon = icons.get(r.recommendation, "")
    emoji_cnt = 2 if r.recommendation in [Signal.STRONG_BUY, Signal.WEAK_BUY, Signal.WEAK_SELL, Signal.STRONG_SELL] else 1
    rec_line = f"  {icon} {r.recommendation.value:<20} Confidence: {r.confidence:.0f}%"
    print("║" + pad(rec_line, w, emoji_cnt) + "║")
    score_line = f"  Overall Score: {r.overall_score:.0f}/100"
    print("║" + pad(score_line, w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Scores
    print("║" + "ANALYSIS BREAKDOWN".center(w) + "║")
    print("╠" + "═" * w + "╣")
    def bar(s): return "█" * int(s/5) + "░" * (20 - int(s/5))
    print("║" + pad(f"  Technical:    {r.technical_score:>5.0f}/100  {bar(r.technical_score)}", w) + "║")
    print("║" + pad(f"  Fundamental:  {r.fundamental_score:>5.0f}/100  {bar(r.fundamental_score)}", w) + "║")
    print("║" + pad(f"  Analyst:      {r.analyst_score:>5.0f}/100  {bar(r.analyst_score)}", w) + "║")
    print("║" + pad(f"  Risk Adj:     {r.risk_score:>5.0f}/100  {bar(r.risk_score)}", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Trend
    print("║" + pad(f"  Trend: {r.trend.value}", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Technical Signals
    print("║" + "TECHNICAL SIGNALS".center(w) + "║")
    print("╠" + "═" * w + "╣")
    for s in r.technical_signals[:7]:
        ic = "[+]" if s.signal == "BUY" else "[-]" if s.signal == "SELL" else "[.]"
        sig_line = f"  {ic} {s.name:<14} {s.description[:55]}"
        print("║" + pad(sig_line, w, 1) + "║")
    print("╠" + "═" * w + "╣")
    
    # Fundamental Signals
    if r.fundamental_signals:
        print("║" + "FUNDAMENTAL SIGNALS".center(w) + "║")
        print("╠" + "═" * w + "╣")
        for s in r.fundamental_signals[:12]:
            ic = "[+]" if s.signal == "BUY" else "[-]" if s.signal == "SELL" else "[.]"
            sig_line = f"  {ic} {s.name:<14} {s.description[:55]}"
            print("║" + pad(sig_line, w, 1) + "║")
        print("╠" + "═" * w + "╣")
    
    # Analyst Opinions
    if r.analyst_signals:
        print("║" + "ANALYST OPINIONS".center(w) + "║")
        print("╠" + "═" * w + "╣")
        for s in r.analyst_signals:
            ic = "[+]" if s.signal == "BUY" else "[-]" if s.signal == "SELL" else "[.]"
            sig_line = f"  {ic} {s.name:<14} {s.description[:55]}"
            print("║" + pad(sig_line, w, 1) + "║")
        print("╠" + "═" * w + "╣")
    
    # Risk Analysis
    print("║" + "RISK ANALYSIS".center(w) + "║")
    print("╠" + "═" * w + "╣")
    rm = r.risk_metrics
    print("║" + pad(f"  Volatility:     {rm.volatility_annual:>6.1f}% annual ({rm.volatility_rating})", w) + "║")
    print("║" + pad(f"  VaR (95%):      {rm.var_95:>6.2f}% max daily loss", w) + "║")
    print("║" + pad(f"  Max Drawdown:   {rm.max_drawdown:>6.1f}% from peak", w) + "║")
    print("║" + pad(f"  Sharpe Ratio:   {rm.sharpe_ratio:>6.2f} risk-adjusted return", w) + "║")
    print("║" + pad(f"  Risk Score:     {rm.risk_score:>6.0f}/10", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Price Targets - handle GBp conversion
    print("║" + "PRICE TARGETS".center(w) + "║")
    print("╠" + "═" * w + "╣")
    c = r.current_price
    
    # Convert targets if GBp
    if r.currency == 'GBp':
        t_low = r.target_low / 100
        t_mid = r.target_mid / 100
        t_high = r.target_high / 100
        dcf = r.dcf_value / 100 if r.dcf_value else None
    else:
        t_low = r.target_low
        t_mid = r.target_mid
        t_high = r.target_high
        dcf = r.dcf_value
    
    print("║" + pad(f"  Analyst Low:    {curr_sym}{t_low:<10.2f} ({(r.target_low-c)/c*100:>+6.1f}%)", w) + "║")
    print("║" + pad(f"  Analyst Avg:    {curr_sym}{t_mid:<10.2f} ({(r.target_mid-c)/c*100:>+6.1f}%)", w) + "║")
    print("║" + pad(f"  Analyst High:   {curr_sym}{t_high:<10.2f} ({(r.target_high-c)/c*100:>+6.1f}%)", w) + "║")
    if dcf:
        print("║" + pad(f"  DCF Value:      {curr_sym}{dcf:<10.2f} ({(r.dcf_value-c)/c*100:>+6.1f}%) intrinsic value", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Support & Resistance - handle GBp conversion
    print("║" + "SUPPORT & RESISTANCE".center(w) + "║")
    print("╠" + "═" * w + "╣")
    if r.currency == 'GBp':
        sup = ", ".join(f"{curr_sym}{x/100:.2f}" for x in r.support_levels) or "None identified"
        res = ", ".join(f"{curr_sym}{x/100:.2f}" for x in r.resistance_levels) or "None identified"
    else:
        sup = ", ".join(f"{curr_sym}{x:.2f}" for x in r.support_levels) or "None identified"
        res = ", ".join(f"{curr_sym}{x:.2f}" for x in r.resistance_levels) or "None identified"
    print("║" + pad(f"  Support:      {sup}", w) + "║")
    print("║" + pad(f"  Resistance:   {res}", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Summary
    print("║" + "SUMMARY".center(w) + "║")
    print("╠" + "═" * w + "╣")
    summary = r.summary[:76]
    print("║" + pad(f"  {summary}", w) + "║")
    print("╠" + "═" * w + "╣")
    
    # Key Factors
    print("║" + "KEY FACTORS".center(w) + "║")
    print("╠" + "═" * w + "╣")
    for f in r.key_factors[:6]:
        factor = f[:72]
        print("║" + pad(f"  • {factor}", w) + "║")
    print("╚" + "═" * w + "╝")
    
    print()
    print("Note: Analysis combines technical, fundamental, and analyst data.")
    print("   For informational purposes only. Not financial advice.")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--brief", action="store_true")
    args = parser.parse_args()
    
    analyzer = StockAnalyzer()
    for sym in args.symbols:
        try:
            print(f"\n{'='*78}\nAnalyzing {sym.upper()}...\n{'='*78}")
            r = analyzer.analyze(sym.upper())
            if args.brief:
                ic = "[+]" if "BUY" in r.recommendation.value else "[-]" if "SELL" in r.recommendation.value else "[~]"
                print(f"\n{ic} {r.company_name} ({sym.upper()}): {r.recommendation.value}")
                print(f"   Score: {r.overall_score:.0f}/100 | Confidence: {r.confidence:.0f}%")
                print(f"   Price: ${r.current_price:.2f} ({r.change_pct:+.2f}%) | Target: ${r.target_mid:.2f}")
                print(f"   P/E: {r.pe_ratio:.1f} | Beta: {r.beta:.2f} | 52w: {r.week_52_position:.0f}%")
            else:
                print_analysis(r)
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
