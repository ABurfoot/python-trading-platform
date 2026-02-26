#!/usr/bin/env python3
"""
Integrated Backtest Runner
==========================
A single tool that downloads data (if needed) and runs backtests.

Usage:
    python backtest.py AAPL                           # Backtest AAPL with defaults
    python backtest.py AAPL --years 10                # Use 10 years of data
    python backtest.py AAPL MSFT GOOGL                # Backtest multiple symbols
    python backtest.py BHP.AX --fast 5 --slow 20      # Australian stock, custom MA
    python backtest.py --list us_tech                 # Backtest predefined list
    python backtest.py AAPL --strategy rsi            # Use RSI strategy
    python backtest.py AAPL --compare                 # Compare vs buy-and-hold

Supported Exchanges:
    US stocks:      AAPL, MSFT, GOOGL (no suffix)
    Australian:     BHP.AX, CBA.AX, CSL.AX
    London:         BP.L, HSBA.L, SHEL.L
    Frankfurt:      SAP.DE, BMW.DE
    Tokyo:          7203.T, 9984.T
"""

import argparse
import csv
import os
import sys
import time
import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

# Fix SSL certificate issues on macOS
ssl._create_default_https_context = ssl._create_unverified_context


# ============================================================================
# Configuration
# ============================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

SYMBOL_LISTS = {
    "us_tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "CRM"],
    "us_finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V"],
    "us_broad": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO"],
    "asx20": ["BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX", "ANZ.AX", "FMG.AX", 
              "WES.AX", "MQG.AX", "TLS.AX", "WOW.AX", "RIO.AX"],
    "energy": ["XOM", "CVX", "COP", "SHEL.L", "BP.L", "WDS.AX", "STO.AX", "ORG.AX"],
    "indices": ["SPY", "QQQ", "DIA", "IWM"],
}


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PriceBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    side: str


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    start_date: str
    end_date: str
    starting_capital: float
    ending_capital: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    volatility_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    avg_trade_pnl: float
    trades: List[Trade]
    equity_curve: List[float]
    buy_hold_return_pct: float = 0.0


class Strategy(Enum):
    MA_CROSSOVER = "ma_crossover"
    RSI = "rsi"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"


# ============================================================================
# Data Downloader
# ============================================================================

class DataManager:
    """Manages historical price data - downloads if needed, loads from cache."""
    
    YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
    
    def _get_filepath(self, symbol: str, years: int) -> str:
        """Get the filepath for a symbol's data file."""
        clean_symbol = symbol.replace(".", "_").replace("^", "")
        return os.path.join(self.data_dir, f"{clean_symbol}_{years}y.csv")
    
    def _data_exists(self, symbol: str, years: int) -> bool:
        """Check if data file exists and is recent enough."""
        filepath = self._get_filepath(symbol, years)
        if not os.path.exists(filepath):
            return False
        
        # Check if file is older than 1 day
        file_age = time.time() - os.path.getmtime(filepath)
        if file_age > 86400:  # 24 hours
            return False
        
        return True
    
    def _download(self, symbol: str, years: int) -> Optional[List[PriceBar]]:
        """Download data from Yahoo Finance."""
        print(f"   Downloading {symbol} ({years} years)...", end=" ", flush=True)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        period1 = int(start_date.timestamp())
        period2 = int(end_date.timestamp())
        
        url = f"{self.YAHOO_URL.format(symbol=symbol)}?period1={period1}&period2={period2}&interval=1d"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
            
            # Parse response
            result = data.get("chart", {}).get("result", [])
            if not result:
                print("[X] No data")
                return None
            
            chart = result[0]
            timestamps = chart.get("timestamp", [])
            quote = chart.get("indicators", {}).get("quote", [{}])[0]
            
            bars = []
            for i, ts in enumerate(timestamps):
                try:
                    if quote["open"][i] is None or quote["close"][i] is None:
                        continue
                    
                    bars.append(PriceBar(
                        date=datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                        open=round(quote["open"][i], 2),
                        high=round(quote["high"][i], 2),
                        low=round(quote["low"][i], 2),
                        close=round(quote["close"][i], 2),
                        volume=int(quote["volume"][i] or 0)
                    ))
                except (IndexError, TypeError):
                    continue
            
            if bars:
                self._save_csv(bars, symbol, years)
                print(f"[OK] {len(bars)} bars")
                return bars
            else:
                print("[X] No valid bars")
                return None
                
        except Exception as e:
            print(f"[X] Error: {str(e)[:50]}")
            return None
    
    def _save_csv(self, bars: List[PriceBar], symbol: str, years: int):
        """Save bars to CSV file."""
        filepath = self._get_filepath(symbol, years)
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            for bar in bars:
                writer.writerow([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])
    
    def _load_csv(self, symbol: str, years: int) -> Optional[List[PriceBar]]:
        """Load bars from CSV file."""
        filepath = self._get_filepath(symbol, years)
        
        if not os.path.exists(filepath):
            return None
        
        bars = []
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bars.append(PriceBar(
                    date=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"])
                ))
        
        return bars
    
    def get_data(self, symbol: str, years: int = 5, force_download: bool = False) -> Optional[List[PriceBar]]:
        """Get data for a symbol - loads from cache or downloads."""
        if not force_download and self._data_exists(symbol, years):
            print(f"   Loading {symbol} from cache...", end=" ", flush=True)
            bars = self._load_csv(symbol, years)
            if bars:
                print(f"[OK] {len(bars)} bars")
                return bars
        
        return self._download(symbol, years)


