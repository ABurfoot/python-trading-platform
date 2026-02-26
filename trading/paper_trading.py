#!/usr/bin/env python3
"""
Live Paper Trading Simulator
=============================
Simulate trading in real-time with virtual money - no risk, real learning.

Features:
- Virtual cash account (default $100,000)
- Real-time price fetching
- Market, limit, and stop orders
- Order book with pending orders
- Position tracking with live P&L
- Trade history and performance metrics
- Realistic order execution simulation
- Support for stocks and crypto

Usage:
    from trading.paper_trading import PaperTradingSimulator
    
    # Create simulator with $100k virtual cash
    sim = PaperTradingSimulator(initial_cash=100000)
    
    # Place orders
    sim.market_buy("AAPL", 10)
    sim.limit_buy("MSFT", 20, limit_price=400.00)
    sim.market_sell("AAPL", 5)
    
    # Check status
    sim.print_portfolio()
    sim.print_orders()
    sim.print_performance()
    
    # Run continuous simulation
    sim.start_simulation(interval=30)  # Check prices every 30 seconds
"""

import os
import sys
import json
import uuid
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AssetType(Enum):
    """Asset type."""
    STOCK = "stock"
    CRYPTO = "crypto"
    ETF = "etf"


@dataclass
class Order:
    """A trading order."""
    id: str
    symbol: str
    side: str  # buy or sell
    order_type: str  # market, limit, stop
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "pending"
    filled_quantity: float = 0
    filled_price: float = 0
    created_at: str = ""
    filled_at: str = ""
    cancelled_at: str = ""
    asset_type: str = "stock"
    notes: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Order':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @property
    def is_active(self) -> bool:
        return self.status in ["pending", "partially_filled"]
    
    @property
    def value(self) -> float:
        if self.filled_quantity > 0:
            return self.filled_quantity * self.filled_price
        return self.quantity * (self.limit_price or 0)


@dataclass
class Position:
    """A portfolio position."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0
    asset_type: str = "stock"
    opened_at: str = ""
    
    def __post_init__(self):
        if not self.opened_at:
            self.opened_at = datetime.now().isoformat()
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "market_value": self.market_value,
            "cost_basis": self.cost_basis,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
        }


@dataclass
class Trade:
    """A completed trade."""
    id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    value: float
    commission: float = 0
    executed_at: str = ""
    pnl: float = 0  # Realized P&L for sells
    
    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class PerformanceMetrics:
    """Trading performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    largest_win: float = 0
    largest_loss: float = 0
    profit_factor: float = 0
    total_commission: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


