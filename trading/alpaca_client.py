#!/usr/bin/env python3
"""
Alpaca Trading Client
=====================
Connects to Alpaca API for paper trading and live data.

Setup:
    1. Create free account at https://alpaca.markets
    2. Get API keys from dashboard (use Paper Trading keys)
    3. Set environment variables or create config file

Usage:
    from alpaca_client import AlpacaClient
    
    client = AlpacaClient()
    client.connect()
    
    # Get account info
    account = client.get_account()
    
    # Place order
    client.buy("AAPL", 10)
    
    # Get positions
    positions = client.get_positions()
"""

import os
import json
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Fix SSL for macOS
ssl._create_default_https_context = ssl._create_unverified_context


# ============================================================================
# Configuration
# ============================================================================

class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass
class AlpacaConfig:
    api_key: str
    secret_key: str
    mode: TradingMode = TradingMode.PAPER
    
    @property
    def base_url(self) -> str:
        if self.mode == TradingMode.PAPER:
            return "https://paper-api.alpaca.markets"
        return "https://api.alpaca.markets"
    
    @property
    def data_url(self) -> str:
        return "https://data.alpaca.markets"
    
    @classmethod
    def from_env(cls) -> 'AlpacaConfig':
        """Load config from environment variables."""
        api_key = os.getenv("ALPACA_API_KEY", "")
        secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        mode = TradingMode.PAPER if os.getenv("ALPACA_PAPER", "true").lower() == "true" else TradingMode.LIVE
        return cls(api_key, secret_key, mode)
    
    @classmethod
    def from_file(cls, filepath: str = "config/alpaca.json") -> 'AlpacaConfig':
        """Load config from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        mode = TradingMode.PAPER if data.get("paper", True) else TradingMode.LIVE
        return cls(data["api_key"], data["secret_key"], mode)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class Account:
    id: str
    status: str
    currency: str
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    last_equity: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float


@dataclass
class Position:
    symbol: str
    qty: int
    side: str
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class Order:
    id: str
    symbol: str
    side: str
    qty: int
    order_type: str
    status: str
    filled_qty: int
    filled_avg_price: Optional[float]
    submitted_at: str
    filled_at: Optional[str]


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp: str


@dataclass
class Bar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# ============================================================================
# Alpaca API Client
# ============================================================================

class AlpacaClient:
    """Client for Alpaca Trading API."""
    
    def __init__(self, config: Optional[AlpacaConfig] = None):
        """Initialize client with config."""
        if config is None:
            # Try loading from file first, then environment
            try:
                config = AlpacaConfig.from_file()
            except FileNotFoundError:
                config = AlpacaConfig.from_env()
        
        self.config = config
        self._connected = False
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                 use_data_api: bool = False) -> Dict:
        """Make authenticated request to Alpaca API."""
        base_url = self.config.data_url if use_data_api else self.config.base_url
        url = f"{base_url}{endpoint}"
        
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.secret_key,
            "Content-Type": "application/json"
        }
        
        body = json.dumps(data).encode() if data else None
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise Exception(f"API Error {e.code}: {error_body}")
    
    # ========================================================================
    # Connection
    # ========================================================================
    
    def connect(self) -> bool:
        """Verify connection and credentials."""
        try:
            account = self._request("GET", "/v2/account")
            self._connected = True
            print(f"[OK] Connected to Alpaca ({self.config.mode.value} mode)")
            print(f"  Account: {account['id'][:8]}...")
            print(f"  Status: {account['status']}")
            print(f"  Equity: ${float(account['equity']):,.2f}")
            return True
        except Exception as e:
            print(f"[X] Connection failed: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    # ========================================================================
    # Account
    # ========================================================================
    
    def get_account(self) -> Account:
        """Get account information."""
        data = self._request("GET", "/v2/account")
        
        equity = float(data["equity"])
        last_equity = float(data["last_equity"])
        cash = float(data["cash"])
        
        # Calculate P&L
        daily_pnl = equity - last_equity
        daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity > 0 else 0
        
        # Total P&L (since account creation) - approximate using deposited cash
        initial = float(data.get("initial_margin", cash))
        total_pnl = equity - initial
        total_pnl_pct = (total_pnl / initial * 100) if initial > 0 else 0
        
        return Account(
            id=data["id"],
            status=data["status"],
            currency=data["currency"],
            cash=cash,
            portfolio_value=float(data["portfolio_value"]),
            buying_power=float(data["buying_power"]),
            equity=equity,
            last_equity=last_equity,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct
        )
    
    # ========================================================================
    # Positions
    # ========================================================================
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        data = self._request("GET", "/v2/positions")
        
        positions = []
        for p in data:
            positions.append(Position(
                symbol=p["symbol"],
                qty=int(p["qty"]),
                side=p["side"],
                avg_entry_price=float(p["avg_entry_price"]),
                current_price=float(p["current_price"]),
                market_value=float(p["market_value"]),
                unrealized_pnl=float(p["unrealized_pl"]),
                unrealized_pnl_pct=float(p["unrealized_plpc"]) * 100
            ))
        
        return positions
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        try:
            p = self._request("GET", f"/v2/positions/{symbol}")
            return Position(
                symbol=p["symbol"],
                qty=int(p["qty"]),
                side=p["side"],
                avg_entry_price=float(p["avg_entry_price"]),
                current_price=float(p["current_price"]),
                market_value=float(p["market_value"]),
                unrealized_pnl=float(p["unrealized_pl"]),
                unrealized_pnl_pct=float(p["unrealized_plpc"]) * 100
            )
        except Exception:
            return None
    
    def close_position(self, symbol: str) -> Order:
        """Close entire position for a symbol."""
        data = self._request("DELETE", f"/v2/positions/{symbol}")
        return self._parse_order(data)
    
    def close_all_positions(self) -> List[Order]:
        """Close all open positions."""
        data = self._request("DELETE", "/v2/positions")
        return [self._parse_order(o) for o in data]
    
    # ========================================================================
    # Orders
    # ========================================================================
    
    def _parse_order(self, data: Dict) -> Order:
        """Parse order response."""
        return Order(
            id=data["id"],
            symbol=data["symbol"],
            side=data["side"],
            qty=int(data["qty"]),
            order_type=data["type"],
            status=data["status"],
            filled_qty=int(data["filled_qty"]),
            filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
            submitted_at=data["submitted_at"],
            filled_at=data.get("filled_at")
        )
    
    def buy(self, symbol: str, qty: int, order_type: str = "market", 
            limit_price: Optional[float] = None) -> Order:
        """Place a buy order."""
        return self._place_order(symbol, qty, "buy", order_type, limit_price)
    
    def sell(self, symbol: str, qty: int, order_type: str = "market",
             limit_price: Optional[float] = None) -> Order:
        """Place a sell order."""
        return self._place_order(symbol, qty, "sell", order_type, limit_price)
    
    def _place_order(self, symbol: str, qty: int, side: str, order_type: str,
                     limit_price: Optional[float] = None) -> Order:
        """Place an order."""
        order_data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": "day"
        }
        
        if order_type == "limit" and limit_price:
            order_data["limit_price"] = str(limit_price)
        
        data = self._request("POST", "/v2/orders", order_data)
        return self._parse_order(data)
    
    def get_orders(self, status: str = "open") -> List[Order]:
        """Get orders by status (open, closed, all)."""
        data = self._request("GET", f"/v2/orders?status={status}")
        return [self._parse_order(o) for o in data]
    
    def get_order(self, order_id: str) -> Order:
        """Get order by ID."""
        data = self._request("GET", f"/v2/orders/{order_id}")
        return self._parse_order(data)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self._request("DELETE", f"/v2/orders/{order_id}")
            return True
        except Exception:
            return False
    
    def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count cancelled."""
        data = self._request("DELETE", "/v2/orders")
        return len(data)
    
    # ========================================================================
    # Market Data
    # ========================================================================
    
    def get_quote(self, symbol: str) -> Quote:
        """Get latest quote for a symbol."""
        data = self._request("GET", f"/v2/stocks/{symbol}/quotes/latest", use_data_api=True)
        q = data["quote"]
        return Quote(
            symbol=symbol,
            bid=float(q["bp"]),
            ask=float(q["ap"]),
            bid_size=int(q["bs"]),
            ask_size=int(q["as"]),
            timestamp=q["t"]
        )
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get latest quotes for multiple symbols."""
        symbols_str = ",".join(symbols)
        data = self._request("GET", f"/v2/stocks/quotes/latest?symbols={symbols_str}", use_data_api=True)
        
        quotes = {}
        for symbol, q_data in data["quotes"].items():
            quotes[symbol] = Quote(
                symbol=symbol,
                bid=float(q_data["bp"]),
                ask=float(q_data["ap"]),
                bid_size=int(q_data["bs"]),
                ask_size=int(q_data["as"]),
                timestamp=q_data["t"]
            )
        return quotes
    
    def get_bars(self, symbol: str, timeframe: str = "1Day", 
                 limit: int = 100) -> List[Bar]:
        """Get historical bars for a symbol."""
        data = self._request(
            "GET", 
            f"/v2/stocks/{symbol}/bars?timeframe={timeframe}&limit={limit}",
            use_data_api=True
        )
        
        bars = []
        for b in data.get("bars", []):
            bars.append(Bar(
                symbol=symbol,
                timestamp=b["t"],
                open=float(b["o"]),
                high=float(b["h"]),
                low=float(b["l"]),
                close=float(b["c"]),
                volume=int(b["v"])
            ))
        return bars
    
    # ========================================================================
    # Convenience Methods
    # ========================================================================
    
    def get_price(self, symbol: str) -> float:
        """Get current price (mid of bid/ask)."""
        quote = self.get_quote(symbol)
        return (quote.bid + quote.ask) / 2
    
    def get_buying_power(self) -> float:
        """Get available buying power."""
        account = self.get_account()
        return account.buying_power
    
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        data = self._request("GET", "/v2/clock")
        return data["is_open"]
    
    def get_market_hours(self) -> Tuple[str, str]:
        """Get today's market open and close times."""
        data = self._request("GET", "/v2/clock")
        return data["next_open"], data["next_close"]