# ============================================================================
# Technical Indicators
# ============================================================================

def calculate_sma(prices: List[float], period: int) -> List[Optional[float]]:
    """Calculate Simple Moving Average."""
    sma = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        sma[i] = sum(prices[i - period + 1:i + 1]) / period
    return sma


def calculate_ema(prices: List[float], period: int) -> List[Optional[float]]:
    """Calculate Exponential Moving Average."""
    ema = [None] * len(prices)
    multiplier = 2 / (period + 1)
    
    # Start with SMA
    if len(prices) >= period:
        ema[period - 1] = sum(prices[:period]) / period
        
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
    
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """Calculate Relative Strength Index."""
    rsi = [None] * len(prices)
    
    if len(prices) < period + 1:
        return rsi
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    for i in range(period, len(prices)):
        avg_gain = sum(gains[i-period:i]) / period
        avg_loss = sum(losses[i-period:i]) / period
        
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_momentum(prices: List[float], period: int = 10) -> List[Optional[float]]:
    """Calculate price momentum (rate of change)."""
    mom = [None] * len(prices)
    for i in range(period, len(prices)):
        mom[i] = (prices[i] - prices[i - period]) / prices[i - period] * 100
    return mom


# ============================================================================
# Trading Strategies
# ============================================================================

class BacktestEngine:
    """Runs backtests with various strategies."""
    
    def __init__(self, bars: List[PriceBar], starting_capital: float = 100000):
        self.bars = bars
        self.starting_capital = starting_capital
        self.prices = [bar.close for bar in bars]
    
    def run_ma_crossover(self, fast_period: int = 10, slow_period: int = 30) -> BacktestResult:
        """Moving Average Crossover strategy."""
        fast_ma = calculate_ema(self.prices, fast_period)
        slow_ma = calculate_ema(self.prices, slow_period)
        
        signals = []  # 1 = buy, -1 = sell, 0 = hold
        for i in range(1, len(self.prices)):
            if fast_ma[i] is None or slow_ma[i] is None or fast_ma[i-1] is None or slow_ma[i-1] is None:
                signals.append(0)
            elif fast_ma[i] > slow_ma[i] and fast_ma[i-1] <= slow_ma[i-1]:
                signals.append(1)  # Buy signal
            elif fast_ma[i] < slow_ma[i] and fast_ma[i-1] >= slow_ma[i-1]:
                signals.append(-1)  # Sell signal
            else:
                signals.append(0)
        
        return self._execute_signals(signals, f"MA Crossover ({fast_period}/{slow_period})")
    
    def run_rsi(self, period: int = 14, oversold: int = 30, overbought: int = 70) -> BacktestResult:
        """RSI Mean Reversion strategy."""
        rsi = calculate_rsi(self.prices, period)
        
        signals = []
        for i in range(1, len(self.prices)):
            if rsi[i] is None or rsi[i-1] is None:
                signals.append(0)
            elif rsi[i-1] < oversold and rsi[i] >= oversold:
                signals.append(1)  # Buy when crossing above oversold
            elif rsi[i-1] > overbought and rsi[i] <= overbought:
                signals.append(-1)  # Sell when crossing below overbought
            else:
                signals.append(0)
        
        return self._execute_signals(signals, f"RSI ({period}, {oversold}/{overbought})")
    
    def run_momentum(self, period: int = 20, threshold: float = 5.0) -> BacktestResult:
        """Momentum strategy - buy on strong upward momentum."""
        mom = calculate_momentum(self.prices, period)
        
        signals = []
        in_position = False
        
        for i in range(1, len(self.prices)):
            if mom[i] is None:
                signals.append(0)
            elif not in_position and mom[i] > threshold:
                signals.append(1)
                in_position = True
            elif in_position and mom[i] < 0:
                signals.append(-1)
                in_position = False
            else:
                signals.append(0)
        
        return self._execute_signals(signals, f"Momentum ({period}, {threshold}%)")
    
    def run_mean_reversion(self, period: int = 20, num_std: float = 2.0) -> BacktestResult:
        """Mean Reversion using Bollinger Bands."""
        sma = calculate_sma(self.prices, period)
        
        # Calculate standard deviation
        std = [None] * len(self.prices)
        for i in range(period - 1, len(self.prices)):
            window = self.prices[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std[i] = math.sqrt(variance)
        
        signals = []
        in_position = False
        
        for i in range(1, len(self.prices)):
            if sma[i] is None or std[i] is None:
                signals.append(0)
                continue
            
            upper = sma[i] + num_std * std[i]
            lower = sma[i] - num_std * std[i]
            
            if not in_position and self.prices[i] < lower:
                signals.append(1)  # Buy below lower band
                in_position = True
            elif in_position and self.prices[i] > sma[i]:
                signals.append(-1)  # Sell at mean
                in_position = False
            else:
                signals.append(0)
        
        return self._execute_signals(signals, f"Mean Reversion ({period}, {num_std}σ)")
    
    def _execute_signals(self, signals: List[int], strategy_name: str) -> BacktestResult:
        """Execute trading signals and calculate results."""
        capital = self.starting_capital
        position = 0
        position_price = 0.0
        entry_date = ""
        
        trades = []
        equity_curve = [capital]
        daily_returns = []
        prev_equity = capital
        
        for i, signal in enumerate(signals):
            bar = self.bars[i + 1]  # signals are offset by 1
            price = bar.close
            
            # Execute signals
            if signal == 1 and position == 0:  # Buy
                shares = int(capital * 0.95 / price)
                if shares > 0:
                    position = shares
                    position_price = price
                    entry_date = bar.date
                    capital -= shares * price
            
            elif signal == -1 and position > 0:  # Sell
                proceeds = position * price
                pnl = proceeds - (position * position_price)
                pnl_pct = (price - position_price) / position_price * 100
                
                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=bar.date,
                    entry_price=position_price,
                    exit_price=price,
                    quantity=position,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    side="LONG"
                ))
                
                capital += proceeds
                position = 0
            
            # Track equity
            equity = capital + position * price
            equity_curve.append(equity)
            
            if prev_equity > 0:
                daily_returns.append((equity - prev_equity) / prev_equity)
            prev_equity = equity
        
        # Close open position
        if position > 0:
            final_price = self.bars[-1].close
            proceeds = position * final_price
            pnl = proceeds - (position * position_price)
            pnl_pct = (final_price - position_price) / position_price * 100
            
            trades.append(Trade(
                entry_date=entry_date,
                exit_date=self.bars[-1].date,
                entry_price=position_price,
                exit_price=final_price,
                quantity=position,
                pnl=pnl,
                pnl_pct=pnl_pct,
                side="LONG"
            ))
            capital += proceeds
        
        # Calculate metrics
        total_return_pct = (capital - self.starting_capital) / self.starting_capital * 100
        
        # Annualized return
        years = len(self.bars) / 252
        ann_return = (math.pow(capital / self.starting_capital, 1 / years) - 1) * 100 if years > 0 else 0
        
        # Sharpe & Sortino
        sharpe = self._calculate_sharpe(daily_returns)
        sortino = self._calculate_sortino(daily_returns)
        
        # Max drawdown
        max_dd = self._calculate_max_drawdown(equity_curve)
        
        # Volatility
        volatility = self._calculate_volatility(daily_returns)
        
        # Trade stats
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        
        total_wins = sum(t.pnl for t in winning)
        total_losses = abs(sum(t.pnl for t in losing))
        
        # Buy and hold comparison
        buy_hold_return = (self.bars[-1].close - self.bars[0].close) / self.bars[0].close * 100
        
        return BacktestResult(
            symbol="",
            strategy=strategy_name,
            start_date=self.bars[0].date,
            end_date=self.bars[-1].date,
            starting_capital=self.starting_capital,
            ending_capital=capital,
            total_return_pct=total_return_pct,
            annualized_return_pct=ann_return,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            volatility_pct=volatility,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate_pct=len(winning) / len(trades) * 100 if trades else 0,
            profit_factor=total_wins / total_losses if total_losses > 0 else 0,
            avg_trade_pnl=sum(t.pnl for t in trades) / len(trades) if trades else 0,
            trades=trades,
            equity_curve=equity_curve,
            buy_hold_return_pct=buy_hold_return
        )
    
    def _calculate_sharpe(self, returns: List[float], risk_free: float = 0.02) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        daily_rf = risk_free / 252
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance) if variance > 0 else 0
        return (mean - daily_rf) / std * math.sqrt(252) if std > 0 else 0
    
    def _calculate_sortino(self, returns: List[float], risk_free: float = 0.02) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        daily_rf = risk_free / 252
        downside = [r for r in returns if r < 0]
        if not downside:
            return 0.0
        downside_var = sum(r ** 2 for r in downside) / len(downside)
        downside_std = math.sqrt(downside_var)
        return (mean - daily_rf) / downside_std * math.sqrt(252) if downside_std > 0 else 0
    
    def _calculate_max_drawdown(self, equity: List[float]) -> float:
        peak = equity[0]
        max_dd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance) * math.sqrt(252) * 100


