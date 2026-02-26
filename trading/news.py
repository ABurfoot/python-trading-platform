#!/usr/bin/env python3
"""
News Integration
================
Fetch recent news for stocks from multiple sources.

Sources:
- Finnhub (free tier: 60 req/min)
- Alpha Vantage News (with API key)
- Yahoo Finance News (no API key)

Usage:
    from trading.news import NewsManager
    
    nm = NewsManager()
    news = nm.get_news("AAPL", limit=10)
"""

import os
import json
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

ssl._create_default_https_context = ssl._create_unverified_context


# Simple cache for news
_news_cache = {}
_cache_ttl = {}
_CACHE_DURATION = 300  # 5 minute cache for news


def _get_cached(key: str) -> Optional[any]:
    """Get cached value if not expired."""
    if key in _news_cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _news_cache[key]
        else:
            del _news_cache[key]
            del _cache_ttl[key]
    return None


def _set_cached(key: str, value: any, ttl: int = None):
    """Set cached value with TTL."""
    _news_cache[key] = value
    _cache_ttl[key] = time.time() + (ttl or _CACHE_DURATION)


@dataclass
class NewsItem:
    """Single news article."""
    headline: str
    summary: str
    source: str
    url: str
    published: str
    symbol: str
    sentiment: str = "neutral"  # positive, negative, neutral
    
    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "source": self.source,
            "url": self.url,
            "published": self.published,
            "symbol": self.symbol,
            "sentiment": self.sentiment
        }


class FinnhubNews:
    """Finnhub news API."""
    
    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "")
        self.base_url = "https://finnhub.io/api/v1"
        self.available = bool(self.api_key)
    
    def get_news(self, symbol: str, days: int = 7) -> List[NewsItem]:
        """Get company news from Finnhub."""
        if not self.available:
            return []
        
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            
            url = (f"{self.base_url}/company-news?"
                   f"symbol={symbol}&"
                   f"from={start.strftime('%Y-%m-%d')}&"
                   f"to={end.strftime('%Y-%m-%d')}&"
                   f"token={self.api_key}")
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            
            news = []
            for item in data[:20]:
                # Simple sentiment from headline
                headline = item.get("headline", "")
                sentiment = self._analyze_sentiment(headline)
                
                news.append(NewsItem(
                    headline=headline,
                    summary=item.get("summary", "")[:200],
                    source=item.get("source", "Unknown"),
                    url=item.get("url", ""),
                    published=datetime.fromtimestamp(item.get("datetime", 0)).isoformat(),
                    symbol=symbol,
                    sentiment=sentiment
                ))
            
            return news
            
        except Exception as e:
            return []
    
    def _analyze_sentiment(self, text: str) -> str:
        """Simple keyword-based sentiment analysis."""
        text = text.lower()
        
        positive = ["surge", "soar", "jump", "rally", "gain", "rise", "up", "high", 
                   "beat", "exceed", "profit", "growth", "bullish", "buy", "upgrade"]
        negative = ["fall", "drop", "plunge", "crash", "decline", "down", "low",
                   "miss", "loss", "cut", "bearish", "sell", "downgrade", "warning"]
        
        pos_count = sum(1 for word in positive if word in text)
        neg_count = sum(1 for word in negative if word in text)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"


class AlphaVantageNews:
    """Alpha Vantage news API."""
    
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY", "")
        self.base_url = "https://www.alphavantage.co/query"
        self.available = bool(self.api_key)
    
    def get_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """Get news and sentiment from Alpha Vantage."""
        if not self.available:
            return []
        
        try:
            url = (f"{self.base_url}?function=NEWS_SENTIMENT&"
                   f"tickers={symbol}&"
                   f"limit={limit}&"
                   f"apikey={self.api_key}")
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            
            if "feed" not in data:
                return []
            
            news = []
            for item in data["feed"][:limit]:
                # Get sentiment from API
                sentiment_score = item.get("overall_sentiment_score", 0)
                if sentiment_score > 0.15:
                    sentiment = "positive"
                elif sentiment_score < -0.15:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"
                
                news.append(NewsItem(
                    headline=item.get("title", ""),
                    summary=item.get("summary", "")[:200],
                    source=item.get("source", "Unknown"),
                    url=item.get("url", ""),
                    published=item.get("time_published", ""),
                    symbol=symbol,
                    sentiment=sentiment
                ))
            
            return news
            
        except Exception:
            return []


