#!/usr/bin/env python3
"""
Multi-Currency Support Module
==============================
Handle multiple currencies for international portfolios.

Features:
- Real-time exchange rate fetching
- Currency conversion for positions
- FX gain/loss tracking
- Historical exchange rates
- Base currency reporting

Usage:
    from trading.currency import CurrencyManager, Currency
    
    cm = CurrencyManager(base_currency="AUD")
    
    # Convert USD to AUD
    aud_value = cm.convert(100, "USD", "AUD")
    
    # Get exchange rate
    rate = cm.get_rate("USD", "AUD")
    
    # Get all rates
    rates = cm.get_all_rates()
"""

import os
import json
import time
import urllib.request
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path


class Currency(Enum):
    """Supported currencies."""
    USD = "USD"  # US Dollar
    AUD = "AUD"  # Australian Dollar
    GBP = "GBP"  # British Pound
    EUR = "EUR"  # Euro
    JPY = "JPY"  # Japanese Yen
    CAD = "CAD"  # Canadian Dollar
    CHF = "CHF"  # Swiss Franc
    HKD = "HKD"  # Hong Kong Dollar
    SGD = "SGD"  # Singapore Dollar
    NZD = "NZD"  # New Zealand Dollar
    CNY = "CNY"  # Chinese Yuan
    INR = "INR"  # Indian Rupee


# Currency symbols for display
CURRENCY_SYMBOLS = {
    "USD": "$",
    "AUD": "A$",
    "GBP": "£",
    "EUR": "€",
    "JPY": "¥",
    "CAD": "C$",
    "CHF": "CHF",
    "HKD": "HK$",
    "SGD": "S$",
    "NZD": "NZ$",
    "CNY": "¥",
    "INR": "₹",
}

# Exchange to currency mapping
EXCHANGE_CURRENCIES = {
    "NYSE": "USD",
    "NASDAQ": "USD",
    "AMEX": "USD",
    "ASX": "AUD",
    "LSE": "GBP",
    "TSX": "CAD",
    "HKEX": "HKD",
    "SGX": "SGD",
    "JPX": "JPY",
    "SSE": "CNY",
    "NSE": "INR",
    "XETRA": "EUR",
    "EURONEXT": "EUR",
}