# ============================================================================
# Output Formatting
# ============================================================================

def print_banner():
    print()
    print("═" * 70)
    print("              TRADING PLATFORM - INTEGRATED BACKTEST")
    print("═" * 70)
    print()


def print_result(result: BacktestResult, show_trades: bool = True, compare_benchmark: bool = True):
    """Print backtest results in a formatted table."""
    print()
    print("╔" + "═" * 68 + "╗")
    print(f"║{'BACKTEST RESULTS':^68}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Symbol:    {result.symbol:<54} ║")
    print(f"║  Strategy:  {result.strategy:<54} ║")
    print(f"║  Period:    {result.start_date} to {result.end_date:<36} ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║{'PERFORMANCE':^68}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Starting Capital:    ${result.starting_capital:>15,.2f}                    ║")
    print(f"║  Ending Capital:      ${result.ending_capital:>15,.2f}                    ║")
    print(f"║  Total Return:        {result.total_return_pct:>+15.2f}%                    ║")
    print(f"║  Annualized Return:   {result.annualized_return_pct:>+15.2f}%                    ║")
    print(f"║  Max Drawdown:        {result.max_drawdown_pct:>15.2f}%                    ║")
    
    if compare_benchmark:
        print("╠" + "═" * 68 + "╣")
        print(f"║{'BENCHMARK COMPARISON':^68}║")
        print("╠" + "═" * 68 + "╣")
        outperform = result.total_return_pct - result.buy_hold_return_pct
        print(f"║  Buy & Hold Return:   {result.buy_hold_return_pct:>+15.2f}%                    ║")
        print(f"║  Strategy Alpha:      {outperform:>+15.2f}%                    ║")
    
    print("╠" + "═" * 68 + "╣")
    print(f"║{'RISK METRICS':^68}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Sharpe Ratio:        {result.sharpe_ratio:>15.2f}                     ║")
    print(f"║  Sortino Ratio:       {result.sortino_ratio:>15.2f}                     ║")
    print(f"║  Volatility (ann.):   {result.volatility_pct:>15.2f}%                    ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║{'TRADE STATISTICS':^68}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Total Trades:        {result.total_trades:>15}                     ║")
    print(f"║  Winning Trades:      {result.winning_trades:>15}                     ║")
    print(f"║  Losing Trades:       {result.losing_trades:>15}                     ║")
    print(f"║  Win Rate:            {result.win_rate_pct:>15.1f}%                    ║")
    print(f"║  Profit Factor:       {result.profit_factor:>15.2f}                     ║")
    print(f"║  Avg Trade P&L:       ${result.avg_trade_pnl:>14,.2f}                     ║")
    print("╚" + "═" * 68 + "╝")
    
    # Show recent trades
    if show_trades and result.trades:
        print()
        print("┌" + "─" * 68 + "┐")
        print(f"│{'RECENT TRADES':^68}│")
        print("├" + "─" * 68 + "┤")
        print(f"│ {'Entry':<12} {'Exit':<12} {'Side':<6} {'Entry $':>10} {'Exit $':>10} {'P&L %':>8} │")
        print("├" + "─" * 68 + "┤")
        
        for trade in result.trades[-5:]:
            pnl_str = f"{trade.pnl_pct:+.2f}%"
            print(f"│ {trade.entry_date:<12} {trade.exit_date:<12} {trade.side:<6} "
                  f"{trade.entry_price:>10.2f} {trade.exit_price:>10.2f} {pnl_str:>8} │")
        
        print("└" + "─" * 68 + "┘")


