#!/usr/bin/env python3
"""
Cryptocurrency Module
======================
Track cryptocurrencies with real-time prices, market data, and analysis.

Features:
- Real-time prices for major cryptocurrencies
- Market cap, volume, and dominance data
- Fear & Greed Index
- Correlation with traditional markets
- Historical price data
- Portfolio tracking for crypto holdings
- DeFi metrics (when available)

Supported Cryptocurrencies:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP 20           STABLECOINS      DEFI            LAYER 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bitcoin (BTC)    USDT             AAVE            Polygon (MATIC)
Ethereum (ETH)   USDC             UNI             Arbitrum (ARB)
BNB              DAI              LINK            Optimism (OP)
Solana (SOL)                      MKR
XRP                               CRV
Cardano (ADA)
Dogecoin (DOGE)
Avalanche (AVAX)
Polkadot (DOT)
Litecoin (LTC)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Data Sources:
- CoinGecko API (free, no key required)
- CoinMarketCap API (optional, for additional data)
- Messari API (optional, for on-chain metrics)

Usage:
    from trading.crypto import CryptoTracker
    
    ct = CryptoTracker()
    
    # Get all top coins
    coins = ct.get_top_coins(limit=20)
    
    # Get specific coin
    btc = ct.get_coin("BTC")
    
    # Print dashboard
    ct.print_dashboard()
    
    # Get market overview
    overview = ct.get_market_overview()
"""

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum


class CoinCategory(Enum):
    """Cryptocurrency categories."""
    LAYER1 = "layer1"
    LAYER2 = "layer2"
    DEFI = "defi"
    STABLECOIN = "stablecoin"
    MEME = "meme"
    EXCHANGE = "exchange"
    GAMING = "gaming"
    NFT = "nft"
    OTHER = "other"


@dataclass
class CoinInfo:
    """Static information about a cryptocurrency."""
    symbol: str
    name: str
    coingecko_id: str
    category: str
    description: str = ""
    website: str = ""
    max_supply: Optional[float] = None


@dataclass 
class CoinQuote:
    """Real-time quote for a cryptocurrency."""
    symbol: str
    name: str
    price: float
    change_1h: float = 0
    change_24h: float = 0
    change_7d: float = 0
    change_30d: float = 0
    market_cap: float = 0
    volume_24h: float = 0
    circulating_supply: float = 0
    total_supply: float = 0
    max_supply: Optional[float] = None
    ath: float = 0  # All-time high
    ath_date: str = ""
    ath_change_pct: float = 0
    atl: float = 0  # All-time low
    rank: int = 0
    last_updated: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @property
    def is_positive_24h(self) -> bool:
        return self.change_24h >= 0
    
    @property
    def formatted_market_cap(self) -> str:
        if self.market_cap >= 1e12:
            return f"${self.market_cap/1e12:.2f}T"
        elif self.market_cap >= 1e9:
            return f"${self.market_cap/1e9:.2f}B"
        elif self.market_cap >= 1e6:
            return f"${self.market_cap/1e6:.2f}M"
        else:
            return f"${self.market_cap:,.0f}"
    
    @property
    def formatted_volume(self) -> str:
        if self.volume_24h >= 1e9:
            return f"${self.volume_24h/1e9:.2f}B"
        elif self.volume_24h >= 1e6:
            return f"${self.volume_24h/1e6:.2f}M"
        else:
            return f"${self.volume_24h:,.0f}"


@dataclass
class MarketOverview:
    """Overall crypto market data."""
    total_market_cap: float
    total_volume_24h: float
    btc_dominance: float
    eth_dominance: float
    market_cap_change_24h: float
    active_cryptocurrencies: int
    markets: int
    last_updated: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FearGreedIndex:
    """Crypto Fear & Greed Index."""
    value: int  # 0-100
    classification: str  # Extreme Fear, Fear, Neutral, Greed, Extreme Greed
    timestamp: str
    
    @property
    def emoji(self) -> str:
        if self.value <= 20:
            return "😱"  # Extreme Fear
        elif self.value <= 40:
            return "😰"  # Fear
        elif self.value <= 60:
            return "😐"  # Neutral
        elif self.value <= 80:
            return "😀"  # Greed
        else:
            return "🤑"  # Extreme Greed


# =============================================================================
# COIN DEFINITIONS
# =============================================================================

