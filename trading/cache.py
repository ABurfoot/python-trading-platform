#!/usr/bin/env python3
"""
Caching Layer
==============
Intelligent caching for API responses to reduce calls and improve speed.

Features:
- In-memory LRU cache for hot data
- Disk cache for persistence across sessions
- TTL (time-to-live) support for different data types
- Cache statistics and management

Usage:
    from trading.cache import cache, CacheConfig
    
    # Get with automatic caching
    @cache.cached(ttl=300)  # 5 minutes
    def get_quote(symbol):
        return api.fetch_quote(symbol)
    
    # Manual cache control
    cache.set("AAPL:quote", data, ttl=60)
    data = cache.get("AAPL:quote")
    
    # Clear cache
    cache.clear()
    cache.clear_symbol("AAPL")
"""

import os
import json
import time
import hashlib
import pickle
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Callable, Union
from dataclasses import dataclass, field
from functools import wraps
from collections import OrderedDict


@dataclass
class CacheConfig:
    """Cache configuration."""
    # Cache directory
    cache_dir: str = field(default_factory=lambda: os.path.expanduser("~/.trading_platform/cache"))
    
    # Memory cache settings
    max_memory_items: int = 1000
    max_memory_mb: int = 100
    
    # Default TTLs (in seconds)
    ttl_quote: int = 60          # 1 minute - real-time quotes
    ttl_bars: int = 300          # 5 minutes - price bars
    ttl_fundamentals: int = 3600 # 1 hour - fundamentals
    ttl_profile: int = 86400     # 24 hours - company profile
    ttl_analysis: int = 600      # 10 minutes - full analysis
    ttl_news: int = 900          # 15 minutes - news
    ttl_earnings: int = 3600     # 1 hour - earnings
    ttl_options: int = 300       # 5 minutes - options data
    
    # Disk cache settings
    enable_disk_cache: bool = True
    max_disk_mb: int = 500
    
    def get_ttl(self, data_type: str) -> int:
        """Get TTL for a data type."""
        return getattr(self, f"ttl_{data_type}", 300)


@dataclass
class CacheEntry:
    """Single cache entry."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    size_bytes: int = 0
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


class MemoryCache:
    """Thread-safe in-memory LRU cache."""
    
    def __init__(self, max_items: int = 1000, max_mb: int = 100):
        self.max_items = max_items
        self.max_bytes = max_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._total_bytes = 0
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired:
                self._delete(key)
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache."""
        with self._lock:
            # Calculate size
            try:
                size = len(pickle.dumps(value))
            except Exception:
                size = 1000  # Estimate
            
            # Check if single item is too large
            if size > self.max_bytes * 0.1:  # Max 10% of cache per item
                return False
            
            # Remove old entry if exists
            if key in self._cache:
                self._delete(key)
            
            # Evict until we have space
            while (len(self._cache) >= self.max_items or 
                   self._total_bytes + size > self.max_bytes):
                if not self._cache:
                    break
                # Remove oldest (least recently used)
                oldest_key = next(iter(self._cache))
                self._delete(oldest_key)
            
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=time.time() + ttl,
                size_bytes=size
            )
            self._cache[key] = entry
            self._total_bytes += size
            return True
    
    def _delete(self, key: str):
        """Delete entry (internal, assumes lock held)."""
        if key in self._cache:
            self._total_bytes -= self._cache[key].size_bytes
            del self._cache[key]
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        with self._lock:
            if key in self._cache:
                self._delete(key)
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._total_bytes = 0
    
    def clear_pattern(self, pattern: str):
        """Clear entries matching pattern (e.g., 'AAPL:*')."""
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern.replace('*', '') in k]
            for key in keys_to_delete:
                self._delete(key)
    
    @property
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "items": len(self._cache),
                "size_mb": self._total_bytes / (1024 * 1024),
                "max_items": self.max_items,
                "max_mb": self.max_bytes / (1024 * 1024),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0,
            }


