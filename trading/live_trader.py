#!/usr/bin/env python3
"""
Live Trading Bot
================
Runs trading strategies in real-time with Alpaca paper trading.

Features:
- Real-time price monitoring
- Multiple strategy support
- Risk management (position limits, stop-loss)
- Trade logging and reporting

Usage:
    python live_trader.py --strategy ma_crossover --symbols AAPL MSFT
    python live_trader.py --strategy rsi --symbols AAPL --capital 50000
    python live_trader.py --dry-run --symbols AAPL  # Test without trading

Setup:
    export ALPACA_API_KEY=your_key
    export ALPACA_SECRET_KEY=your_secret
"""

import os
import sys
import time
import json
import signal
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.alpaca_client import AlpacaClient, AlpacaConfig, TradingMode


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_pct: float = 0.20      # Max 20% of portfolio in one stock
    max_positions: int = 10             # Max number of positions
    stop_loss_pct: float = 0.05         # 5% stop loss
    take_profit_pct: float = 0.15       # 15% take profit
    max_daily_loss_pct: float = 0.03    # Stop trading if down 3% in a day


@dataclass 
class StrategyConfig:
    """Strategy configuration."""
    name: str
    params: Dict = field(default_factory=dict)
    

@dataclass
class TradingConfig:
    """Overall trading configuration."""
    symbols: List[str]
    strategy: StrategyConfig
    risk: RiskConfig = field(default_factory=RiskConfig)
    capital: float = 100000
    check_interval: int = 60  # seconds between checks
    dry_run: bool = False     # If True, don't place real orders


# ============================================================================
# Price History Buffer
# ============================================================================