COINS = {
    # Major coins
    "BTC": CoinInfo("BTC", "Bitcoin", "bitcoin", "layer1", 
                    "The original cryptocurrency", "https://bitcoin.org", 21000000),
    "ETH": CoinInfo("ETH", "Ethereum", "ethereum", "layer1",
                    "Smart contract platform", "https://ethereum.org"),
    "BNB": CoinInfo("BNB", "BNB", "binancecoin", "exchange",
                    "Binance ecosystem token", "https://bnbchain.org"),
    "SOL": CoinInfo("SOL", "Solana", "solana", "layer1",
                    "High-performance blockchain", "https://solana.com"),
    "XRP": CoinInfo("XRP", "XRP", "ripple", "layer1",
                    "Payment protocol", "https://ripple.com"),
    "ADA": CoinInfo("ADA", "Cardano", "cardano", "layer1",
                    "Proof-of-stake blockchain", "https://cardano.org"),
    "DOGE": CoinInfo("DOGE", "Dogecoin", "dogecoin", "meme",
                     "The original meme coin", "https://dogecoin.com"),
    "AVAX": CoinInfo("AVAX", "Avalanche", "avalanche-2", "layer1",
                     "Fast smart contracts", "https://avax.network"),
    "DOT": CoinInfo("DOT", "Polkadot", "polkadot", "layer1",
                    "Multi-chain protocol", "https://polkadot.network"),
    "LTC": CoinInfo("LTC", "Litecoin", "litecoin", "layer1",
                    "Silver to Bitcoin's gold", "https://litecoin.org", 84000000),
    "SHIB": CoinInfo("SHIB", "Shiba Inu", "shiba-inu", "meme",
                     "Dogecoin competitor"),
    "TRX": CoinInfo("TRX", "TRON", "tron", "layer1",
                    "Entertainment blockchain"),
    "ATOM": CoinInfo("ATOM", "Cosmos", "cosmos", "layer1",
                     "Internet of blockchains", "https://cosmos.network"),
    "LINK": CoinInfo("LINK", "Chainlink", "chainlink", "defi",
                     "Decentralized oracle network", "https://chain.link"),
    "UNI": CoinInfo("UNI", "Uniswap", "uniswap", "defi",
                    "Decentralized exchange", "https://uniswap.org"),
    "XLM": CoinInfo("XLM", "Stellar", "stellar", "layer1",
                    "Cross-border payments"),
    "NEAR": CoinInfo("NEAR", "NEAR Protocol", "near", "layer1",
                     "Scalable blockchain"),
    "APT": CoinInfo("APT", "Aptos", "aptos", "layer1",
                    "Move-based blockchain"),
    "ARB": CoinInfo("ARB", "Arbitrum", "arbitrum", "layer2",
                    "Ethereum L2 scaling"),
    "OP": CoinInfo("OP", "Optimism", "optimism", "layer2",
                   "Ethereum L2 scaling"),
    
    # Layer 2
    "MATIC": CoinInfo("MATIC", "Polygon", "matic-network", "layer2",
                      "Ethereum scaling", "https://polygon.technology"),
    
    # DeFi
    "AAVE": CoinInfo("AAVE", "Aave", "aave", "defi",
                     "Lending protocol", "https://aave.com"),
    "MKR": CoinInfo("MKR", "Maker", "maker", "defi",
                    "DAI stablecoin governance"),
    "CRV": CoinInfo("CRV", "Curve", "curve-dao-token", "defi",
                    "Stablecoin DEX"),
    "LDO": CoinInfo("LDO", "Lido DAO", "lido-dao", "defi",
                    "Liquid staking"),
    
    # Stablecoins
    "USDT": CoinInfo("USDT", "Tether", "tether", "stablecoin",
                     "USD-pegged stablecoin"),
    "USDC": CoinInfo("USDC", "USD Coin", "usd-coin", "stablecoin",
                     "USD-backed stablecoin"),
    "DAI": CoinInfo("DAI", "Dai", "dai", "stablecoin",
                    "Decentralized stablecoin"),
    
    # Other notable
    "FIL": CoinInfo("FIL", "Filecoin", "filecoin", "other",
                    "Decentralized storage"),
    "ICP": CoinInfo("ICP", "Internet Computer", "internet-computer", "layer1",
                    "World computer"),
    "HBAR": CoinInfo("HBAR", "Hedera", "hedera-hashgraph", "layer1",
                     "Enterprise blockchain"),
    "VET": CoinInfo("VET", "VeChain", "vechain", "layer1",
                    "Supply chain blockchain"),
    "INJ": CoinInfo("INJ", "Injective", "injective-protocol", "defi",
                    "DeFi derivatives"),
    "RENDER": CoinInfo("RENDER", "Render", "render-token", "other",
                       "Distributed GPU rendering"),
    "FET": CoinInfo("FET", "Fetch.ai", "fetch-ai", "other",
                    "AI blockchain"),
}

