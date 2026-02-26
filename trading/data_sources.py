#!/usr/bin/env python3
"""
Multi-Source Data Fetcher v2.0
===============================
Fetches stock data from 8 sources with intelligent fallback and rate limiting.

Supported APIs (in order of priority):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Source         | Price | Fundamentals | Quote | News | Free Tier          |
|----------------|-------|--------------|-------|------|--------------------|
| Alpaca         | [Y]     | [N]            | [Y]     | [N]    | Unlimited          |
| FMP            | [Y]     | [Y]            | [Y]     | [Y]    | 250/day            |
| Finnhub        | [Y]     | [Y]            | [Y]     | [Y]    | 60/min             |
| Polygon        | [Y]     | [N]            | [Y]     | [N]    | 5/min              |
| Twelvedata     | [Y]     | [N]            | [Y]     | [N]    | 800/day, 8/min     |
| Alpha Vantage  | [Y]     | [Y]            | [Y]     | [N]    | 25/day             |
| EODHD          | [Y]     | [Y]            | [Y]     | [Y]    | 20/day             |
| Yahoo          | [Y]     | [Y]            | [Y]     | [N]    | Unlimited (flaky)  |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Features:
- Automatic fallback when a source fails
- Rate limit tracking to avoid hitting limits
- Source health monitoring
- Caching to reduce API calls
- Smart source selection based on data type
- Support for US and international stocks

Usage:
    from trading.data_sources import DataFetcher
    
    fetcher = DataFetcher()
    
    # Get price data (auto-selects best source)
    bars, source = fetcher.get_bars("AAPL")
    
    # Get real-time quote
    quote, source = fetcher.get_quote("AAPL")
    
    # Get fundamentals
    data, source = fetcher.get_fundamentals("AAPL")
    
    # Check source health
    fetcher.print_source_status()
"""

import os
import json
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

# Allow unverified SSL for some APIs
ssl._create_default_https_context = ssl._create_unverified_context


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SourceConfig:
    """Configuration for a data source."""
    name: str
    env_var: str
    supports_price: bool = True
    supports_fundamentals: bool = False
    supports_quote: bool = True
    supports_news: bool = False
    supports_international: bool = True
    rate_limit_per_min: int = 60
    rate_limit_per_day: int = 10000
    priority_price: int = 10
    priority_fundamentals: int = 10
    priority_quote: int = 10


# Source configurations with priorities (lower = higher priority)
SOURCE_CONFIGS = {
    "alpaca": SourceConfig(
        name="Alpaca", env_var="ALPACA_API_KEY",
        supports_fundamentals=False, supports_news=False,
        supports_international=False,
        rate_limit_per_min=200, rate_limit_per_day=999999,
        priority_price=1, priority_quote=1
    ),
    "fmp": SourceConfig(
        name="FMP", env_var="FMP_API_KEY",
        supports_fundamentals=True, supports_news=True,
        rate_limit_per_min=60, rate_limit_per_day=250,
        priority_price=2, priority_fundamentals=1, priority_quote=2
    ),
    "finnhub": SourceConfig(
        name="Finnhub", env_var="FINNHUB_API_KEY",
        supports_fundamentals=True, supports_news=True,
        rate_limit_per_min=60, rate_limit_per_day=999999,
        priority_price=3, priority_fundamentals=2, priority_quote=3
    ),
    "polygon": SourceConfig(
        name="Polygon", env_var="POLYGON_API_KEY",
        supports_fundamentals=False, supports_news=False,
        supports_international=False,
        rate_limit_per_min=5, rate_limit_per_day=999999,
        priority_price=4, priority_quote=4
    ),
    "twelvedata": SourceConfig(
        name="Twelvedata", env_var="TWELVEDATA_API_KEY",
        supports_fundamentals=False, supports_news=False,
        rate_limit_per_min=8, rate_limit_per_day=800,
        priority_price=5, priority_quote=5
    ),
    "alphavantage": SourceConfig(
        name="AlphaVantage", env_var="ALPHAVANTAGE_API_KEY",
        supports_fundamentals=True, supports_news=False,
        rate_limit_per_min=5, rate_limit_per_day=25,
        priority_price=6, priority_fundamentals=4, priority_quote=6
    ),
    "eodhd": SourceConfig(
        name="EODHD", env_var="EODHD_API_KEY",
        supports_fundamentals=True, supports_news=True,
        rate_limit_per_min=10, rate_limit_per_day=20,
        priority_price=7, priority_fundamentals=3, priority_quote=7
    ),
    "yahoo": SourceConfig(
        name="Yahoo", env_var="",  # No API key needed
        supports_fundamentals=True, supports_news=False,
        rate_limit_per_min=60, rate_limit_per_day=999999,
        priority_price=8, priority_fundamentals=5, priority_quote=8
    ),
}


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """Track API usage and enforce rate limits."""
    
    def __init__(self, cache_file: str = None):
        self.cache_file = cache_file or os.path.expanduser("~/.trading_platform/rate_limits.json")
        self._usage: Dict[str, Dict] = defaultdict(lambda: {"minute": [], "day": []})
        self._load_usage()
    
    def _load_usage(self):
        """Load usage from file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file) as f:
                    data = json.load(f)
                    for source, usage in data.items():
                        self._usage[source] = usage
        except (IOError, FileNotFoundError):
            pass
    
    def _save_usage(self):
        """Save usage to file."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(dict(self._usage), f)
        except (IOError, FileNotFoundError):
            pass
    
    def can_use(self, source: str, config: SourceConfig) -> bool:
        """Check if we can use a source without hitting rate limits."""
        now = time.time()
        usage = self._usage[source]
        
        # Clean old entries
        minute_ago = now - 60
        day_ago = now - 86400
        
        usage["minute"] = [t for t in usage["minute"] if t > minute_ago]
        usage["day"] = [t for t in usage["day"] if t > day_ago]
        
        # Check limits
        if len(usage["minute"]) >= config.rate_limit_per_min:
            return False
        if len(usage["day"]) >= config.rate_limit_per_day:
            return False
        
        return True
    
    def record_use(self, source: str):
        """Record API usage."""
        now = time.time()
        self._usage[source]["minute"].append(now)
        self._usage[source]["day"].append(now)
        self._save_usage()
    
    def get_usage(self, source: str, config: SourceConfig) -> Dict:
        """Get current usage stats."""
        now = time.time()
        usage = self._usage[source]
        
        minute_ago = now - 60
        day_ago = now - 86400
        
        minute_count = len([t for t in usage.get("minute", []) if t > minute_ago])
        day_count = len([t for t in usage.get("day", []) if t > day_ago])
        
        return {
            "minute": minute_count,
            "minute_limit": config.rate_limit_per_min,
            "day": day_count,
            "day_limit": config.rate_limit_per_day,
            "minute_pct": minute_count / config.rate_limit_per_min * 100,
            "day_pct": day_count / config.rate_limit_per_day * 100
        }