class YahooNews:
    """Yahoo Finance news scraper (no API key needed)."""
    
    def __init__(self):
        self.available = True
    
    def get_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """Get news from Yahoo Finance."""
        try:
            import urllib.parse
            encoded_symbol = urllib.parse.quote(symbol)
            
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={encoded_symbol}&newsCount={limit}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            
            news = []
            for item in data.get("news", [])[:limit]:
                news.append(NewsItem(
                    headline=item.get("title", ""),
                    summary="",
                    source=item.get("publisher", "Yahoo Finance"),
                    url=item.get("link", ""),
                    published=datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat(),
                    symbol=symbol,
                    sentiment="neutral"
                ))
            
            return news
            
        except Exception:
            return []


class NewsManager:
    """Aggregate news from multiple sources."""
    
    def __init__(self):
        self.finnhub = FinnhubNews()
        self.alphavantage = AlphaVantageNews()
        self.yahoo = YahooNews()
    
    def get_news(self, symbol: str, limit: int = 10, days: int = 7) -> List[NewsItem]:
        """
        Get news from all available sources (with caching and parallel fetch).
        
        Args:
            symbol: Stock symbol
            limit: Maximum number of articles
            days: Number of days to look back
        
        Returns:
            List of NewsItem, sorted by date (newest first)
        """
        original_symbol = symbol.upper().strip().replace(" ", "")
        symbol = original_symbol.replace(":", "")
        # Remove exchange prefix if present
        if len(symbol) > 5 and symbol[3] == ":":
            symbol = symbol[4:]
        
        # Check cache
        cache_key = f"news_{symbol}_{limit}_{days}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached
        
        all_news = []
        
        # Fetch from all sources in parallel
        def fetch_alphavantage():
            if self.alphavantage.available:
                return self.alphavantage.get_news(symbol, limit)
            return []
        
        def fetch_finnhub():
            if self.finnhub.available:
                return self.finnhub.get_news(symbol, days)
            return []
        
        def fetch_yahoo():
            return self.yahoo.get_news(symbol, limit)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(fetch_alphavantage),
                executor.submit(fetch_finnhub),
                executor.submit(fetch_yahoo)
            ]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    all_news.extend(result)
                except Exception:
                    pass
        
        # Remove duplicates by headline
        seen = set()
        unique_news = []
        for item in all_news:
            headline_key = item.headline[:50].lower()
            if headline_key not in seen:
                seen.add(headline_key)
                unique_news.append(item)
        
        # Sort by date (newest first)
        unique_news.sort(key=lambda x: x.published, reverse=True)
        
        result = unique_news[:limit]
        
        # Cache results
        _set_cached(cache_key, result)
        
        return result
    
    def get_sentiment_summary(self, news: List[NewsItem]) -> Dict:
        """Get sentiment summary from news list."""
        if not news:
            return {"positive": 0, "negative": 0, "neutral": 0, "overall": "neutral"}
        
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for item in news:
            counts[item.sentiment] = counts.get(item.sentiment, 0) + 1
        
        total = len(news)
        pos_pct = counts["positive"] / total * 100
        neg_pct = counts["negative"] / total * 100
        
        if pos_pct > neg_pct + 20:
            overall = "bullish"
        elif neg_pct > pos_pct + 20:
            overall = "bearish"
        else:
            overall = "neutral"
        
        return {
            "positive": counts["positive"],
            "negative": counts["negative"],
            "neutral": counts["neutral"],
            "positive_pct": pos_pct,
            "negative_pct": neg_pct,
            "overall": overall
        }


def print_news(symbol: str, limit: int = 10):
    """Print news for a stock."""
    nm = NewsManager()
    news = nm.get_news(symbol, limit)
    sentiment = nm.get_sentiment_summary(news)
    
    print(f"\n📰 News for {symbol.upper()}")
    print(f"   Sentiment: {sentiment['overall'].upper()} "
          f"(👍 {sentiment['positive']} | 👎 {sentiment['negative']} | ➖ {sentiment['neutral']})")
    print("=" * 70)
    
    if not news:
        print("  No news found")
        return
    
    for item in news:
        # Sentiment icon
        icon = "[+]" if item.sentiment == "positive" else "[-]" if item.sentiment == "negative" else "[.]"
        
        # Format date
        try:
            dt = datetime.fromisoformat(item.published.replace("Z", "+00:00"))
            date_str = dt.strftime("%b %d")
        except Exception:
            date_str = ""
        
        # Print headline
        headline = item.headline[:65] + "..." if len(item.headline) > 65 else item.headline
        print(f"\n  {icon} {headline}")
        print(f"     {item.source} • {date_str}")
        if item.summary:
            summary = item.summary[:100] + "..." if len(item.summary) > 100 else item.summary
            print(f"     {summary}")
    
    print()


# CLI
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Stock News")
    parser.add_argument("symbol", help="Stock symbol")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Number of articles")
    
    args = parser.parse_args()
    print_news(args.symbol, args.limit)


if __name__ == "__main__":
    main()
