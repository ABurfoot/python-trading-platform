#!/usr/bin/env python3
"""
Global Indices Module
======================
Track major world indices across Americas, Asia-Pacific, and Europe.

Features:
- Real-time index prices and changes
- Market open/close status with local times
- Regional grouping (Americas, Asia-Pacific, Europe)
- Correlation analysis between indices
- Historical performance comparison
- Futures data for pre-market indication

Supported Indices:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMERICAS          ASIA-PACIFIC       EUROPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S&P 500           ASX 200            FTSE 100
Dow Jones         All Ordinaries     DAX
Nasdaq            Nikkei 225         CAC 40
Russell 2000      Hang Seng          EURO STOXX 50
TSX Composite     Shanghai Comp      IBEX 35
Bovespa           KOSPI              SMI
                  Sensex             AEX
                  NZX 50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    from trading.global_indices import GlobalIndices
    
    gi = GlobalIndices()
    
    # Get all indices
    indices = gi.get_all_indices()
    
    # Print dashboard
    gi.print_dashboard()
    
    # Get specific region
    asia = gi.get_region("asia")
    
    # Check market status
    status = gi.get_market_status()
"""

import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import math


class MarketStatus(Enum):
    """Market trading status."""
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"


class Region(Enum):
    """Geographic regions."""
    AMERICAS = "americas"
    ASIA_PACIFIC = "asia_pacific"
    EUROPE = "europe"


@dataclass
class IndexInfo:
    """Information about a market index."""
    symbol: str
    name: str
    country: str
    region: str
    currency: str
    exchange: str
    # Trading hours in local time (24h format)
    open_time: str  # "09:30"
    close_time: str  # "16:00"
    timezone: str  # "America/New_York"
    utc_offset: float  # hours from UTC
    # Yahoo Finance symbol for data fetching
    yahoo_symbol: str
    # FMP symbol
    fmp_symbol: str = ""
    # Description
    description: str = ""


@dataclass
class IndexQuote:
    """Real-time quote for an index."""
    symbol: str
    name: str
    country: str
    region: str
    price: float
    change: float
    change_pct: float
    day_high: float = 0
    day_low: float = 0
    open_price: float = 0
    prev_close: float = 0
    volume: int = 0
    market_status: str = "unknown"
    last_updated: str = ""
    currency: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @property
    def is_positive(self) -> bool:
        return self.change >= 0
    
    @property
    def country_flag(self) -> str:
        flags = {
            "US": "🇺🇸", "AU": "🇦🇺", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
            "JP": "🇯🇵", "CN": "🇨🇳", "HK": "🇭🇰", "KR": "🇰🇷", "IN": "🇮🇳",
            "CA": "🇨🇦", "BR": "🇧🇷", "NZ": "🇳🇿", "ES": "🇪🇸", "IT": "🇮🇹",
            "CH": "🇨🇭", "NL": "🇳🇱", "EU": "🇪🇺", "SG": "🇸🇬", "TW": "🇹🇼",
        }
        return flags.get(self.country, "🌍")


# =============================================================================
# INDEX DEFINITIONS
# =============================================================================

