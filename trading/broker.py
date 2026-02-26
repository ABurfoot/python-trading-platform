#!/usr/bin/env python3
"""
Broker Integration Module
==========================
Connect to live brokers for real trading.

Supported Brokers:
- Interactive Brokers (IBKR) via ib_insync
- Alpaca (US stocks, commission-free)

Features:
- Live account data
- Real-time positions
- Order placement (market, limit, stop)
- Order management (modify, cancel)
- Trade history
- Portfolio sync
- Paper trading mode

Usage:
    from trading.broker import BrokerManager, Broker
    
    # Alpaca (easier setup)
    broker = BrokerManager(Broker.ALPACA)
    broker.connect()
    
    # Get account info
    account = broker.get_account()
    positions = broker.get_positions()
    
    # Place order
    order = broker.buy("AAPL", quantity=10, order_type="market")
    
    # Interactive Brokers
    broker = BrokerManager(Broker.IBKR)
    broker.connect(host="127.0.0.1", port=7497)  # TWS paper trading port
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from pathlib import Path
import urllib.request


class Broker(Enum):
    """Supported brokers."""
    ALPACA = "alpaca"
    IBKR = "ibkr"
    PAPER = "paper"  # Internal paper trading


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    """Time in force options."""
    DAY = "day"
    GTC = "gtc"  # Good til cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    OPG = "opg"  # Market on open
    CLS = "cls"  # Market on close


@dataclass
class BrokerAccount:
    """Broker account information."""
    account_id: str
    broker: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    margin_used: float = 0
    margin_available: float = 0
    day_trades_remaining: int = 0  # PDT rule
    is_paper: bool = False
    currency: str = "USD"
    status: str = "active"
    
    def to_dict(self) -> Dict:
        return {
            "account_id": self.account_id,
            "broker": self.broker,
            "buying_power": round(self.buying_power, 2),
            "cash": round(self.cash, 2),
            "portfolio_value": round(self.portfolio_value, 2),
            "equity": round(self.equity, 2),
            "margin_used": round(self.margin_used, 2),
            "margin_available": round(self.margin_available, 2),
            "day_trades_remaining": self.day_trades_remaining,
            "is_paper": self.is_paper,
            "currency": self.currency,
            "status": self.status
        }


@dataclass
class Position:
    """A position in a security."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    side: str = "long"  # long or short
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": round(self.avg_cost, 4),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
            "side": self.side
        }