class PaperTradingSimulator:
    """
    Paper trading simulator with real-time price updates.
    """
    
    def __init__(self, 
                 initial_cash: float = 100000.0,
                 commission: float = 0.0,
                 storage_path: str = None,
                 auto_save: bool = True):
        """
        Initialize paper trading simulator.
        
        Args:
            initial_cash: Starting virtual cash
            commission: Commission per trade (default 0 for simplicity)
            storage_path: Path to save/load state
            auto_save: Auto-save after each trade
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission = commission
        self.auto_save = auto_save
        
        # Storage
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".trading_platform" / "paper_trading.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # State
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.realized_pnl: float = 0
        
        # Simulation
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._price_cache: Dict[str, Tuple[float, datetime]] = {}
        self._price_cache_ttl = 10  # seconds
        
        # Callbacks
        self.on_fill: Optional[Callable[[Order, Trade], None]] = None
        self.on_price_update: Optional[Callable[[str, float], None]] = None
        
        # Load existing state
        self._load_state()
    
    # =========================================================================
    # PRICE FETCHING
    # =========================================================================
    
    def _get_price(self, symbol: str, force_refresh: bool = False) -> Optional[float]:
        """Get current price for a symbol."""
        symbol = symbol.upper()
        
        # Check cache
        if not force_refresh and symbol in self._price_cache:
            price, cached_at = self._price_cache[symbol]
            if datetime.now() - cached_at < timedelta(seconds=self._price_cache_ttl):
                return price
        
        price = None
        
        # Try data sources
        try:
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            quote, _ = fetcher.get_quote(symbol)
            if quote and quote.get("price"):
                price = quote["price"]
        except Exception:
            pass
        
        # Try crypto if stock failed
        if price is None:
            try:
                from trading.crypto import CryptoTracker
                ct = CryptoTracker()
                coin = ct.get_coin(symbol)
                if coin:
                    price = coin.price
            except Exception:
                pass
        
        # Cache the price
        if price is not None:
            self._price_cache[symbol] = (price, datetime.now())
            
            # Update position prices
            if symbol in self.positions:
                self.positions[symbol].current_price = price
        
        return price
    
    def _detect_asset_type(self, symbol: str) -> str:
        """Detect if symbol is stock, crypto, or ETF."""
        symbol = symbol.upper()
        
        # Common crypto symbols
        crypto_symbols = {"BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "AVAX", 
                         "DOT", "MATIC", "LINK", "UNI", "ATOM", "LTC", "SHIB"}
        if symbol in crypto_symbols:
            return "crypto"
        
        # Common ETFs
        etf_symbols = {"SPY", "QQQ", "IWM", "VTI", "VOO", "VAS", "VGS", "VDHG"}
        if symbol in etf_symbols:
            return "etf"
        
        return "stock"
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    def market_buy(self, symbol: str, quantity: float, notes: str = "") -> Optional[Order]:
        """
        Place a market buy order.
        
        Args:
            symbol: Stock/crypto symbol
            quantity: Number of shares/units
            notes: Optional notes
        
        Returns:
            Order object if successful
        """
        return self._place_order(symbol, OrderSide.BUY, OrderType.MARKET, quantity, notes=notes)
    
    def market_sell(self, symbol: str, quantity: float, notes: str = "") -> Optional[Order]:
        """Place a market sell order."""
        return self._place_order(symbol, OrderSide.SELL, OrderType.MARKET, quantity, notes=notes)
    
    def limit_buy(self, symbol: str, quantity: float, limit_price: float, notes: str = "") -> Optional[Order]:
        """
        Place a limit buy order.
        
        Args:
            symbol: Stock/crypto symbol
            quantity: Number of shares/units
            limit_price: Maximum price to pay
            notes: Optional notes
        
        Returns:
            Order object
        """
        return self._place_order(symbol, OrderSide.BUY, OrderType.LIMIT, quantity, 
                                limit_price=limit_price, notes=notes)
    
    def limit_sell(self, symbol: str, quantity: float, limit_price: float, notes: str = "") -> Optional[Order]:
        """Place a limit sell order."""
        return self._place_order(symbol, OrderSide.SELL, OrderType.LIMIT, quantity,
                                limit_price=limit_price, notes=notes)
    
    def stop_buy(self, symbol: str, quantity: float, stop_price: float, notes: str = "") -> Optional[Order]:
        """Place a stop buy order (triggers when price rises to stop_price)."""
        return self._place_order(symbol, OrderSide.BUY, OrderType.STOP, quantity,
                                stop_price=stop_price, notes=notes)
    
    def stop_sell(self, symbol: str, quantity: float, stop_price: float, notes: str = "") -> Optional[Order]:
        """Place a stop sell order (stop-loss)."""
        return self._place_order(symbol, OrderSide.SELL, OrderType.STOP, quantity,
                                stop_price=stop_price, notes=notes)
    
    def stop_limit_buy(self, symbol: str, quantity: float, stop_price: float, 
                       limit_price: float, notes: str = "") -> Optional[Order]:
        """Place a stop-limit buy order."""
        return self._place_order(symbol, OrderSide.BUY, OrderType.STOP_LIMIT, quantity,
                                stop_price=stop_price, limit_price=limit_price, notes=notes)
    
    def stop_limit_sell(self, symbol: str, quantity: float, stop_price: float,
                        limit_price: float, notes: str = "") -> Optional[Order]:
        """Place a stop-limit sell order."""
        return self._place_order(symbol, OrderSide.SELL, OrderType.STOP_LIMIT, quantity,
                                stop_price=stop_price, limit_price=limit_price, notes=notes)
    
    def _place_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                     quantity: float, limit_price: float = None, stop_price: float = None,
                     notes: str = "") -> Optional[Order]:
        """Internal method to place an order."""
        symbol = symbol.upper()
        
        # Validate quantity
        if quantity <= 0:
            print(f"[X] Invalid quantity: {quantity}")
            return None
        
        # For sell orders, check we have the position
        if side == OrderSide.SELL:
            position = self.positions.get(symbol)
            if not position or position.quantity < quantity:
                available = position.quantity if position else 0
                print(f"[X] Insufficient shares. Have: {available}, Want to sell: {quantity}")
                return None
        
        # For buy orders, check cash (estimate for market orders)
        if side == OrderSide.BUY:
            price = limit_price or self._get_price(symbol)
            if price is None:
                print(f"[X] Could not get price for {symbol}")
                return None
            
            estimated_cost = quantity * price + self.commission
            if estimated_cost > self.cash:
                print(f"[X] Insufficient cash. Have: ${self.cash:,.2f}, Need: ${estimated_cost:,.2f}")
                return None
        
        # Create order
        order = Order(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side.value,
            order_type=order_type.value,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            asset_type=self._detect_asset_type(symbol),
            notes=notes,
        )
        
        # Store order
        self.orders[order.id] = order
        
        # Try to execute immediately for market orders
        if order_type == OrderType.MARKET:
            self._try_execute_order(order)
        else:
            print(f"📝 Order placed: {side.value.upper()} {quantity} {symbol} @ {order_type.value}")
            if limit_price:
                print(f"   Limit: ${limit_price:,.2f}")
            if stop_price:
                print(f"   Stop: ${stop_price:,.2f}")
        
        if self.auto_save:
            self._save_state()
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id not in self.orders:
            print(f"[X] Order not found: {order_id}")
            return False
        
        order = self.orders[order_id]
        
        if not order.is_active:
            print(f"[X] Order {order_id} is not active (status: {order.status})")
            return False
        
        order.status = OrderStatus.CANCELLED.value
        order.cancelled_at = datetime.now().isoformat()
        
        print(f"[OK] Order {order_id} cancelled")
        
        if self.auto_save:
            self._save_state()
        
        return True
    
    def cancel_all_orders(self, symbol: str = None) -> int:
        """Cancel all pending orders, optionally for a specific symbol."""
        cancelled = 0
        
        for order in self.orders.values():
            if order.is_active:
                if symbol is None or order.symbol == symbol.upper():
                    order.status = OrderStatus.CANCELLED.value
                    order.cancelled_at = datetime.now().isoformat()
                    cancelled += 1
        
        print(f"[OK] Cancelled {cancelled} order(s)")
        
        if self.auto_save:
            self._save_state()
        
        return cancelled
    
    def _try_execute_order(self, order: Order) -> bool:
        """Try to execute an order based on current price."""
        price = self._get_price(order.symbol)
        
        if price is None:
            print(f"[X] Could not get price for {order.symbol}")
            order.status = OrderStatus.REJECTED.value
            return False
        
        should_fill = False
        fill_price = price
        
        if order.order_type == OrderType.MARKET.value:
            should_fill = True
            # Add slight slippage for realism (0.01%)
            if order.side == OrderSide.BUY.value:
                fill_price = price * 1.0001
            else:
                fill_price = price * 0.9999
        
        elif order.order_type == OrderType.LIMIT.value:
            if order.side == OrderSide.BUY.value and price <= order.limit_price:
                should_fill = True
                fill_price = min(price, order.limit_price)
            elif order.side == OrderSide.SELL.value and price >= order.limit_price:
                should_fill = True
                fill_price = max(price, order.limit_price)
        
        elif order.order_type == OrderType.STOP.value:
            if order.side == OrderSide.BUY.value and price >= order.stop_price:
                should_fill = True
                fill_price = price
            elif order.side == OrderSide.SELL.value and price <= order.stop_price:
                should_fill = True
                fill_price = price
        
        elif order.order_type == OrderType.STOP_LIMIT.value:
            if order.side == OrderSide.BUY.value:
                if price >= order.stop_price and price <= order.limit_price:
                    should_fill = True
                    fill_price = min(price, order.limit_price)
            else:
                if price <= order.stop_price and price >= order.limit_price:
                    should_fill = True
                    fill_price = max(price, order.limit_price)
        
        if should_fill:
            return self._fill_order(order, fill_price)
        
        return False
    
    def _fill_order(self, order: Order, fill_price: float) -> bool:
        """Fill an order at the given price."""
        quantity = order.quantity - order.filled_quantity
        value = quantity * fill_price
        commission = self.commission
        
        # Check cash for buys
        if order.side == OrderSide.BUY.value:
            total_cost = value + commission
            if total_cost > self.cash:
                print(f"[X] Insufficient cash to fill order")
                order.status = OrderStatus.REJECTED.value
                return False
            
            # Deduct cash
            self.cash -= total_cost
            
            # Update or create position
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                total_shares = pos.quantity + quantity
                total_cost = (pos.quantity * pos.avg_cost) + value
                pos.avg_cost = total_cost / total_shares
                pos.quantity = total_shares
                pos.current_price = fill_price
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=quantity,
                    avg_cost=fill_price,
                    current_price=fill_price,
                    asset_type=order.asset_type,
                )
            
            pnl = 0
        
        else:  # SELL
            # Calculate realized P&L
            pos = self.positions[order.symbol]
            cost_basis = quantity * pos.avg_cost
            pnl = value - cost_basis - commission
            self.realized_pnl += pnl
            
            # Add cash
            self.cash += value - commission
            
            # Update position
            pos.quantity -= quantity
            pos.current_price = fill_price
            
            # Remove position if fully closed
            if pos.quantity <= 0:
                del self.positions[order.symbol]
        
        # Update order
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.status = OrderStatus.FILLED.value
        order.filled_at = datetime.now().isoformat()
        
        # Create trade record
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=fill_price,
            value=value,
            commission=commission,
            pnl=pnl,
        )
        self.trades.append(trade)
        
        # Notify
        emoji = "[+]" if order.side == OrderSide.BUY.value else "[-]"
        print(f"{emoji} FILLED: {order.side.upper()} {quantity} {order.symbol} @ ${fill_price:,.2f}")
        if pnl != 0:
            pnl_emoji = "" if pnl > 0 else ""
            print(f"   {pnl_emoji} P&L: ${pnl:,.2f}")
        
        # Callback
        if self.on_fill:
            self.on_fill(order, trade)
        
        if self.auto_save:
            self._save_state()
        
        return True
    
    # =========================================================================
    # SIMULATION
    # =========================================================================
    
    def check_orders(self) -> int:
        """Check all pending orders and try to execute them."""
        filled = 0
        
        for order in list(self.orders.values()):
            if order.is_active:
                if self._try_execute_order(order):
                    filled += 1
        
        return filled
    
    def update_prices(self) -> Dict[str, float]:
        """Update prices for all positions."""
        prices = {}
        
        for symbol, position in self.positions.items():
            price = self._get_price(symbol, force_refresh=True)
            if price:
                position.current_price = price
                prices[symbol] = price
                
                if self.on_price_update:
                    self.on_price_update(symbol, price)
        
        return prices
    
    def start_simulation(self, interval: int = 30):
        """
        Start continuous simulation.
        
        Args:
            interval: Seconds between price checks
        """
        if self._running:
            print("Simulation already running")
            return
        
        self._running = True
        
        def simulation_loop():
            while self._running:
                try:
                    # Update prices
                    self.update_prices()
                    
                    # Check pending orders
                    self.check_orders()
                    
                except Exception as e:
                    print(f"Simulation error: {e}")
                
                time.sleep(interval)
        
        self._thread = threading.Thread(target=simulation_loop, daemon=True)
        self._thread.start()
        
        print(f" Simulation started (checking every {interval}s)")
        print("   Use sim.stop_simulation() to stop")
    
    def stop_simulation(self):
        """Stop the simulation."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("⏹️ Simulation stopped")
    
    # =========================================================================
    # PORTFOLIO & PERFORMANCE
    # =========================================================================
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value (cash + positions)."""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value
    
    def get_total_pnl(self) -> float:
        """Get total P&L (realized + unrealized)."""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.realized_pnl + unrealized
    
    def get_total_return(self) -> float:
        """Get total return percentage."""
        return ((self.get_portfolio_value() - self.initial_cash) / self.initial_cash) * 100
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics."""
        metrics = PerformanceMetrics()
        
        # Count trades
        sell_trades = [t for t in self.trades if t.side == "sell"]
        metrics.total_trades = len(sell_trades)
        
        if metrics.total_trades == 0:
            return metrics
        
        wins = [t for t in sell_trades if t.pnl > 0]
        losses = [t for t in sell_trades if t.pnl < 0]
        
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = (len(wins) / metrics.total_trades) * 100 if metrics.total_trades > 0 else 0
        
        # P&L metrics
        metrics.realized_pnl = self.realized_pnl
        metrics.unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        metrics.total_pnl = metrics.realized_pnl + metrics.unrealized_pnl
        
        if wins:
            metrics.avg_win = sum(t.pnl for t in wins) / len(wins)
            metrics.largest_win = max(t.pnl for t in wins)
        
        if losses:
            metrics.avg_loss = sum(t.pnl for t in losses) / len(losses)
            metrics.largest_loss = min(t.pnl for t in losses)
        
        # Profit factor
        total_wins = sum(t.pnl for t in wins) if wins else 0
        total_losses = abs(sum(t.pnl for t in losses)) if losses else 0
        metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Commission
        metrics.total_commission = sum(t.commission for t in self.trades)
        
        return metrics
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_portfolio(self):
        """Print portfolio summary."""
        portfolio_value = self.get_portfolio_value()
        total_pnl = self.get_total_pnl()
        total_return = self.get_total_return()
        
        print(f"\n{'='*70}")
        print("💼 PAPER TRADING PORTFOLIO")
        print(f"{'='*70}")
        
        print(f"\n SUMMARY")
        print("-"*50)
        print(f"   Initial Cash:    ${self.initial_cash:>14,.2f}")
        print(f"   Current Cash:    ${self.cash:>14,.2f}")
        print(f"   Positions Value: ${sum(p.market_value for p in self.positions.values()):>14,.2f}")
        print(f"   Portfolio Value: ${portfolio_value:>14,.2f}")
        print(f"   ")
        
        pnl_color = "" if total_pnl >= 0 else ""
        print(f"   {pnl_color} Total P&L:     ${total_pnl:>+14,.2f} ({total_return:+.2f}%)")
        print(f"   Realized P&L:    ${self.realized_pnl:>+14,.2f}")
        
        if self.positions:
            print(f"\n POSITIONS ({len(self.positions)})")
            print("-"*70)
            print(f"   {'Symbol':<8} {'Qty':>8} {'Avg Cost':>10} {'Price':>10} {'Value':>12} {'P&L':>12}")
            print(f"   {'-'*66}")
            
            for pos in sorted(self.positions.values(), key=lambda p: p.market_value, reverse=True):
                pnl_str = f"${pos.unrealized_pnl:+,.2f}"
                print(f"   {pos.symbol:<8} {pos.quantity:>8.2f} ${pos.avg_cost:>9.2f} ${pos.current_price:>9.2f} ${pos.market_value:>11,.2f} {pnl_str:>12}")
        else:
            print(f"\n   No open positions")
        
        print(f"\n{'='*70}\n")
    
    def print_orders(self, show_all: bool = False):
        """Print orders."""
        if show_all:
            orders = list(self.orders.values())
        else:
            orders = [o for o in self.orders.values() if o.is_active]
        
        print(f"\n{'='*70}")
        print(" ORDERS" + (" (All)" if show_all else " (Pending)"))
        print(f"{'='*70}")
        
        if not orders:
            print("\n   No orders\n")
            return
        
        print(f"\n   {'ID':<10} {'Symbol':<8} {'Side':<6} {'Type':<8} {'Qty':>8} {'Price':>10} {'Status':<12}")
        print(f"   {'-'*68}")
        
        for order in sorted(orders, key=lambda o: o.created_at, reverse=True):
            price_str = ""
            if order.limit_price:
                price_str = f"${order.limit_price:,.2f}"
            elif order.stop_price:
                price_str = f"${order.stop_price:,.2f}"
            else:
                price_str = "MARKET"
            
            status_emoji = {
                "pending": "⏳",
                "filled": "[Y]",
                "cancelled": "[X]",
                "rejected": "⛔",
            }.get(order.status, "")
            
            print(f"   {order.id:<10} {order.symbol:<8} {order.side.upper():<6} {order.order_type:<8} {order.quantity:>8.2f} {price_str:>10} {status_emoji} {order.status:<10}")
        
        print(f"\n{'='*70}\n")
    
    def print_trades(self, limit: int = 20):
        """Print trade history."""
        print(f"\n{'='*70}")
        print("📜 TRADE HISTORY")
        print(f"{'='*70}")
        
        if not self.trades:
            print("\n   No trades yet\n")
            return
        
        recent_trades = self.trades[-limit:]
        
        print(f"\n   {'Time':<12} {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10} {'Value':>12} {'P&L':>12}")
        print(f"   {'-'*72}")
        
        for trade in reversed(recent_trades):
            time_str = trade.executed_at[11:19] if trade.executed_at else ""
            pnl_str = f"${trade.pnl:+,.2f}" if trade.pnl != 0 else "-"
            
            emoji = "[+]" if trade.side == "buy" else "[-]"
            print(f"   {time_str:<12} {emoji} {trade.symbol:<6} {trade.side.upper():<6} {trade.quantity:>8.2f} ${trade.price:>9.2f} ${trade.value:>11,.2f} {pnl_str:>12}")
        
        print(f"\n   Showing {len(recent_trades)} of {len(self.trades)} trades")
        print(f"{'='*70}\n")
    
    def print_performance(self):
        """Print performance metrics."""
        metrics = self.get_performance_metrics()
        
        print(f"\n{'='*60}")
        print(" PERFORMANCE METRICS")
        print(f"{'='*60}")
        
        print(f"\n    P&L")
        print(f"   {'-'*40}")
        print(f"   Total P&L:        ${metrics.total_pnl:>+12,.2f}")
        print(f"   Realized P&L:     ${metrics.realized_pnl:>+12,.2f}")
        print(f"   Unrealized P&L:   ${metrics.unrealized_pnl:>+12,.2f}")
        print(f"   Total Return:     {self.get_total_return():>+12.2f}%")
        
        print(f"\n    TRADES")
        print(f"   {'-'*40}")
        print(f"   Total Trades:     {metrics.total_trades:>12}")
        print(f"   Winning Trades:   {metrics.winning_trades:>12}")
        print(f"   Losing Trades:    {metrics.losing_trades:>12}")
        print(f"   Win Rate:         {metrics.win_rate:>11.1f}%")
        
        if metrics.total_trades > 0:
            print(f"\n    AVERAGES")
            print(f"   {'-'*40}")
            print(f"   Avg Win:          ${metrics.avg_win:>+12,.2f}")
            print(f"   Avg Loss:         ${metrics.avg_loss:>+12,.2f}")
            print(f"   Largest Win:      ${metrics.largest_win:>+12,.2f}")
            print(f"   Largest Loss:     ${metrics.largest_loss:>+12,.2f}")
            print(f"   Profit Factor:    {metrics.profit_factor:>12.2f}")
        
        print(f"\n{'='*60}\n")
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _save_state(self):
        """Save state to disk."""
        state = {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "orders": {k: v.to_dict() for k, v in self.orders.items()},
            "trades": [t.to_dict() for t in self.trades],
            "saved_at": datetime.now().isoformat(),
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self):
        """Load state from disk."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                state = json.load(f)
            
            self.initial_cash = state.get("initial_cash", self.initial_cash)
            self.cash = state.get("cash", self.initial_cash)
            self.realized_pnl = state.get("realized_pnl", 0)
            
            self.positions = {
                k: Position(**{key: val for key, val in v.items() 
                              if key in Position.__dataclass_fields__})
                for k, v in state.get("positions", {}).items()
            }
            
            self.orders = {
                k: Order.from_dict(v)
                for k, v in state.get("orders", {}).items()
            }
            
            self.trades = [
                Trade(**{key: val for key, val in t.items() 
                        if key in Trade.__dataclass_fields__})
                for t in state.get("trades", [])
            ]
            
            print(f" Loaded paper trading state from {self.storage_path}")
            
        except Exception as e:
            print(f"Warning: Could not load state: {e}")
    
    def reset(self, confirm: bool = False):
        """Reset the simulator to initial state."""
        if not confirm:
            print("[WARN]  This will reset all positions, orders, and trades!")
            print("   Call reset(confirm=True) to confirm.")
            return
        
        self.cash = self.initial_cash
        self.positions = {}
        self.orders = {}
        self.trades = []
        self.realized_pnl = 0
        
        if self.auto_save:
            self._save_state()
        
        print(" Simulator reset to initial state")
    
    # =========================================================================
    # QUICK ACTIONS
    # =========================================================================
    
    def close_position(self, symbol: str) -> Optional[Order]:
        """Close entire position for a symbol."""
        symbol = symbol.upper()
        
        if symbol not in self.positions:
            print(f"[X] No position in {symbol}")
            return None
        
        quantity = self.positions[symbol].quantity
        return self.market_sell(symbol, quantity, notes="Close position")
    
    def close_all_positions(self) -> int:
        """Close all positions."""
        closed = 0
        
        for symbol in list(self.positions.keys()):
            if self.close_position(symbol):
                closed += 1
        
        return closed


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Paper Trading Simulator")
    parser.add_argument("--cash", type=float, default=100000, help="Initial cash")
    parser.add_argument("--buy", nargs=2, metavar=("SYMBOL", "QTY"), help="Market buy")
    parser.add_argument("--sell", nargs=2, metavar=("SYMBOL", "QTY"), help="Market sell")
    parser.add_argument("--portfolio", "-p", action="store_true", help="Show portfolio")
    parser.add_argument("--orders", "-o", action="store_true", help="Show orders")
    parser.add_argument("--trades", "-t", action="store_true", help="Show trades")
    parser.add_argument("--performance", action="store_true", help="Show performance")
    parser.add_argument("--reset", action="store_true", help="Reset simulator")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    sim = PaperTradingSimulator(initial_cash=args.cash)
    
    if args.buy:
        symbol, qty = args.buy
        sim.market_buy(symbol, float(qty))
    
    elif args.sell:
        symbol, qty = args.sell
        sim.market_sell(symbol, float(qty))
    
    elif args.portfolio:
        sim.print_portfolio()
    
    elif args.orders:
        sim.print_orders(show_all=True)
    
    elif args.trades:
        sim.print_trades()
    
    elif args.performance:
        sim.print_performance()
    
    elif args.reset:
        sim.reset(confirm=True)
    
    elif args.interactive:
        print(f"\n{'='*60}")
        print("🎮 PAPER TRADING SIMULATOR - Interactive Mode")
        print(f"{'='*60}")
        print(f"\nStarting cash: ${sim.initial_cash:,.2f}")
        print("\nCommands:")
        print("  buy SYMBOL QTY [PRICE]  - Buy (market or limit)")
        print("  sell SYMBOL QTY [PRICE] - Sell (market or limit)")
        print("  portfolio / p           - Show portfolio")
        print("  orders / o              - Show orders")
        print("  trades / t              - Show trades")
        print("  perf                    - Show performance")
        print("  close SYMBOL            - Close position")
        print("  cancel ORDER_ID         - Cancel order")
        print("  reset                   - Reset simulator")
        print("  quit / q                - Exit")
        print()
        
        while True:
            try:
                cmd = input(" > ").strip().lower().split()
                
                if not cmd:
                    continue
                
                if cmd[0] in ["quit", "q", "exit"]:
                    break
                
                elif cmd[0] == "buy" and len(cmd) >= 3:
                    symbol, qty = cmd[1], float(cmd[2])
                    if len(cmd) >= 4:
                        sim.limit_buy(symbol, qty, float(cmd[3]))
                    else:
                        sim.market_buy(symbol, qty)
                
                elif cmd[0] == "sell" and len(cmd) >= 3:
                    symbol, qty = cmd[1], float(cmd[2])
                    if len(cmd) >= 4:
                        sim.limit_sell(symbol, qty, float(cmd[3]))
                    else:
                        sim.market_sell(symbol, qty)
                
                elif cmd[0] in ["portfolio", "p"]:
                    sim.print_portfolio()
                
                elif cmd[0] in ["orders", "o"]:
                    sim.print_orders(show_all=True)
                
                elif cmd[0] in ["trades", "t"]:
                    sim.print_trades()
                
                elif cmd[0] == "perf":
                    sim.print_performance()
                
                elif cmd[0] == "close" and len(cmd) >= 2:
                    sim.close_position(cmd[1])
                
                elif cmd[0] == "cancel" and len(cmd) >= 2:
                    sim.cancel_order(cmd[1])
                
                elif cmd[0] == "reset":
                    confirm = input("Are you sure? (yes/no): ").strip().lower()
                    if confirm == "yes":
                        sim.reset(confirm=True)
                
                else:
                    print("Unknown command. Type 'quit' to exit.")
            
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("\nGoodbye! 👋")
    
    else:
        # Default: show portfolio
        sim.print_portfolio()


if __name__ == "__main__":
    main()