# ============================================================================
# CLI for Testing
# ============================================================================

def print_account(account: Account):
    """Pretty print account info."""
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                         ACCOUNT SUMMARY                          ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Account ID:     {account.id[:20]:<44} ║")
    print(f"║  Status:         {account.status:<44} ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Cash:           ${account.cash:>14,.2f}                         ║")
    print(f"║  Portfolio:      ${account.portfolio_value:>14,.2f}                         ║")
    print(f"║  Equity:         ${account.equity:>14,.2f}                         ║")
    print(f"║  Buying Power:   ${account.buying_power:>14,.2f}                         ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Daily P&L:      ${account.daily_pnl:>+14,.2f} ({account.daily_pnl_pct:>+6.2f}%)            ║")
    print(f"║  Total P&L:      ${account.total_pnl:>+14,.2f} ({account.total_pnl_pct:>+6.2f}%)            ║")
    print("╚══════════════════════════════════════════════════════════════════╝")


def print_positions(positions: List[Position]):
    """Pretty print positions."""
    if not positions:
        print("\nNo open positions.")
        return
    
    print("\n┌─────────────────────────────────────────────────────────────────────┐")
    print("│                           POSITIONS                                 │")
    print("├──────────┬────────┬───────────┬───────────┬──────────────┬──────────┤")
    print("│ Symbol   │   Qty  │  Avg Cost │  Current  │  Unrealized  │   P&L %  │")
    print("├──────────┼────────┼───────────┼───────────┼──────────────┼──────────┤")
    
    for p in positions:
        print(f"│ {p.symbol:<8} │ {p.qty:>6} │ ${p.avg_entry_price:>8.2f} │ "
              f"${p.current_price:>8.2f} │ ${p.unrealized_pnl:>+10.2f} │ {p.unrealized_pnl_pct:>+7.2f}% │")
    
    print("└──────────┴────────┴───────────┴───────────┴──────────────┴──────────┘")