@dataclass
class Order:
    """An order."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    status: OrderStatus
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: float = 0
    filled_price: float = 0
    time_in_force: TimeInForce = TimeInForce.DAY
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    broker: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "filled_quantity": self.filled_quantity,
            "filled_price": round(self.filled_price, 4) if self.filled_price else None,
            "time_in_force": self.time_in_force.value,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "broker": self.broker
        }


class AlpacaBroker:
    """
    Alpaca broker integration.
    
    Requires:
    - ALPACA_API_KEY
    - ALPACA_SECRET_KEY
    - ALPACA_PAPER (optional, default True for safety)
    """
    
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    
    def __init__(self, paper: bool = True):
        self.api_key = os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        self.paper = paper
        
        self.base_url = self.PAPER_URL if paper else self.LIVE_URL
        self.connected = False
        
        if not self.api_key or not self.secret_key:
            print("Warning: Alpaca API keys not set")
    
    def _request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make API request to Alpaca."""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }
        
        try:
            if data:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers=headers,
                    method=method
                )
            else:
                req = urllib.request.Request(url, headers=headers, method=method)
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            print(f"Alpaca API error: {e.code} - {error_body}")
            return None
        except Exception as e:
            print(f"Alpaca request error: {e}")
            return None
    
    def connect(self) -> bool:
        """Test connection to Alpaca."""
        account = self._request("GET", "/v2/account")
        if account:
            self.connected = True
            print(f"Connected to Alpaca ({'Paper' if self.paper else 'Live'})")
            return True
        return False
    
    def get_account(self) -> Optional[BrokerAccount]:
        """Get account information."""
        data = self._request("GET", "/v2/account")
        
        if not data:
            return None
        
        return BrokerAccount(
            account_id=data.get("account_number", ""),
            broker="alpaca",
            buying_power=float(data.get("buying_power", 0)),
            cash=float(data.get("cash", 0)),
            portfolio_value=float(data.get("portfolio_value", 0)),
            equity=float(data.get("equity", 0)),
            margin_used=float(data.get("initial_margin", 0)),
            margin_available=float(data.get("regt_buying_power", 0)),
            day_trades_remaining=int(data.get("daytrade_count", 0)),
            is_paper=self.paper,
            currency=data.get("currency", "USD"),
            status=data.get("status", "")
        )
    
    def get_positions(self) -> List[Position]:
        """Get all positions."""
        data = self._request("GET", "/v2/positions")
        
        if not data:
            return []
        
        positions = []
        for p in data:
            positions.append(Position(
                symbol=p.get("symbol", ""),
                quantity=float(p.get("qty", 0)),
                avg_cost=float(p.get("avg_entry_price", 0)),
                current_price=float(p.get("current_price", 0)),
                market_value=float(p.get("market_value", 0)),
                unrealized_pnl=float(p.get("unrealized_pl", 0)),
                unrealized_pnl_pct=float(p.get("unrealized_plpc", 0)) * 100,
                side="long" if float(p.get("qty", 0)) > 0 else "short"
            ))
        
        return positions
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        data = self._request("GET", f"/v2/positions/{symbol.upper()}")
        
        if not data:
            return None
        
        return Position(
            symbol=data.get("symbol", ""),
            quantity=float(data.get("qty", 0)),
            avg_cost=float(data.get("avg_entry_price", 0)),
            current_price=float(data.get("current_price", 0)),
            market_value=float(data.get("market_value", 0)),
            unrealized_pnl=float(data.get("unrealized_pl", 0)),
            unrealized_pnl_pct=float(data.get("unrealized_plpc", 0)) * 100,
            side="long" if float(data.get("qty", 0)) > 0 else "short"
        )
    
    def place_order(self, symbol: str, quantity: float, side: OrderSide,
                    order_type: OrderType = OrderType.MARKET,
                    limit_price: float = None, stop_price: float = None,
                    time_in_force: TimeInForce = TimeInForce.DAY) -> Optional[Order]:
        """Place an order."""
        order_data = {
            "symbol": symbol.upper(),
            "qty": str(quantity),
            "side": side.value,
            "type": order_type.value,
            "time_in_force": time_in_force.value
        }
        
        if limit_price and order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            order_data["limit_price"] = str(limit_price)
        
        if stop_price and order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            order_data["stop_price"] = str(stop_price)
        
        data = self._request("POST", "/v2/orders", order_data)
        
        if not data:
            return None
        
        return self._parse_order(data)
    
    def _parse_order(self, data: Dict) -> Order:
        """Parse order response."""
        status_map = {
            "new": OrderStatus.SUBMITTED,
            "accepted": OrderStatus.SUBMITTED,
            "pending_new": OrderStatus.PENDING,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED
        }
        
        return Order(
            order_id=data.get("id", ""),
            symbol=data.get("symbol", ""),
            side=OrderSide(data.get("side", "buy")),
            quantity=float(data.get("qty", 0)),
            order_type=OrderType(data.get("type", "market")),
            status=status_map.get(data.get("status", ""), OrderStatus.PENDING),
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
            filled_quantity=float(data.get("filled_qty", 0)),
            filled_price=float(data.get("filled_avg_price", 0)) if data.get("filled_avg_price") else 0,
            time_in_force=TimeInForce(data.get("time_in_force", "day")),
            submitted_at=datetime.fromisoformat(data["submitted_at"].replace("Z", "+00:00")) if data.get("submitted_at") else None,
            filled_at=datetime.fromisoformat(data["filled_at"].replace("Z", "+00:00")) if data.get("filled_at") else None,
            broker="alpaca"
        )
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        data = self._request("GET", f"/v2/orders/{order_id}")
        
        if not data:
            return None
        
        return self._parse_order(data)
    
    def get_orders(self, status: str = "open", limit: int = 50) -> List[Order]:
        """Get orders."""
        data = self._request("GET", f"/v2/orders?status={status}&limit={limit}")
        
        if not data:
            return []
        
        return [self._parse_order(o) for o in data]
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        result = self._request("DELETE", f"/v2/orders/{order_id}")
        return result is not None or True  # DELETE returns empty on success
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        self._request("DELETE", "/v2/orders")
        return True
    
    def close_position(self, symbol: str) -> Optional[Order]:
        """Close a position."""
        data = self._request("DELETE", f"/v2/positions/{symbol.upper()}")
        
        if data:
            return self._parse_order(data)
        return None
    
    def close_all_positions(self) -> bool:
        """Close all positions."""
        self._request("DELETE", "/v2/positions")
        return True


