#!/usr/bin/env python3
"""
Backtesting Engine
===================
Professional-grade backtesting for trading strategies.

Features:
- Multiple strategy types (MA crossover, RSI, breakout, custom)
- Walk-forward analysis
- Monte Carlo simulation
- Transaction costs and slippage modeling
- Detailed performance metrics
- Trade-by-trade analysis
- Equity curve generation
- Drawdown analysis
- Benchmark comparison

Usage:
    from trading.backtest_engine import BacktestEngine, Strategy, MACrossoverStrategy
    
    # Create engine
    engine = BacktestEngine(initial_capital=100000)
    
    # Use built-in strategy
    strategy = MACrossoverStrategy(fast_period=10, slow_period=30)
    
    # Run backtest
    results = engine.run(
        symbol="AAPL",
        strategy=strategy,
        start_date="2023-01-01",
        end_date="2024-01-01"
    )
    
    # Analyze results
    engine.print_report()
    engine.print_trades()
"""

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod
import statistics


class SignalType(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PositionType(Enum):
    """Position types."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    """A trading signal."""
    type: SignalType
    price: float
    date: str
    strength: float = 1.0  # 0-1, for position sizing
    reason: str = ""
    
    def is_buy(self) -> bool:
        return self.type == SignalType.BUY
    
    def is_sell(self) -> bool:
        return self.type == SignalType.SELL


@dataclass
class Trade:
    """A completed trade."""
    id: int
    symbol: str
    side: str  # long or short
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    holding_days: int
    entry_reason: str = ""
    exit_reason: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Position:
    """An open position."""
    symbol: str
    side: str
    entry_date: str
    entry_price: float
    quantity: float
    current_price: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    
    @property
    def unrealized_pnl(self) -> float:
        if self.side == "long":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0
        if self.side == "long":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100


@dataclass
class BacktestResults:
    """Results from a backtest run."""
    # Basic info
    symbol: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    
    # Returns
    total_return: float = 0
    total_return_pct: float = 0
    cagr: float = 0
    
    # Risk metrics
    volatility: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    max_drawdown: float = 0
    max_drawdown_pct: float = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    expectancy: float = 0
    
    # Time analysis
    avg_holding_days: float = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Costs
    total_commission: float = 0
    total_slippage: float = 0
    
    # Data
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[str, float]] = field(default_factory=list)
    drawdown_curve: List[Tuple[str, float]] = field(default_factory=list)
    
    # Benchmark
    benchmark_return: float = 0
    alpha: float = 0
    beta: float = 0
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data['trades'] = [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.trades]
        return data


# =============================================================================
# STRATEGY BASE CLASS
# =============================================================================

class Strategy(ABC):
    """Base class for trading strategies."""
    
    def __init__(self, name: str = "Strategy"):
        self.name = name
        self.params: Dict[str, Any] = {}
    
    @abstractmethod
    def generate_signal(self, data: List[Dict], current_index: int, 
                       position: Optional[Position] = None) -> Signal:
        """
        Generate trading signal based on data.
        
        Args:
            data: List of OHLCV dictionaries
            current_index: Current bar index
            position: Current open position (if any)
        
        Returns:
            Signal object
        """
        pass
    
    def initialize(self, data: List[Dict]):
        """Initialize strategy with historical data (optional override)."""
        pass
    
    def get_position_size(self, signal: Signal, capital: float, 
                         price: float) -> float:
        """
        Calculate position size.
        
        Args:
            signal: The trading signal
            capital: Available capital
            price: Current price
        
        Returns:
            Number of shares/units
        """
        # Default: use all available capital
        return int(capital / price)
    
    def __str__(self) -> str:
        return f"{self.name}({self.params})"


# =============================================================================
# BUILT-IN STRATEGIES
# =============================================================================

class MACrossoverStrategy(Strategy):
    """Moving Average Crossover Strategy."""
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__(name="MA_Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.params = {"fast": fast_period, "slow": slow_period}
    
    def _calculate_ma(self, data: List[Dict], period: int, end_index: int) -> float:
        """Calculate simple moving average."""
        if end_index < period - 1:
            return 0
        
        prices = [data[i]["close"] for i in range(end_index - period + 1, end_index + 1)]
        return sum(prices) / len(prices)
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        if current_index < self.slow_period:
            return Signal(SignalType.HOLD, data[current_index]["close"], 
                         data[current_index]["date"])
        
        fast_ma = self._calculate_ma(data, self.fast_period, current_index)
        slow_ma = self._calculate_ma(data, self.slow_period, current_index)
        
        fast_ma_prev = self._calculate_ma(data, self.fast_period, current_index - 1)
        slow_ma_prev = self._calculate_ma(data, self.slow_period, current_index - 1)
        
        price = data[current_index]["close"]
        date = data[current_index]["date"]
        
        # Golden cross - buy signal
        if fast_ma_prev <= slow_ma_prev and fast_ma > slow_ma:
            return Signal(SignalType.BUY, price, date, 
                         reason=f"Golden cross: Fast MA ({fast_ma:.2f}) > Slow MA ({slow_ma:.2f})")
        
        # Death cross - sell signal
        if fast_ma_prev >= slow_ma_prev and fast_ma < slow_ma:
            return Signal(SignalType.SELL, price, date,
                         reason=f"Death cross: Fast MA ({fast_ma:.2f}) < Slow MA ({slow_ma:.2f})")
        
        return Signal(SignalType.HOLD, price, date)


class RSIStrategy(Strategy):
    """RSI Overbought/Oversold Strategy."""
    
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__(name="RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.params = {"period": period, "oversold": oversold, "overbought": overbought}
    
    def _calculate_rsi(self, data: List[Dict], end_index: int) -> float:
        """Calculate RSI."""
        if end_index < self.period:
            return 50
        
        gains = []
        losses = []
        
        for i in range(end_index - self.period + 1, end_index + 1):
            change = data[i]["close"] - data[i - 1]["close"]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        if current_index < self.period:
            return Signal(SignalType.HOLD, data[current_index]["close"],
                         data[current_index]["date"])
        
        rsi = self._calculate_rsi(data, current_index)
        rsi_prev = self._calculate_rsi(data, current_index - 1)
        
        price = data[current_index]["close"]
        date = data[current_index]["date"]
        
        # Oversold bounce - buy signal
        if rsi_prev < self.oversold and rsi >= self.oversold:
            return Signal(SignalType.BUY, price, date,
                         strength=min(1.0, (self.oversold - rsi_prev) / 20),
                         reason=f"RSI bounced from oversold ({rsi_prev:.1f} -> {rsi:.1f})")
        
        # Overbought reversal - sell signal
        if rsi_prev > self.overbought and rsi <= self.overbought:
            return Signal(SignalType.SELL, price, date,
                         reason=f"RSI dropped from overbought ({rsi_prev:.1f} -> {rsi:.1f})")
        
        return Signal(SignalType.HOLD, price, date)


class BreakoutStrategy(Strategy):
    """Price Breakout Strategy."""
    
    def __init__(self, lookback: int = 20, volume_factor: float = 1.5):
        super().__init__(name="Breakout")
        self.lookback = lookback
        self.volume_factor = volume_factor
        self.params = {"lookback": lookback, "volume_factor": volume_factor}
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        if current_index < self.lookback:
            return Signal(SignalType.HOLD, data[current_index]["close"],
                         data[current_index]["date"])
        
        # Calculate high/low of lookback period
        highs = [data[i]["high"] for i in range(current_index - self.lookback, current_index)]
        lows = [data[i]["low"] for i in range(current_index - self.lookback, current_index)]
        
        resistance = max(highs)
        support = min(lows)
        
        current = data[current_index]
        price = current["close"]
        date = current["date"]
        
        # Volume confirmation (if available)
        volume_ok = True
        if "volume" in current and current_index > 0:
            avg_volume = statistics.mean(
                data[i].get("volume", 0) for i in range(current_index - self.lookback, current_index)
            )
            volume_ok = current.get("volume", 0) > avg_volume * self.volume_factor
        
        # Breakout above resistance
        if price > resistance and volume_ok:
            return Signal(SignalType.BUY, price, date,
                         reason=f"Breakout above resistance ({resistance:.2f})")
        
        # Breakdown below support (exit signal)
        if price < support and position:
            return Signal(SignalType.SELL, price, date,
                         reason=f"Breakdown below support ({support:.2f})")
        
        return Signal(SignalType.HOLD, price, date)


class MeanReversionStrategy(Strategy):
    """Mean Reversion using Bollinger Bands."""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__(name="MeanReversion")
        self.period = period
        self.std_dev = std_dev
        self.params = {"period": period, "std_dev": std_dev}
    
    def _calculate_bands(self, data: List[Dict], end_index: int) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if end_index < self.period - 1:
            return 0, 0, 0
        
        prices = [data[i]["close"] for i in range(end_index - self.period + 1, end_index + 1)]
        
        middle = statistics.mean(prices)
        std = statistics.stdev(prices) if len(prices) > 1 else 0
        
        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)
        
        return lower, middle, upper
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        if current_index < self.period:
            return Signal(SignalType.HOLD, data[current_index]["close"],
                         data[current_index]["date"])
        
        lower, middle, upper = self._calculate_bands(data, current_index)
        
        price = data[current_index]["close"]
        date = data[current_index]["date"]
        
        # Price below lower band - buy signal (expect reversion up)
        if price < lower:
            return Signal(SignalType.BUY, price, date,
                         strength=min(1.0, (lower - price) / lower * 10),
                         reason=f"Price below lower band ({lower:.2f})")
        
        # Price above upper band - sell signal (expect reversion down)
        if price > upper and position:
            return Signal(SignalType.SELL, price, date,
                         reason=f"Price above upper band ({upper:.2f})")
        
        # Price crosses middle band - take profit
        if position and position.side == "long":
            if price >= middle:
                return Signal(SignalType.SELL, price, date,
                             reason=f"Price reached middle band ({middle:.2f})")
        
        return Signal(SignalType.HOLD, price, date)


class BuyAndHoldStrategy(Strategy):
    """Simple Buy and Hold Strategy (benchmark)."""
    
    def __init__(self):
        super().__init__(name="BuyAndHold")
        self._bought = False
    
    def initialize(self, data: List[Dict]):
        self._bought = False
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        price = data[current_index]["close"]
        date = data[current_index]["date"]
        
        if not self._bought and not position:
            self._bought = True
            return Signal(SignalType.BUY, price, date, reason="Buy and hold entry")
        
        return Signal(SignalType.HOLD, price, date)


class CustomStrategy(Strategy):
    """Custom strategy using user-defined function."""
    
    def __init__(self, signal_func: Callable, name: str = "Custom"):
        super().__init__(name=name)
        self.signal_func = signal_func
    
    def generate_signal(self, data: List[Dict], current_index: int,
                       position: Optional[Position] = None) -> Signal:
        return self.signal_func(data, current_index, position)


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    """
    Professional backtesting engine.
    """
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 commission: float = 0.001,  # 0.1% per trade
                 slippage: float = 0.0005,   # 0.05% slippage
                 risk_free_rate: float = 0.05):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital
            commission: Commission rate (as decimal)
            slippage: Slippage rate (as decimal)
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission
        self.slippage_rate = slippage
        self.risk_free_rate = risk_free_rate
        
        # State
        self.capital = initial_capital
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[str, float]] = []
        self.daily_returns: List[float] = []
        
        # Results
        self.results: Optional[BacktestResults] = None
        
        # Data
        self._data: List[Dict] = []
        self._symbol: str = ""
        self._strategy: Optional[Strategy] = None
    
    # =========================================================================
    # DATA LOADING
    # =========================================================================
    
    def _fetch_data(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch historical data for backtesting."""
        # Try data sources
        try:
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            
            # Calculate days needed
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end - start).days + 60  # Extra buffer for indicators
            
            data = fetcher.get_historical(symbol, period=f"{days}d")
            
            if data:
                # Filter to date range
                filtered = []
                for d in data:
                    date = d.get("date", "")[:10]
                    if start_date <= date <= end_date:
                        filtered.append(d)
                return filtered
        except Exception:
            pass
        
        return []
    
    def load_data(self, data: List[Dict]):
        """
        Load data directly.
        
        Args:
            data: List of OHLCV dictionaries with keys: date, open, high, low, close, volume
        """
        self._data = data
    
    # =========================================================================
    # MAIN BACKTEST
    # =========================================================================
    
    def run(self, symbol: str, strategy: Strategy, 
            start_date: str = None, end_date: str = None,
            data: List[Dict] = None) -> BacktestResults:
        """
        Run backtest.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy instance
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data: Optional pre-loaded data
        
        Returns:
            BacktestResults object
        """
        self._symbol = symbol.upper()
        self._strategy = strategy
        
        # Reset state
        self.capital = self.initial_capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.daily_returns = []
        
        # Load data
        if data:
            self._data = data
        elif start_date and end_date:
            print(f" Loading data for {symbol}...")
            self._data = self._fetch_data(symbol, start_date, end_date)
        
        if not self._data:
            print(f"[X] No data available for {symbol}")
            return BacktestResults(
                symbol=symbol,
                strategy_name=strategy.name,
                start_date=start_date or "",
                end_date=end_date or "",
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
            )
        
        # Initialize strategy
        strategy.initialize(self._data)
        
        print(f" Running backtest: {strategy.name} on {symbol}")
        print(f"   Period: {self._data[0]['date'][:10]} to {self._data[-1]['date'][:10]}")
        print(f"   Data points: {len(self._data)}")
        
        # Run simulation
        trade_id = 0
        
        for i in range(len(self._data)):
            current_bar = self._data[i]
            date = current_bar["date"][:10]
            price = current_bar["close"]
            
            # Update position value
            if self.position:
                self.position.current_price = price
            
            # Generate signal
            signal = strategy.generate_signal(self._data, i, self.position)
            
            # Execute trades
            if signal.is_buy() and not self.position:
                # Calculate position size
                qty = strategy.get_position_size(signal, self.capital, price)
                
                if qty > 0:
                    # Apply slippage (buy at higher price)
                    entry_price = price * (1 + self.slippage_rate)
                    commission = entry_price * qty * self.commission_rate
                    
                    cost = entry_price * qty + commission
                    
                    if cost <= self.capital:
                        self.position = Position(
                            symbol=symbol,
                            side="long",
                            entry_date=date,
                            entry_price=entry_price,
                            quantity=qty,
                            current_price=price,
                        )
                        self.capital -= cost
            
            elif signal.is_sell() and self.position:
                # Apply slippage (sell at lower price)
                exit_price = price * (1 - self.slippage_rate)
                commission = exit_price * self.position.quantity * self.commission_rate
                slippage_cost = price * self.position.quantity * self.slippage_rate
                
                # Calculate P&L
                gross_pnl = (exit_price - self.position.entry_price) * self.position.quantity
                net_pnl = gross_pnl - commission
                pnl_pct = ((exit_price - self.position.entry_price) / self.position.entry_price) * 100
                
                # Calculate holding days
                try:
                    entry_dt = datetime.strptime(self.position.entry_date[:10], "%Y-%m-%d")
                    exit_dt = datetime.strptime(date[:10], "%Y-%m-%d")
                    holding_days = (exit_dt - entry_dt).days
                except Exception:
                    holding_days = 0
                
                # Record trade
                trade_id += 1
                trade = Trade(
                    id=trade_id,
                    symbol=symbol,
                    side="long",
                    entry_date=self.position.entry_date,
                    entry_price=self.position.entry_price,
                    exit_date=date,
                    exit_price=exit_price,
                    quantity=self.position.quantity,
                    pnl=net_pnl,
                    pnl_pct=pnl_pct,
                    commission=commission,
                    slippage=slippage_cost,
                    holding_days=holding_days,
                    entry_reason=signal.reason if hasattr(signal, 'reason') else "",
                    exit_reason=signal.reason,
                )
                self.trades.append(trade)
                
                # Update capital
                self.capital += exit_price * self.position.quantity - commission
                self.position = None
            
            # Record equity
            equity = self.capital
            if self.position:
                equity += self.position.current_price * self.position.quantity
            
            self.equity_curve.append((date, equity))
            
            # Calculate daily return
            if len(self.equity_curve) > 1:
                prev_equity = self.equity_curve[-2][1]
                if prev_equity > 0:
                    daily_return = (equity - prev_equity) / prev_equity
                    self.daily_returns.append(daily_return)
        
        # Close any remaining position
        if self.position:
            final_price = self._data[-1]["close"]
            exit_price = final_price * (1 - self.slippage_rate)
            commission = exit_price * self.position.quantity * self.commission_rate
            
            gross_pnl = (exit_price - self.position.entry_price) * self.position.quantity
            net_pnl = gross_pnl - commission
            pnl_pct = ((exit_price - self.position.entry_price) / self.position.entry_price) * 100
            
            trade_id += 1
            trade = Trade(
                id=trade_id,
                symbol=symbol,
                side="long",
                entry_date=self.position.entry_date,
                entry_price=self.position.entry_price,
                exit_date=self._data[-1]["date"][:10],
                exit_price=exit_price,
                quantity=self.position.quantity,
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                commission=commission,
                slippage=0,
                holding_days=0,
                exit_reason="End of backtest",
            )
            self.trades.append(trade)
            
            self.capital += exit_price * self.position.quantity - commission
            self.position = None
        
        # Calculate results
        self.results = self._calculate_results(symbol, strategy.name, 
                                               self._data[0]["date"][:10],
                                               self._data[-1]["date"][:10])
        
        print(f"[OK] Backtest complete: {len(self.trades)} trades")
        
        return self.results
    
    def _calculate_results(self, symbol: str, strategy_name: str,
                          start_date: str, end_date: str) -> BacktestResults:
        """Calculate backtest results and metrics."""
        results = BacktestResults(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            trades=self.trades,
            equity_curve=self.equity_curve,
        )
        
        # Returns
        results.total_return = self.capital - self.initial_capital
        results.total_return_pct = (results.total_return / self.initial_capital) * 100
        
        # CAGR
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            years = (end_dt - start_dt).days / 365.25
            if years > 0 and self.capital > 0:
                results.cagr = ((self.capital / self.initial_capital) ** (1 / years) - 1) * 100
        except Exception:
            pass
        
        # Risk metrics
        if len(self.daily_returns) > 1:
            results.volatility = statistics.stdev(self.daily_returns) * math.sqrt(252) * 100
            
            # Sharpe ratio
            daily_rf = self.risk_free_rate / 252
            excess_returns = [r - daily_rf for r in self.daily_returns]
            if statistics.stdev(self.daily_returns) > 0:
                results.sharpe_ratio = (statistics.mean(excess_returns) / 
                                       statistics.stdev(self.daily_returns)) * math.sqrt(252)
            
            # Sortino ratio
            downside_returns = [r for r in self.daily_returns if r < 0]
            if len(downside_returns) > 1:
                downside_std = statistics.stdev(downside_returns)
                if downside_std > 0:
                    results.sortino_ratio = (statistics.mean(excess_returns) * 252 / 
                                            (downside_std * math.sqrt(252)))
        
        # Drawdown
        if self.equity_curve:
            peak = self.equity_curve[0][1]
            max_dd = 0
            drawdowns = []
            
            for date, equity in self.equity_curve:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                drawdowns.append((date, dd))
                if dd > max_dd:
                    max_dd = dd
            
            results.max_drawdown_pct = max_dd * 100
            results.max_drawdown = max_dd * self.initial_capital
            results.drawdown_curve = drawdowns
            
            # Calmar ratio
            if results.max_drawdown_pct > 0:
                results.calmar_ratio = results.cagr / results.max_drawdown_pct
        
        # Trade statistics
        if self.trades:
            results.total_trades = len(self.trades)
            
            winners = [t for t in self.trades if t.pnl > 0]
            losers = [t for t in self.trades if t.pnl < 0]
            
            results.winning_trades = len(winners)
            results.losing_trades = len(losers)
            results.win_rate = (len(winners) / len(self.trades)) * 100
            
            if winners:
                results.avg_win = statistics.mean(t.pnl for t in winners)
            if losers:
                results.avg_loss = statistics.mean(t.pnl for t in losers)
            
            # Profit factor
            total_wins = sum(t.pnl for t in winners) if winners else 0
            total_losses = abs(sum(t.pnl for t in losers)) if losers else 0
            if total_losses > 0:
                results.profit_factor = total_wins / total_losses
            elif total_wins > 0:
                results.profit_factor = float('inf')
            
            # Expectancy
            results.expectancy = statistics.mean(t.pnl for t in self.trades)
            
            # Holding days
            holding_days = [t.holding_days for t in self.trades if t.holding_days > 0]
            if holding_days:
                results.avg_holding_days = statistics.mean(holding_days)
            
            # Streaks
            results.max_consecutive_wins, results.max_consecutive_losses = self._calculate_streaks()
            
            # Costs
            results.total_commission = sum(t.commission for t in self.trades)
            results.total_slippage = sum(t.slippage for t in self.trades)
        
        # Benchmark comparison (buy and hold)
        if self._data:
            start_price = self._data[0]["close"]
            end_price = self._data[-1]["close"]
            results.benchmark_return = ((end_price - start_price) / start_price) * 100
            results.alpha = results.total_return_pct - results.benchmark_return
        
        return results
    
    def _calculate_streaks(self) -> Tuple[int, int]:
        """Calculate max consecutive wins and losses."""
        if not self.trades:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in self.trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
        
        return max_wins, max_losses
    
    # =========================================================================
    # WALK-FORWARD ANALYSIS
    # =========================================================================
    
    def walk_forward(self, symbol: str, strategy: Strategy,
                     start_date: str, end_date: str,
                     in_sample_pct: float = 0.7,
                     num_folds: int = 5,
                     data: List[Dict] = None) -> Dict:
        """
        Perform walk-forward analysis.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy instance
            start_date: Start date
            end_date: End date
            in_sample_pct: Percentage of data for in-sample
            num_folds: Number of folds
            data: Optional pre-loaded data
        
        Returns:
            Dictionary with walk-forward results
        """
        # Load data
        if data:
            all_data = data
        else:
            all_data = self._fetch_data(symbol, start_date, end_date)
        
        if not all_data:
            return {"error": "No data available"}
        
        print(f"\n Walk-Forward Analysis: {num_folds} folds")
        print(f"   In-sample: {in_sample_pct*100:.0f}%, Out-of-sample: {(1-in_sample_pct)*100:.0f}%")
        
        fold_size = len(all_data) // num_folds
        results = []
        
        for fold in range(num_folds):
            fold_start = fold * fold_size
            fold_end = min((fold + 1) * fold_size, len(all_data))
            
            if fold_end - fold_start < 20:
                continue
            
            fold_data = all_data[fold_start:fold_end]
            
            # Split into in-sample and out-of-sample
            split_idx = int(len(fold_data) * in_sample_pct)
            
            in_sample = fold_data[:split_idx]
            out_sample = fold_data[split_idx:]
            
            if len(out_sample) < 5:
                continue
            
            # Run backtest on out-of-sample
            self.run(symbol, strategy, data=out_sample)
            
            if self.results:
                results.append({
                    "fold": fold + 1,
                    "start_date": out_sample[0]["date"][:10],
                    "end_date": out_sample[-1]["date"][:10],
                    "return_pct": self.results.total_return_pct,
                    "trades": self.results.total_trades,
                    "win_rate": self.results.win_rate,
                    "sharpe": self.results.sharpe_ratio,
                })
                
                print(f"   Fold {fold+1}: Return={self.results.total_return_pct:+.2f}%, "
                      f"Win Rate={self.results.win_rate:.1f}%")
        
        # Aggregate results
        if results:
            avg_return = statistics.mean(r["return_pct"] for r in results)
            avg_win_rate = statistics.mean(r["win_rate"] for r in results)
            
            print(f"\n    Average Return: {avg_return:+.2f}%")
            print(f"    Average Win Rate: {avg_win_rate:.1f}%")
            
            return {
                "folds": results,
                "avg_return": avg_return,
                "avg_win_rate": avg_win_rate,
                "total_folds": len(results),
            }
        
        return {"error": "No valid folds"}
    
    # =========================================================================
    # MONTE CARLO SIMULATION
    # =========================================================================
    
    def monte_carlo(self, num_simulations: int = 1000, 
                    confidence_level: float = 0.95) -> Dict:
        """
        Run Monte Carlo simulation on trade results.
        
        Args:
            num_simulations: Number of simulations
            confidence_level: Confidence level for VaR
        
        Returns:
            Dictionary with simulation results
        """
        if not self.trades:
            return {"error": "No trades to simulate"}
        
        print(f"\n🎲 Monte Carlo Simulation: {num_simulations} runs")
        
        trade_returns = [t.pnl_pct for t in self.trades]
        
        final_returns = []
        max_drawdowns = []
        
        for _ in range(num_simulations):
            # Randomly shuffle trades
            shuffled = random.choices(trade_returns, k=len(trade_returns))
            
            # Calculate cumulative return
            equity = 100
            peak = 100
            max_dd = 0
            
            for ret in shuffled:
                equity *= (1 + ret / 100)
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
            
            final_returns.append((equity - 100))
            max_drawdowns.append(max_dd * 100)
        
        # Calculate statistics
        final_returns.sort()
        max_drawdowns.sort(reverse=True)
        
        var_index = int((1 - confidence_level) * num_simulations)
        
        results = {
            "num_simulations": num_simulations,
            "confidence_level": confidence_level,
            "mean_return": statistics.mean(final_returns),
            "median_return": statistics.median(final_returns),
            "std_return": statistics.stdev(final_returns),
            "min_return": min(final_returns),
            "max_return": max(final_returns),
            "var": final_returns[var_index],  # Value at Risk
            "cvar": statistics.mean(final_returns[:var_index+1]),  # Conditional VaR
            "mean_max_drawdown": statistics.mean(max_drawdowns),
            "worst_drawdown": max(max_drawdowns),
            "percentile_5": final_returns[int(0.05 * num_simulations)],
            "percentile_25": final_returns[int(0.25 * num_simulations)],
            "percentile_75": final_returns[int(0.75 * num_simulations)],
            "percentile_95": final_returns[int(0.95 * num_simulations)],
        }
        
        print(f"   Mean Return: {results['mean_return']:+.2f}%")
        print(f"   VaR ({confidence_level*100:.0f}%): {results['var']:+.2f}%")
        print(f"   Worst Case: {results['min_return']:+.2f}%")
        print(f"   Best Case: {results['max_return']:+.2f}%")
        
        return results
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_report(self):
        """Print comprehensive backtest report."""
        if not self.results:
            print("No backtest results. Run backtest first.")
            return
        
        r = self.results
        
        print(f"\n{'='*70}")
        print(f" BACKTEST REPORT: {r.strategy_name}")
        print(f"{'='*70}")
        
        print(f"\n    OVERVIEW")
        print(f"   {'-'*50}")
        print(f"   Symbol:              {r.symbol:>15}")
        print(f"   Strategy:            {r.strategy_name:>15}")
        print(f"   Period:              {r.start_date} to {r.end_date}")
        print(f"   Initial Capital:     ${r.initial_capital:>14,.2f}")
        print(f"   Final Capital:       ${r.final_capital:>14,.2f}")
        
        print(f"\n    RETURNS")
        print(f"   {'-'*50}")
        print(f"   Total Return:        ${r.total_return:>+14,.2f}")
        print(f"   Total Return %:       {r.total_return_pct:>+14.2f}%")
        print(f"   CAGR:                 {r.cagr:>+14.2f}%")
        print(f"   Benchmark Return:     {r.benchmark_return:>+14.2f}%")
        print(f"   Alpha:                {r.alpha:>+14.2f}%")
        
        print(f"\n   [WARN]  RISK METRICS")
        print(f"   {'-'*50}")
        print(f"   Volatility (Ann.):    {r.volatility:>14.2f}%")
        print(f"   Sharpe Ratio:         {r.sharpe_ratio:>14.2f}")
        print(f"   Sortino Ratio:        {r.sortino_ratio:>14.2f}")
        print(f"   Calmar Ratio:         {r.calmar_ratio:>14.2f}")
        print(f"   Max Drawdown:         {r.max_drawdown_pct:>14.2f}%")
        
        print(f"\n    TRADE STATISTICS")
        print(f"   {'-'*50}")
        print(f"   Total Trades:         {r.total_trades:>14}")
        print(f"   Winning Trades:       {r.winning_trades:>14}")
        print(f"   Losing Trades:        {r.losing_trades:>14}")
        print(f"   Win Rate:             {r.win_rate:>13.1f}%")
        print(f"   Avg Win:             ${r.avg_win:>+14,.2f}")
        print(f"   Avg Loss:            ${r.avg_loss:>+14,.2f}")
        print(f"   Profit Factor:        {r.profit_factor:>14.2f}")
        print(f"   Expectancy:          ${r.expectancy:>+14,.2f}")
        print(f"   Avg Holding Days:     {r.avg_holding_days:>14.1f}")
        
        print(f"\n   🔥 STREAKS")
        print(f"   {'-'*50}")
        print(f"   Max Consec. Wins:     {r.max_consecutive_wins:>14}")
        print(f"   Max Consec. Losses:   {r.max_consecutive_losses:>14}")
        
        print(f"\n   💸 COSTS")
        print(f"   {'-'*50}")
        print(f"   Total Commission:    ${r.total_commission:>14,.2f}")
        print(f"   Total Slippage:      ${r.total_slippage:>14,.2f}")
        
        print(f"\n{'='*70}\n")
    
    def print_trades(self, limit: int = 20):
        """Print trade history."""
        if not self.trades:
            print("No trades to display.")
            return
        
        print(f"\n{'='*90}")
        print("📜 TRADE HISTORY")
        print(f"{'='*90}")
        
        print(f"\n   {'#':>3} {'Entry Date':<12} {'Exit Date':<12} {'Entry':>10} {'Exit':>10} {'Qty':>8} {'P&L':>12} {'%':>8}")
        print(f"   {'-'*86}")
        
        for trade in self.trades[:limit]:
            emoji = "[+]" if trade.pnl > 0 else "[-]" if trade.pnl < 0 else "[.]"
            print(f"   {trade.id:>3} {trade.entry_date:<12} {trade.exit_date:<12} "
                  f"${trade.entry_price:>9.2f} ${trade.exit_price:>9.2f} "
                  f"{trade.quantity:>8.0f} {emoji}${trade.pnl:>+10,.2f} {trade.pnl_pct:>+7.2f}%")
        
        if len(self.trades) > limit:
            print(f"\n   ... and {len(self.trades) - limit} more trades")
        
        print(f"\n{'='*90}\n")
    
    def print_equity_curve(self, width: int = 60):
        """Print ASCII equity curve."""
        if not self.equity_curve:
            print("No equity curve data.")
            return
        
        print(f"\n{'='*70}")
        print(" EQUITY CURVE")
        print(f"{'='*70}\n")
        
        values = [e[1] for e in self.equity_curve]
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            max_val = min_val + 1
        
        # Sample points
        step = max(1, len(values) // 20)
        sampled = [(self.equity_curve[i][0], values[i]) for i in range(0, len(values), step)]
        
        for date, value in sampled:
            bar_len = int((value - min_val) / (max_val - min_val) * width)
            bar = "█" * bar_len
            print(f"   {date[:10]} |{bar} ${value:,.0f}")
        
        print(f"\n{'='*70}\n")


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Backtest Engine")
    parser.add_argument("--demo", action="store_true", help="Run demo backtest")
    parser.add_argument("--symbol", "-s", default="AAPL", help="Symbol to backtest")
    parser.add_argument("--strategy", choices=["ma", "rsi", "breakout", "meanrev", "buyhold"],
                       default="ma", help="Strategy to use")
    parser.add_argument("--capital", "-c", type=float, default=100000, help="Initial capital")
    
    args = parser.parse_args()
    
    if args.demo:
        print("\n🎮 BACKTEST ENGINE DEMO")
        print("="*50)
        
        # Generate sample data
        sample_data = []
        price = 100.0
        date = datetime(2023, 1, 1)
        
        for i in range(252):  # 1 year of trading days
            # Random walk with slight upward bias
            change = random.gauss(0.0003, 0.02)
            price *= (1 + change)
            
            sample_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": price * (1 - random.uniform(0, 0.01)),
                "high": price * (1 + random.uniform(0, 0.02)),
                "low": price * (1 - random.uniform(0, 0.02)),
                "close": price,
                "volume": random.randint(1000000, 5000000),
            })
            
            date += timedelta(days=1)
            # Skip weekends
            while date.weekday() >= 5:
                date += timedelta(days=1)
        
        # Test different strategies
        strategies = [
            MACrossoverStrategy(fast_period=10, slow_period=30),
            RSIStrategy(period=14, oversold=30, overbought=70),
            MeanReversionStrategy(period=20, std_dev=2.0),
            BuyAndHoldStrategy(),
        ]
        
        engine = BacktestEngine(initial_capital=100000)
        
        print("\n Comparing Strategies on Simulated Data (1 Year)")
        print("-"*60)
        
        results_summary = []
        
        for strategy in strategies:
            results = engine.run("TEST", strategy, data=sample_data)
            results_summary.append({
                "strategy": strategy.name,
                "return": results.total_return_pct,
                "sharpe": results.sharpe_ratio,
                "max_dd": results.max_drawdown_pct,
                "trades": results.total_trades,
                "win_rate": results.win_rate,
            })
        
        # Print comparison
        print(f"\n   {'Strategy':<20} {'Return':>10} {'Sharpe':>10} {'Max DD':>10} {'Trades':>8} {'Win Rate':>10}")
        print(f"   {'-'*68}")
        
        for r in results_summary:
            print(f"   {r['strategy']:<20} {r['return']:>+9.2f}% {r['sharpe']:>10.2f} "
                  f"{r['max_dd']:>9.2f}% {r['trades']:>8} {r['win_rate']:>9.1f}%")
        
        # Show detailed report for best strategy
        best = max(results_summary, key=lambda x: x['return'])
        print(f"\n   🏆 Best Strategy: {best['strategy']} ({best['return']:+.2f}%)")
        
        # Run Monte Carlo on best
        print("\n" + "="*50)
        engine.run("TEST", MACrossoverStrategy(10, 30), data=sample_data)
        engine.monte_carlo(num_simulations=500)
        
        print("\n" + "="*50)
        print("Usage in code:")
        print("-"*40)
        print("""
from trading.backtest_engine import BacktestEngine, MACrossoverStrategy

engine = BacktestEngine(initial_capital=100000)
strategy = MACrossoverStrategy(fast_period=10, slow_period=30)

results = engine.run(
    symbol="AAPL",
    strategy=strategy,
    start_date="2023-01-01",
    end_date="2024-01-01"
)

engine.print_report()
engine.print_trades()

# Monte Carlo simulation
engine.monte_carlo(num_simulations=1000)

# Walk-forward analysis
engine.walk_forward("AAPL", strategy, "2022-01-01", "2024-01-01")
""")
    
    else:
        print("\nUsage: python -m trading.backtest_engine --demo")
        print("       python -m trading.backtest_engine --symbol AAPL --strategy ma")


if __name__ == "__main__":
    main()
