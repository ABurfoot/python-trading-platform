#!/usr/bin/env python3
"""
Sector Heatmap
==============
Visual sector performance overview.

Features:
- S&P 500 sector ETFs performance
- Daily/weekly/monthly performance
- Color-coded heatmap
- Top movers by sector

Usage:
    from trading.sectors import SectorHeatmap
    
    sh = SectorHeatmap()
    performance = sh.get_sector_performance()
    sh.print_heatmap()
"""

import os
import json
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

ssl._create_default_https_context = ssl._create_unverified_context


# S&P 500 Sector ETFs
SECTOR_ETFS = {
    "XLK": {"name": "Technology", "color": "blue"},
    "XLF": {"name": "Financials", "color": "green"},
    "XLV": {"name": "Healthcare", "color": "cyan"},
    "XLY": {"name": "Consumer Discretionary", "color": "yellow"},
    "XLP": {"name": "Consumer Staples", "color": "brown"},
    "XLE": {"name": "Energy", "color": "orange"},
    "XLI": {"name": "Industrials", "color": "gray"},
    "XLB": {"name": "Materials", "color": "purple"},
    "XLRE": {"name": "Real Estate", "color": "pink"},
    "XLU": {"name": "Utilities", "color": "teal"},
    "XLC": {"name": "Communication Services", "color": "red"},
}

# Major index ETFs
INDEX_ETFS = {
    "SPY": "S&P 500",
    "QQQ": "NASDAQ 100",
    "DIA": "Dow Jones",
    "IWM": "Russell 2000",
}


# Simple cache for sector data
_sector_cache = {}
_cache_ttl = {}
_CACHE_DURATION = 30  # 30 second cache


def _get_cached(key: str) -> Optional[any]:
    """Get cached value if not expired."""
    if key in _sector_cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _sector_cache[key]
        else:
            del _sector_cache[key]
            del _cache_ttl[key]
    return None


def _set_cached(key: str, value: any, ttl: int = None):
    """Set cached value with TTL."""
    _sector_cache[key] = value
    _cache_ttl[key] = time.time() + (ttl or _CACHE_DURATION)


@dataclass
class SectorPerformance:
    """Performance data for a sector."""
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    week_change_pct: float = 0
    month_change_pct: float = 0
    ytd_change_pct: float = 0


