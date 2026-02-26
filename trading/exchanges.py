#!/usr/bin/env python3
"""
Exchange Mapper - Global Stock Exchange Support
================================================
Supports professional format (NYSE:AAPL) and suffix format (BHP.AX)
for all major global exchanges.

Usage:
    from trading.exchanges import ExchangeMapper
    
    mapper = ExchangeMapper()
    parsed = mapper.parse("ASX:BHP")      # Returns ExchangeSymbol
    parsed = mapper.parse("BHP.AX")       # Same result
    parsed = mapper.parse("AAPL")         # Defaults to US
    
    # Get format for different APIs
    parsed.alpaca_symbol    # "BHP" (US only, or None)
    parsed.fmp_symbol       # "BHP.AX"
    parsed.yahoo_symbol     # "BHP.AX"
    parsed.display          # "ASX:BHP"
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import re


@dataclass
class ExchangeSymbol:
    """Parsed exchange and symbol with formats for different APIs."""
    symbol: str              # Raw symbol without suffix
    exchange: str            # Exchange code (NYSE, ASX, LSE, etc.)
    exchange_name: str       # Full exchange name
    country: str             # Country code
    currency: str            # Trading currency
    currency_symbol: str     # Currency symbol ($, £, €, etc.)
    price_divisor: float     # Divisor for price (100 for GBp -> GBP)
    
    # API-specific formats
    alpaca_symbol: Optional[str]   # Alpaca format (US only)
    fmp_symbol: str                # FMP format
    yahoo_symbol: str              # Yahoo Finance format
    
    @property
    def display(self) -> str:
        """Professional display format: EXCHANGE:SYMBOL"""
        return f"{self.exchange}:{self.symbol}"
    
    @property
    def is_us(self) -> bool:
        """Check if this is a US exchange."""
        return self.exchange in ('NYSE', 'NASDAQ', 'AMEX', 'NYSEARCA', 'BATS')


# Currency symbols and special handling
CURRENCY_INFO = {
    'USD': {'symbol': '$', 'divisor': 1},
    'AUD': {'symbol': 'A$', 'divisor': 1},
    'GBP': {'symbol': '£', 'divisor': 1},
    'GBp': {'symbol': 'p', 'divisor': 100},  # Pence - divide by 100 for pounds
    'EUR': {'symbol': '€', 'divisor': 1},
    'JPY': {'symbol': '¥', 'divisor': 1},
    'HKD': {'symbol': 'HK$', 'divisor': 1},
    'CNY': {'symbol': '¥', 'divisor': 1},
    'CAD': {'symbol': 'C$', 'divisor': 1},
    'CHF': {'symbol': 'CHF ', 'divisor': 1},
    'SGD': {'symbol': 'S$', 'divisor': 1},
    'KRW': {'symbol': '₩', 'divisor': 1},
    'INR': {'symbol': '₹', 'divisor': 1},
    'BRL': {'symbol': 'R$', 'divisor': 1},
    'ZAR': {'symbol': 'R', 'divisor': 1},
    'SEK': {'symbol': 'kr', 'divisor': 1},
    'NOK': {'symbol': 'kr', 'divisor': 1},
    'DKK': {'symbol': 'kr', 'divisor': 1},
    'NZD': {'symbol': 'NZ$', 'divisor': 1},
    'MXN': {'symbol': 'MX$', 'divisor': 1},
    'TWD': {'symbol': 'NT$', 'divisor': 1},
    'THB': {'symbol': '฿', 'divisor': 1},
    'MYR': {'symbol': 'RM', 'divisor': 1},
    'IDR': {'symbol': 'Rp', 'divisor': 1},
    'ILS': {'symbol': '₪', 'divisor': 1},
    'SAR': {'symbol': 'SR', 'divisor': 1},
}


# Exchange definitions: suffix, full name, country, currency
EXCHANGES = {
    # === United States ===
    'NYSE':     {'suffix': '',      'name': 'New York Stock Exchange',        'country': 'US', 'currency': 'USD'},
    'NASDAQ':   {'suffix': '',      'name': 'NASDAQ',                         'country': 'US', 'currency': 'USD'},
    'AMEX':     {'suffix': '',      'name': 'NYSE American',                  'country': 'US', 'currency': 'USD'},
    'NYSEARCA': {'suffix': '',      'name': 'NYSE Arca',                      'country': 'US', 'currency': 'USD'},
    'BATS':     {'suffix': '',      'name': 'BATS Global Markets',            'country': 'US', 'currency': 'USD'},
    
    # === Australia ===
    'ASX':      {'suffix': '.AX',   'name': 'Australian Securities Exchange', 'country': 'AU', 'currency': 'AUD'},
    
    # === United Kingdom ===
    'LSE':      {'suffix': '.L',    'name': 'London Stock Exchange',          'country': 'GB', 'currency': 'GBP'},
    'LON':      {'suffix': '.L',    'name': 'London Stock Exchange',          'country': 'GB', 'currency': 'GBP'},
    
    # === Europe ===
    'FRA':      {'suffix': '.F',    'name': 'Frankfurt Stock Exchange',       'country': 'DE', 'currency': 'EUR'},
    'XETRA':    {'suffix': '.DE',   'name': 'XETRA',                          'country': 'DE', 'currency': 'EUR'},
    'EPA':      {'suffix': '.PA',   'name': 'Euronext Paris',                 'country': 'FR', 'currency': 'EUR'},
    'PAR':      {'suffix': '.PA',   'name': 'Euronext Paris',                 'country': 'FR', 'currency': 'EUR'},
    'AMS':      {'suffix': '.AS',   'name': 'Euronext Amsterdam',             'country': 'NL', 'currency': 'EUR'},
    'BRU':      {'suffix': '.BR',   'name': 'Euronext Brussels',              'country': 'BE', 'currency': 'EUR'},
    'LIS':      {'suffix': '.LS',   'name': 'Euronext Lisbon',                'country': 'PT', 'currency': 'EUR'},
    'MIL':      {'suffix': '.MI',   'name': 'Borsa Italiana',                 'country': 'IT', 'currency': 'EUR'},
    'BME':      {'suffix': '.MC',   'name': 'Bolsa de Madrid',                'country': 'ES', 'currency': 'EUR'},
    'MAD':      {'suffix': '.MC',   'name': 'Bolsa de Madrid',                'country': 'ES', 'currency': 'EUR'},
    'SWX':      {'suffix': '.SW',   'name': 'SIX Swiss Exchange',             'country': 'CH', 'currency': 'CHF'},
    'VIE':      {'suffix': '.VI',   'name': 'Vienna Stock Exchange',          'country': 'AT', 'currency': 'EUR'},
    'OSL':      {'suffix': '.OL',   'name': 'Oslo Stock Exchange',            'country': 'NO', 'currency': 'NOK'},
    'STO':      {'suffix': '.ST',   'name': 'Stockholm Stock Exchange',       'country': 'SE', 'currency': 'SEK'},
    'CPH':      {'suffix': '.CO',   'name': 'Copenhagen Stock Exchange',      'country': 'DK', 'currency': 'DKK'},
    'HEL':      {'suffix': '.HE',   'name': 'Helsinki Stock Exchange',        'country': 'FI', 'currency': 'EUR'},
    
    # === Asia Pacific ===
    'TYO':      {'suffix': '.T',    'name': 'Tokyo Stock Exchange',           'country': 'JP', 'currency': 'JPY'},
    'TSE':      {'suffix': '.T',    'name': 'Tokyo Stock Exchange',           'country': 'JP', 'currency': 'JPY'},
    'HKG':      {'suffix': '.HK',   'name': 'Hong Kong Stock Exchange',       'country': 'HK', 'currency': 'HKD'},
    'HKEX':     {'suffix': '.HK',   'name': 'Hong Kong Stock Exchange',       'country': 'HK', 'currency': 'HKD'},
    'SHA':      {'suffix': '.SS',   'name': 'Shanghai Stock Exchange',        'country': 'CN', 'currency': 'CNY'},
    'SHE':      {'suffix': '.SZ',   'name': 'Shenzhen Stock Exchange',        'country': 'CN', 'currency': 'CNY'},
    'SGX':      {'suffix': '.SI',   'name': 'Singapore Exchange',             'country': 'SG', 'currency': 'SGD'},
    'KRX':      {'suffix': '.KS',   'name': 'Korea Exchange',                 'country': 'KR', 'currency': 'KRW'},
    'KOSDAQ':   {'suffix': '.KQ',   'name': 'KOSDAQ',                         'country': 'KR', 'currency': 'KRW'},
    'TAI':      {'suffix': '.TW',   'name': 'Taiwan Stock Exchange',          'country': 'TW', 'currency': 'TWD'},
    'BOM':      {'suffix': '.BO',   'name': 'Bombay Stock Exchange',          'country': 'IN', 'currency': 'INR'},
    'NSE':      {'suffix': '.NS',   'name': 'National Stock Exchange India',  'country': 'IN', 'currency': 'INR'},
    'IDX':      {'suffix': '.JK',   'name': 'Indonesia Stock Exchange',       'country': 'ID', 'currency': 'IDR'},
    'SET':      {'suffix': '.BK',   'name': 'Stock Exchange of Thailand',     'country': 'TH', 'currency': 'THB'},
    'KLSE':     {'suffix': '.KL',   'name': 'Bursa Malaysia',                 'country': 'MY', 'currency': 'MYR'},
    'NZX':      {'suffix': '.NZ',   'name': 'New Zealand Exchange',           'country': 'NZ', 'currency': 'NZD'},
    
    # === Americas ===
    'TSX':      {'suffix': '.TO',   'name': 'Toronto Stock Exchange',         'country': 'CA', 'currency': 'CAD'},
    'TSXV':     {'suffix': '.V',    'name': 'TSX Venture Exchange',           'country': 'CA', 'currency': 'CAD'},
    'BMV':      {'suffix': '.MX',   'name': 'Mexican Stock Exchange',         'country': 'MX', 'currency': 'MXN'},
    'BVSP':     {'suffix': '.SA',   'name': 'B3 (Brazil)',                    'country': 'BR', 'currency': 'BRL'},
    'SAO':      {'suffix': '.SA',   'name': 'B3 (Brazil)',                    'country': 'BR', 'currency': 'BRL'},
    
    # === Middle East & Africa ===
    'TASE':     {'suffix': '.TA',   'name': 'Tel Aviv Stock Exchange',        'country': 'IL', 'currency': 'ILS'},
    'JSE':      {'suffix': '.JO',   'name': 'Johannesburg Stock Exchange',    'country': 'ZA', 'currency': 'ZAR'},
    'TADAWUL':  {'suffix': '.SR',   'name': 'Saudi Stock Exchange',           'country': 'SA', 'currency': 'SAR'},
}

# Reverse mapping: suffix -> exchange
SUFFIX_TO_EXCHANGE = {}
for exc, data in EXCHANGES.items():
    if data['suffix'] and data['suffix'] not in SUFFIX_TO_EXCHANGE:
        SUFFIX_TO_EXCHANGE[data['suffix']] = exc


# Well-known NASDAQ stocks (for accurate exchange display)
NASDAQ_STOCKS = {
    # FAANG / Mega-cap tech
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'META', 'NVDA', 'TSLA', 'NFLX',
    # Other major NASDAQ stocks
    'ADBE', 'AMD', 'AMGN', 'ADP', 'ASML', 'ATVI', 'AVGO', 'BIDU', 'BIIB',
    'BKNG', 'CDNS', 'CHTR', 'CMCSA', 'COST', 'CPRT', 'CRWD', 'CSCO', 'CSX',
    'CTAS', 'CTSH', 'DDOG', 'DLTR', 'DOCU', 'DXCM', 'EA', 'EBAY', 'EXC',
    'FANG', 'FAST', 'FISV', 'FTNT', 'GILD', 'ILMN', 'INTC', 'INTU', 'ISRG',
    'JD', 'KDP', 'KHC', 'KLAC', 'LCID', 'LRCX', 'LULU', 'MAR', 'MCHP', 'MDLZ',
    'MELI', 'MNST', 'MRNA', 'MRVL', 'MU', 'NTES', 'NXPI', 'ODFL', 'OKTA',
    'ORLY', 'PANW', 'PAYX', 'PCAR', 'PDD', 'PEP', 'PYPL', 'QCOM', 'REGN',
    'RIVN', 'ROST', 'SBUX', 'SGEN', 'SIRI', 'SNPS', 'SPLK', 'SWKS', 'TEAM',
    'TMUS', 'TTD', 'TXN', 'VRSK', 'VRSN', 'VRTX', 'WBA', 'WDAY', 'XEL',
    'ZM', 'ZS',
    # Popular ETFs on NASDAQ
    'QQQ', 'TQQQ', 'SQQQ', 'ARKK', 'ARKG', 'ARKW', 'ARKF',
}


class ExchangeMapper:
    """Parse and convert stock symbols between different formats."""
    
    def __init__(self, default_exchange: str = 'NYSE'):
        self.default_exchange = default_exchange
    
    def parse(self, input_str: str) -> ExchangeSymbol:
        """
        Parse a symbol string in any supported format.
        
        Supported formats:
            NYSE:AAPL     - Professional format
            NYSE: AAPL    - With space (also supported)
            ASX:BHP       - Professional format  
            AAPL          - Default to US
            BHP.AX        - Yahoo/suffix format
            BHP.L         - LSE suffix format
        
        Returns:
            ExchangeSymbol with all format variants
        """
        # Clean input: uppercase, strip whitespace, remove spaces around colon
        input_str = input_str.strip().upper()
        input_str = input_str.replace(": ", ":").replace(" :", ":")  # Fix "LON: SHEL" -> "LON:SHEL"
        input_str = ''.join(input_str.split())  # Remove any remaining spaces
        
        # Check for professional format (EXCHANGE:SYMBOL)
        if ':' in input_str:
            parts = input_str.split(':', 1)
            exchange = parts[0].strip()
            symbol = parts[1].strip()
            
            if exchange not in EXCHANGES:
                # Try to find a matching exchange
                exchange = self._find_exchange(exchange) or self.default_exchange
        
        # Check for suffix format (SYMBOL.XX)
        elif '.' in input_str:
            # Find the suffix
            match = re.match(r'^([A-Z0-9]+)(\.[\w]+)$', input_str)
            if match:
                symbol = match.group(1)
                suffix = match.group(2)
                exchange = SUFFIX_TO_EXCHANGE.get(suffix, self.default_exchange)
            else:
                symbol = input_str
                exchange = self.default_exchange
        
        # Plain symbol - default to US (check if NASDAQ)
        else:
            symbol = input_str
            # Check if it's a known NASDAQ stock
            if symbol in NASDAQ_STOCKS:
                exchange = 'NASDAQ'
            else:
                exchange = self.default_exchange
        
        return self._create_symbol(symbol, exchange)
    
    def _find_exchange(self, code: str) -> Optional[str]:
        """Find exchange by code or alias."""
        code = code.upper()
        if code in EXCHANGES:
            return code
        
        # Common aliases
        aliases = {
            'NEW YORK': 'NYSE',
            'NEWYORK': 'NYSE',
            'NY': 'NYSE',
            'AUSTRALIA': 'ASX',
            'SYDNEY': 'ASX',
            'LONDON': 'LSE',
            'UK': 'LSE',
            'FRANKFURT': 'FRA',
            'GERMANY': 'XETRA',
            'PARIS': 'EPA',
            'FRANCE': 'EPA',
            'TOKYO': 'TYO',
            'JAPAN': 'TYO',
            'HONGKONG': 'HKG',
            'HK': 'HKG',
            'SHANGHAI': 'SHA',
            'SHENZHEN': 'SHE',
            'CHINA': 'SHA',
            'SINGAPORE': 'SGX',
            'KOREA': 'KRX',
            'INDIA': 'NSE',
            'MUMBAI': 'BOM',
            'TORONTO': 'TSX',
            'CANADA': 'TSX',
            'BRAZIL': 'BVSP',
            'MEXICO': 'BMV',
            'SWISS': 'SWX',
            'SWITZERLAND': 'SWX',
        }
        return aliases.get(code)
    
    def _create_symbol(self, symbol: str, exchange: str) -> ExchangeSymbol:
        """Create ExchangeSymbol with all format variants."""
        exc_data = EXCHANGES.get(exchange, EXCHANGES[self.default_exchange])
        suffix = exc_data['suffix']
        currency = exc_data['currency']
        
        # Get currency info
        curr_info = CURRENCY_INFO.get(currency, {'symbol': '$', 'divisor': 1})
        
        # Build API-specific symbols
        is_us = exchange in ('NYSE', 'NASDAQ', 'AMEX', 'NYSEARCA', 'BATS')
        
        # Alpaca only supports US stocks
        alpaca_symbol = symbol if is_us else None
        
        # FMP uses suffix format for international
        fmp_symbol = symbol if is_us else f"{symbol}{suffix}"
        
        # Yahoo always uses suffix format (empty for US)
        yahoo_symbol = symbol if is_us else f"{symbol}{suffix}"
        
        return ExchangeSymbol(
            symbol=symbol,
            exchange=exchange,
            exchange_name=exc_data['name'],
            country=exc_data['country'],
            currency=currency,
            currency_symbol=curr_info['symbol'],
            price_divisor=curr_info['divisor'],
            alpaca_symbol=alpaca_symbol,
            fmp_symbol=fmp_symbol,
            yahoo_symbol=yahoo_symbol,
        )
    
    def format_display(self, symbol: str, exchange: str) -> str:
        """Format for display: EXCHANGE:SYMBOL"""
        return f"{exchange}:{symbol}"
    
    def get_exchange_info(self, exchange: str) -> dict:
        """Get exchange information."""
        return EXCHANGES.get(exchange.upper(), {})
    
    def list_exchanges(self, country: Optional[str] = None) -> list:
        """List all supported exchanges, optionally filtered by country."""
        result = []
        for code, data in EXCHANGES.items():
            if country is None or data['country'] == country.upper():
                result.append({
                    'code': code,
                    'name': data['name'],
                    'country': data['country'],
                    'currency': data['currency'],
                    'suffix': data['suffix'],
                })
        return result


# Convenience function
def parse_symbol(input_str: str) -> ExchangeSymbol:
    """Quick parse function."""
    return ExchangeMapper().parse(input_str)


if __name__ == "__main__":
    # Test the mapper
    mapper = ExchangeMapper()
    
    test_cases = [
        "AAPL",           # US default
        "NYSE:AAPL",      # Professional US
        "ASX:BHP",        # Professional Australian
        "BHP.AX",         # Yahoo Australian
        "LSE:VOD",        # Professional UK
        "VOD.L",          # Yahoo UK
        "TYO:7203",       # Tokyo (Toyota)
        "7203.T",         # Yahoo Tokyo
        "XETRA:SAP",      # German
        "SAP.DE",         # Yahoo German
    ]
    
    print("Exchange Mapper Test")
    print("=" * 80)
    
    for test in test_cases:
        result = mapper.parse(test)
        print(f"\nInput: {test}")
        print(f"  Display:  {result.display}")
        print(f"  Exchange: {result.exchange_name} ({result.country})")
        print(f"  Currency: {result.currency}")
        print(f"  Alpaca:   {result.alpaca_symbol or 'N/A (not US)'}")
        print(f"  FMP:      {result.fmp_symbol}")
        print(f"  Yahoo:    {result.yahoo_symbol}")