# Top coins by market cap (for quick access)
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
             "LINK", "LTC", "SHIB", "TRX", "ATOM", "UNI", "XLM", "NEAR", "APT", "ARB"]


class CryptoTracker:
    """
    Cryptocurrency tracker with real-time data from multiple sources.
    """
    
    def __init__(self, cache_minutes: int = 2):
        self.cache_minutes = cache_minutes
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        
        # API keys (optional)
        self.cmc_key = os.environ.get("COINMARKETCAP_API_KEY", "")
        self.messari_key = os.environ.get("MESSARI_API_KEY", "")
        
        # CoinGecko base URL (free, no key needed)
        self.coingecko_url = "https://api.coingecko.com/api/v3"
    
    def _request(self, url: str, headers: Dict = None, timeout: int = 15) -> Optional[Dict]:
        """Make HTTP request."""
        try:
            default_headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
            if headers:
                default_headers.update(headers)
            
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(minutes=self.cache_minutes):
                return data
        return None
    
    def _set_cached(self, key: str, data: Any):
        """Cache data."""
        self._cache[key] = (data, datetime.now())
    
    # =========================================================================
    # COINGECKO DATA FETCHING
    # =========================================================================
    
    def _fetch_coingecko_prices(self, coin_ids: List[str]) -> Dict:
        """Fetch prices from CoinGecko."""
        ids_str = ",".join(coin_ids)
        url = (f"{self.coingecko_url}/simple/price?ids={ids_str}"
               f"&vs_currencies=usd"
               f"&include_market_cap=true"
               f"&include_24hr_vol=true"
               f"&include_24hr_change=true"
               f"&include_last_updated_at=true")
        
        return self._request(url) or {}
    
    def _fetch_coingecko_coin(self, coin_id: str) -> Optional[Dict]:
        """Fetch detailed coin data from CoinGecko."""
        url = (f"{self.coingecko_url}/coins/{coin_id}"
               f"?localization=false"
               f"&tickers=false"
               f"&community_data=false"
               f"&developer_data=false")
        
        return self._request(url)
    
    def _fetch_coingecko_markets(self, limit: int = 100) -> List[Dict]:
        """Fetch market data from CoinGecko."""
        url = (f"{self.coingecko_url}/coins/markets"
               f"?vs_currency=usd"
               f"&order=market_cap_desc"
               f"&per_page={limit}"
               f"&page=1"
               f"&sparkline=false"
               f"&price_change_percentage=1h,24h,7d,30d")
        
        return self._request(url) or []
    
    def _fetch_coingecko_global(self) -> Optional[Dict]:
        """Fetch global market data."""
        url = f"{self.coingecko_url}/global"
        return self._request(url)
    
    def _fetch_fear_greed(self) -> Optional[Dict]:
        """Fetch Fear & Greed Index from alternative.me."""
        url = "https://api.alternative.me/fng/?limit=1"
        return self._request(url)
    
    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================
    
    def get_coin(self, symbol: str, use_cache: bool = True) -> Optional[CoinQuote]:
        """
        Get quote for a specific cryptocurrency.
        
        Args:
            symbol: Coin symbol (BTC, ETH, etc.)
            use_cache: Whether to use cached data
        
        Returns:
            CoinQuote object or None
        """
        symbol = symbol.upper()
        
        # Check cache
        cache_key = f"coin_{symbol}"
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # Get coin info
        if symbol not in COINS:
            # Try to find by name
            for sym, info in COINS.items():
                if symbol.lower() == info.name.lower():
                    symbol = sym
                    break
            else:
                return None
        
        coin_info = COINS[symbol]
        
        # Fetch from CoinGecko
        data = self._fetch_coingecko_coin(coin_info.coingecko_id)
        
        if not data:
            return None
        
        market_data = data.get("market_data", {})
        
        quote = CoinQuote(
            symbol=symbol,
            name=coin_info.name,
            price=market_data.get("current_price", {}).get("usd", 0),
            change_1h=market_data.get("price_change_percentage_1h_in_currency", {}).get("usd", 0) or 0,
            change_24h=market_data.get("price_change_percentage_24h", 0) or 0,
            change_7d=market_data.get("price_change_percentage_7d", 0) or 0,
            change_30d=market_data.get("price_change_percentage_30d", 0) or 0,
            market_cap=market_data.get("market_cap", {}).get("usd", 0),
            volume_24h=market_data.get("total_volume", {}).get("usd", 0),
            circulating_supply=market_data.get("circulating_supply", 0) or 0,
            total_supply=market_data.get("total_supply", 0) or 0,
            max_supply=market_data.get("max_supply"),
            ath=market_data.get("ath", {}).get("usd", 0),
            ath_date=market_data.get("ath_date", {}).get("usd", ""),
            ath_change_pct=market_data.get("ath_change_percentage", {}).get("usd", 0) or 0,
            atl=market_data.get("atl", {}).get("usd", 0),
            rank=data.get("market_cap_rank", 0) or 0,
            last_updated=data.get("last_updated", ""),
        )
        
        self._set_cached(cache_key, quote)
        return quote
    
    def get_top_coins(self, limit: int = 20, use_cache: bool = True) -> List[CoinQuote]:
        """
        Get top cryptocurrencies by market cap.
        
        Args:
            limit: Number of coins to return (max 100)
            use_cache: Whether to use cached data
        
        Returns:
            List of CoinQuote objects
        """
        cache_key = f"top_coins_{limit}"
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        data = self._fetch_coingecko_markets(limit)
        
        if not data:
            return []
        
        quotes = []
        for coin in data:
            # Find symbol from our definitions or use the one from API
            symbol = coin.get("symbol", "").upper()
            name = coin.get("name", "")
            
            quote = CoinQuote(
                symbol=symbol,
                name=name,
                price=coin.get("current_price", 0) or 0,
                change_1h=coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                change_24h=coin.get("price_change_percentage_24h", 0) or 0,
                change_7d=coin.get("price_change_percentage_7d_in_currency", 0) or 0,
                change_30d=coin.get("price_change_percentage_30d_in_currency", 0) or 0,
                market_cap=coin.get("market_cap", 0) or 0,
                volume_24h=coin.get("total_volume", 0) or 0,
                circulating_supply=coin.get("circulating_supply", 0) or 0,
                total_supply=coin.get("total_supply", 0) or 0,
                max_supply=coin.get("max_supply"),
                ath=coin.get("ath", 0) or 0,
                ath_date=coin.get("ath_date", ""),
                ath_change_pct=coin.get("ath_change_percentage", 0) or 0,
                atl=coin.get("atl", 0) or 0,
                rank=coin.get("market_cap_rank", 0) or 0,
                last_updated=coin.get("last_updated", ""),
            )
            quotes.append(quote)
        
        self._set_cached(cache_key, quotes)
        return quotes
    
    def get_market_overview(self, use_cache: bool = True) -> Optional[MarketOverview]:
        """
        Get overall crypto market data.
        
        Returns:
            MarketOverview object
        """
        cache_key = "market_overview"
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        data = self._fetch_coingecko_global()
        
        if not data or "data" not in data:
            return None
        
        d = data["data"]
        
        overview = MarketOverview(
            total_market_cap=d.get("total_market_cap", {}).get("usd", 0),
            total_volume_24h=d.get("total_volume", {}).get("usd", 0),
            btc_dominance=d.get("market_cap_percentage", {}).get("btc", 0),
            eth_dominance=d.get("market_cap_percentage", {}).get("eth", 0),
            market_cap_change_24h=d.get("market_cap_change_percentage_24h_usd", 0),
            active_cryptocurrencies=d.get("active_cryptocurrencies", 0),
            markets=d.get("markets", 0),
            last_updated=datetime.fromtimestamp(d.get("updated_at", 0)).isoformat() if d.get("updated_at") else "",
        )
        
        self._set_cached(cache_key, overview)
        return overview
    
    def get_fear_greed_index(self, use_cache: bool = True) -> Optional[FearGreedIndex]:
        """
        Get the Crypto Fear & Greed Index.
        
        Returns:
            FearGreedIndex object
        """
        cache_key = "fear_greed"
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        data = self._fetch_fear_greed()
        
        if not data or "data" not in data or not data["data"]:
            return None
        
        fg_data = data["data"][0]
        
        index = FearGreedIndex(
            value=int(fg_data.get("value", 50)),
            classification=fg_data.get("value_classification", "Neutral"),
            timestamp=fg_data.get("timestamp", ""),
        )
        
        self._set_cached(cache_key, index)
        return index
    
    def get_coins_by_category(self, category: str, use_cache: bool = True) -> List[CoinQuote]:
        """
        Get coins filtered by category.
        
        Args:
            category: layer1, layer2, defi, stablecoin, meme, exchange
        """
        category = category.lower()
        
        # Get all coins we track in this category
        symbols = [sym for sym, info in COINS.items() if info.category == category]
        
        # Get quotes for each
        quotes = []
        for symbol in symbols:
            quote = self.get_coin(symbol, use_cache)
            if quote:
                quotes.append(quote)
        
        # Sort by market cap
        quotes.sort(key=lambda q: q.market_cap, reverse=True)
        return quotes
    
    def get_gainers_losers(self, limit: int = 5, use_cache: bool = True) -> Dict[str, List[CoinQuote]]:
        """
        Get top gainers and losers in last 24h.
        
        Returns:
            Dict with 'gainers' and 'losers' lists
        """
        coins = self.get_top_coins(50, use_cache)
        
        # Sort by 24h change
        sorted_coins = sorted(coins, key=lambda c: c.change_24h, reverse=True)
        
        gainers = sorted_coins[:limit]
        losers = sorted_coins[-limit:][::-1]
        
        return {
            "gainers": gainers,
            "losers": losers,
        }
    
    def get_historical_prices(self, symbol: str, days: int = 30) -> List[Dict]:
        """
        Get historical price data.
        
        Args:
            symbol: Coin symbol
            days: Number of days of history
        
        Returns:
            List of {date, price, volume, market_cap}
        """
        symbol = symbol.upper()
        
        if symbol not in COINS:
            return []
        
        coin_id = COINS[symbol].coingecko_id
        
        url = (f"{self.coingecko_url}/coins/{coin_id}/market_chart"
               f"?vs_currency=usd&days={days}")
        
        data = self._request(url)
        
        if not data:
            return []
        
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        market_caps = data.get("market_caps", [])
        
        history = []
        for i, (timestamp, price) in enumerate(prices):
            history.append({
                "date": datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d"),
                "timestamp": timestamp,
                "price": price,
                "volume": volumes[i][1] if i < len(volumes) else 0,
                "market_cap": market_caps[i][1] if i < len(market_caps) else 0,
            })
        
        return history
    
    def compare_to_stocks(self, symbol: str = "BTC") -> Dict:
        """
        Compare crypto performance to stock indices.
        
        Note: Requires stock data module
        """
        # Get crypto data
        crypto = self.get_coin(symbol)
        
        if not crypto:
            return {}
        
        result = {
            "crypto": {
                "symbol": symbol,
                "price": crypto.price,
                "change_24h": crypto.change_24h,
                "change_7d": crypto.change_7d,
                "change_30d": crypto.change_30d,
            },
            "stocks": {},
            "correlation": None,
        }
        
        # Try to get stock index data
        try:
            from trading.global_indices import GlobalIndices
            gi = GlobalIndices()
            
            for idx_symbol in ["SPX", "IXIC"]:
                quote = gi.get_index(idx_symbol)
                if quote:
                    result["stocks"][idx_symbol] = {
                        "name": quote.name,
                        "price": quote.price,
                        "change_pct": quote.change_pct,
                    }
        except ImportError:
            pass
        
        return result
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_dashboard(self, limit: int = 15):
        """Print a formatted crypto dashboard."""
        # Get data
        overview = self.get_market_overview()
        fear_greed = self.get_fear_greed_index()
        coins = self.get_top_coins(limit)
        
        print(f"\n{'='*85}")
        print("🪙 CRYPTOCURRENCY MARKETS")
        print(f"   Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*85}")
        
        # Market overview
        if overview:
            print(f"\n MARKET OVERVIEW")
            print("-"*85)
            
            total_cap = overview.total_market_cap
            if total_cap >= 1e12:
                cap_str = f"${total_cap/1e12:.2f}T"
            else:
                cap_str = f"${total_cap/1e9:.2f}B"
            
            vol = overview.total_volume_24h
            vol_str = f"${vol/1e9:.2f}B" if vol >= 1e9 else f"${vol/1e6:.2f}M"
            
            change_emoji = "" if overview.market_cap_change_24h >= 0 else ""
            
            print(f"   Total Market Cap: {cap_str} {change_emoji} {overview.market_cap_change_24h:+.2f}%")
            print(f"   24h Volume:       {vol_str}")
            print(f"   BTC Dominance:    {overview.btc_dominance:.1f}%")
            print(f"   ETH Dominance:    {overview.eth_dominance:.1f}%")
        
        # Fear & Greed
        if fear_greed:
            print(f"\n🎭 FEAR & GREED INDEX")
            print("-"*85)
            
            # Create visual bar
            bar_length = 30
            filled = int(fear_greed.value / 100 * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"   {fear_greed.emoji} {fear_greed.value}/100 - {fear_greed.classification}")
            print(f"   [Fear {bar} Greed]")
        
        # Top coins
        if coins:
            print(f"\n TOP {limit} CRYPTOCURRENCIES")
            print("-"*85)
            print(f"   {'#':<3} {'Symbol':<8} {'Price':>12} {'24h':>10} {'7d':>10} {'Market Cap':>14} {'Volume':>12}")
            print(f"   {'-'*79}")
            
            for coin in coins:
                # Format price based on value
                if coin.price >= 1000:
                    price_str = f"${coin.price:,.0f}"
                elif coin.price >= 1:
                    price_str = f"${coin.price:,.2f}"
                elif coin.price >= 0.01:
                    price_str = f"${coin.price:.4f}"
                else:
                    price_str = f"${coin.price:.6f}"
                
                # Color indicators
                change_24h = f"{coin.change_24h:+.2f}%"
                change_7d = f"{coin.change_7d:+.2f}%"
                
                print(f"   {coin.rank:<3} {coin.symbol:<8} {price_str:>12} {change_24h:>10} {change_7d:>10} {coin.formatted_market_cap:>14} {coin.formatted_volume:>12}")
        
        print(f"\n{'='*85}")
        print("   Legend: Green (+) = Gaining | Red (-) = Losing")
        print(f"{'='*85}\n")
    
    def print_coin(self, symbol: str):
        """Print detailed information about a coin."""
        coin = self.get_coin(symbol)
        
        if not coin:
            print(f"Coin not found: {symbol}")
            return
        
        info = COINS.get(symbol.upper())
        
        print(f"\n{'='*60}")
        print(f"🪙 {coin.name} ({coin.symbol})")
        print(f"{'='*60}")
        
        # Price info
        print(f"\n💵 PRICE")
        print("-"*40)
        
        if coin.price >= 1:
            print(f"   Current:     ${coin.price:,.2f}")
        else:
            print(f"   Current:     ${coin.price:.6f}")
        
        print(f"   1h Change:   {coin.change_1h:+.2f}%")
        print(f"   24h Change:  {coin.change_24h:+.2f}%")
        print(f"   7d Change:   {coin.change_7d:+.2f}%")
        print(f"   30d Change:  {coin.change_30d:+.2f}%")
        
        # ATH info
        print(f"\n ALL-TIME HIGH")
        print("-"*40)
        print(f"   ATH:         ${coin.ath:,.2f}")
        print(f"   From ATH:    {coin.ath_change_pct:.2f}%")
        if coin.ath_date:
            print(f"   Date:        {coin.ath_date[:10]}")
        
        # Market info
        print(f"\n MARKET DATA")
        print("-"*40)
        print(f"   Rank:        #{coin.rank}")
        print(f"   Market Cap:  {coin.formatted_market_cap}")
        print(f"   24h Volume:  {coin.formatted_volume}")
        
        # Supply info
        print(f"\n🔢 SUPPLY")
        print("-"*40)
        print(f"   Circulating: {coin.circulating_supply:,.0f}")
        if coin.total_supply:
            print(f"   Total:       {coin.total_supply:,.0f}")
        if coin.max_supply:
            print(f"   Max:         {coin.max_supply:,.0f}")
            pct_mined = (coin.circulating_supply / coin.max_supply) * 100
            print(f"   % Mined:     {pct_mined:.1f}%")
        
        # Category and description
        if info:
            print(f"\n📝 INFO")
            print("-"*40)
            print(f"   Category:    {info.category}")
            if info.description:
                print(f"   Description: {info.description}")
            if info.website:
                print(f"   Website:     {info.website}")
        
        print(f"\n{'='*60}\n")
    
    def print_gainers_losers(self):
        """Print top gainers and losers."""
        data = self.get_gainers_losers(limit=7)
        
        print(f"\n{'='*60}")
        print(" TOP GAINERS (24h)")
        print("-"*60)
        
        for coin in data["gainers"]:
            print(f"   {coin.symbol:<8} ${coin.price:>12,.2f}  {coin.change_24h:>+8.2f}%")
        
        print(f"\n TOP LOSERS (24h)")
        print("-"*60)
        
        for coin in data["losers"]:
            print(f"   {coin.symbol:<8} ${coin.price:>12,.2f}  {coin.change_24h:>+8.2f}%")
        
        print(f"{'='*60}\n")
    
    def print_category(self, category: str):
        """Print coins in a specific category."""
        coins = self.get_coins_by_category(category)
        
        if not coins:
            print(f"No coins found in category: {category}")
            return
        
        category_names = {
            "layer1": "🔷 LAYER 1 BLOCKCHAINS",
            "layer2": "🔶 LAYER 2 SCALING",
            "defi": "🏦 DEFI PROTOCOLS",
            "stablecoin": "💵 STABLECOINS",
            "meme": "🐕 MEME COINS",
            "exchange": "🏛️ EXCHANGE TOKENS",
        }
        
        print(f"\n{'='*70}")
        print(category_names.get(category, category.upper()))
        print(f"{'='*70}")
        print(f"   {'Symbol':<8} {'Name':<15} {'Price':>12} {'24h':>10} {'Market Cap':>14}")
        print(f"   {'-'*60}")
        
        for coin in coins:
            if coin.price >= 1:
                price_str = f"${coin.price:,.2f}"
            else:
                price_str = f"${coin.price:.4f}"
            
            print(f"   {coin.symbol:<8} {coin.name:<15} {price_str:>12} {coin.change_24h:>+9.2f}% {coin.formatted_market_cap:>14}")
        
        print(f"{'='*70}\n")
    
    def list_coins(self) -> List[Dict]:
        """List all supported coins."""
        return [
            {
                "symbol": sym,
                "name": info.name,
                "category": info.category,
                "coingecko_id": info.coingecko_id,
            }
            for sym, info in COINS.items()
        ]


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Cryptocurrency Tracker")
    parser.add_argument("--top", "-t", type=int, default=15, help="Number of top coins to show")
    parser.add_argument("--coin", "-c", help="Show specific coin (e.g., BTC, ETH)")
    parser.add_argument("--category", help="Filter by category (layer1, defi, stablecoin, meme)")
    parser.add_argument("--movers", "-m", action="store_true", help="Show gainers/losers")
    parser.add_argument("--list", "-l", action="store_true", help="List all supported coins")
    parser.add_argument("--history", help="Show price history for coin")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days of history")
    
    args = parser.parse_args()
    ct = CryptoTracker()
    
    if args.list:
        print(f"\n{'='*60}")
        print("SUPPORTED CRYPTOCURRENCIES")
        print(f"{'='*60}")
        
        coins = ct.list_coins()
        categories = {}
        for coin in coins:
            cat = coin["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(coin)
        
        for cat, cat_coins in sorted(categories.items()):
            print(f"\n{cat.upper()}:")
            for coin in cat_coins:
                print(f"   {coin['symbol']:<8} {coin['name']}")
        print()
    
    elif args.coin:
        ct.print_coin(args.coin)
    
    elif args.category:
        ct.print_category(args.category)
    
    elif args.movers:
        ct.print_gainers_losers()
    
    elif args.history:
        history = ct.get_historical_prices(args.history, args.days)
        if history:
            print(f"\n{'='*50}")
            print(f"PRICE HISTORY: {args.history.upper()} ({args.days} days)")
            print(f"{'='*50}")
            print(f"   {'Date':<12} {'Price':>14}")
            print(f"   {'-'*30}")
            
            # Show first and last few entries
            entries = history[::max(1, len(history)//10)]  # Sample ~10 entries
            for entry in entries:
                print(f"   {entry['date']:<12} ${entry['price']:>13,.2f}")
            print()
        else:
            print(f"No history found for: {args.history}")
    
    else:
        ct.print_dashboard(args.top)


if __name__ == "__main__":
    main()