class SectorHeatmap:
    """Generate sector performance heatmap."""
    
    def __init__(self):
        self.fmp_key = os.getenv("FMP_API_KEY", "")
        self.av_key = os.getenv("ALPHAVANTAGE_API_KEY", "")
    
    def _fetch_batch_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch quotes for multiple symbols in one batch request."""
        results = {}
        
        # Try FMP batch quote first
        if self.fmp_key:
            try:
                symbols_str = ",".join(symbols)
                url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={self.fmp_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    if isinstance(data, list):
                        for item in data:
                            symbol = item.get("symbol", "")
                            if symbol:
                                results[symbol] = {
                                    "price": item.get("price", 0),
                                    "change": item.get("change", 0),
                                    "changesPercentage": item.get("changesPercentage", 0),
                                    "volume": item.get("volume", 0),
                                    "previousClose": item.get("previousClose", 0),
                                }
                if results:
                    return results
            except Exception:
                pass
        
        # Fallback: fetch individually from Yahoo Finance
        def fetch_yahoo(symbol):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    result = data.get("chart", {}).get("result", [])
                    if result:
                        meta = result[0].get("meta", {})
                        return symbol, {
                            "price": meta.get("regularMarketPrice", 0),
                            "changesPercentage": meta.get("regularMarketChangePercent", 0),
                            "change": meta.get("regularMarketChange", 0),
                            "volume": meta.get("regularMarketVolume", 0),
                            "previousClose": meta.get("chartPreviousClose", 0),
                        }
            except Exception:
                pass
            return symbol, None
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_yahoo, s) for s in symbols]
            for future in as_completed(futures):
                symbol, data = future.result()
                if data:
                    results[symbol] = data
        
        return results
    
    def _fetch_historical_prices(self, symbol: str, days: int) -> Optional[List[float]]:
        """Fetch historical closing prices from Yahoo Finance."""
        try:
            # Yahoo Finance chart API - free and reliable
            period_map = {
                1: "5d", 5: "5d", 7: "5d", 30: "1mo", 
                90: "3mo", 180: "6mo", 365: "1y", 
                1095: "5y", 1825: "5y"
            }
            range_str = period_map.get(days, "1mo")
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={range_str}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                result = data.get("chart", {}).get("result", [])
                if result:
                    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                    # Filter out None values
                    return [c for c in closes if c is not None]
        except Exception:
            pass
        return None
    
    def _fetch_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote data for a single symbol (fallback method)."""
        quotes = self._fetch_batch_quotes([symbol])
        return quotes.get(symbol)
    
    def get_sector_performance(self) -> List[SectorPerformance]:
        """Get performance for all sectors (with caching and batch fetch)."""
        # Check cache first
        cached = _get_cached("sector_performance")
        if cached is not None:
            return cached
        
        # Batch fetch all sector ETFs at once
        symbols = list(SECTOR_ETFS.keys())
        quotes = self._fetch_batch_quotes(symbols)
        
        results = []
        for symbol, info in SECTOR_ETFS.items():
            quote = quotes.get(symbol, {})
            results.append(SectorPerformance(
                symbol=symbol,
                name=info["name"],
                price=quote.get("price", 0),
                change=quote.get("change", 0),
                change_pct=quote.get("changesPercentage", 0),
                volume=quote.get("volume", 0)
            ))
        
        # Sort by change percentage
        results.sort(key=lambda x: x.change_pct, reverse=True)
        
        # Cache results
        _set_cached("sector_performance", results, ttl=30)
        
        return results
    
    def get_index_performance(self) -> List[SectorPerformance]:
        """Get performance for major indices (with caching and batch fetch)."""
        # Check cache first
        cached = _get_cached("index_performance")
        if cached is not None:
            return cached
        
        # Batch fetch all indices at once
        symbols = list(INDEX_ETFS.keys())
        quotes = self._fetch_batch_quotes(symbols)
        
        results = []
        for symbol, name in INDEX_ETFS.items():
            quote = quotes.get(symbol, {})
            results.append(SectorPerformance(
                symbol=symbol,
                name=name,
                price=quote.get("price", 0),
                change=quote.get("change", 0),
                change_pct=quote.get("changesPercentage", 0),
                volume=quote.get("volume", 0)
            ))
        
        # Cache results
        _set_cached("index_performance", results, ttl=30)
        
        return results
    
    def get_sector_performance_period(self, period: str = '1d') -> List[SectorPerformance]:
        """Get sector performance for a specific time period using Yahoo Finance."""
        cache_key = f"sector_performance_{period}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Map period to days
        period_days = {
            '1d': 1, '5d': 5, '1w': 7, '1m': 30, '3m': 90,
            '6m': 180, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
            '1y': 365, '3y': 1095, '5y': 1825
        }
        days = period_days.get(period, 1)
        
        # For 1d, just use regular quote
        if period == '1d':
            return self.get_sector_performance()
        
        # For other periods, fetch historical data
        def fetch_with_history(item):
            symbol, info = item
            try:
                # Get current price
                quotes = self._fetch_batch_quotes([symbol])
                quote = quotes.get(symbol, {})
                current_price = quote.get("price", 0)
                
                if current_price <= 0:
                    return None
                
                # Get historical prices
                hist_prices = self._fetch_historical_prices(symbol, days)
                
                if hist_prices and len(hist_prices) > 0:
                    # Use price from 'days' ago or oldest available
                    idx = min(days, len(hist_prices) - 1)
                    old_price = hist_prices[-(idx+1)] if idx < len(hist_prices) else hist_prices[0]
                    
                    if old_price and old_price > 0:
                        change = current_price - old_price
                        change_pct = ((current_price - old_price) / old_price) * 100
                        
                        return SectorPerformance(
                            symbol=symbol,
                            name=info["name"],
                            price=current_price,
                            change=change,
                            change_pct=change_pct,
                            volume=quote.get("volume", 0)
                        )
            except Exception:
                pass
            return None
        
        results = []
        items = [(s, SECTOR_ETFS[s]) for s in SECTOR_ETFS.keys()]
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_with_history, item) for item in items]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        results.sort(key=lambda x: x.change_pct, reverse=True)
        
        # Longer cache for historical data
        ttl = 30 if period == '1d' else 300
        _set_cached(cache_key, results, ttl=ttl)
        
        return results
    
    def get_index_performance_period(self, period: str = '1d') -> List[SectorPerformance]:
        """Get index performance for a specific time period using Yahoo Finance."""
        cache_key = f"index_performance_{period}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Map period to days
        period_days = {
            '1d': 1, '5d': 5, '1w': 7, '1m': 30, '3m': 90,
            '6m': 180, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
            '1y': 365, '3y': 1095, '5y': 1825
        }
        days = period_days.get(period, 1)
        
        # For 1d, just use regular quote
        if period == '1d':
            return self.get_index_performance()
        
        # For other periods, fetch historical data
        def fetch_with_history(item):
            symbol, name = item
            try:
                # Get current price
                quotes = self._fetch_batch_quotes([symbol])
                quote = quotes.get(symbol, {})
                current_price = quote.get("price", 0)
                
                if current_price <= 0:
                    return None
                
                # Get historical prices
                hist_prices = self._fetch_historical_prices(symbol, days)
                
                if hist_prices and len(hist_prices) > 0:
                    idx = min(days, len(hist_prices) - 1)
                    old_price = hist_prices[-(idx+1)] if idx < len(hist_prices) else hist_prices[0]
                    
                    if old_price and old_price > 0:
                        change = current_price - old_price
                        change_pct = ((current_price - old_price) / old_price) * 100
                        
                        return SectorPerformance(
                            symbol=symbol,
                            name=name,
                            price=current_price,
                            change=change,
                            change_pct=change_pct,
                            volume=quote.get("volume", 0)
                        )
            except Exception:
                pass
            return None
        
        results = []
        items = list(INDEX_ETFS.items())
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch_with_history, item) for item in items]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # Longer cache for historical data
        ttl = 30 if period == '1d' else 300
        _set_cached(cache_key, results, ttl=ttl)
        
        return results
    
    def print_heatmap(self):
        """Print sector heatmap to terminal."""
        sectors = self.get_sector_performance()
        indices = self.get_index_performance()
        
        w = 70
        
        def color_bar(pct: float, width: int = 20) -> str:
            """Generate a color bar for percentage."""
            if pct >= 0:
                filled = min(int(pct * 2), width)
                return "🟩" * filled + "⬜" * (width - filled)
            else:
                filled = min(int(abs(pct) * 2), width)
                return "⬜" * (width - filled) + "🟥" * filled
        
        def pct_color(pct: float) -> str:
            """Get colored percentage string."""
            if pct >= 2:
                return f"[+] {pct:+.2f}%"
            elif pct >= 0.5:
                return f"[+] {pct:+.2f}%"
            elif pct >= 0:
                return f"⚪ {pct:+.2f}%"
            elif pct >= -0.5:
                return f"⚪ {pct:+.2f}%"
            elif pct >= -2:
                return f"[-] {pct:+.2f}%"
            else:
                return f"[-] {pct:+.2f}%"
        
        print()
        print("╔" + "═" * w + "╗")
        print("║" + "MARKET SECTOR HEATMAP".center(w) + "║")
        print("║" + datetime.now().strftime("%Y-%m-%d %H:%M").center(w) + "║")
        print("╠" + "═" * w + "╣")
        
        # Major indices
        print("║" + " MAJOR INDICES".ljust(w) + "║")
        print("╠" + "─" * w + "╣")
        
        for idx in indices:
            line = f"  {idx.name:<20} ${idx.price:>8.2f}  {pct_color(idx.change_pct)}"
            print("║" + line.ljust(w) + "║")
        
        print("╠" + "═" * w + "╣")
        
        # Sectors
        print("║" + " SECTORS (Best to Worst)".ljust(w) + "║")
        print("╠" + "─" * w + "╣")
        
        for sector in sectors:
            name = sector.name[:25]
            line = f"  {name:<25} {pct_color(sector.change_pct):<20}"
            print("║" + line.ljust(w) + "║")
        
        print("╠" + "═" * w + "╣")
        
        # Visual heatmap
        print("║" + " VISUAL HEATMAP".ljust(w) + "║")
        print("╠" + "─" * w + "╣")
        
        # Scale
        print("║" + "  -5%           0%           +5%".center(w) + "║")
        
        for sector in sectors:
            # Create visual bar
            pct = max(-5, min(5, sector.change_pct))
            bar_width = 30
            center = bar_width // 2
            
            if pct >= 0:
                bars = "░" * center + "█" * int(pct / 5 * center) + " " * (center - int(pct / 5 * center))
            else:
                bars = " " * (center + int(pct / 5 * center)) + "█" * (-int(pct / 5 * center)) + "░" * center
            
            symbol = sector.symbol
            line = f"  {symbol:<6} [{bars}] {sector.change_pct:+.2f}%"
            print("║" + line.ljust(w) + "║")
        
        print("╠" + "═" * w + "╣")
        
        # Summary
        gainers = sum(1 for s in sectors if s.change_pct > 0)
        losers = len(sectors) - gainers
        
        if gainers > losers:
            market_status = "[+] RISK-ON (More sectors up)"
        elif losers > gainers:
            market_status = "[-] RISK-OFF (More sectors down)"
        else:
            market_status = "⚪ MIXED (Sectors split)"
        
        print("║" + f"  {market_status}".ljust(w) + "║")
        print("║" + f"  Sectors: {gainers} up, {losers} down".ljust(w) + "║")
        
        print("╚" + "═" * w + "╝")
        print()
    
    def get_sector_stocks(self, sector_etf: str, top_n: int = 5) -> List[str]:
        """Get top holdings of a sector ETF."""
        # This would require additional API calls or data
        # For now, return common stocks per sector
        holdings = {
            "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "ADBE"],
            "XLF": ["BRK.B", "JPM", "V", "MA", "BAC"],
            "XLV": ["UNH", "JNJ", "LLY", "PFE", "ABBV"],
            "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
            "XLP": ["PG", "KO", "PEP", "COST", "WMT"],
            "XLE": ["XOM", "CVX", "COP", "EOG", "SLB"],
            "XLI": ["UNP", "HON", "UPS", "CAT", "BA"],
            "XLB": ["LIN", "APD", "SHW", "ECL", "FCX"],
            "XLRE": ["AMT", "PLD", "CCI", "EQIX", "SPG"],
            "XLU": ["NEE", "DUK", "SO", "D", "AEP"],
            "XLC": ["META", "GOOGL", "GOOG", "NFLX", "DIS"],
        }
        return holdings.get(sector_etf.upper(), [])[:top_n]


# CLI
def main():
    sh = SectorHeatmap()
    sh.print_heatmap()


if __name__ == "__main__":
    main()
