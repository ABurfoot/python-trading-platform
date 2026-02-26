#!/usr/bin/env python3
"""
Performance Analytics Module
=============================
Comprehensive trading performance analysis and risk metrics.

Features:
- Return metrics (total, CAGR, daily/monthly returns)
- Risk metrics (volatility, Sharpe ratio, Sortino ratio)
- Drawdown analysis (max drawdown, drawdown duration)
- Trade statistics (win rate, profit factor, expectancy)
- Benchmark comparison (vs S&P 500, custom benchmarks)
- Risk-adjusted returns (Calmar, Information ratio)
- Rolling performance windows

Usage:
    from trading.performance import PerformanceAnalyzer
    
    # Analyze a list of trades
    analyzer = PerformanceAnalyzer(initial_capital=100000)
    analyzer.add_trades(trades)
    
    # Or analyze from equity curve
    analyzer.set_equity_curve(dates, values)
    
    # Get metrics
    metrics = analyzer.calculate_all_metrics()
    analyzer.print_report()
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import statistics


@dataclass
class TradeRecord:
    """A single trade for analysis."""
    symbol: str
    side: str  # 'buy' or 'sell'
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    holding_days: int = 0
    
    def __post_init__(self):
        if self.holding_days == 0 and self.entry_date and self.exit_date:
            try:
                entry = datetime.fromisoformat(self.entry_date[:10])
                exit = datetime.fromisoformat(self.exit_date[:10])
                self.holding_days = (exit - entry).days
            except Exception:
                pass


@dataclass
class PerformanceMetrics:
    """Complete performance metrics."""
    # Return metrics
    total_return: float = 0
    total_return_pct: float = 0
    cagr: float = 0  # Compound Annual Growth Rate
    avg_daily_return: float = 0
    avg_monthly_return: float = 0
    
    # Risk metrics
    volatility: float = 0  # Annualized standard deviation
    downside_volatility: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    
    # Drawdown metrics
    max_drawdown: float = 0
    max_drawdown_pct: float = 0
    max_drawdown_duration: int = 0  # days
    avg_drawdown: float = 0
    current_drawdown: float = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    loss_rate: float = 0
    
    avg_win: float = 0
    avg_loss: float = 0
    avg_win_pct: float = 0
    avg_loss_pct: float = 0
    
    largest_win: float = 0
    largest_loss: float = 0
    largest_win_pct: float = 0
    largest_loss_pct: float = 0
    
    profit_factor: float = 0
    payoff_ratio: float = 0  # avg_win / avg_loss
    expectancy: float = 0  # Expected value per trade
    expectancy_pct: float = 0
    
    # Time metrics
    avg_holding_period: float = 0  # days
    avg_winning_hold: float = 0
    avg_losing_hold: float = 0
    
    # Streaks
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_streak: int = 0
    
    # Additional
    recovery_factor: float = 0  # total_return / max_drawdown
    risk_reward_ratio: float = 0
    ulcer_index: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkComparison:
    """Comparison against a benchmark."""
    benchmark_name: str
    benchmark_return: float
    portfolio_return: float
    alpha: float  # Excess return
    beta: float  # Market sensitivity
    correlation: float
    information_ratio: float
    tracking_error: float
    up_capture: float  # % of benchmark gains captured
    down_capture: float  # % of benchmark losses captured
    
    def to_dict(self) -> dict:
        return asdict(self)


class PerformanceAnalyzer:
    """
    Comprehensive performance analysis for trading.
    """
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 risk_free_rate: float = 0.05,
                 trading_days_per_year: int = 252):
        """
        Initialize performance analyzer.
        
        Args:
            initial_capital: Starting portfolio value
            risk_free_rate: Annual risk-free rate (default 5%)
            trading_days_per_year: Trading days per year (default 252)
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days_per_year
        
        # Data storage
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[Tuple[str, float]] = []  # (date, value)
        self.daily_returns: List[float] = []
        self.benchmark_returns: List[float] = []
        
        # Cached metrics
        self._metrics: Optional[PerformanceMetrics] = None
    
    # =========================================================================
    # DATA INPUT
    # =========================================================================
    
    def add_trade(self, symbol: str, side: str, entry_date: str, exit_date: str,
                  entry_price: float, exit_price: float, quantity: float) -> TradeRecord:
        """Add a single trade."""
        if side.lower() == 'long' or side.lower() == 'buy':
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:  # short
            pnl = (entry_price - exit_price) * quantity
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100
        
        trade = TradeRecord(
            symbol=symbol,
            side=side,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )
        
        self.trades.append(trade)
        self._metrics = None  # Invalidate cache
        return trade
    
    def add_trades(self, trades: List[Dict]) -> int:
        """
        Add multiple trades from a list of dicts.
        
        Expected format:
        [
            {
                "symbol": "AAPL",
                "side": "long",
                "entry_date": "2024-01-15",
                "exit_date": "2024-02-01",
                "entry_price": 150.00,
                "exit_price": 165.00,
                "quantity": 100
            },
            ...
        ]
        """
        count = 0
        for t in trades:
            try:
                self.add_trade(
                    symbol=t["symbol"],
                    side=t.get("side", "long"),
                    entry_date=t["entry_date"],
                    exit_date=t["exit_date"],
                    entry_price=t["entry_price"],
                    exit_price=t["exit_price"],
                    quantity=t.get("quantity", 1),
                )
                count += 1
            except (KeyError, ValueError) as e:
                continue
        
        return count
    
    def set_equity_curve(self, dates: List[str], values: List[float]):
        """Set equity curve from lists of dates and values."""
        if len(dates) != len(values):
            raise ValueError("Dates and values must have same length")
        
        self.equity_curve = list(zip(dates, values))
        self._calculate_daily_returns()
        self._metrics = None
    
    def add_equity_point(self, date: str, value: float):
        """Add a single point to the equity curve."""
        self.equity_curve.append((date, value))
        self._metrics = None
    
    def set_benchmark_returns(self, returns: List[float]):
        """Set benchmark returns for comparison."""
        self.benchmark_returns = returns
    
    def _calculate_daily_returns(self):
        """Calculate daily returns from equity curve."""
        if len(self.equity_curve) < 2:
            self.daily_returns = []
            return
        
        self.daily_returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = self.equity_curve[i-1][1]
            curr_value = self.equity_curve[i][1]
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                self.daily_returns.append(daily_return)
    
    def _build_equity_from_trades(self):
        """Build equity curve from trade records."""
        if not self.trades:
            return
        
        # Sort trades by exit date
        sorted_trades = sorted(self.trades, key=lambda t: t.exit_date)
        
        equity = self.initial_capital
        curve = [(sorted_trades[0].entry_date, equity)]
        
        for trade in sorted_trades:
            equity += trade.pnl
            curve.append((trade.exit_date, equity))
        
        self.equity_curve = curve
        self._calculate_daily_returns()
    
    # =========================================================================
    # RETURN METRICS
    # =========================================================================
    
    def _calculate_return_metrics(self, metrics: PerformanceMetrics):
        """Calculate return-based metrics."""
        if self.equity_curve:
            start_value = self.equity_curve[0][1]
            end_value = self.equity_curve[-1][1]
        elif self.trades:
            start_value = self.initial_capital
            end_value = self.initial_capital + sum(t.pnl for t in self.trades)
        else:
            return
        
        # Total return
        metrics.total_return = end_value - start_value
        metrics.total_return_pct = ((end_value - start_value) / start_value) * 100
        
        # CAGR
        if self.equity_curve and len(self.equity_curve) > 1:
            try:
                start_date = datetime.fromisoformat(self.equity_curve[0][0][:10])
                end_date = datetime.fromisoformat(self.equity_curve[-1][0][:10])
                years = (end_date - start_date).days / 365.25
                
                if years > 0 and end_value > 0 and start_value > 0:
                    metrics.cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
            except Exception:
                pass
        
        # Daily returns
        if self.daily_returns:
            metrics.avg_daily_return = statistics.mean(self.daily_returns) * 100
            metrics.avg_monthly_return = metrics.avg_daily_return * 21  # ~21 trading days/month
    
    # =========================================================================
    # RISK METRICS
    # =========================================================================
    
    def _calculate_risk_metrics(self, metrics: PerformanceMetrics):
        """Calculate risk-based metrics."""
        if not self.daily_returns or len(self.daily_returns) < 2:
            return
        
        # Volatility (annualized)
        daily_std = statistics.stdev(self.daily_returns)
        metrics.volatility = daily_std * math.sqrt(self.trading_days) * 100
        
        # Downside volatility (only negative returns)
        negative_returns = [r for r in self.daily_returns if r < 0]
        if len(negative_returns) >= 2:
            downside_std = statistics.stdev(negative_returns)
            metrics.downside_volatility = downside_std * math.sqrt(self.trading_days) * 100
        
        # Sharpe Ratio
        daily_rf = self.risk_free_rate / self.trading_days
        excess_returns = [r - daily_rf for r in self.daily_returns]
        
        if daily_std > 0:
            sharpe_daily = statistics.mean(excess_returns) / daily_std
            metrics.sharpe_ratio = sharpe_daily * math.sqrt(self.trading_days)
        
        # Sortino Ratio
        if metrics.downside_volatility > 0:
            avg_excess_return = statistics.mean(excess_returns) * self.trading_days * 100
            metrics.sortino_ratio = avg_excess_return / metrics.downside_volatility
        
        # Calmar Ratio
        if metrics.max_drawdown_pct > 0 and metrics.cagr != 0:
            metrics.calmar_ratio = metrics.cagr / abs(metrics.max_drawdown_pct)
    
    # =========================================================================
    # DRAWDOWN METRICS
    # =========================================================================
    
    def _calculate_drawdown_metrics(self, metrics: PerformanceMetrics):
        """Calculate drawdown metrics."""
        if not self.equity_curve:
            return
        
        values = [v for _, v in self.equity_curve]
        
        if not values:
            return
        
        # Calculate drawdown series
        peak = values[0]
        drawdowns = []
        drawdown_start = 0
        max_dd_duration = 0
        current_dd_duration = 0
        
        for i, value in enumerate(values):
            if value > peak:
                peak = value
                if current_dd_duration > max_dd_duration:
                    max_dd_duration = current_dd_duration
                current_dd_duration = 0
                drawdown_start = i
            else:
                current_dd_duration = i - drawdown_start
            
            drawdown = (peak - value) / peak if peak > 0 else 0
            drawdowns.append(drawdown)
        
        if drawdowns:
            metrics.max_drawdown_pct = max(drawdowns) * 100
            metrics.max_drawdown = metrics.max_drawdown_pct * self.initial_capital / 100
            metrics.avg_drawdown = statistics.mean(drawdowns) * 100
            metrics.current_drawdown = drawdowns[-1] * 100
            metrics.max_drawdown_duration = max_dd_duration
        
        # Ulcer Index (RMS of drawdowns)
        if drawdowns:
            squared_dd = [d ** 2 for d in drawdowns]
            metrics.ulcer_index = math.sqrt(statistics.mean(squared_dd)) * 100
        
        # Recovery Factor
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = metrics.total_return / metrics.max_drawdown
    
    # =========================================================================
    # TRADE STATISTICS
    # =========================================================================
    
    def _calculate_trade_statistics(self, metrics: PerformanceMetrics):
        """Calculate trade-based statistics."""
        if not self.trades:
            return
        
        metrics.total_trades = len(self.trades)
        
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl < 0]
        
        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        
        # Win/Loss rates
        metrics.win_rate = (len(winners) / len(self.trades)) * 100 if self.trades else 0
        metrics.loss_rate = (len(losers) / len(self.trades)) * 100 if self.trades else 0
        
        # Average win/loss
        if winners:
            metrics.avg_win = statistics.mean(t.pnl for t in winners)
            metrics.avg_win_pct = statistics.mean(t.pnl_pct for t in winners)
            metrics.largest_win = max(t.pnl for t in winners)
            metrics.largest_win_pct = max(t.pnl_pct for t in winners)
        
        if losers:
            metrics.avg_loss = statistics.mean(t.pnl for t in losers)
            metrics.avg_loss_pct = statistics.mean(t.pnl_pct for t in losers)
            metrics.largest_loss = min(t.pnl for t in losers)
            metrics.largest_loss_pct = min(t.pnl_pct for t in losers)
        
        # Profit factor
        total_wins = sum(t.pnl for t in winners) if winners else 0
        total_losses = abs(sum(t.pnl for t in losers)) if losers else 0
        
        if total_losses > 0:
            metrics.profit_factor = total_wins / total_losses
        elif total_wins > 0:
            metrics.profit_factor = float('inf')
        
        # Payoff ratio (risk/reward)
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)
            metrics.risk_reward_ratio = metrics.payoff_ratio
        
        # Expectancy (expected value per trade)
        win_prob = metrics.win_rate / 100
        loss_prob = metrics.loss_rate / 100
        metrics.expectancy = (win_prob * metrics.avg_win) + (loss_prob * metrics.avg_loss)
        
        if self.trades:
            avg_trade_value = statistics.mean(t.entry_price * t.quantity for t in self.trades)
            if avg_trade_value > 0:
                metrics.expectancy_pct = (metrics.expectancy / avg_trade_value) * 100
        
        # Holding periods
        holding_days = [t.holding_days for t in self.trades if t.holding_days > 0]
        if holding_days:
            metrics.avg_holding_period = statistics.mean(holding_days)
        
        winner_holds = [t.holding_days for t in winners if t.holding_days > 0]
        loser_holds = [t.holding_days for t in losers if t.holding_days > 0]
        
        if winner_holds:
            metrics.avg_winning_hold = statistics.mean(winner_holds)
        if loser_holds:
            metrics.avg_losing_hold = statistics.mean(loser_holds)
        
        # Streaks
        self._calculate_streaks(metrics)
    
    def _calculate_streaks(self, metrics: PerformanceMetrics):
        """Calculate win/loss streaks."""
        if not self.trades:
            return
        
        # Sort by exit date
        sorted_trades = sorted(self.trades, key=lambda t: t.exit_date)
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        current_streak = 0
        
        for trade in sorted_trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
                current_streak = current_wins
            elif trade.pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
                current_streak = -current_losses
            else:
                current_wins = 0
                current_losses = 0
        
        metrics.max_consecutive_wins = max_wins
        metrics.max_consecutive_losses = max_losses
        metrics.current_streak = current_streak
    
    # =========================================================================
    # BENCHMARK COMPARISON
    # =========================================================================
    
    def compare_to_benchmark(self, benchmark_returns: List[float] = None,
                             benchmark_name: str = "Benchmark") -> Optional[BenchmarkComparison]:
        """
        Compare portfolio performance to a benchmark.
        
        Args:
            benchmark_returns: List of benchmark daily returns (as decimals)
            benchmark_name: Name of the benchmark
        
        Returns:
            BenchmarkComparison object
        """
        if benchmark_returns is None:
            benchmark_returns = self.benchmark_returns
        
        if not benchmark_returns or not self.daily_returns:
            return None
        
        # Ensure same length
        min_len = min(len(benchmark_returns), len(self.daily_returns))
        bench_ret = benchmark_returns[:min_len]
        port_ret = self.daily_returns[:min_len]
        
        # Calculate cumulative returns
        bench_cumulative = 1
        port_cumulative = 1
        for b, p in zip(bench_ret, port_ret):
            bench_cumulative *= (1 + b)
            port_cumulative *= (1 + p)
        
        bench_total = (bench_cumulative - 1) * 100
        port_total = (port_cumulative - 1) * 100
        
        # Alpha (excess return)
        alpha = port_total - bench_total
        
        # Beta (covariance / variance)
        if len(bench_ret) > 1:
            bench_mean = statistics.mean(bench_ret)
            port_mean = statistics.mean(port_ret)
            
            covariance = sum((p - port_mean) * (b - bench_mean) 
                           for p, b in zip(port_ret, bench_ret)) / (len(bench_ret) - 1)
            bench_variance = statistics.variance(bench_ret)
            
            beta = covariance / bench_variance if bench_variance > 0 else 0
            
            # Correlation
            port_std = statistics.stdev(port_ret)
            bench_std = statistics.stdev(bench_ret)
            
            if port_std > 0 and bench_std > 0:
                correlation = covariance / (port_std * bench_std)
            else:
                correlation = 0
            
            # Tracking error
            tracking_diff = [p - b for p, b in zip(port_ret, bench_ret)]
            tracking_error = statistics.stdev(tracking_diff) * math.sqrt(self.trading_days) * 100
            
            # Information ratio
            excess_return = statistics.mean(tracking_diff) * self.trading_days * 100
            information_ratio = excess_return / tracking_error if tracking_error > 0 else 0
        else:
            beta = 0
            correlation = 0
            tracking_error = 0
            information_ratio = 0
        
        # Up/Down capture
        up_bench = [i for i, b in enumerate(bench_ret) if b > 0]
        down_bench = [i for i, b in enumerate(bench_ret) if b < 0]
        
        if up_bench:
            up_capture = (sum(port_ret[i] for i in up_bench) / 
                         sum(bench_ret[i] for i in up_bench)) * 100
        else:
            up_capture = 0
        
        if down_bench:
            down_capture = (sum(port_ret[i] for i in down_bench) / 
                          sum(bench_ret[i] for i in down_bench)) * 100
        else:
            down_capture = 0
        
        return BenchmarkComparison(
            benchmark_name=benchmark_name,
            benchmark_return=bench_total,
            portfolio_return=port_total,
            alpha=alpha,
            beta=beta,
            correlation=correlation,
            information_ratio=information_ratio,
            tracking_error=tracking_error,
            up_capture=up_capture,
            down_capture=down_capture,
        )
    
    # =========================================================================
    # MAIN CALCULATION
    # =========================================================================
    
    def calculate_all_metrics(self) -> PerformanceMetrics:
        """Calculate all performance metrics."""
        if self._metrics is not None:
            return self._metrics
        
        # Build equity curve from trades if needed
        if not self.equity_curve and self.trades:
            self._build_equity_from_trades()
        
        metrics = PerformanceMetrics()
        
        self._calculate_return_metrics(metrics)
        self._calculate_drawdown_metrics(metrics)
        self._calculate_risk_metrics(metrics)
        self._calculate_trade_statistics(metrics)
        
        self._metrics = metrics
        return metrics
    
    # =========================================================================
    # ROLLING METRICS
    # =========================================================================
    
    def calculate_rolling_sharpe(self, window: int = 60) -> List[Tuple[str, float]]:
        """Calculate rolling Sharpe ratio."""
        if len(self.daily_returns) < window:
            return []
        
        results = []
        daily_rf = self.risk_free_rate / self.trading_days
        
        for i in range(window, len(self.daily_returns) + 1):
            window_returns = self.daily_returns[i-window:i]
            excess = [r - daily_rf for r in window_returns]
            
            if statistics.stdev(window_returns) > 0:
                sharpe = (statistics.mean(excess) / statistics.stdev(window_returns)) * math.sqrt(self.trading_days)
            else:
                sharpe = 0
            
            if i < len(self.equity_curve):
                date = self.equity_curve[i][0]
            else:
                date = str(i)
            
            results.append((date, sharpe))
        
        return results
    
    def calculate_rolling_volatility(self, window: int = 30) -> List[Tuple[str, float]]:
        """Calculate rolling volatility."""
        if len(self.daily_returns) < window:
            return []
        
        results = []
        
        for i in range(window, len(self.daily_returns) + 1):
            window_returns = self.daily_returns[i-window:i]
            vol = statistics.stdev(window_returns) * math.sqrt(self.trading_days) * 100
            
            if i < len(self.equity_curve):
                date = self.equity_curve[i][0]
            else:
                date = str(i)
            
            results.append((date, vol))
        
        return results
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_report(self):
        """Print a comprehensive performance report."""
        metrics = self.calculate_all_metrics()
        
        print(f"\n{'='*70}")
        print(" PERFORMANCE ANALYTICS REPORT")
        print(f"{'='*70}")
        
        # Returns Section
        print(f"\n RETURNS")
        print("-"*50)
        print(f"   Total Return:        ${metrics.total_return:>+14,.2f}")
        print(f"   Total Return %:       {metrics.total_return_pct:>+14.2f}%")
        print(f"   CAGR:                 {metrics.cagr:>+14.2f}%")
        print(f"   Avg Daily Return:     {metrics.avg_daily_return:>+14.4f}%")
        print(f"   Avg Monthly Return:   {metrics.avg_monthly_return:>+14.2f}%")
        
        # Risk Section
        print(f"\n[WARN]  RISK METRICS")
        print("-"*50)
        print(f"   Volatility (Ann.):    {metrics.volatility:>14.2f}%")
        print(f"   Downside Vol:         {metrics.downside_volatility:>14.2f}%")
        print(f"   Sharpe Ratio:         {metrics.sharpe_ratio:>14.2f}")
        print(f"   Sortino Ratio:        {metrics.sortino_ratio:>14.2f}")
        print(f"   Calmar Ratio:         {metrics.calmar_ratio:>14.2f}")
        
        # Drawdown Section
        print(f"\n DRAWDOWN")
        print("-"*50)
        print(f"   Max Drawdown:        ${metrics.max_drawdown:>+14,.2f}")
        print(f"   Max Drawdown %:       {metrics.max_drawdown_pct:>14.2f}%")
        print(f"   Avg Drawdown %:       {metrics.avg_drawdown:>14.2f}%")
        print(f"   Current Drawdown:     {metrics.current_drawdown:>14.2f}%")
        print(f"   Max DD Duration:      {metrics.max_drawdown_duration:>14} days")
        print(f"   Ulcer Index:          {metrics.ulcer_index:>14.2f}")
        print(f"   Recovery Factor:      {metrics.recovery_factor:>14.2f}")
        
        # Trade Statistics
        if metrics.total_trades > 0:
            print(f"\n TRADE STATISTICS")
            print("-"*50)
            print(f"   Total Trades:         {metrics.total_trades:>14}")
            print(f"   Winning Trades:       {metrics.winning_trades:>14}")
            print(f"   Losing Trades:        {metrics.losing_trades:>14}")
            print(f"   Win Rate:             {metrics.win_rate:>13.1f}%")
            print(f"   Loss Rate:            {metrics.loss_rate:>13.1f}%")
            
            print(f"\n   Avg Win:             ${metrics.avg_win:>+14,.2f} ({metrics.avg_win_pct:+.2f}%)")
            print(f"   Avg Loss:            ${metrics.avg_loss:>+14,.2f} ({metrics.avg_loss_pct:+.2f}%)")
            print(f"   Largest Win:         ${metrics.largest_win:>+14,.2f} ({metrics.largest_win_pct:+.2f}%)")
            print(f"   Largest Loss:        ${metrics.largest_loss:>+14,.2f} ({metrics.largest_loss_pct:+.2f}%)")
            
            print(f"\n   Profit Factor:        {metrics.profit_factor:>14.2f}")
            print(f"   Payoff Ratio:         {metrics.payoff_ratio:>14.2f}")
            print(f"   Expectancy:          ${metrics.expectancy:>+14,.2f}")
            print(f"   Expectancy %:         {metrics.expectancy_pct:>+13.2f}%")
            
            print(f"\n   Avg Hold Period:      {metrics.avg_holding_period:>14.1f} days")
            print(f"   Avg Winner Hold:      {metrics.avg_winning_hold:>14.1f} days")
            print(f"   Avg Loser Hold:       {metrics.avg_losing_hold:>14.1f} days")
            
            print(f"\n   Max Consec. Wins:     {metrics.max_consecutive_wins:>14}")
            print(f"   Max Consec. Losses:   {metrics.max_consecutive_losses:>14}")
            
            streak_str = f"+{metrics.current_streak}" if metrics.current_streak > 0 else str(metrics.current_streak)
            print(f"   Current Streak:       {streak_str:>14}")
        
        print(f"\n{'='*70}\n")
    
    def print_summary(self):
        """Print a brief performance summary."""
        metrics = self.calculate_all_metrics()
        
        print(f"\n{'='*50}")
        print(" PERFORMANCE SUMMARY")
        print(f"{'='*50}")
        
        print(f"\n   Return:    {metrics.total_return_pct:>+8.2f}%")
        print(f"   Sharpe:    {metrics.sharpe_ratio:>8.2f}")
        print(f"   Max DD:    {metrics.max_drawdown_pct:>8.2f}%")
        
        if metrics.total_trades > 0:
            print(f"   Win Rate:  {metrics.win_rate:>7.1f}%")
            print(f"   Profit F:  {metrics.profit_factor:>8.2f}")
        
        print(f"\n{'='*50}\n")
    
    def print_benchmark_comparison(self, benchmark_returns: List[float] = None,
                                   benchmark_name: str = "S&P 500"):
        """Print benchmark comparison."""
        comparison = self.compare_to_benchmark(benchmark_returns, benchmark_name)
        
        if not comparison:
            print("Insufficient data for benchmark comparison")
            return
        
        print(f"\n{'='*50}")
        print(f" BENCHMARK COMPARISON vs {comparison.benchmark_name}")
        print(f"{'='*50}")
        
        print(f"\n   Portfolio Return:     {comparison.portfolio_return:>+10.2f}%")
        print(f"   Benchmark Return:     {comparison.benchmark_return:>+10.2f}%")
        print(f"   Alpha:                {comparison.alpha:>+10.2f}%")
        print(f"   Beta:                 {comparison.beta:>10.2f}")
        print(f"   Correlation:          {comparison.correlation:>10.2f}")
        print(f"   Information Ratio:    {comparison.information_ratio:>10.2f}")
        print(f"   Tracking Error:       {comparison.tracking_error:>10.2f}%")
        print(f"   Up Capture:           {comparison.up_capture:>10.1f}%")
        print(f"   Down Capture:         {comparison.down_capture:>10.1f}%")
        
        print(f"\n{'='*50}\n")
    
    def get_metrics_dict(self) -> Dict:
        """Get all metrics as a dictionary."""
        return self.calculate_all_metrics().to_dict()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.05,
                          periods_per_year: int = 252) -> float:
    """
    Calculate Sharpe ratio from a list of returns.
    
    Args:
        returns: List of period returns (as decimals, e.g., 0.01 for 1%)
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
    
    Returns:
        Annualized Sharpe ratio
    """
    if len(returns) < 2:
        return 0
    
    period_rf = risk_free_rate / periods_per_year
    excess_returns = [r - period_rf for r in returns]
    
    std = statistics.stdev(returns)
    if std == 0:
        return 0
    
    return (statistics.mean(excess_returns) / std) * math.sqrt(periods_per_year)