INDICES = {
    # Americas
    "SPX": IndexInfo(
        symbol="SPX", name="S&P 500", country="US", region="americas",
        currency="USD", exchange="NYSE", open_time="09:30", close_time="16:00",
        timezone="America/New_York", utc_offset=-5,
        yahoo_symbol="^GSPC", fmp_symbol="^GSPC",
        description="500 largest US companies by market cap"
    ),
    "DJI": IndexInfo(
        symbol="DJI", name="Dow Jones", country="US", region="americas",
        currency="USD", exchange="NYSE", open_time="09:30", close_time="16:00",
        timezone="America/New_York", utc_offset=-5,
        yahoo_symbol="^DJI", fmp_symbol="^DJI",
        description="30 large-cap US blue chips"
    ),
    "IXIC": IndexInfo(
        symbol="IXIC", name="Nasdaq Composite", country="US", region="americas",
        currency="USD", exchange="NASDAQ", open_time="09:30", close_time="16:00",
        timezone="America/New_York", utc_offset=-5,
        yahoo_symbol="^IXIC", fmp_symbol="^IXIC",
        description="All Nasdaq-listed stocks"
    ),
    "RUT": IndexInfo(
        symbol="RUT", name="Russell 2000", country="US", region="americas",
        currency="USD", exchange="NYSE", open_time="09:30", close_time="16:00",
        timezone="America/New_York", utc_offset=-5,
        yahoo_symbol="^RUT", fmp_symbol="^RUT",
        description="2000 small-cap US stocks"
    ),
    "GSPTSE": IndexInfo(
        symbol="GSPTSE", name="TSX Composite", country="CA", region="americas",
        currency="CAD", exchange="TSX", open_time="09:30", close_time="16:00",
        timezone="America/Toronto", utc_offset=-5,
        yahoo_symbol="^GSPTSE", fmp_symbol="^GSPTSE",
        description="Canadian benchmark index"
    ),
    "BVSP": IndexInfo(
        symbol="BVSP", name="Bovespa", country="BR", region="americas",
        currency="BRL", exchange="B3", open_time="10:00", close_time="17:00",
        timezone="America/Sao_Paulo", utc_offset=-3,
        yahoo_symbol="^BVSP", fmp_symbol="^BVSP",
        description="Brazilian benchmark index"
    ),
    
    # Asia-Pacific
    "AXJO": IndexInfo(
        symbol="AXJO", name="ASX 200", country="AU", region="asia_pacific",
        currency="AUD", exchange="ASX", open_time="10:00", close_time="16:00",
        timezone="Australia/Sydney", utc_offset=11,
        yahoo_symbol="^AXJO", fmp_symbol="^AXJO",
        description="Top 200 Australian companies"
    ),
    "AORD": IndexInfo(
        symbol="AORD", name="All Ordinaries", country="AU", region="asia_pacific",
        currency="AUD", exchange="ASX", open_time="10:00", close_time="16:00",
        timezone="Australia/Sydney", utc_offset=11,
        yahoo_symbol="^AORD", fmp_symbol="^AORD",
        description="Broad Australian market index"
    ),
    "N225": IndexInfo(
        symbol="N225", name="Nikkei 225", country="JP", region="asia_pacific",
        currency="JPY", exchange="TSE", open_time="09:00", close_time="15:00",
        timezone="Asia/Tokyo", utc_offset=9,
        yahoo_symbol="^N225", fmp_symbol="^N225",
        description="Top 225 Japanese blue chips"
    ),
    "HSI": IndexInfo(
        symbol="HSI", name="Hang Seng", country="HK", region="asia_pacific",
        currency="HKD", exchange="HKEX", open_time="09:30", close_time="16:00",
        timezone="Asia/Hong_Kong", utc_offset=8,
        yahoo_symbol="^HSI", fmp_symbol="^HSI",
        description="Hong Kong benchmark index"
    ),
    "SSEC": IndexInfo(
        symbol="SSEC", name="Shanghai Composite", country="CN", region="asia_pacific",
        currency="CNY", exchange="SSE", open_time="09:30", close_time="15:00",
        timezone="Asia/Shanghai", utc_offset=8,
        yahoo_symbol="000001.SS", fmp_symbol="000001.SS",
        description="All stocks on Shanghai Stock Exchange"
    ),
    "KS11": IndexInfo(
        symbol="KS11", name="KOSPI", country="KR", region="asia_pacific",
        currency="KRW", exchange="KRX", open_time="09:00", close_time="15:30",
        timezone="Asia/Seoul", utc_offset=9,
        yahoo_symbol="^KS11", fmp_symbol="^KS11",
        description="Korean benchmark index"
    ),
    "BSESN": IndexInfo(
        symbol="BSESN", name="BSE Sensex", country="IN", region="asia_pacific",
        currency="INR", exchange="BSE", open_time="09:15", close_time="15:30",
        timezone="Asia/Kolkata", utc_offset=5.5,
        yahoo_symbol="^BSESN", fmp_symbol="^BSESN",
        description="30 largest Indian companies"
    ),
    "NZ50": IndexInfo(
        symbol="NZ50", name="NZX 50", country="NZ", region="asia_pacific",
        currency="NZD", exchange="NZX", open_time="10:00", close_time="16:45",
        timezone="Pacific/Auckland", utc_offset=13,
        yahoo_symbol="^NZ50", fmp_symbol="^NZ50",
        description="New Zealand benchmark index"
    ),
    "STI": IndexInfo(
        symbol="STI", name="Straits Times", country="SG", region="asia_pacific",
        currency="SGD", exchange="SGX", open_time="09:00", close_time="17:00",
        timezone="Asia/Singapore", utc_offset=8,
        yahoo_symbol="^STI", fmp_symbol="^STI",
        description="Singapore benchmark index"
    ),
    "TWII": IndexInfo(
        symbol="TWII", name="Taiwan Weighted", country="TW", region="asia_pacific",
        currency="TWD", exchange="TWSE", open_time="09:00", close_time="13:30",
        timezone="Asia/Taipei", utc_offset=8,
        yahoo_symbol="^TWII", fmp_symbol="^TWII",
        description="Taiwan benchmark index"
    ),
    
    # Europe
    "FTSE": IndexInfo(
        symbol="FTSE", name="FTSE 100", country="GB", region="europe",
        currency="GBP", exchange="LSE", open_time="08:00", close_time="16:30",
        timezone="Europe/London", utc_offset=0,
        yahoo_symbol="^FTSE", fmp_symbol="^FTSE",
        description="100 largest UK companies"
    ),
    "GDAXI": IndexInfo(
        symbol="GDAXI", name="DAX", country="DE", region="europe",
        currency="EUR", exchange="XETRA", open_time="09:00", close_time="17:30",
        timezone="Europe/Berlin", utc_offset=1,
        yahoo_symbol="^GDAXI", fmp_symbol="^GDAXI",
        description="40 largest German companies"
    ),
    "FCHI": IndexInfo(
        symbol="FCHI", name="CAC 40", country="FR", region="europe",
        currency="EUR", exchange="Euronext", open_time="09:00", close_time="17:30",
        timezone="Europe/Paris", utc_offset=1,
        yahoo_symbol="^FCHI", fmp_symbol="^FCHI",
        description="40 largest French companies"
    ),
    "STOXX50E": IndexInfo(
        symbol="STOXX50E", name="EURO STOXX 50", country="EU", region="europe",
        currency="EUR", exchange="STOXX", open_time="09:00", close_time="17:30",
        timezone="Europe/Berlin", utc_offset=1,
        yahoo_symbol="^STOXX50E", fmp_symbol="^STOXX50E",
        description="50 largest Eurozone blue chips"
    ),
    "IBEX": IndexInfo(
        symbol="IBEX", name="IBEX 35", country="ES", region="europe",
        currency="EUR", exchange="BME", open_time="09:00", close_time="17:30",
        timezone="Europe/Madrid", utc_offset=1,
        yahoo_symbol="^IBEX", fmp_symbol="^IBEX",
        description="35 largest Spanish companies"
    ),
    "FTSEMIB": IndexInfo(
        symbol="FTSEMIB", name="FTSE MIB", country="IT", region="europe",
        currency="EUR", exchange="Borsa Italiana", open_time="09:00", close_time="17:30",
        timezone="Europe/Rome", utc_offset=1,
        yahoo_symbol="FTSEMIB.MI", fmp_symbol="FTSEMIB.MI",
        description="40 largest Italian companies"
    ),
    "SMI": IndexInfo(
        symbol="SMI", name="SMI", country="CH", region="europe",
        currency="CHF", exchange="SIX", open_time="09:00", close_time="17:30",
        timezone="Europe/Zurich", utc_offset=1,
        yahoo_symbol="^SSMI", fmp_symbol="^SSMI",
        description="20 largest Swiss companies"
    ),
    "AEX": IndexInfo(
        symbol="AEX", name="AEX", country="NL", region="europe",
        currency="EUR", exchange="Euronext", open_time="09:00", close_time="17:30",
        timezone="Europe/Amsterdam", utc_offset=1,
        yahoo_symbol="^AEX", fmp_symbol="^AEX",
        description="25 largest Dutch companies"
    ),
}