def print_comparison(results: List[Tuple[str, BacktestResult]]):
    """Print comparison of multiple backtests."""
    print()
    print("╔" + "═" * 78 + "╗")
    print(f"║{'STRATEGY COMPARISON':^78}║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ {'Symbol':<10} {'Strategy':<25} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>8} ║")
    print("╠" + "═" * 78 + "╣")
    
    for symbol, result in results:
        print(f"║ {symbol:<10} {result.strategy:<25} {result.total_return_pct:>+9.1f}% "
              f"{result.sharpe_ratio:>10.2f} {result.max_drawdown_pct:>9.1f}% {result.total_trades:>8} ║")
    
    print("╚" + "═" * 78 + "╝")


# ============================================================================
# Main CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Download data and run backtests - all in one tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backtest.py AAPL                          # Backtest AAPL with MA crossover
  python backtest.py AAPL --years 10               # Use 10 years of data
  python backtest.py AAPL MSFT GOOGL               # Multiple symbols
  python backtest.py BHP.AX CBA.AX                 # Australian stocks
  python backtest.py AAPL --strategy rsi           # Use RSI strategy
  python backtest.py AAPL --all-strategies         # Compare all strategies
  python backtest.py --list us_tech                # Backtest predefined list
  python backtest.py AAPL --fast 5 --slow 20       # Custom MA periods
        """
    )
    
    parser.add_argument("symbols", nargs="*", help="Stock symbols to backtest")
    parser.add_argument("--years", type=int, default=5, help="Years of history (default: 5)")
    parser.add_argument("--capital", type=float, default=100000, help="Starting capital (default: 100000)")
    parser.add_argument("--strategy", choices=["ma_crossover", "rsi", "momentum", "mean_reversion"],
                        default="ma_crossover", help="Trading strategy")
    parser.add_argument("--all-strategies", action="store_true", help="Compare all strategies")
    parser.add_argument("--fast", type=int, default=10, help="Fast MA period (default: 10)")
    parser.add_argument("--slow", type=int, default=30, help="Slow MA period (default: 30)")
    parser.add_argument("--list", dest="symbol_list", choices=list(SYMBOL_LISTS.keys()),
                        help="Use predefined symbol list")
    parser.add_argument("--force-download", action="store_true", help="Force re-download of data")
    parser.add_argument("--no-trades", action="store_true", help="Don't show individual trades")
    
    args = parser.parse_args()
    
    print_banner()
    
    # Collect symbols
    symbols = list(args.symbols) if args.symbols else []
    if args.symbol_list:
        symbols.extend(SYMBOL_LISTS[args.symbol_list])
    
    if not symbols:
        print("No symbols specified. Use --help for usage.")
        print()
        print("Available lists: " + ", ".join(SYMBOL_LISTS.keys()))
        return
    
    # Remove duplicates
    symbols = list(dict.fromkeys(symbols))
    
    print(f"Backtesting {len(symbols)} symbol(s) with {args.years} years of data")
    print(f"Strategy: {args.strategy}")
    print(f"Starting capital: ${args.capital:,.2f}")
    print("-" * 50)
    
    # Process each symbol
    data_manager = DataManager()
    all_results = []
    
    for symbol in symbols:
        print(f"\n[{symbol}]")
        
        # Get data
        bars = data_manager.get_data(symbol, args.years, args.force_download)
        if not bars:
            print(f"  ⚠ Skipping {symbol} - no data available")
            continue
        
        # Run backtest
        engine = BacktestEngine(bars, args.capital)
        
        if args.all_strategies:
            # Compare all strategies
            strategies = [
                ("MA Crossover", engine.run_ma_crossover(args.fast, args.slow)),
                ("RSI", engine.run_rsi()),
                ("Momentum", engine.run_momentum()),
                ("Mean Reversion", engine.run_mean_reversion()),
            ]
            for name, result in strategies:
                result.symbol = symbol
                all_results.append((symbol, result))
        else:
            # Run selected strategy
            if args.strategy == "ma_crossover":
                result = engine.run_ma_crossover(args.fast, args.slow)
            elif args.strategy == "rsi":
                result = engine.run_rsi()
            elif args.strategy == "momentum":
                result = engine.run_momentum()
            elif args.strategy == "mean_reversion":
                result = engine.run_mean_reversion()
            
            result.symbol = symbol
            all_results.append((symbol, result))
            
            # Print individual result
            print_result(result, show_trades=not args.no_trades)
    
    # Print comparison if multiple results
    if len(all_results) > 1:
        print_comparison(all_results)
    
    print()
    print("═" * 70)
    print("                         BACKTEST COMPLETE")
    print("═" * 70)
    print()


if __name__ == "__main__":
    main()