# =============================================================================
# DATA CACHE
# =============================================================================

class DataCache:
    """Simple cache for API responses."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minute default TTL
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Cache a value."""
        self._cache[key] = (value, time.time())
    
    def clear(self):
        """Clear the cache."""
        self._cache.clear()


# =============================================================================
# BASE SOURCE CLASS
# =============================================================================

class BaseSource:
    """Base class for all data sources."""
    
    name = "Base"
    config_key = ""
    
    def __init__(self):
        self.api_key = ""
        self.available = False
        self._last_error = ""
        self._error_count = 0
        self._success_count = 0
    
    def _request(self, url: str, headers: Dict = None, timeout: int = 15) -> Optional[Dict]:
        """Make HTTP request with error handling."""
        try:
            default_headers = {"User-Agent": "Mozilla/5.0"}
            if headers:
                default_headers.update(headers)
            
            req = urllib.request.Request(url, headers=default_headers)
            
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                self._success_count += 1
                return data
        
        except urllib.error.HTTPError as e:
            self._last_error = f"HTTP {e.code}"
            self._error_count += 1
        except urllib.error.URLError as e:
            self._last_error = f"URL Error: {e.reason}"
            self._error_count += 1
        except json.JSONDecodeError:
            self._last_error = "Invalid JSON"
            self._error_count += 1
        except Exception as e:
            self._last_error = str(e)[:50]
            self._error_count += 1
        
        return None
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        """Get historical price bars. Override in subclass."""
        return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        """Get real-time quote. Override in subclass."""
        return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        """Get fundamental data. Override in subclass."""
        return {}, ""
    
    def get_news(self, symbol: str, limit: int = 10) -> Tuple[List[Dict], str]:
        """Get news. Override in subclass."""
        return [], ""
    
    def health_score(self) -> float:
        """Calculate health score (0-1) based on success rate."""
        total = self._success_count + self._error_count
        if total == 0:
            return 1.0
        return self._success_count / total


# =============================================================================
# ALPACA SOURCE
# =============================================================================