# Popular indices for quick access
POPULAR_INDICES = ["SPX", "DJI", "IXIC", "AXJO", "N225", "HSI", "FTSE", "GDAXI"]


class GlobalIndices:
    """
    Track and analyze global market indices.
    """
    
    def __init__(self, cache_minutes: int = 5):
        self.cache_minutes = cache_minutes
        self._cache: Dict[str, Tuple[IndexQuote, datetime]] = {}
        
        # API keys
        self.fmp_key = os.environ.get("FMP_API_KEY", "")
        self.finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
        self.twelvedata_key = os.environ.get("TWELVEDATA_API_KEY", "")
    
    def _request(self, url: str, timeout: int = 15) -> Optional[Dict]:
        """Make HTTP request."""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None
    
    def _get_market_status(self, index_info: IndexInfo) -> str:
        """Determine if market is open based on trading hours."""
        now_utc = datetime.now(timezone.utc)
        
        # Convert to local time
        local_offset = timedelta(hours=index_info.utc_offset)
        local_time = now_utc + local_offset
        
        # Get current time as string
        current_time = local_time.strftime("%H:%M")
        current_weekday = local_time.weekday()
        
        # Weekend check
        if current_weekday >= 5:  # Saturday = 5, Sunday = 6
            return MarketStatus.CLOSED.value
        
        # Compare times
        if index_info.open_time <= current_time <= index_info.close_time:
            return MarketStatus.OPEN.value
        elif current_time < index_info.open_time:
            return MarketStatus.PRE_MARKET.value
        else:
            return MarketStatus.CLOSED.value
    
    def _fetch_yahoo_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote from Yahoo Finance."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            data = self._request(url)
            
            if not data or "chart" not in data:
                return None
            
            result = data["chart"].get("result", [])
            if not result:
                return None
            
            meta = result[0].get("meta", {})
            
            price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("chartPreviousClose", meta.get("previousClose", 0))
            
            return {
                "price": price,
                "prev_close": prev_close,
                "change": price - prev_close if prev_close else 0,
                "change_pct": ((price - prev_close) / prev_close * 100) if prev_close else 0,
                "day_high": meta.get("regularMarketDayHigh", 0),
                "day_low": meta.get("regularMarketDayLow", 0),
                "open": meta.get("regularMarketOpen", 0),
                "volume": meta.get("regularMarketVolume", 0),
            }
        except Exception:
            return None
    
    def _fetch_fmp_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote from FMP."""
        if not self.fmp_key:
            return None
        
        try:
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={self.fmp_key}"
            data = self._request(url)
            
            if not data or not isinstance(data, list) or len(data) == 0:
                return None
            
            q = data[0]
            return {
                "price": q.get("price", 0),
                "prev_close": q.get("previousClose", 0),
                "change": q.get("change", 0),
                "change_pct": q.get("changesPercentage", 0),
                "day_high": q.get("dayHigh", 0),
                "day_low": q.get("dayLow", 0),
                "open": q.get("open", 0),
                "volume": q.get("volume", 0),
            }
        except Exception:
            return None
    
    def _fetch_twelvedata_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote from Twelvedata."""
        if not self.twelvedata_key:
            return None
        
        try:
            url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={self.twelvedata_key}"
            data = self._request(url)
            
            if not data or "code" in data:
                return None
            
            price = float(data.get("close", 0))
            prev_close = float(data.get("previous_close", 0))
            
            return {
                "price": price,
                "prev_close": prev_close,
                "change": float(data.get("change", 0)),
                "change_pct": float(data.get("percent_change", 0)),
                "day_high": float(data.get("high", 0)),
                "day_low": float(data.get("low", 0)),
                "open": float(data.get("open", 0)),
                "volume": int(data.get("volume", 0) or 0),
            }
        except Exception:
            return None
    
    def get_index(self, symbol: str, use_cache: bool = True) -> Optional[IndexQuote]:
        """
        Get quote for a specific index.
        
        Args:
            symbol: Index symbol (SPX, AXJO, FTSE, etc.)
            use_cache: Whether to use cached data
        
        Returns:
            IndexQuote object or None
        """
        symbol = symbol.upper()
        
        if symbol not in INDICES:
            # Try to find by name
            for sym, info in INDICES.items():
                if symbol.lower() in info.name.lower():
                    symbol = sym
                    break
            else:
                return None
        
        # Check cache
        if use_cache and symbol in self._cache:
            cached_quote, cached_time = self._cache[symbol]
            if datetime.now() - cached_time < timedelta(minutes=self.cache_minutes):
                return cached_quote
        
        index_info = INDICES[symbol]
        
        # Try data sources in order
        quote_data = None
        
        # Try Yahoo first (free, no key needed)
        quote_data = self._fetch_yahoo_quote(index_info.yahoo_symbol)
        
        # Try FMP if Yahoo failed
        if not quote_data and self.fmp_key:
            quote_data = self._fetch_fmp_quote(index_info.fmp_symbol or index_info.yahoo_symbol)
        
        # Try Twelvedata if others failed
        if not quote_data and self.twelvedata_key:
            quote_data = self._fetch_twelvedata_quote(index_info.yahoo_symbol.replace("^", ""))
        
        if not quote_data:
            return None
        
        # Create IndexQuote
        quote = IndexQuote(
            symbol=symbol,
            name=index_info.name,
            country=index_info.country,
            region=index_info.region,
            price=quote_data["price"],
            change=quote_data["change"],
            change_pct=quote_data["change_pct"],
            day_high=quote_data.get("day_high", 0),
            day_low=quote_data.get("day_low", 0),
            open_price=quote_data.get("open", 0),
            prev_close=quote_data.get("prev_close", 0),
            volume=quote_data.get("volume", 0),
            market_status=self._get_market_status(index_info),
            last_updated=datetime.now().isoformat(),
            currency=index_info.currency,
        )
        
        # Cache the result
        self._cache[symbol] = (quote, datetime.now())
        
        return quote
    
    def get_all_indices(self, use_cache: bool = True) -> List[IndexQuote]:
        """Get quotes for all indices."""
        quotes = []
        for symbol in INDICES.keys():
            quote = self.get_index(symbol, use_cache)
            if quote:
                quotes.append(quote)
        return quotes
    
    def get_popular_indices(self, use_cache: bool = True) -> List[IndexQuote]:
        """Get quotes for popular indices only."""
        quotes = []
        for symbol in POPULAR_INDICES:
            quote = self.get_index(symbol, use_cache)
            if quote:
                quotes.append(quote)
        return quotes
    
    def get_region(self, region: str, use_cache: bool = True) -> List[IndexQuote]:
        """
        Get indices for a specific region.
        
        Args:
            region: americas, asia_pacific, or europe
        """
        region = region.lower().replace("-", "_").replace(" ", "_")
        
        quotes = []
        for symbol, info in INDICES.items():
            if info.region == region:
                quote = self.get_index(symbol, use_cache)
                if quote:
                    quotes.append(quote)
        
        return quotes
    
    def get_market_status(self) -> Dict[str, List[Dict]]:
        """Get market open/closed status for all regions."""
        status = {
            "open": [],
            "closed": [],
            "pre_market": [],
        }
        
        for symbol, info in INDICES.items():
            market_status = self._get_market_status(info)
            
            entry = {
                "symbol": symbol,
                "name": info.name,
                "country": info.country,
                "local_time": self._get_local_time(info),
                "status": market_status,
            }
            
            if market_status == MarketStatus.OPEN.value:
                status["open"].append(entry)
            elif market_status == MarketStatus.PRE_MARKET.value:
                status["pre_market"].append(entry)
            else:
                status["closed"].append(entry)
        
        return status
    
    def _get_local_time(self, info: IndexInfo) -> str:
        """Get current local time for an index."""
        now_utc = datetime.now(timezone.utc)
        local_offset = timedelta(hours=info.utc_offset)
        local_time = now_utc + local_offset
        return local_time.strftime("%H:%M")
    
    def get_gainers_losers(self, use_cache: bool = True) -> Dict[str, List[IndexQuote]]:
        """Get top gainers and losers."""
        quotes = self.get_all_indices(use_cache)
        
        # Sort by change percentage
        sorted_quotes = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
        
        gainers = [q for q in sorted_quotes if q.change_pct > 0][:5]
        losers = [q for q in sorted_quotes if q.change_pct < 0][-5:][::-1]
        
        return {
            "gainers": gainers,
            "losers": losers,
        }
    
    def print_dashboard(self, show_all: bool = False):
        """
        Print a formatted dashboard of global indices.
        
        Args:
            show_all: Show all indices (default: popular only)
        """
        if show_all:
            quotes = self.get_all_indices()
        else:
            quotes = self.get_popular_indices()
        
        # Group by region
        regions = {
            "americas": [],
            "asia_pacific": [],
            "europe": [],
        }
        
        for quote in quotes:
            if quote.region in regions:
                regions[quote.region].append(quote)
        
        print(f"\n{'='*80}")
        print("🌍 GLOBAL MARKET INDICES")
        print(f"   Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        # Americas
        if regions["americas"]:
            print(f"\n🌎 AMERICAS")
            print("-"*80)
            self._print_region_table(regions["americas"])
        
        # Asia-Pacific
        if regions["asia_pacific"]:
            print(f"\n🌏 ASIA-PACIFIC")
            print("-"*80)
            self._print_region_table(regions["asia_pacific"])
        
        # Europe
        if regions["europe"]:
            print(f"\n🌍 EUROPE")
            print("-"*80)
            self._print_region_table(regions["europe"])
        
        # Summary
        all_quotes = [q for qs in regions.values() for q in qs]
        advancing = len([q for q in all_quotes if q.change >= 0])
        declining = len(all_quotes) - advancing
        
        print(f"\n{'='*80}")
        print(f" SUMMARY: [+] Advancing: {advancing} | [-] Declining: {declining}")
        print(f"{'='*80}\n")
    
    def _print_region_table(self, quotes: List[IndexQuote]):
        """Print a formatted table for a region."""
        print(f"{'':2}{'Index':<20} {'Price':>12} {'Change':>10} {'%':>8} {'Status':<10}")
        print(f"{'':2}{'-'*70}")
        
        for q in quotes:
            # Status indicator
            if q.market_status == "open":
                status = "[+] Open"
            elif q.market_status == "pre_market":
                status = "[~] Pre"
            else:
                status = "[-] Closed"
            
            # Change color indicator
            if q.change >= 0:
                change_str = f"+{q.change:,.2f}"
                pct_str = f"+{q.change_pct:.2f}%"
            else:
                change_str = f"{q.change:,.2f}"
                pct_str = f"{q.change_pct:.2f}%"
            
            print(f"{q.country_flag} {q.name:<18} {q.price:>12,.2f} {change_str:>10} {pct_str:>8} {status:<10}")
    
    def print_region(self, region: str):
        """Print indices for a specific region."""
        quotes = self.get_region(region)
        
        if not quotes:
            print(f"No data available for region: {region}")
            return
        
        region_names = {
            "americas": "🌎 AMERICAS",
            "asia_pacific": "🌏 ASIA-PACIFIC",
            "europe": "🌍 EUROPE",
        }
        
        region_key = region.lower().replace("-", "_").replace(" ", "_")
        
        print(f"\n{'='*70}")
        print(region_names.get(region_key, region.upper()))
        print(f"{'='*70}")
        self._print_region_table(quotes)
        print(f"{'='*70}\n")
    
    def print_market_status(self):
        """Print current market status."""
        status = self.get_market_status()
        
        print(f"\n{'='*60}")
        print("🕐 MARKET STATUS")
        print(f"{'='*60}")
        
        if status["open"]:
            print(f"\n[+] OPEN NOW ({len(status['open'])} markets)")
            print("-"*40)
            for m in status["open"]:
                flags = {"US": "🇺🇸", "AU": "🇦🇺", "GB": "🇬🇧", "DE": "🇩🇪", "JP": "🇯🇵",
                        "HK": "🇭🇰", "CN": "🇨🇳", "FR": "🇫🇷", "CA": "🇨🇦"}.get(m["country"], "🌍")
                print(f"   {flags} {m['name']:<20} (Local: {m['local_time']})")
        
        if status["pre_market"]:
            print(f"\n[~] PRE-MARKET ({len(status['pre_market'])} markets)")
            print("-"*40)
            for m in status["pre_market"]:
                flags = {"US": "🇺🇸", "AU": "🇦🇺", "GB": "🇬🇧", "DE": "🇩🇪", "JP": "🇯🇵",
                        "HK": "🇭🇰", "CN": "🇨🇳", "FR": "🇫🇷", "CA": "🇨🇦"}.get(m["country"], "🌍")
                print(f"   {flags} {m['name']:<20} (Local: {m['local_time']})")
        
        if status["closed"]:
            print(f"\n[-] CLOSED ({len(status['closed'])} markets)")
            print("-"*40)
            for m in status["closed"][:8]:  # Limit display
                flags = {"US": "🇺🇸", "AU": "🇦🇺", "GB": "🇬🇧", "DE": "🇩🇪", "JP": "🇯🇵",
                        "HK": "🇭🇰", "CN": "🇨🇳", "FR": "🇫🇷", "CA": "🇨🇦"}.get(m["country"], "🌍")
                print(f"   {flags} {m['name']:<20} (Local: {m['local_time']})")
            if len(status["closed"]) > 8:
                print(f"   ... and {len(status['closed']) - 8} more")
        
        print(f"\n{'='*60}\n")
    
    def print_gainers_losers(self):
        """Print top gainers and losers."""
        data = self.get_gainers_losers()
        
        print(f"\n{'='*60}")
        print(" TOP GAINERS")
        print("-"*60)
        
        for q in data["gainers"]:
            print(f"   {q.country_flag} {q.name:<20} {q.price:>10,.2f}  +{q.change_pct:.2f}%")
        
        print(f"\n TOP LOSERS")
        print("-"*60)
        
        for q in data["losers"]:
            print(f"   {q.country_flag} {q.name:<20} {q.price:>10,.2f}  {q.change_pct:.2f}%")
        
        print(f"{'='*60}\n")
    
    def get_index_info(self, symbol: str) -> Optional[IndexInfo]:
        """Get static information about an index."""
        symbol = symbol.upper()
        return INDICES.get(symbol)
    
    def list_indices(self) -> List[Dict]:
        """List all available indices."""
        return [
            {
                "symbol": sym,
                "name": info.name,
                "country": info.country,
                "region": info.region,
                "currency": info.currency,
                "exchange": info.exchange,
            }
            for sym, info in INDICES.items()
        ]


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Global Market Indices")
    parser.add_argument("--all", "-a", action="store_true", help="Show all indices")
    parser.add_argument("--region", "-r", choices=["americas", "asia", "europe"], help="Show specific region")
    parser.add_argument("--status", "-s", action="store_true", help="Show market status")
    parser.add_argument("--movers", "-m", action="store_true", help="Show gainers/losers")
    parser.add_argument("--index", "-i", help="Show specific index (e.g., SPX, AXJO)")
    parser.add_argument("--list", "-l", action="store_true", help="List all available indices")
    
    args = parser.parse_args()
    gi = GlobalIndices()
    
    if args.list:
        print(f"\n{'='*70}")
        print("AVAILABLE INDICES")
        print(f"{'='*70}")
        indices = gi.list_indices()
        
        for region in ["americas", "asia_pacific", "europe"]:
            region_indices = [i for i in indices if i["region"] == region]
            print(f"\n{region.upper().replace('_', '-')}:")
            for idx in region_indices:
                print(f"   {idx['symbol']:<10} {idx['name']:<25} {idx['country']}")
        print()
    
    elif args.index:
        quote = gi.get_index(args.index)
        if quote:
            print(f"\n{quote.country_flag} {quote.name} ({quote.symbol})")
            print("-"*40)
            print(f"   Price:      {quote.price:>12,.2f} {quote.currency}")
            print(f"   Change:     {quote.change:>+12,.2f}")
            print(f"   Change %:   {quote.change_pct:>+12.2f}%")
            print(f"   Day High:   {quote.day_high:>12,.2f}")
            print(f"   Day Low:    {quote.day_low:>12,.2f}")
            print(f"   Status:     {quote.market_status}")
            print()
        else:
            print(f"Index not found: {args.index}")
    
    elif args.status:
        gi.print_market_status()
    
    elif args.movers:
        gi.print_gainers_losers()
    
    elif args.region:
        region_map = {"asia": "asia_pacific"}
        region = region_map.get(args.region, args.region)
        gi.print_region(region)
    
    else:
        gi.print_dashboard(show_all=args.all)


if __name__ == "__main__":
    main()