def main():
    """CLI for testing Alpaca connection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpaca Trading Client")
    parser.add_argument("--status", action="store_true", help="Show account status")
    parser.add_argument("--positions", action="store_true", help="Show positions")
    parser.add_argument("--buy", nargs=2, metavar=("SYMBOL", "QTY"), help="Buy shares")
    parser.add_argument("--sell", nargs=2, metavar=("SYMBOL", "QTY"), help="Sell shares")
    parser.add_argument("--quote", metavar="SYMBOL", help="Get quote")
    parser.add_argument("--close", metavar="SYMBOL", help="Close position")
    parser.add_argument("--close-all", action="store_true", help="Close all positions")
    
    args = parser.parse_args()
    
    # Initialize client
    client = AlpacaClient()
    
    if not client.connect():
        print("\nFailed to connect. Check your API keys.")
        print("Set environment variables:")
        print("  export ALPACA_API_KEY=your_key")
        print("  export ALPACA_SECRET_KEY=your_secret")
        return
    
    # Handle commands
    if args.status or (not any([args.positions, args.buy, args.sell, args.quote, args.close, args.close_all])):
        account = client.get_account()
        print_account(account)
    
    if args.positions:
        positions = client.get_positions()
        print_positions(positions)
    
    if args.quote:
        quote = client.get_quote(args.quote)
        print(f"\n{quote.symbol}: Bid ${quote.bid:.2f} x {quote.bid_size} | "
              f"Ask ${quote.ask:.2f} x {quote.ask_size}")
    
    if args.buy:
        symbol, qty = args.buy
        order = client.buy(symbol, int(qty))
        print(f"\n[OK] Buy order placed: {order.qty} {order.symbol} - Status: {order.status}")
    
    if args.sell:
        symbol, qty = args.sell
        order = client.sell(symbol, int(qty))
        print(f"\n[OK] Sell order placed: {order.qty} {order.symbol} - Status: {order.status}")
    
    if args.close:
        order = client.close_position(args.close)
        print(f"\n[OK] Closed position: {order.symbol}")
    
    if args.close_all:
        orders = client.close_all_positions()
        print(f"\n[OK] Closed {len(orders)} positions")


if __name__ == "__main__":
    main()