@dataclass
class ExchangeRate:
    """Exchange rate data."""
    from_currency: str
    to_currency: str
    rate: float
    timestamp: datetime
    source: str = "api"
    
    @property
    def inverse(self) -> float:
        """Get inverse rate."""
        return 1 / self.rate if self.rate > 0 else 0
    
    @property
    def age_minutes(self) -> float:
        """Get age of rate in minutes."""
        return (datetime.now() - self.timestamp).total_seconds() / 60
    
    def to_dict(self) -> Dict:
        return {
            "from": self.from_currency,
            "to": self.to_currency,
            "rate": self.rate,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


@dataclass
class FXTransaction:
    """Foreign exchange transaction for tracking FX gains/losses."""
    date: str
    from_currency: str
    from_amount: float
    to_currency: str
    to_amount: float
    rate: float
    purpose: str = ""  # e.g., "Stock purchase", "Dividend conversion"
    
    def to_dict(self) -> Dict:
        return {
            "date": self.date,
            "from_currency": self.from_currency,
            "from_amount": self.from_amount,
            "to_currency": self.to_currency,
            "to_amount": self.to_amount,
            "rate": self.rate,
            "purpose": self.purpose
        }


class CurrencyManager:
    """
    Manage currency conversions and exchange rates.
    
    Args:
        base_currency: Default currency for reporting (default: AUD)
        cache_minutes: How long to cache exchange rates (default: 15)
    """
    
    def __init__(self, base_currency: str = "AUD", cache_minutes: int = 15):
        self.base_currency = base_currency.upper()
        self.cache_minutes = cache_minutes
        
        self._rates: Dict[str, ExchangeRate] = {}
        self._fx_history: List[FXTransaction] = []
        
        # Data directory
        self.data_dir = Path(os.path.expanduser("~/.trading_platform"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_data()
    
    def _load_data(self):
        """Load cached rates and FX history."""
        # Load cached rates
        rates_file = self.data_dir / "exchange_rates.json"
        if rates_file.exists():
            try:
                with open(rates_file) as f:
                    data = json.load(f)
                    for key, rate_data in data.get("rates", {}).items():
                        self._rates[key] = ExchangeRate(
                            from_currency=rate_data["from"],
                            to_currency=rate_data["to"],
                            rate=rate_data["rate"],
                            timestamp=datetime.fromisoformat(rate_data["timestamp"]),
                            source=rate_data.get("source", "cache")
                        )
            except Exception:
                pass
        
        # Load FX history
        history_file = self.data_dir / "fx_history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                    self._fx_history = [
                        FXTransaction(**tx) for tx in data.get("transactions", [])
                    ]
            except Exception:
                pass
    
    def _save_data(self):
        """Save rates and FX history."""
        # Save rates
        rates_file = self.data_dir / "exchange_rates.json"
        with open(rates_file, 'w') as f:
            json.dump({
                "rates": {k: v.to_dict() for k, v in self._rates.items()},
                "updated": datetime.now().isoformat()
            }, f, indent=2)
        
        # Save FX history
        history_file = self.data_dir / "fx_history.json"
        with open(history_file, 'w') as f:
            json.dump({
                "transactions": [tx.to_dict() for tx in self._fx_history],
                "updated": datetime.now().isoformat()
            }, f, indent=2)
    
    def get_rate(self, from_currency: str, to_currency: str, 
                 force_refresh: bool = False) -> float:
        """
        Get exchange rate between two currencies.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            force_refresh: Force API call even if cached
        
        Returns:
            Exchange rate (multiply from_currency amount to get to_currency amount)
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # Same currency
        if from_currency == to_currency:
            return 1.0
        
        # Check cache
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self._rates and not force_refresh:
            rate = self._rates[cache_key]
            if rate.age_minutes < self.cache_minutes:
                return rate.rate
        
        # Check inverse
        inverse_key = f"{to_currency}_{from_currency}"
        if inverse_key in self._rates and not force_refresh:
            rate = self._rates[inverse_key]
            if rate.age_minutes < self.cache_minutes:
                return rate.inverse
        
        # Fetch from API
        rate = self._fetch_rate(from_currency, to_currency)
        
        # Cache result
        self._rates[cache_key] = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            timestamp=datetime.now(),
            source="api"
        )
        self._save_data()
        
        return rate
    
    def _fetch_rate(self, from_currency: str, to_currency: str) -> float:
        """Fetch exchange rate from API."""
        # Try multiple sources
        rate = self._fetch_from_fmp(from_currency, to_currency)
        if rate:
            return rate
        
        rate = self._fetch_from_exchangerate(from_currency, to_currency)
        if rate:
            return rate
        
        # Fallback to hardcoded approximates (updated periodically)
        return self._get_fallback_rate(from_currency, to_currency)
    
    def _fetch_from_fmp(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Fetch rate from Financial Modeling Prep."""
        try:
            api_key = os.environ.get("FMP_API_KEY", "")
            if not api_key:
                return None
            
            url = f"https://financialmodelingprep.com/api/v3/fx/{from_currency}{to_currency}?apikey={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data and len(data) > 0:
                    return float(data[0].get("bid", 0) or data[0].get("price", 0))
        except Exception as e:
            pass
        return None
    
    def _fetch_from_exchangerate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Fetch rate from exchangerate.host (free, no key required)."""
        try:
            url = f"https://api.exchangerate.host/convert?from={from_currency}&to={to_currency}&amount=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("success"):
                    return float(data.get("result", 0))
        except Exception:
            pass
        return None
    
    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> float:
        """Get approximate fallback rate."""
        # Rates relative to USD (approximate)
        usd_rates = {
            "USD": 1.0,
            "AUD": 1.55,    # 1 USD = 1.55 AUD
            "GBP": 0.79,    # 1 USD = 0.79 GBP
            "EUR": 0.92,    # 1 USD = 0.92 EUR
            "JPY": 150.0,   # 1 USD = 150 JPY
            "CAD": 1.36,    # 1 USD = 1.36 CAD
            "CHF": 0.88,    # 1 USD = 0.88 CHF
            "HKD": 7.82,    # 1 USD = 7.82 HKD
            "SGD": 1.35,    # 1 USD = 1.35 SGD
            "NZD": 1.68,    # 1 USD = 1.68 NZD
            "CNY": 7.24,    # 1 USD = 7.24 CNY
            "INR": 83.0,    # 1 USD = 83 INR
        }
        
        from_usd = usd_rates.get(from_currency, 1.0)
        to_usd = usd_rates.get(to_currency, 1.0)
        
        # from_currency -> USD -> to_currency
        return to_usd / from_usd
    
    def convert(self, amount: float, from_currency: str, to_currency: str = None,
                record_transaction: bool = False, purpose: str = "") -> float:
        """
        Convert amount between currencies.
        
        Args:
            amount: Amount in from_currency
            from_currency: Source currency
            to_currency: Target currency (default: base_currency)
            record_transaction: Whether to record in FX history
            purpose: Description for FX history
        
        Returns:
            Converted amount
        """
        to_currency = to_currency or self.base_currency
        rate = self.get_rate(from_currency, to_currency)
        converted = amount * rate
        
        if record_transaction and from_currency != to_currency:
            self._fx_history.append(FXTransaction(
                date=datetime.now().strftime("%Y-%m-%d"),
                from_currency=from_currency,
                from_amount=amount,
                to_currency=to_currency,
                to_amount=converted,
                rate=rate,
                purpose=purpose
            ))
            self._save_data()
        
        return converted
    
    def convert_to_base(self, amount: float, from_currency: str) -> float:
        """Convert amount to base currency."""
        return self.convert(amount, from_currency, self.base_currency)
    
    def get_currency_for_exchange(self, exchange: str) -> str:
        """Get the currency used by an exchange."""
        exchange = exchange.upper()
        return EXCHANGE_CURRENCIES.get(exchange, "USD")
    
    def get_symbol(self, currency: str) -> str:
        """Get currency symbol for display."""
        return CURRENCY_SYMBOLS.get(currency.upper(), currency)
    
    def format_amount(self, amount: float, currency: str, decimals: int = 2) -> str:
        """Format amount with currency symbol."""
        symbol = self.get_symbol(currency)
        if currency in ["JPY", "INR"]:
            return f"{symbol}{amount:,.0f}"
        return f"{symbol}{amount:,.{decimals}f}"
    
    def get_all_rates(self, base: str = None) -> Dict[str, float]:
        """Get all exchange rates relative to a base currency."""
        base = base or self.base_currency
        rates = {}
        
        for currency in Currency:
            if currency.value != base:
                rates[currency.value] = self.get_rate(base, currency.value)
        
        return rates
    
    def get_fx_history(self, currency: str = None, 
                       start_date: str = None, end_date: str = None) -> List[FXTransaction]:
        """Get FX transaction history with optional filters."""
        history = self._fx_history
        
        if currency:
            currency = currency.upper()
            history = [tx for tx in history 
                      if tx.from_currency == currency or tx.to_currency == currency]
        
        if start_date:
            history = [tx for tx in history if tx.date >= start_date]
        
        if end_date:
            history = [tx for tx in history if tx.date <= end_date]
        
        return history
    
    def calculate_fx_gain_loss(self, currency: str, start_date: str = None) -> Dict:
        """
        Calculate FX gain/loss for a currency.
        
        This compares the rate at which currency was acquired vs current rate.
        """
        history = self.get_fx_history(currency, start_date=start_date)
        
        if not history:
            return {"currency": currency, "gain_loss": 0, "transactions": 0}
        
        # Calculate weighted average acquisition rate
        total_acquired = 0
        weighted_rate_sum = 0
        
        for tx in history:
            if tx.to_currency == currency:
                total_acquired += tx.to_amount
                weighted_rate_sum += tx.to_amount * tx.rate
        
        if total_acquired == 0:
            return {"currency": currency, "gain_loss": 0, "transactions": len(history)}
        
        avg_rate = weighted_rate_sum / total_acquired
        current_rate = self.get_rate(history[0].from_currency, currency)
        
        # Gain/loss = (current_rate - avg_rate) * amount
        rate_change = current_rate - avg_rate
        gain_loss = rate_change * total_acquired
        
        return {
            "currency": currency,
            "total_acquired": total_acquired,
            "avg_acquisition_rate": avg_rate,
            "current_rate": current_rate,
            "rate_change": rate_change,
            "gain_loss": gain_loss,
            "gain_loss_pct": (rate_change / avg_rate * 100) if avg_rate > 0 else 0,
            "transactions": len(history)
        }
    
    def to_dict(self) -> Dict:
        """Get currency manager state as dict."""
        return {
            "base_currency": self.base_currency,
            "cached_rates": {k: v.to_dict() for k, v in self._rates.items()},
            "fx_transactions": len(self._fx_history)
        }
    
    def print_rates(self):
        """Print all exchange rates."""
        print(f"\n{'='*50}")
        print(f"EXCHANGE RATES (Base: {self.base_currency})")
        print(f"{'='*50}")
        
        rates = self.get_all_rates()
        for currency, rate in sorted(rates.items()):
            symbol = self.get_symbol(currency)
            base_symbol = self.get_symbol(self.base_currency)
            print(f"  {self.base_currency}/{currency}: {rate:.4f} ({base_symbol}1 = {symbol}{rate:.4f})")
        
        print(f"{'='*50}")


# Convenience functions
_default_manager = None

def get_currency_manager(base_currency: str = "AUD") -> CurrencyManager:
    """Get or create default currency manager."""
    global _default_manager
    if _default_manager is None or _default_manager.base_currency != base_currency:
        _default_manager = CurrencyManager(base_currency)
    return _default_manager


def convert(amount: float, from_currency: str, to_currency: str = "AUD") -> float:
    """Quick conversion using default manager."""
    return get_currency_manager().convert(amount, from_currency, to_currency)


if __name__ == "__main__":
    # Demo
    print("Multi-Currency Support Demo")
    print("="*50)
    
    cm = CurrencyManager(base_currency="AUD")
    
    # Test conversions
    print("\nCurrency Conversions:")
    print(f"  $100 USD = {cm.format_amount(cm.convert(100, 'USD', 'AUD'), 'AUD')}")
    print(f"  £100 GBP = {cm.format_amount(cm.convert(100, 'GBP', 'AUD'), 'AUD')}")
    print(f"  €100 EUR = {cm.format_amount(cm.convert(100, 'EUR', 'AUD'), 'AUD')}")
    print(f"  ¥10000 JPY = {cm.format_amount(cm.convert(10000, 'JPY', 'AUD'), 'AUD')}")
    
    # Print all rates
    cm.print_rates()
    
    # Test exchange currency lookup
    print("\nExchange Currencies:")
    for exchange in ["NYSE", "ASX", "LSE", "TSX"]:
        currency = cm.get_currency_for_exchange(exchange)
        print(f"  {exchange}: {currency}")