class IBKRBroker:
    """
    Interactive Brokers integration via ib_insync.
    
    Requires:
    - ib_insync package: pip install ib_insync
    - TWS or IB Gateway running
    
    Ports:
    - TWS Paper: 7497
    - TWS Live: 7496
    - Gateway Paper: 4002
    - Gateway Live: 4001
    """
    
    def __init__(self):
        self.ib = None
        self.connected = False
        
        try:
            from ib_insync import IB
            self.IB = IB
            self.ib_available = True
        except ImportError:
            self.ib_available = False
            print("Warning: ib_insync not installed. Install with: pip install ib_insync")
    
    def connect(self, host: str = "127.0.0.1", port: int = 7497, 
                client_id: int = 1, readonly: bool = False) -> bool:
        """
        Connect to TWS/Gateway.
        
        Args:
            host: TWS/Gateway host
            port: Port (7497=TWS paper, 7496=TWS live, 4002=Gateway paper)
            client_id: Client ID
            readonly: Read-only mode (no trading)
        """
        if not self.ib_available:
            print("ib_insync not available")
            return False
        
        try:
            self.ib = self.IB()
            self.ib.connect(host, port, clientId=client_id, readonly=readonly)
            self.connected = self.ib.isConnected()
            
            if self.connected:
                print(f"Connected to IBKR at {host}:{port}")
            
            return self.connected
        
        except Exception as e:
            print(f"IBKR connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib and self.connected:
            self.ib.disconnect()
            self.connected = False
    
    def get_account(self) -> Optional[BrokerAccount]:
        """Get account information."""
        if not self.connected:
            return None
        
        try:
            account_values = self.ib.accountValues()
            
            values = {}
            for av in account_values:
                values[av.tag] = av.value
            
            return BrokerAccount(
                account_id=values.get("AccountCode", ""),
                broker="ibkr",
                buying_power=float(values.get("BuyingPower", 0)),
                cash=float(values.get("CashBalance", 0)),
                portfolio_value=float(values.get("NetLiquidation", 0)),
                equity=float(values.get("EquityWithLoanValue", 0)),
                margin_used=float(values.get("MaintMarginReq", 0)),
                margin_available=float(values.get("AvailableFunds", 0)),
                is_paper="Paper" in values.get("AccountType", ""),
                currency=values.get("Currency", "USD")
            )
        
        except Exception as e:
            print(f"Error getting IBKR account: {e}")
            return None
    
    def get_positions(self) -> List[Position]:
        """Get all positions."""
        if not self.connected:
            return []
        
        try:
            positions = []
            
            for pos in self.ib.positions():
                contract = pos.contract
                qty = pos.position
                avg_cost = pos.avgCost
                
                # Get current price
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.ib.sleep(1)  # Wait for data
                
                current_price = ticker.marketPrice() or avg_cost
                market_value = qty * current_price
                unrealized_pnl = market_value - (qty * avg_cost)
                
                positions.append(Position(
                    symbol=contract.symbol,
                    quantity=qty,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=(unrealized_pnl / (qty * avg_cost) * 100) if avg_cost else 0,
                    side="long" if qty > 0 else "short"
                ))
            
            return positions
        
        except Exception as e:
            print(f"Error getting IBKR positions: {e}")
            return []
    
    def place_order(self, symbol: str, quantity: float, side: OrderSide,
                    order_type: OrderType = OrderType.MARKET,
                    limit_price: float = None, stop_price: float = None,
                    time_in_force: TimeInForce = TimeInForce.DAY) -> Optional[Order]:
        """Place an order."""
        if not self.connected or not self.ib_available:
            return None
        
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder, StopLimitOrder
            
            # Create contract
            contract = Stock(symbol.upper(), "SMART", "USD")
            self.ib.qualifyContracts(contract)
            
            # Determine action
            action = "BUY" if side == OrderSide.BUY else "SELL"
            
            # Create order
            if order_type == OrderType.MARKET:
                ib_order = MarketOrder(action, quantity)
            elif order_type == OrderType.LIMIT:
                ib_order = LimitOrder(action, quantity, limit_price)
            elif order_type == OrderType.STOP:
                ib_order = StopOrder(action, quantity, stop_price)
            elif order_type == OrderType.STOP_LIMIT:
                ib_order = StopLimitOrder(action, quantity, limit_price, stop_price)
            else:
                ib_order = MarketOrder(action, quantity)
            
            # Set time in force
            tif_map = {
                TimeInForce.DAY: "DAY",
                TimeInForce.GTC: "GTC",
                TimeInForce.IOC: "IOC",
                TimeInForce.FOK: "FOK"
            }
            ib_order.tif = tif_map.get(time_in_force, "DAY")
            
            # Place order
            trade = self.ib.placeOrder(contract, ib_order)
            self.ib.sleep(1)  # Wait for submission
            
            return Order(
                order_id=str(trade.order.orderId),
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status=OrderStatus.SUBMITTED,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force,
                submitted_at=datetime.now(),
                broker="ibkr"
            )
        
        except Exception as e:
            print(f"Error placing IBKR order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.connected:
            return False
        
        try:
            for trade in self.ib.openTrades():
                if str(trade.order.orderId) == order_id:
                    self.ib.cancelOrder(trade.order)
                    return True
            return False
        except Exception as e:
            print(f"Error cancelling IBKR order: {e}")
            return False


class BrokerManager:
    """
    Unified broker interface.
    
    Provides a consistent API across different brokers.
    """
    
    def __init__(self, broker: Broker = Broker.ALPACA, paper: bool = True):
        self.broker_type = broker
        self.paper = paper
        self._broker = None
        
        if broker == Broker.ALPACA:
            self._broker = AlpacaBroker(paper=paper)
        elif broker == Broker.IBKR:
            self._broker = IBKRBroker()
        else:
            print(f"Unknown broker: {broker}")
    
    def connect(self, **kwargs) -> bool:
        """Connect to broker."""
        if self._broker is None:
            return False
        
        return self._broker.connect(**kwargs)
    
    def disconnect(self):
        """Disconnect from broker."""
        if hasattr(self._broker, 'disconnect'):
            self._broker.disconnect()
    
    def get_account(self) -> Optional[BrokerAccount]:
        """Get account information."""
        if self._broker is None:
            return None
        return self._broker.get_account()
    
    def get_positions(self) -> List[Position]:
        """Get all positions."""
        if self._broker is None:
            return []
        return self._broker.get_positions()
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        if hasattr(self._broker, 'get_position'):
            return self._broker.get_position(symbol)
        
        # Fallback: search all positions
        for pos in self.get_positions():
            if pos.symbol.upper() == symbol.upper():
                return pos
        return None
    
    def buy(self, symbol: str, quantity: float, 
            order_type: OrderType = OrderType.MARKET,
            limit_price: float = None, stop_price: float = None,
            time_in_force: TimeInForce = TimeInForce.DAY) -> Optional[Order]:
        """Place a buy order."""
        return self._broker.place_order(
            symbol=symbol,
            quantity=quantity,
            side=OrderSide.BUY,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force
        )
    
    def sell(self, symbol: str, quantity: float,
             order_type: OrderType = OrderType.MARKET,
             limit_price: float = None, stop_price: float = None,
             time_in_force: TimeInForce = TimeInForce.DAY) -> Optional[Order]:
        """Place a sell order."""
        return self._broker.place_order(
            symbol=symbol,
            quantity=quantity,
            side=OrderSide.SELL,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force
        )
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        if hasattr(self._broker, 'get_order'):
            return self._broker.get_order(order_id)
        return None
    
    def get_orders(self, status: str = "open") -> List[Order]:
        """Get orders."""
        if hasattr(self._broker, 'get_orders'):
            return self._broker.get_orders(status=status)
        return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if self._broker is None:
            return False
        return self._broker.cancel_order(order_id)
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if hasattr(self._broker, 'cancel_all_orders'):
            return self._broker.cancel_all_orders()
        return False
    
    def close_position(self, symbol: str) -> Optional[Order]:
        """Close a position."""
        if hasattr(self._broker, 'close_position'):
            return self._broker.close_position(symbol)
        
        # Fallback: get position and sell
        pos = self.get_position(symbol)
        if pos and pos.quantity > 0:
            return self.sell(symbol, abs(pos.quantity))
        elif pos and pos.quantity < 0:
            return self.buy(symbol, abs(pos.quantity))
        return None
    
    def close_all_positions(self) -> bool:
        """Close all positions."""
        if hasattr(self._broker, 'close_all_positions'):
            return self._broker.close_all_positions()
        return False
    
    def print_account(self):
        """Print account summary."""
        account = self.get_account()
        
        if not account:
            print("Could not fetch account information")
            return
        
        print(f"\n{'='*50}")
        print(f"ACCOUNT SUMMARY - {account.broker.upper()}")
        print(f"{'='*50}")
        print(f"Account ID:      {account.account_id}")
        print(f"Status:          {account.status}")
        print(f"Paper Trading:   {'Yes' if account.is_paper else 'No'}")
        print(f"-"*50)
        print(f"Portfolio Value: ${account.portfolio_value:>12,.2f}")
        print(f"Cash:            ${account.cash:>12,.2f}")
        print(f"Buying Power:    ${account.buying_power:>12,.2f}")
        print(f"Equity:          ${account.equity:>12,.2f}")
        print(f"Margin Used:     ${account.margin_used:>12,.2f}")
        print(f"{'='*50}")
    
    def print_positions(self):
        """Print positions."""
        positions = self.get_positions()
        
        print(f"\n{'='*70}")
        print("POSITIONS")
        print(f"{'='*70}")
        
        if not positions:
            print("No open positions")
            return
        
        print(f"{'Symbol':<8} {'Qty':>8} {'Avg Cost':>10} {'Price':>10} {'Value':>12} {'P&L':>12}")
        print("-"*70)
        
        total_value = 0
        total_pnl = 0
        
        for pos in positions:
            pnl_color = "+" if pos.unrealized_pnl >= 0 else ""
            print(f"{pos.symbol:<8} {pos.quantity:>8.2f} ${pos.avg_cost:>9.2f} ${pos.current_price:>9.2f} "
                  f"${pos.market_value:>11,.2f} {pnl_color}${pos.unrealized_pnl:>10,.2f}")
            total_value += pos.market_value
            total_pnl += pos.unrealized_pnl
        
        print("-"*70)
        pnl_color = "+" if total_pnl >= 0 else ""
        print(f"{'TOTAL':<8} {'':<8} {'':<10} {'':<10} ${total_value:>11,.2f} {pnl_color}${total_pnl:>10,.2f}")
        print(f"{'='*70}")


# Convenience functions
def connect_alpaca(paper: bool = True) -> BrokerManager:
    """Quick connect to Alpaca."""
    broker = BrokerManager(Broker.ALPACA, paper=paper)
    broker.connect()
    return broker


def connect_ibkr(port: int = 7497) -> BrokerManager:
    """Quick connect to Interactive Brokers."""
    broker = BrokerManager(Broker.IBKR)
    broker.connect(port=port)
    return broker


if __name__ == "__main__":
    import sys
    
    print("Broker Integration Module")
    print("="*50)
    
    # Check for API keys
    has_alpaca = bool(os.environ.get("ALPACA_API_KEY"))
    
    if has_alpaca:
        print("\nConnecting to Alpaca (Paper)...")
        broker = connect_alpaca(paper=True)
        
        if broker._broker.connected:
            broker.print_account()
            broker.print_positions()
        else:
            print("Could not connect to Alpaca")
    else:
        print("\nAlpaca API keys not configured.")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.")
    
    print("\nUsage:")
    print("  from trading.broker import BrokerManager, Broker")
    print("  broker = BrokerManager(Broker.ALPACA, paper=True)")
    print("  broker.connect()")
    print("  broker.buy('AAPL', 10)")