def calculate_max_drawdown(values: List[float]) -> Tuple[float, float]:
    """
    Calculate maximum drawdown.
    
    Args:
        values: List of portfolio values
    
    Returns:
        Tuple of (max_drawdown_amount, max_drawdown_pct)
    """
    if not values:
        return 0, 0
    
    peak = values[0]
    max_dd = 0
    max_dd_pct = 0
    
    for value in values:
        if value > peak:
            peak = value
        
        drawdown = peak - value
        drawdown_pct = drawdown / peak if peak > 0 else 0
        
        if drawdown > max_dd:
            max_dd = drawdown
            max_dd_pct = drawdown_pct
    
    return max_dd, max_dd_pct * 100


def calculate_cagr(start_value: float, end_value: float, years: float) -> float:
    """
    Calculate Compound Annual Growth Rate.
    
    Args:
        start_value: Starting portfolio value
        end_value: Ending portfolio value
        years: Number of years
    
    Returns:
        CAGR as percentage
    """
    if years <= 0 or start_value <= 0:
        return 0
    
    return ((end_value / start_value) ** (1 / years) - 1) * 100


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Analytics")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample data")
    
    args = parser.parse_args()
    
    if args.demo:
        print("\n🎮 PERFORMANCE ANALYTICS DEMO")
        print("="*50)
        
        # Create sample trades
        sample_trades = [
            {"symbol": "AAPL", "side": "long", "entry_date": "2024-01-15", 
             "exit_date": "2024-02-01", "entry_price": 150, "exit_price": 165, "quantity": 100},
            {"symbol": "MSFT", "side": "long", "entry_date": "2024-02-05",
             "exit_date": "2024-02-20", "entry_price": 400, "exit_price": 380, "quantity": 50},
            {"symbol": "GOOGL", "side": "long", "entry_date": "2024-02-25",
             "exit_date": "2024-03-15", "entry_price": 140, "exit_price": 155, "quantity": 75},
            {"symbol": "TSLA", "side": "long", "entry_date": "2024-03-01",
             "exit_date": "2024-03-20", "entry_price": 200, "exit_price": 185, "quantity": 60},
            {"symbol": "NVDA", "side": "long", "entry_date": "2024-03-10",
             "exit_date": "2024-04-01", "entry_price": 800, "exit_price": 900, "quantity": 25},
            {"symbol": "AMZN", "side": "long", "entry_date": "2024-04-05",
             "exit_date": "2024-04-25", "entry_price": 180, "exit_price": 195, "quantity": 80},
            {"symbol": "META", "side": "long", "entry_date": "2024-04-15",
             "exit_date": "2024-05-01", "entry_price": 500, "exit_price": 475, "quantity": 40},
            {"symbol": "AAPL", "side": "long", "entry_date": "2024-05-01",
             "exit_date": "2024-05-20", "entry_price": 170, "exit_price": 190, "quantity": 100},
        ]
        
        analyzer = PerformanceAnalyzer(initial_capital=100000)
        analyzer.add_trades(sample_trades)
        
        print(f"\nLoaded {len(sample_trades)} sample trades")
        
        analyzer.print_report()
        
        print("\nUse in your code:")
        print("-"*40)
        print("""
from trading.performance import PerformanceAnalyzer

analyzer = PerformanceAnalyzer(initial_capital=100000)
analyzer.add_trades(your_trades)
metrics = analyzer.calculate_all_metrics()

print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
print(f"Win Rate: {metrics.win_rate:.1f}%")
""")
    
    else:
        print("\nUsage: python -m trading.performance --demo")
        print("\nOr import in Python:")
        print("  from trading.performance import PerformanceAnalyzer")


if __name__ == "__main__":
    main()