class AlpacaSource(BaseSource):
    """Alpaca Markets - US stocks, very reliable, unlimited free."""
    
    name = "Alpaca"
    config_key = "alpaca"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url = "https://data.alpaca.markets"
        self.available = bool(self.api_key and self.secret_key)
    
    def _alpaca_request(self, endpoint: str) -> Optional[Dict]:
        """Make Alpaca API request."""
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        return self._request(f"{self.base_url}{endpoint}", headers, timeout=30)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            endpoint = (f"/v2/stocks/{symbol}/bars?timeframe=1Day"
                       f"&start={start.strftime('%Y-%m-%d')}"
                       f"&end={end.strftime('%Y-%m-%d')}"
                       f"&limit=1000&feed=iex")
            
            data = self._alpaca_request(endpoint)
            if not data:
                return [], ""
            
            bars = [{
                "date": b["t"][:10],
                "open": float(b["o"]),
                "high": float(b["h"]),
                "low": float(b["l"]),
                "close": float(b["c"]),
                "volume": int(b["v"])
            } for b in data.get("bars", [])]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            data = self._alpaca_request(f"/v2/stocks/{symbol}/quotes/latest?feed=iex")
            if not data or "quote" not in data:
                return {}, ""
            
            q = data["quote"]
            return {
                "symbol": symbol,
                "bid": float(q.get("bp", 0)),
                "ask": float(q.get("ap", 0)),
                "price": (float(q.get("bp", 0)) + float(q.get("ap", 0))) / 2,
                "timestamp": q.get("t", "")
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# FMP SOURCE
# =============================================================================

class FMPSource(BaseSource):
    """Financial Modeling Prep - Global, excellent fundamentals."""
    
    name = "FMP"
    config_key = "fmp"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("FMP_API_KEY", "")
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.available = bool(self.api_key)
    
    def _fmp_request(self, endpoint: str) -> Optional[Any]:
        """Make FMP API request."""
        url = f"{self.base_url}/{endpoint}"
        if "?" in url:
            url += f"&apikey={self.api_key}"
        else:
            url += f"?apikey={self.api_key}"
        return self._request(url)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            data = self._fmp_request(f"historical-price-full/{symbol}?timeseries={days}")
            if not data or "historical" not in data:
                return [], ""
            
            bars = [{
                "date": h["date"],
                "open": float(h.get("open", 0)),
                "high": float(h.get("high", 0)),
                "low": float(h.get("low", 0)),
                "close": float(h.get("adjClose", h.get("close", 0))),
                "volume": int(h.get("volume", 0))
            } for h in reversed(data["historical"])]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            data = self._fmp_request(f"quote/{symbol}")
            if not data or not isinstance(data, list) or len(data) == 0:
                return {}, ""
            
            q = data[0]
            return {
                "symbol": symbol,
                "price": float(q.get("price", 0)),
                "change": float(q.get("change", 0)),
                "change_pct": float(q.get("changesPercentage", 0)),
                "volume": int(q.get("volume", 0)),
                "avg_volume": int(q.get("avgVolume", 0)),
                "market_cap": float(q.get("marketCap", 0)),
                "pe": float(q.get("pe", 0)) if q.get("pe") else None,
                "high": float(q.get("dayHigh", 0)),
                "low": float(q.get("dayLow", 0)),
                "open": float(q.get("open", 0)),
                "prev_close": float(q.get("previousClose", 0)),
                "year_high": float(q.get("yearHigh", 0)),
                "year_low": float(q.get("yearLow", 0)),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            profile = self._fmp_request(f"profile/{symbol}")
            ratios = self._fmp_request(f"ratios-ttm/{symbol}")
            metrics = self._fmp_request(f"key-metrics-ttm/{symbol}")
            
            if not profile:
                return {}, ""
            
            p = profile[0] if isinstance(profile, list) else profile
            r = ratios[0] if isinstance(ratios, list) and ratios else {}
            m = metrics[0] if isinstance(metrics, list) and metrics else {}
            
            return {
                "company_name": p.get("companyName", ""),
                "sector": p.get("sector", ""),
                "industry": p.get("industry", ""),
                "country": p.get("country", ""),
                "market_cap": p.get("mktCap", 0),
                "employees": p.get("fullTimeEmployees", 0),
                "description": p.get("description", ""),
                "website": p.get("website", ""),
                "pe_ratio": r.get("peRatioTTM"),
                "pb_ratio": r.get("priceToBookRatioTTM"),
                "ps_ratio": r.get("priceToSalesRatioTTM"),
                "dividend_yield": r.get("dividendYielTTM"),
                "roe": r.get("returnOnEquityTTM"),
                "roa": r.get("returnOnAssetsTTM"),
                "profit_margin": r.get("netProfitMarginTTM"),
                "debt_to_equity": r.get("debtEquityRatioTTM"),
                "current_ratio": r.get("currentRatioTTM"),
                "ev_to_ebitda": m.get("enterpriseValueOverEBITDATTM"),
                "free_cash_flow_yield": m.get("freeCashFlowYieldTTM"),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_news(self, symbol: str, limit: int = 10) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            data = self._fmp_request(f"stock_news?tickers={symbol}&limit={limit}")
            if not data:
                return [], ""
            
            news = [{
                "title": n.get("title", ""),
                "url": n.get("url", ""),
                "source": n.get("site", ""),
                "published": n.get("publishedDate", ""),
                "summary": n.get("text", "")[:200]
            } for n in data]
            
            return (news, self.name) if news else ([], "")
        except Exception:
            return [], ""


# =============================================================================
# FINNHUB SOURCE
# =============================================================================

class FinnhubSource(BaseSource):
    """Finnhub - Real-time data, good fundamentals, news."""
    
    name = "Finnhub"
    config_key = "finnhub"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("FINNHUB_API_KEY", "")
        self.base_url = "https://finnhub.io/api/v1"
        self.available = bool(self.api_key)
    
    def _finnhub_request(self, endpoint: str) -> Optional[Any]:
        """Make Finnhub API request."""
        url = f"{self.base_url}/{endpoint}"
        if "?" in url:
            url += f"&token={self.api_key}"
        else:
            url += f"?token={self.api_key}"
        return self._request(url)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=days)).timestamp())
            
            data = self._finnhub_request(f"stock/candle?symbol={symbol}&resolution=D&from={start}&to={end}")
            
            if not data or data.get("s") != "ok":
                return [], ""
            
            bars = []
            for i in range(len(data.get("t", []))):
                bars.append({
                    "date": datetime.fromtimestamp(data["t"][i]).strftime("%Y-%m-%d"),
                    "open": float(data["o"][i]),
                    "high": float(data["h"][i]),
                    "low": float(data["l"][i]),
                    "close": float(data["c"][i]),
                    "volume": int(data["v"][i])
                })
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            data = self._finnhub_request(f"quote?symbol={symbol}")
            if not data or data.get("c") == 0:
                return {}, ""
            
            return {
                "symbol": symbol,
                "price": float(data.get("c", 0)),
                "change": float(data.get("d", 0)),
                "change_pct": float(data.get("dp", 0)),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
                "open": float(data.get("o", 0)),
                "prev_close": float(data.get("pc", 0)),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            profile = self._finnhub_request(f"stock/profile2?symbol={symbol}")
            metrics = self._finnhub_request(f"stock/metric?symbol={symbol}&metric=all")
            
            if not profile:
                return {}, ""
            
            m = metrics.get("metric", {}) if metrics else {}
            
            return {
                "company_name": profile.get("name", ""),
                "sector": profile.get("finnhubIndustry", ""),
                "industry": profile.get("finnhubIndustry", ""),
                "country": profile.get("country", ""),
                "market_cap": profile.get("marketCapitalization", 0) * 1e6,
                "employees": profile.get("employeeTotal", 0),
                "website": profile.get("weburl", ""),
                "pe_ratio": m.get("peBasicExclExtraTTM"),
                "pb_ratio": m.get("pbQuarterly"),
                "ps_ratio": m.get("psAnnual"),
                "dividend_yield": m.get("dividendYieldIndicatedAnnual"),
                "roe": m.get("roeTTM"),
                "roa": m.get("roaTTM"),
                "profit_margin": m.get("netProfitMarginTTM"),
                "beta": m.get("beta"),
                "52_week_high": m.get("52WeekHigh"),
                "52_week_low": m.get("52WeekLow"),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_news(self, symbol: str, limit: int = 10) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            data = self._finnhub_request(f"company-news?symbol={symbol}&from={start}&to={end}")
            if not data:
                return [], ""
            
            news = [{
                "title": n.get("headline", ""),
                "url": n.get("url", ""),
                "source": n.get("source", ""),
                "published": datetime.fromtimestamp(n.get("datetime", 0)).isoformat(),
                "summary": n.get("summary", "")[:200]
            } for n in data[:limit]]
            
            return (news, self.name) if news else ([], "")
        except Exception:
            return [], ""


# =============================================================================
# POLYGON SOURCE
# =============================================================================

class PolygonSource(BaseSource):
    """Polygon.io - US stocks, options, low rate limit on free tier."""
    
    name = "Polygon"
    config_key = "polygon"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("POLYGON_API_KEY", "")
        self.base_url = "https://api.polygon.io"
        self.available = bool(self.api_key)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            url = (f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
                   f"?adjusted=true&sort=asc&apiKey={self.api_key}")
            
            data = self._request(url, timeout=30)
            if not data or data.get("status") != "OK":
                return [], ""
            
            bars = [{
                "date": datetime.fromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d"),
                "open": float(r.get("o", 0)),
                "high": float(r.get("h", 0)),
                "low": float(r.get("l", 0)),
                "close": float(r.get("c", 0)),
                "volume": int(r.get("v", 0))
            } for r in data.get("results", [])]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/prev?adjusted=true&apiKey={self.api_key}"
            data = self._request(url)
            
            if not data or not data.get("results"):
                return {}, ""
            
            r = data["results"][0]
            return {
                "symbol": symbol,
                "price": float(r.get("c", 0)),
                "open": float(r.get("o", 0)),
                "high": float(r.get("h", 0)),
                "low": float(r.get("l", 0)),
                "volume": int(r.get("v", 0)),
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# TWELVEDATA SOURCE
# =============================================================================

class TwelveDataSource(BaseSource):
    """Twelvedata - Global coverage, good free tier."""
    
    name = "Twelvedata"
    config_key = "twelvedata"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("TWELVEDATA_API_KEY", "")
        self.base_url = "https://api.twelvedata.com"
        self.available = bool(self.api_key)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            url = f"{self.base_url}/time_series?symbol={symbol}&interval=1day&outputsize={days}&apikey={self.api_key}"
            data = self._request(url, timeout=30)
            
            if not data or data.get("status") == "error":
                return [], ""
            
            bars = [{
                "date": v.get("datetime", ""),
                "open": float(v.get("open", 0)),
                "high": float(v.get("high", 0)),
                "low": float(v.get("low", 0)),
                "close": float(v.get("close", 0)),
                "volume": int(v.get("volume", 0) or 0)
            } for v in reversed(data.get("values", []))]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            url = f"{self.base_url}/quote?symbol={symbol}&apikey={self.api_key}"
            data = self._request(url)
            
            if not data or "code" in data:
                return {}, ""
            
            return {
                "symbol": symbol,
                "price": float(data.get("close", 0)),
                "change": float(data.get("change", 0)),
                "change_pct": float(data.get("percent_change", 0)),
                "open": float(data.get("open", 0)),
                "high": float(data.get("high", 0)),
                "low": float(data.get("low", 0)),
                "volume": int(data.get("volume", 0) or 0),
                "prev_close": float(data.get("previous_close", 0)),
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# ALPHA VANTAGE SOURCE
# =============================================================================

class AlphaVantageSource(BaseSource):
    """Alpha Vantage - Global, limited free tier (25/day)."""
    
    name = "AlphaVantage"
    config_key = "alphavantage"
    
    def __init__(self):
        super().__init__()
        # Support both naming conventions
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY", "") or os.getenv("ALPHA_VANTAGE_KEY", "")
        self.base_url = "https://www.alphavantage.co/query"
        self.available = bool(self.api_key)
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            outputsize = "full" if days > 100 else "compact"
            url = f"{self.base_url}?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&outputsize={outputsize}&apikey={self.api_key}"
            
            data = self._request(url, timeout=30)
            if not data or "Error Message" in data or "Note" in data:
                return [], ""
            
            time_series = data.get("Time Series (Daily)", {})
            if not time_series:
                return [], ""
            
            bars = []
            for date_str, values in sorted(time_series.items()):
                bars.append({
                    "date": date_str,
                    "open": float(values.get("1. open", 0)),
                    "high": float(values.get("2. high", 0)),
                    "low": float(values.get("3. low", 0)),
                    "close": float(values.get("5. adjusted close", values.get("4. close", 0))),
                    "volume": int(values.get("6. volume", 0))
                })
            
            if len(bars) > days:
                bars = bars[-days:]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            url = f"{self.base_url}?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"
            data = self._request(url)
            
            if not data or "Global Quote" not in data:
                return {}, ""
            
            q = data["Global Quote"]
            return {
                "symbol": symbol,
                "price": float(q.get("05. price", 0)),
                "change": float(q.get("09. change", 0)),
                "change_pct": float(q.get("10. change percent", "0").rstrip("%")),
                "open": float(q.get("02. open", 0)),
                "high": float(q.get("03. high", 0)),
                "low": float(q.get("04. low", 0)),
                "volume": int(q.get("06. volume", 0)),
                "prev_close": float(q.get("08. previous close", 0)),
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# EODHD SOURCE
# =============================================================================

class EODHDSource(BaseSource):
    """EOD Historical Data - Global, limited free tier (20/day)."""
    
    name = "EODHD"
    config_key = "eodhd"
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("EODHD_API_KEY", "")
        self.base_url = "https://eodhd.com/api"
        self.available = bool(self.api_key)
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol to EODHD format (SYMBOL.EXCHANGE)."""
        if "." in symbol:
            return symbol
        return f"{symbol}.US"  # Default to US
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        if not self.available:
            return [], ""
        
        try:
            eod_symbol = self._convert_symbol(symbol)
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            url = f"{self.base_url}/eod/{eod_symbol}?from={start}&to={end}&period=d&fmt=json&api_token={self.api_key}"
            data = self._request(url, timeout=30)
            
            if not data or not isinstance(data, list):
                return [], ""
            
            bars = [{
                "date": d.get("date", ""),
                "open": float(d.get("open", 0)),
                "high": float(d.get("high", 0)),
                "low": float(d.get("low", 0)),
                "close": float(d.get("adjusted_close", d.get("close", 0))),
                "volume": int(d.get("volume", 0))
            } for d in data]
            
            return (bars, self.name) if bars else ([], "")
        except Exception:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            eod_symbol = self._convert_symbol(symbol)
            url = f"{self.base_url}/real-time/{eod_symbol}?fmt=json&api_token={self.api_key}"
            data = self._request(url)
            
            if not data:
                return {}, ""
            
            return {
                "symbol": symbol,
                "price": float(data.get("close", 0)),
                "change": float(data.get("change", 0)),
                "change_pct": float(data.get("change_p", 0)),
                "open": float(data.get("open", 0)),
                "high": float(data.get("high", 0)),
                "low": float(data.get("low", 0)),
                "volume": int(data.get("volume", 0)),
                "prev_close": float(data.get("previousClose", 0)),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        if not self.available:
            return {}, ""
        
        try:
            eod_symbol = self._convert_symbol(symbol)
            url = f"{self.base_url}/fundamentals/{eod_symbol}?api_token={self.api_key}"
            data = self._request(url, timeout=30)
            
            if not data:
                return {}, ""
            
            general = data.get("General", {})
            highlights = data.get("Highlights", {})
            valuation = data.get("Valuation", {})
            
            return {
                "company_name": general.get("Name", ""),
                "sector": general.get("Sector", ""),
                "industry": general.get("Industry", ""),
                "country": general.get("CountryName", ""),
                "market_cap": highlights.get("MarketCapitalization", 0),
                "employees": general.get("FullTimeEmployees", 0),
                "description": general.get("Description", ""),
                "website": general.get("WebURL", ""),
                "pe_ratio": highlights.get("PERatio"),
                "pb_ratio": valuation.get("PriceBookMRQ"),
                "dividend_yield": highlights.get("DividendYield"),
                "roe": highlights.get("ReturnOnEquityTTM"),
                "profit_margin": highlights.get("ProfitMargin"),
                "eps": highlights.get("EarningsShare"),
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# YAHOO SOURCE
# =============================================================================

class YahooSource(BaseSource):
    """Yahoo Finance - Free, global, but sometimes unreliable."""
    
    name = "Yahoo"
    config_key = "yahoo"
    
    def __init__(self):
        super().__init__()
        self.available = True  # Always available
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        try:
            import urllib.parse
            import time
            
            # Try both original and uppercase symbol (Yahoo sometimes is case-sensitive)
            symbols_to_try = [symbol, symbol.upper()]
            
            # Determine range
            if days <= 30:
                range_val = "1mo"
            elif days <= 100:
                range_val = "6mo"
            elif days <= 252:
                range_val = "1y"
            else:
                range_val = "2y"
            
            for sym in symbols_to_try:
                encoded = urllib.parse.quote(sym)
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range={range_val}"
                
                # Retry up to 2 times with small delay
                for attempt in range(2):
                    data = self._request(url, timeout=30)
                    
                    if data:
                        result = data.get("chart", {}).get("result", [])
                        if result:
                            quotes = result[0]
                            timestamps = quotes.get("timestamp", [])
                            ohlc = quotes.get("indicators", {}).get("quote", [{}])[0]
                            
                            if timestamps:
                                bars = []
                                for i, ts in enumerate(timestamps):
                                    close = ohlc.get("close", [None])[i]
                                    if close is not None:
                                        bars.append({
                                            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                                            "open": ohlc.get("open", [0])[i] or close,
                                            "high": ohlc.get("high", [0])[i] or close,
                                            "low": ohlc.get("low", [0])[i] or close,
                                            "close": close,
                                            "volume": ohlc.get("volume", [0])[i] or 0
                                        })
                                
                                if bars:
                                    return (bars, self.name)
                    
                    # Small delay before retry
                    if attempt == 0:
                        time.sleep(0.5)
            
            return [], ""
        except Exception as e:
            return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        try:
            import urllib.parse
            encoded = urllib.parse.quote(symbol)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range=1d"
            data = self._request(url)
            
            if not data:
                return {}, ""
            
            result = data.get("chart", {}).get("result", [])
            if not result:
                return {}, ""
            
            meta = result[0].get("meta", {})
            
            return {
                "symbol": symbol,
                "price": float(meta.get("regularMarketPrice", 0)),
                "prev_close": float(meta.get("chartPreviousClose", 0)),
                "change": float(meta.get("regularMarketPrice", 0)) - float(meta.get("chartPreviousClose", 0)),
            }, self.name
        except Exception:
            return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        try:
            import urllib.parse
            encoded = urllib.parse.quote(symbol)
            
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{encoded}?modules=summaryProfile,summaryDetail,defaultKeyStatistics,financialData"
            data = self._request(url)
            
            if not data:
                return {}, ""
            
            result = data.get("quoteSummary", {}).get("result", [])
            if not result:
                return {}, ""
            
            r = result[0]
            profile = r.get("summaryProfile", {})
            detail = r.get("summaryDetail", {})
            stats = r.get("defaultKeyStatistics", {})
            financial = r.get("financialData", {})
            
            return {
                "company_name": "",
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "country": profile.get("country", ""),
                "employees": profile.get("fullTimeEmployees", 0),
                "website": profile.get("website", ""),
                "pe_ratio": detail.get("trailingPE", {}).get("raw"),
                "pb_ratio": stats.get("priceToBook", {}).get("raw"),
                "dividend_yield": detail.get("dividendYield", {}).get("raw"),
                "roe": financial.get("returnOnEquity", {}).get("raw"),
                "profit_margin": financial.get("profitMargins", {}).get("raw"),
                "market_cap": detail.get("marketCap", {}).get("raw", 0),
            }, self.name
        except Exception:
            return {}, ""


# =============================================================================
# MAIN DATA FETCHER
# =============================================================================

class DataFetcher:
    """
    Multi-source data fetcher with intelligent fallback.
    
    Automatically selects the best available source based on:
    - API availability (has key configured)
    - Rate limit status (not exceeded)
    - Source health (recent success rate)
    - Priority for data type
    - US vs international stock support
    """
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.rate_limiter = RateLimiter()
        self.cache = DataCache(ttl_seconds=60)  # 1 minute cache for quotes
        
        # Initialize all sources
        self.sources = {
            "alpaca": AlpacaSource(),
            "fmp": FMPSource(),
            "finnhub": FinnhubSource(),
            "polygon": PolygonSource(),
            "twelvedata": TwelveDataSource(),
            "alphavantage": AlphaVantageSource(),
            "eodhd": EODHDSource(),
            "yahoo": YahooSource(),
        }
    
    def _get_sorted_sources(self, data_type: str, is_us: bool = True) -> List[Tuple[str, BaseSource]]:
        """Get sources sorted by priority for a data type."""
        available = []
        
        for key, source in self.sources.items():
            config = SOURCE_CONFIGS.get(key)
            if not config:
                continue
            
            # Check if source is available
            if not source.available:
                continue
            
            # Check if source supports this data type
            if data_type == "price" and not config.supports_price:
                continue
            if data_type == "fundamentals" and not config.supports_fundamentals:
                continue
            if data_type == "quote" and not config.supports_quote:
                continue
            if data_type == "news" and not config.supports_news:
                continue
            
            # Check international support
            if not is_us and not config.supports_international:
                continue
            
            # Check rate limits
            if not self.rate_limiter.can_use(key, config):
                if self.verbose:
                    print(f"    [WARN] {source.name}: Rate limit reached")
                continue
            
            # Get priority
            if data_type == "price":
                priority = config.priority_price
            elif data_type == "fundamentals":
                priority = config.priority_fundamentals
            else:
                priority = config.priority_quote
            
            # Adjust priority by health score
            health = source.health_score()
            adjusted_priority = priority / max(health, 0.1)
            
            available.append((key, source, adjusted_priority))
        
        # Sort by priority (lower = better)
        available.sort(key=lambda x: x[2])
        
        return [(k, s) for k, s, _ in available]
    
    def _is_us_stock(self, symbol: str) -> bool:
        """Determine if symbol is a US stock."""
        # If has suffix like .AX, .L, .TO, it's international
        if "." in symbol:
            suffix = symbol.split(".")[-1].upper()
            if suffix in ["AX", "L", "TO", "HK", "T", "PA", "DE", "MI", "AS", "SW"]:
                return False
        return True
    
    def get_bars(self, symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
        """
        Get historical price bars from the best available source.
        
        Args:
            symbol: Stock symbol
            days: Number of days of history
        
        Returns:
            Tuple of (bars, source_name)
        """
        symbol = symbol.upper()
        is_us = self._is_us_stock(symbol)
        
        # Check cache
        cache_key = f"bars_{symbol}_{days}"
        cached = self.cache.get(cache_key)
        if cached:
            if self.verbose:
                print(f"    → Using cached data")
            return cached
        
        sources = self._get_sorted_sources("price", is_us)
        
        if not sources:
            if self.verbose:
                print(f"    [WARN] No sources available for {symbol}")
            return [], ""
        
        for key, source in sources:
            config = SOURCE_CONFIGS[key]
            
            if self.verbose:
                print(f"    → Trying {source.name}...", end=" ", flush=True)
            
            bars, source_name = source.get_bars(symbol, days)
            
            if bars:
                self.rate_limiter.record_use(key)
                if self.verbose:
                    print(f"[Y] ({len(bars)} bars)")
                
                # Cache the result
                self.cache.set(cache_key, (bars, source_name))
                return bars, source_name
            else:
                if self.verbose:
                    print(f"[N] ({source._last_error or 'No data'})")
        
        return [], ""
    
    def get_quote(self, symbol: str) -> Tuple[Dict, str]:
        """Get real-time quote from the best available source."""
        symbol = symbol.upper()
        is_us = self._is_us_stock(symbol)
        
        # Check cache (short TTL for quotes)
        cache_key = f"quote_{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        sources = self._get_sorted_sources("quote", is_us)
        
        for key, source in sources:
            if self.verbose:
                print(f"    → Trying {source.name}...", end=" ", flush=True)
            
            quote, source_name = source.get_quote(symbol)
            
            if quote:
                self.rate_limiter.record_use(key)
                if self.verbose:
                    print(f"[Y]")
                self.cache.set(cache_key, (quote, source_name))
                return quote, source_name
            else:
                if self.verbose:
                    print(f"[N]")
        
        return {}, ""
    
    def get_fundamentals(self, symbol: str) -> Tuple[Dict, str]:
        """Get fundamental data from the best available source."""
        symbol = symbol.upper()
        is_us = self._is_us_stock(symbol)
        
        cache_key = f"fundamentals_{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        sources = self._get_sorted_sources("fundamentals", is_us)
        
        for key, source in sources:
            if self.verbose:
                print(f"    → Trying {source.name}...", end=" ", flush=True)
            
            data, source_name = source.get_fundamentals(symbol)
            
            if data:
                self.rate_limiter.record_use(key)
                if self.verbose:
                    print(f"[Y]")
                self.cache.set(cache_key, (data, source_name))
                return data, source_name
            else:
                if self.verbose:
                    print(f"[N]")
        
        return {}, ""
    
    def get_news(self, symbol: str, limit: int = 10) -> Tuple[List[Dict], str]:
        """Get news from the best available source."""
        symbol = symbol.upper()
        is_us = self._is_us_stock(symbol)
        
        sources = self._get_sorted_sources("news", is_us)
        
        for key, source in sources:
            if self.verbose:
                print(f"    → Trying {source.name}...", end=" ", flush=True)
            
            news, source_name = source.get_news(symbol, limit)
            
            if news:
                self.rate_limiter.record_use(key)
                if self.verbose:
                    print(f"[Y] ({len(news)} articles)")
                return news, source_name
            else:
                if self.verbose:
                    print(f"[N]")
        
        return [], ""
    
    def print_source_status(self):
        """Print status of all data sources."""
        print("\n" + "="*70)
        print("DATA SOURCE STATUS")
        print("="*70)
        
        print(f"\n{'Source':<15} {'Status':<12} {'Health':>8} {'Today':>10} {'Limit':>10}")
        print("-"*70)
        
        for key, source in self.sources.items():
            config = SOURCE_CONFIGS.get(key)
            if not config:
                continue
            
            status = "[Y] Ready" if source.available else "[N] No Key"
            health = f"{source.health_score()*100:.0f}%"
            
            usage = self.rate_limiter.get_usage(key, config)
            today = f"{usage['day']}/{usage['day_limit']}"
            limit_pct = f"{usage['day_pct']:.0f}%"
            
            print(f"{source.name:<15} {status:<12} {health:>8} {today:>10} {limit_pct:>10}")
        
        print("="*70)
        
        # Print priority order
        print("\nPriority Order by Data Type:")
        for dtype in ["price", "quote", "fundamentals"]:
            sources = self._get_sorted_sources(dtype, is_us=True)
            names = [s.name for _, s in sources[:5]]
            print(f"  {dtype.capitalize()}: {' → '.join(names)}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_stock_data(symbol: str, days: int = 400) -> Tuple[List[Dict], str]:
    """Quick function to get stock bars."""
    fetcher = DataFetcher(verbose=False)
    return fetcher.get_bars(symbol, days)


def get_quote(symbol: str) -> Tuple[Dict, str]:
    """Quick function to get a quote."""
    fetcher = DataFetcher(verbose=False)
    return fetcher.get_quote(symbol)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Testing Enhanced Multi-Source Data Fetcher")
    print("="*60)
    
    fetcher = DataFetcher(verbose=True)
    
    # Print source status
    fetcher.print_source_status()
    
    # Test symbols
    test_symbols = [
        ("AAPL", "US Tech"),
        ("BHP.AX", "Australian"),
        ("VOD.L", "UK"),
    ]
    
    for symbol, desc in test_symbols:
        print(f"\n{'='*60}")
        print(f"Testing {symbol} ({desc})")
        print("="*60)
        
        print("\nPrice Data:")
        bars, source = fetcher.get_bars(symbol, days=30)
        if bars:
            print(f"  [Y] Got {len(bars)} bars from {source}")
            print(f"  Latest: {bars[-1]['date']} - ${bars[-1]['close']:.2f}")
        else:
            print(f"  [N] No price data available")
        
        print("\nQuote:")
        quote, source = fetcher.get_quote(symbol)
        if quote:
            print(f"  [Y] Got quote from {source}")
            print(f"  Price: ${quote.get('price', 0):.2f}")
        else:
            print(f"  [N] No quote available")
        
        print("\nFundamentals:")
        data, source = fetcher.get_fundamentals(symbol)
        if data:
            print(f"  [Y] Got fundamentals from {source}")
            print(f"  Company: {data.get('company_name', 'N/A')}")
            print(f"  Sector: {data.get('sector', 'N/A')}")
        else:
            print(f"  [N] No fundamentals available")