class DiskCache:
    """Persistent disk cache."""
    
    def __init__(self, cache_dir: str, max_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_mb * 1024 * 1024
        self._index_file = self.cache_dir / "index.json"
        self._index: Dict[str, Dict] = self._load_index()
        self._lock = threading.RLock()
    
    def _load_index(self) -> Dict:
        """Load cache index from disk."""
        if self._index_file.exists():
            try:
                with open(self._index_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_index(self):
        """Save cache index to disk."""
        try:
            with open(self._index_file, 'w') as f:
                json.dump(self._index, f)
        except Exception:
            pass
    
    def _key_to_filename(self, key: str) -> str:
        """Convert cache key to safe filename."""
        return hashlib.md5(key.encode()).hexdigest() + ".cache"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from disk cache."""
        with self._lock:
            if key not in self._index:
                return None
            
            entry = self._index[key]
            if time.time() > entry.get("expires_at", 0):
                self.delete(key)
                return None
            
            filepath = self.cache_dir / entry["filename"]
            if not filepath.exists():
                del self._index[key]
                return None
            
            try:
                with open(filepath, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                self.delete(key)
                return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in disk cache."""
        with self._lock:
            filename = self._key_to_filename(key)
            filepath = self.cache_dir / filename
            
            try:
                data = pickle.dumps(value)
                size = len(data)
                
                # Check size limit
                if size > self.max_bytes * 0.1:
                    return False
                
                # Write to disk
                with open(filepath, 'wb') as f:
                    f.write(data)
                
                # Update index
                self._index[key] = {
                    "filename": filename,
                    "created_at": time.time(),
                    "expires_at": time.time() + ttl,
                    "size": size
                }
                self._save_index()
                
                # Cleanup if needed
                self._cleanup_if_needed()
                
                return True
            except Exception as e:
                return False
    
    def delete(self, key: str) -> bool:
        """Delete entry from disk cache."""
        with self._lock:
            if key not in self._index:
                return False
            
            entry = self._index[key]
            filepath = self.cache_dir / entry["filename"]
            
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception:
                pass
            
            del self._index[key]
            self._save_index()
            return True
    
    def clear(self):
        """Clear all disk cache."""
        with self._lock:
            for entry in self._index.values():
                try:
                    filepath = self.cache_dir / entry["filename"]
                    if filepath.exists():
                        filepath.unlink()
                except Exception:
                    pass
            self._index = {}
            self._save_index()
    
    def _cleanup_if_needed(self):
        """Remove expired entries and enforce size limit."""
        now = time.time()
        
        # Remove expired
        expired = [k for k, v in self._index.items() if now > v.get("expires_at", 0)]
        for key in expired:
            self.delete(key)
        
        # Check total size
        total_size = sum(e.get("size", 0) for e in self._index.values())
        if total_size > self.max_bytes:
            # Remove oldest entries
            sorted_entries = sorted(self._index.items(), key=lambda x: x[1].get("created_at", 0))
            for key, _ in sorted_entries:
                self.delete(key)
                total_size = sum(e.get("size", 0) for e in self._index.values())
                if total_size <= self.max_bytes * 0.8:
                    break
    
    @property
    def stats(self) -> Dict:
        """Get disk cache statistics."""
        with self._lock:
            total_size = sum(e.get("size", 0) for e in self._index.values())
            return {
                "items": len(self._index),
                "size_mb": total_size / (1024 * 1024),
                "max_mb": self.max_bytes / (1024 * 1024),
                "cache_dir": str(self.cache_dir),
            }


class TradingCache:
    """
    Main cache interface combining memory and disk caching.
    
    Usage:
        cache = TradingCache()
        
        # Decorator for automatic caching
        @cache.cached(ttl=300, data_type="quote")
        def get_quote(symbol):
            return api.fetch(symbol)
        
        # Manual caching
        cache.set("AAPL:quote", data, ttl=60)
        data = cache.get("AAPL:quote")
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.memory = MemoryCache(
            max_items=self.config.max_memory_items,
            max_mb=self.config.max_memory_mb
        )
        self.disk = DiskCache(
            cache_dir=self.config.cache_dir,
            max_mb=self.config.max_disk_mb
        ) if self.config.enable_disk_cache else None
    
    def get(self, key: str, use_disk: bool = True) -> Optional[Any]:
        """
        Get value from cache.
        Checks memory first, then disk.
        """
        # Try memory cache first
        value = self.memory.get(key)
        if value is not None:
            return value
        
        # Try disk cache
        if use_disk and self.disk:
            value = self.disk.get(key)
            if value is not None:
                # Promote to memory cache
                self.memory.set(key, value, ttl=300)
                return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300, persist: bool = False) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            persist: Also save to disk cache
        """
        success = self.memory.set(key, value, ttl)
        
        if persist and self.disk:
            self.disk.set(key, value, ttl)
        
        return success
    
    def delete(self, key: str) -> bool:
        """Delete from both caches."""
        m = self.memory.delete(key)
        d = self.disk.delete(key) if self.disk else False
        return m or d
    
    def clear(self):
        """Clear all caches."""
        self.memory.clear()
        if self.disk:
            self.disk.clear()
    
    def clear_symbol(self, symbol: str):
        """Clear all cached data for a symbol."""
        pattern = f"{symbol}:*"
        self.memory.clear_pattern(pattern)
        # Note: Disk cache doesn't support pattern clear efficiently
    
    def cached(self, ttl: int = None, data_type: str = None, persist: bool = False, 
               key_func: Callable = None):
        """
        Decorator for automatic caching.
        
        Args:
            ttl: Time-to-live (or use data_type default)
            data_type: Type of data (quote, bars, fundamentals, etc.)
            persist: Also save to disk
            key_func: Custom function to generate cache key
        
        Example:
            @cache.cached(data_type="quote")
            def get_quote(symbol):
                return api.fetch(symbol)
        """
        if ttl is None and data_type:
            ttl = self.config.get_ttl(data_type)
        elif ttl is None:
            ttl = 300
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default: function name + args
                    key_parts = [func.__name__]
                    key_parts.extend(str(a) for a in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = ":".join(key_parts)
                
                # Try cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Call function
                result = func(*args, **kwargs)
                
                # Cache result
                if result is not None:
                    self.set(cache_key, result, ttl=ttl, persist=persist)
                
                return result
            
            # Add cache control methods to wrapper
            wrapper.cache_clear = lambda: self.memory.clear_pattern(f"{func.__name__}:*")
            wrapper.cache_info = lambda: self.memory.stats
            
            return wrapper
        return decorator
    
    @property
    def stats(self) -> Dict:
        """Get combined cache statistics."""
        stats = {
            "memory": self.memory.stats,
        }
        if self.disk:
            stats["disk"] = self.disk.stats
        return stats
    
    def print_stats(self):
        """Print cache statistics."""
        stats = self.stats
        print("\n" + "="*50)
        print("📦 CACHE STATISTICS")
        print("="*50)
        
        mem = stats["memory"]
        print(f"\n💾 Memory Cache:")
        print(f"   Items: {mem['items']}/{mem['max_items']}")
        print(f"   Size:  {mem['size_mb']:.1f}/{mem['max_mb']:.0f} MB")
        print(f"   Hits:  {mem['hits']} ({mem['hit_rate']*100:.1f}% hit rate)")
        
        if "disk" in stats:
            disk = stats["disk"]
            print(f"\n💿 Disk Cache:")
            print(f"   Items: {disk['items']}")
            print(f"   Size:  {disk['size_mb']:.1f}/{disk['max_mb']:.0f} MB")
            print(f"   Path:  {disk['cache_dir']}")
        
        print("="*50)


# Global cache instance
cache = TradingCache()


def get_cache() -> TradingCache:
    """Get the global cache instance."""
    return cache


# Convenience decorators
def cached_quote(func):
    """Cache decorator for quote data (1 min TTL)."""
    return cache.cached(data_type="quote")(func)


def cached_bars(func):
    """Cache decorator for price bars (5 min TTL)."""
    return cache.cached(data_type="bars")(func)


def cached_fundamentals(func):
    """Cache decorator for fundamental data (1 hour TTL)."""
    return cache.cached(data_type="fundamentals", persist=True)(func)


def cached_analysis(func):
    """Cache decorator for analysis results (10 min TTL)."""
    return cache.cached(data_type="analysis")(func)


if __name__ == "__main__":
    # Demo
    print("Cache Demo")
    print("-" * 40)
    
    # Test basic operations
    cache.set("test:1", {"price": 150.0}, ttl=60)
    print(f"Set test:1")
    
    value = cache.get("test:1")
    print(f"Get test:1: {value}")
    
    # Test decorator
    @cache.cached(ttl=10, data_type="quote")
    def slow_fetch(symbol):
        print(f"  (Fetching {symbol}...)")
        time.sleep(0.1)
        return {"symbol": symbol, "price": 100.0}
    
    print("\nFirst call (cache miss):")
    result1 = slow_fetch("AAPL")
    
    print("Second call (cache hit):")
    result2 = slow_fetch("AAPL")
    
    print("\nCache stats:")
    cache.print_stats()