class PriceBuffer:
    """Maintains rolling window of prices for technical analysis."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.prices: Dict[str, List[float]] = {}
        self.timestamps: Dict[str, List[datetime]] = {}
    
    def add(self, symbol: str, price: float, timestamp: Optional[datetime] = None):
        """Add a price observation."""
        if symbol not in self.prices:
            self.prices[symbol] = []
            self.timestamps[symbol] = []
        
        self.prices[symbol].append(price)
        self.timestamps[symbol].append(timestamp or datetime.now())
        
        # Trim to max size
        if len(self.prices[symbol]) > self.max_size:
            self.prices[symbol] = self.prices[symbol][-self.max_size:]
            self.timestamps[symbol] = self.timestamps[symbol][-self.max_size:]
    
    def get(self, symbol: str) -> List[float]:
        """Get price history for a symbol."""
        return self.prices.get(symbol, [])
    
    def latest(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol."""
        prices = self.prices.get(symbol, [])
        return prices[-1] if prices else None
    
    def sma(self, symbol: str, period: int) -> Optional[float]:
        """Calculate SMA for a symbol."""
        prices = self.get(symbol)
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def ema(self, symbol: str, period: int) -> Optional[float]:
        """Calculate EMA for a symbol."""
        prices = self.get(symbol)
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate RSI for a symbol."""
        prices = self.get(symbol)
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        recent_gains = gains[-(period):]
        recent_losses = losses[-(period):]
        
        avg_gain = sum(recent_gains) / period
        avg_loss = sum(recent_losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


# ============================================================================
# Trading Signals
# ============================================================================

class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Strategy:
    """Base strategy class."""
    
    def __init__(self, params: Dict = None):
        self.params = params or {}
    
    def generate_signal(self, symbol: str, buffer: PriceBuffer) -> Signal:
        raise NotImplementedError


class MACrossoverStrategy(Strategy):
    """Moving Average Crossover strategy."""
    
    def generate_signal(self, symbol: str, buffer: PriceBuffer) -> Signal:
        fast_period = self.params.get("fast", 10)
        slow_period = self.params.get("slow", 30)
        
        fast_ema = buffer.ema(symbol, fast_period)
        slow_ema = buffer.ema(symbol, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return Signal.HOLD
        
        # Need previous values for crossover detection
        prices = buffer.get(symbol)
        if len(prices) < slow_period + 1:
            return Signal.HOLD
        
        # Calculate previous EMAs (approximate)
        prev_fast = buffer.ema(symbol, fast_period)  # Simplified
        prev_slow = buffer.ema(symbol, slow_period)
        
        # Crossover logic
        if fast_ema > slow_ema and prev_fast <= prev_slow:
            return Signal.BUY
        elif fast_ema < slow_ema and prev_fast >= prev_slow:
            return Signal.SELL
        
        return Signal.HOLD


class RSIStrategy(Strategy):
    """RSI mean reversion strategy."""
    
    def generate_signal(self, symbol: str, buffer: PriceBuffer) -> Signal:
        period = self.params.get("period", 14)
        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)
        
        rsi = buffer.rsi(symbol, period)
        
        if rsi is None:
            return Signal.HOLD
        
        if rsi < oversold:
            return Signal.BUY
        elif rsi > overbought:
            return Signal.SELL
        
        return Signal.HOLD


class MomentumStrategy(Strategy):
    """Momentum strategy."""
    
    def generate_signal(self, symbol: str, buffer: PriceBuffer) -> Signal:
        period = self.params.get("period", 20)
        threshold = self.params.get("threshold", 5.0)
        
        prices = buffer.get(symbol)
        if len(prices) < period:
            return Signal.HOLD
        
        momentum = (prices[-1] - prices[-period]) / prices[-period] * 100
        
        if momentum > threshold:
            return Signal.BUY
        elif momentum < -threshold:
            return Signal.SELL
        
        return Signal.HOLD


def get_strategy(name: str, params: Dict = None) -> Strategy:
    """Factory function for strategies."""
    strategies = {
        "ma_crossover": MACrossoverStrategy,
        "rsi": RSIStrategy,
        "momentum": MomentumStrategy,
    }
    
    if name not in strategies:
        raise ValueError(f"Unknown strategy: {name}")
    
    return strategies[name](params or {})


# ============================================================================
# Trade Logger
# ============================================================================

class TradeLogger:
    """Logs trades to file and console."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"trades_{timestamp}.json")
        self.trades = []
    
    def log_trade(self, symbol: str, side: str, qty: int, price: float, 
                  signal: Signal, pnl: float = 0):
        """Log a trade."""
        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "signal": signal.value,
            "pnl": pnl
        }
        self.trades.append(trade)
        
        # Write to file
        with open(self.log_file, "w") as f:
            json.dump(self.trades, f, indent=2)
        
        # Print to console
        print(f"  {'[+]' if side == 'buy' else '[-]'} {side.upper()} {qty} {symbol} @ ${price:.2f}")
    
    def log_status(self, message: str):
        """Log a status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def get_summary(self) -> Dict:
        """Get trading summary."""
        if not self.trades:
            return {"total_trades": 0}
        
        buys = [t for t in self.trades if t["side"] == "buy"]
        sells = [t for t in self.trades if t["side"] == "sell"]
        
        return {
            "total_trades": len(self.trades),
            "buys": len(buys),
            "sells": len(sells),
            "total_pnl": sum(t.get("pnl", 0) for t in self.trades)
        }


# ============================================================================
# Live Trader
# ============================================================================

class LiveTrader:
    """Main live trading engine."""
    
    def __init__(self, config: TradingConfig, client: AlpacaClient):
        self.config = config
        self.client = client
        self.strategy = get_strategy(config.strategy.name, config.strategy.params)
        self.buffer = PriceBuffer()
        self.logger = TradeLogger()
        self.running = False
        self.positions: Dict[str, int] = {}  # symbol -> qty
        self.entry_prices: Dict[str, float] = {}  # symbol -> entry price
        self.start_equity = 0
    
    def start(self):
        """Start the trading bot."""
        print("\n" + "=" * 60)
        print("           LIVE TRADING BOT")
        print("=" * 60)
        print(f"\nStrategy:    {self.config.strategy.name}")
        print(f"Symbols:     {', '.join(self.config.symbols)}")
        print(f"Capital:     ${self.config.capital:,.2f}")
        print(f"Dry Run:     {self.config.dry_run}")
        print(f"Interval:    {self.config.check_interval}s")
        print("\n" + "-" * 60)
        
        # Check market status
        if not self.client.is_market_open():
            self.logger.log_status("⚠ Market is closed")
            next_open, _ = self.client.get_market_hours()
            self.logger.log_status(f"  Next open: {next_open}")
        
        # Get starting equity
        account = self.client.get_account()
        self.start_equity = account.equity
        
        # Load existing positions
        self._load_positions()
        
        # Load initial price history
        self._load_history()
        
        # Start trading loop
        self.running = True
        self._run_loop()
    
    def stop(self):
        """Stop the trading bot."""
        self.running = False
        self.logger.log_status("Stopping trader...")
        
        # Print summary
        summary = self.logger.get_summary()
        print("\n" + "=" * 60)
        print("                    SESSION SUMMARY")
        print("=" * 60)
        print(f"  Total Trades:  {summary['total_trades']}")
        print(f"  Buys:          {summary.get('buys', 0)}")
        print(f"  Sells:         {summary.get('sells', 0)}")
        print(f"  P&L:           ${summary.get('total_pnl', 0):+,.2f}")
        print("=" * 60 + "\n")
    
    def _load_positions(self):
        """Load existing positions from broker."""
        positions = self.client.get_positions()
        for p in positions:
            if p.symbol in self.config.symbols:
                self.positions[p.symbol] = p.qty
                self.entry_prices[p.symbol] = p.avg_entry_price
                self.logger.log_status(f"Existing position: {p.qty} {p.symbol} @ ${p.avg_entry_price:.2f}")
    
    def _load_history(self):
        """Load initial price history for each symbol."""
        self.logger.log_status("Loading price history...")
        
        for symbol in self.config.symbols:
            try:
                bars = self.client.get_bars(symbol, "1Hour", limit=50)
                for bar in bars:
                    self.buffer.add(symbol, bar.close)
                self.logger.log_status(f"  {symbol}: {len(bars)} bars loaded")
            except Exception as e:
                self.logger.log_status(f"  {symbol}: Failed to load history - {e}")
    
    def _run_loop(self):
        """Main trading loop."""
        self.logger.log_status("Starting trading loop...")
        
        while self.running:
            try:
                self._check_signals()
                self._check_risk()
                time.sleep(self.config.check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.log_status(f"Error: {e}")
                time.sleep(10)
        
        self.stop()
    
    def _check_signals(self):
        """Check for trading signals on all symbols."""
        for symbol in self.config.symbols:
            try:
                # Get current price
                price = self.client.get_price(symbol)
                self.buffer.add(symbol, price)
                
                # Generate signal
                signal = self.strategy.generate_signal(symbol, self.buffer)
                
                # Execute signal
                if signal == Signal.BUY and symbol not in self.positions:
                    self._execute_buy(symbol, price)
                elif signal == Signal.SELL and symbol in self.positions:
                    self._execute_sell(symbol, price)
                    
            except Exception as e:
                self.logger.log_status(f"Error checking {symbol}: {e}")
    
    def _check_risk(self):
        """Check risk limits and stop-losses."""
        for symbol, qty in list(self.positions.items()):
            try:
                price = self.buffer.latest(symbol)
                if price is None:
                    continue
                
                entry = self.entry_prices.get(symbol, price)
                pnl_pct = (price - entry) / entry
                
                # Stop loss
                if pnl_pct < -self.config.risk.stop_loss_pct:
                    self.logger.log_status(f"⚠ Stop loss triggered for {symbol}")
                    self._execute_sell(symbol, price)
                
                # Take profit
                elif pnl_pct > self.config.risk.take_profit_pct:
                    self.logger.log_status(f"[OK] Take profit triggered for {symbol}")
                    self._execute_sell(symbol, price)
                    
            except Exception as e:
                self.logger.log_status(f"Error checking risk for {symbol}: {e}")
        
        # Check daily loss limit
        try:
            account = self.client.get_account()
            daily_pnl_pct = (account.equity - self.start_equity) / self.start_equity
            
            if daily_pnl_pct < -self.config.risk.max_daily_loss_pct:
                self.logger.log_status("⚠ Daily loss limit reached - stopping")
                self.running = False
        except Exception:
            pass
    
    def _execute_buy(self, symbol: str, price: float):
        """Execute a buy order."""
        # Calculate position size
        account = self.client.get_account()
        max_value = account.equity * self.config.risk.max_position_pct
        qty = int(max_value / price)
        
        if qty < 1:
            return
        
        # Check position limit
        if len(self.positions) >= self.config.risk.max_positions:
            self.logger.log_status(f"Max positions reached, skipping {symbol}")
            return
        
        # Execute
        if self.config.dry_run:
            self.logger.log_status(f"[DRY RUN] Would buy {qty} {symbol} @ ${price:.2f}")
        else:
            order = self.client.buy(symbol, qty)
            self.positions[symbol] = qty
            self.entry_prices[symbol] = price
            self.logger.log_trade(symbol, "buy", qty, price, Signal.BUY)
    
    def _execute_sell(self, symbol: str, price: float):
        """Execute a sell order."""
        qty = self.positions.get(symbol, 0)
        if qty == 0:
            return
        
        # Calculate P&L
        entry = self.entry_prices.get(symbol, price)
        pnl = (price - entry) * qty
        
        # Execute
        if self.config.dry_run:
            self.logger.log_status(f"[DRY RUN] Would sell {qty} {symbol} @ ${price:.2f} (P&L: ${pnl:+,.2f})")
        else:
            order = self.client.sell(symbol, qty)
            self.logger.log_trade(symbol, "sell", qty, price, Signal.SELL, pnl)
        
        # Update state
        del self.positions[symbol]
        if symbol in self.entry_prices:
            del self.entry_prices[symbol]


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Live Trading Bot")
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to trade")
    parser.add_argument("--strategy", default="ma_crossover", 
                        choices=["ma_crossover", "rsi", "momentum"],
                        help="Trading strategy")
    parser.add_argument("--capital", type=float, default=100000, help="Starting capital")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Paper trade without orders")
    parser.add_argument("--fast", type=int, default=10, help="Fast MA period")
    parser.add_argument("--slow", type=int, default=30, help="Slow MA period")
    
    args = parser.parse_args()
    
    # Build config
    strategy_params = {"fast": args.fast, "slow": args.slow}
    config = TradingConfig(
        symbols=args.symbols,
        strategy=StrategyConfig(name=args.strategy, params=strategy_params),
        capital=args.capital,
        check_interval=args.interval,
        dry_run=args.dry_run
    )
    
    # Initialize client
    client = AlpacaClient()
    if not client.connect():
        print("\nFailed to connect to Alpaca.")
        print("Set your API keys:")
        print("  export ALPACA_API_KEY=your_key")
        print("  export ALPACA_SECRET_KEY=your_secret")
        return
    
    # Handle Ctrl+C gracefully
    trader = LiveTrader(config, client)
    
    def signal_handler(sig, frame):
        trader.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start trading
    trader.start()


if __name__ == "__main__":
    main()
