#!/usr/bin/env python3
"""
Risk Manager Module
====================
Comprehensive risk management for trading portfolios.

Features:
- Position Sizing (Kelly Criterion, Fixed Fractional, Volatility-based)
- Value at Risk (VaR) - Historical, Parametric, Monte Carlo
- Conditional VaR (CVaR / Expected Shortfall)
- Maximum Drawdown monitoring
- Exposure limits (per position, sector, asset class)
- Risk/Reward analysis
- Stop loss calculations
- Portfolio heat map
- Risk alerts and warnings
- Daily risk reports

Usage:
    from trading.risk_manager import RiskManager
    
    rm = RiskManager(portfolio_value=100000)
    
    # Calculate position size
    size = rm.calculate_position_size(
        symbol="AAPL",
        entry_price=150,
        stop_loss=140,
        method="kelly"
    )
    
    # Calculate VaR
    var = rm.calculate_var(confidence=0.95)
    
    # Check risk limits
    rm.check_risk_limits()
    
    # Print risk report
    rm.print_risk_report()
"""

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import statistics


class PositionSizingMethod(Enum):
    """Position sizing methods."""
    FIXED_DOLLAR = "fixed_dollar"
    FIXED_PERCENT = "fixed_percent"
    FIXED_FRACTIONAL = "fixed_fractional"
    KELLY = "kelly"
    HALF_KELLY = "half_kelly"
    VOLATILITY = "volatility"
    ATR = "atr"


class VaRMethod(Enum):
    """VaR calculation methods."""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


@dataclass
class Position:
    """A portfolio position for risk tracking."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float = 0
    take_profit: float = 0
    sector: str = ""
    asset_class: str = "equity"
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.entry_price
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    @property
    def risk_amount(self) -> float:
        """Amount at risk to stop loss."""
        if self.stop_loss > 0:
            return (self.current_price - self.stop_loss) * self.quantity
        return self.market_value  # Full position at risk if no stop
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "stop_loss": self.stop_loss,
            "risk_amount": self.risk_amount,
        }


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_size_pct: float = 0.10  # Max 10% per position
    max_sector_exposure_pct: float = 0.30  # Max 30% per sector
    max_asset_class_pct: float = 0.80  # Max 80% in single asset class
    max_portfolio_risk_pct: float = 0.02  # Max 2% portfolio risk per trade
    max_daily_loss_pct: float = 0.05  # Max 5% daily loss
    max_drawdown_pct: float = 0.20  # Max 20% drawdown
    max_leverage: float = 1.0  # No leverage by default
    max_correlated_positions: int = 5  # Max highly correlated positions
    min_cash_pct: float = 0.05  # Minimum 5% cash


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""
    # VaR metrics
    var_95: float = 0  # 95% VaR
    var_99: float = 0  # 99% VaR
    cvar_95: float = 0  # 95% CVaR (Expected Shortfall)
    cvar_99: float = 0  # 99% CVaR
    
    # Portfolio metrics
    portfolio_volatility: float = 0
    portfolio_beta: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    
    # Drawdown
    current_drawdown: float = 0
    max_drawdown: float = 0
    
    # Exposure
    total_exposure: float = 0
    net_exposure: float = 0
    gross_exposure: float = 0
    leverage: float = 0
    
    # Position metrics
    largest_position_pct: float = 0
    total_risk_amount: float = 0
    
    def to_dict(self) -> dict:
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "portfolio_volatility": self.portfolio_volatility,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "leverage": self.leverage,
        }


@dataclass
class RiskAlert:
    """A risk alert."""
    level: str  # "warning", "critical"
    category: str  # "position", "exposure", "drawdown", "var"
    message: str
    value: float
    limit: float
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""
    shares: int
    dollar_amount: float
    risk_amount: float
    risk_percent: float
    method: str
    
    def to_dict(self) -> dict:
        return {
            "shares": self.shares,
            "dollar_amount": self.dollar_amount,
            "risk_amount": self.risk_amount,
            "risk_percent": self.risk_percent,
            "method": self.method,
        }


class RiskManager:
    """
    Comprehensive risk management system.
    """
    
    def __init__(self, 
                 portfolio_value: float = 100000,
                 risk_free_rate: float = 0.05,
                 limits: RiskLimits = None):
        """
        Initialize risk manager.
        
        Args:
            portfolio_value: Total portfolio value
            risk_free_rate: Annual risk-free rate
            limits: Risk limit configuration
        """
        self.portfolio_value = portfolio_value
        self.cash = portfolio_value
        self.risk_free_rate = risk_free_rate
        self.limits = limits or RiskLimits()
        
        # Positions
        self.positions: Dict[str, Position] = {}
        
        # Historical data
        self.daily_returns: List[float] = []
        self.equity_history: List[Tuple[str, float]] = []
        self.peak_value = portfolio_value
        
        # Alerts
        self.alerts: List[RiskAlert] = []
        
        # Trade history for Kelly calculation
        self.win_rate: float = 0.5
        self.avg_win_loss_ratio: float = 1.5
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    def add_position(self, symbol: str, quantity: float, entry_price: float,
                    current_price: float = None, stop_loss: float = 0,
                    take_profit: float = 0, sector: str = "",
                    asset_class: str = "equity") -> Position:
        """Add a position to track."""
        symbol = symbol.upper()
        
        if current_price is None:
            current_price = entry_price
        
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            sector=sector,
            asset_class=asset_class,
        )
        
        self.positions[symbol] = position
        self._update_cash()
        
        return position
    
    def update_position(self, symbol: str, current_price: float = None,
                       stop_loss: float = None, take_profit: float = None):
        """Update position details."""
        symbol = symbol.upper()
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        if current_price is not None:
            pos.current_price = current_price
        if stop_loss is not None:
            pos.stop_loss = stop_loss
        if take_profit is not None:
            pos.take_profit = take_profit
    
    def remove_position(self, symbol: str):
        """Remove a position."""
        symbol = symbol.upper()
        if symbol in self.positions:
            del self.positions[symbol]
            self._update_cash()
    
    def _update_cash(self):
        """Update available cash."""
        positions_value = sum(p.market_value for p in self.positions.values())
        self.cash = self.portfolio_value - positions_value
    
    def update_portfolio_value(self, value: float):
        """Update total portfolio value."""
        self.portfolio_value = value
        
        # Track for drawdown
        if value > self.peak_value:
            self.peak_value = value
        
        self.equity_history.append((datetime.now().isoformat(), value))
        
        # Calculate daily return if we have history
        if len(self.equity_history) >= 2:
            prev_value = self.equity_history[-2][1]
            if prev_value > 0:
                daily_return = (value - prev_value) / prev_value
                self.daily_returns.append(daily_return)
    
    def set_trade_stats(self, win_rate: float, avg_win_loss_ratio: float):
        """Set trading statistics for Kelly calculation."""
        self.win_rate = win_rate
        self.avg_win_loss_ratio = avg_win_loss_ratio
    
    # =========================================================================
    # POSITION SIZING
    # =========================================================================
    
    def calculate_position_size(self, symbol: str, entry_price: float,
                               stop_loss: float = None,
                               method: PositionSizingMethod = PositionSizingMethod.FIXED_FRACTIONAL,
                               risk_percent: float = 0.02,
                               volatility: float = None,
                               atr: float = None,
                               fixed_amount: float = None) -> PositionSizeResult:
        """
        Calculate position size using various methods.
        
        Args:
            symbol: Stock symbol
            entry_price: Entry price
            stop_loss: Stop loss price (required for most methods)
            method: Position sizing method
            risk_percent: Percent of portfolio to risk (for fixed fractional)
            volatility: Annual volatility (for volatility-based)
            atr: Average True Range (for ATR-based)
            fixed_amount: Fixed dollar amount (for fixed dollar method)
        
        Returns:
            PositionSizeResult with calculated position size
        """
        if isinstance(method, str):
            method = PositionSizingMethod(method)
        
        # Calculate risk per share
        if stop_loss and stop_loss > 0:
            risk_per_share = abs(entry_price - stop_loss)
        else:
            risk_per_share = entry_price * 0.10  # Default 10% if no stop
        
        shares = 0
        risk_amount = 0
        
        if method == PositionSizingMethod.FIXED_DOLLAR:
            amount = fixed_amount or (self.portfolio_value * 0.05)
            shares = int(amount / entry_price)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.FIXED_PERCENT:
            amount = self.portfolio_value * risk_percent
            shares = int(amount / entry_price)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.FIXED_FRACTIONAL:
            # Risk a fixed percentage of portfolio
            risk_budget = self.portfolio_value * risk_percent
            if risk_per_share > 0:
                shares = int(risk_budget / risk_per_share)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.KELLY:
            kelly_pct = self._kelly_criterion()
            risk_budget = self.portfolio_value * kelly_pct
            if risk_per_share > 0:
                shares = int(risk_budget / risk_per_share)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.HALF_KELLY:
            kelly_pct = self._kelly_criterion() / 2
            risk_budget = self.portfolio_value * kelly_pct
            if risk_per_share > 0:
                shares = int(risk_budget / risk_per_share)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.VOLATILITY:
            if volatility is None:
                volatility = 0.20  # Default 20% volatility
            # Target 1% daily volatility contribution
            target_vol = 0.01
            daily_vol = volatility / math.sqrt(252)
            if daily_vol > 0:
                position_value = (self.portfolio_value * target_vol) / daily_vol
                shares = int(position_value / entry_price)
            risk_amount = shares * risk_per_share
        
        elif method == PositionSizingMethod.ATR:
            if atr is None:
                atr = entry_price * 0.02  # Default 2% of price
            # Risk 2 ATR per position
            atr_risk = atr * 2
            risk_budget = self.portfolio_value * risk_percent
            if atr_risk > 0:
                shares = int(risk_budget / atr_risk)
            risk_amount = shares * atr_risk
        
        # Apply position size limits
        max_position_value = self.portfolio_value * self.limits.max_position_size_pct
        max_shares = int(max_position_value / entry_price)
        shares = min(shares, max_shares)
        
        # Can't buy more than we have cash for
        max_affordable = int(self.cash / entry_price)
        shares = min(shares, max_affordable)
        
        shares = max(0, shares)
        dollar_amount = shares * entry_price
        risk_pct = (risk_amount / self.portfolio_value) * 100 if self.portfolio_value > 0 else 0
        
        return PositionSizeResult(
            shares=shares,
            dollar_amount=dollar_amount,
            risk_amount=risk_amount,
            risk_percent=risk_pct,
            method=method.value,
        )
    
    def _kelly_criterion(self) -> float:
        """Calculate Kelly Criterion percentage."""
        # Kelly % = W - [(1-W) / R]
        # W = win rate, R = win/loss ratio
        
        w = self.win_rate
        r = self.avg_win_loss_ratio
        
        if r <= 0:
            return 0
        
        kelly = w - ((1 - w) / r)
        
        # Cap Kelly at reasonable levels
        kelly = max(0, min(kelly, 0.25))  # Max 25%
        
        return kelly
    
    # =========================================================================
    # VALUE AT RISK (VaR)
    # =========================================================================
    
    def calculate_var(self, confidence: float = 0.95,
                     method: VaRMethod = VaRMethod.HISTORICAL,
                     horizon_days: int = 1,
                     num_simulations: int = 10000) -> float:
        """
        Calculate Value at Risk.
        
        Args:
            confidence: Confidence level (0.95 = 95%)
            method: VaR calculation method
            horizon_days: Time horizon in days
            num_simulations: Number of Monte Carlo simulations
        
        Returns:
            VaR as dollar amount (positive number = potential loss)
        """
        if isinstance(method, str):
            method = VaRMethod(method)
        
        if method == VaRMethod.HISTORICAL:
            return self._historical_var(confidence, horizon_days)
        elif method == VaRMethod.PARAMETRIC:
            return self._parametric_var(confidence, horizon_days)
        elif method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(confidence, horizon_days, num_simulations)
        
        return 0
    
    def _historical_var(self, confidence: float, horizon_days: int) -> float:
        """Calculate historical VaR."""
        if len(self.daily_returns) < 10:
            # Not enough data, use parametric estimate
            return self._parametric_var(confidence, horizon_days)
        
        # Scale returns to horizon
        scaled_returns = [r * math.sqrt(horizon_days) for r in self.daily_returns]
        
        # Sort returns
        sorted_returns = sorted(scaled_returns)
        
        # Find percentile
        index = int((1 - confidence) * len(sorted_returns))
        var_return = sorted_returns[index]
        
        # Convert to dollar amount
        var = abs(var_return) * self.portfolio_value
        
        return var
    
    def _parametric_var(self, confidence: float, horizon_days: int) -> float:
        """Calculate parametric (variance-covariance) VaR."""
        # Estimate volatility
        if len(self.daily_returns) >= 2:
            daily_vol = statistics.stdev(self.daily_returns)
        else:
            daily_vol = 0.01  # Assume 1% daily volatility
        
        # Scale to horizon
        vol = daily_vol * math.sqrt(horizon_days)
        
        # Z-score for confidence level
        z_scores = {0.90: 1.28, 0.95: 1.645, 0.99: 2.33}
        z = z_scores.get(confidence, 1.645)
        
        # VaR = Portfolio Value * Z * Volatility
        var = self.portfolio_value * z * vol
        
        return var
    
    def _monte_carlo_var(self, confidence: float, horizon_days: int,
                        num_simulations: int) -> float:
        """Calculate Monte Carlo VaR."""
        if len(self.daily_returns) >= 2:
            mean_return = statistics.mean(self.daily_returns)
            std_return = statistics.stdev(self.daily_returns)
        else:
            mean_return = 0.0005  # ~12% annual
            std_return = 0.01  # ~16% annual vol
        
        # Simulate returns
        final_values = []
        
        for _ in range(num_simulations):
            value = self.portfolio_value
            for _ in range(horizon_days):
                daily_return = random.gauss(mean_return, std_return)
                value *= (1 + daily_return)
            final_values.append(value)
        
        # Sort and find percentile
        sorted_values = sorted(final_values)
        index = int((1 - confidence) * len(sorted_values))
        var_value = sorted_values[index]
        
        # VaR is the loss from current value
        var = self.portfolio_value - var_value
        
        return max(0, var)
    
    def calculate_cvar(self, confidence: float = 0.95,
                      method: VaRMethod = VaRMethod.HISTORICAL) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).
        
        CVaR is the expected loss given that loss exceeds VaR.
        """
        if len(self.daily_returns) < 10:
            # Use parametric estimate
            var = self._parametric_var(confidence, 1)
            return var * 1.2  # Rough approximation
        
        # Get returns beyond VaR threshold
        sorted_returns = sorted(self.daily_returns)
        cutoff_index = int((1 - confidence) * len(sorted_returns))
        
        tail_returns = sorted_returns[:cutoff_index + 1]
        
        if tail_returns:
            avg_tail_return = statistics.mean(tail_returns)
            cvar = abs(avg_tail_return) * self.portfolio_value
        else:
            cvar = self.calculate_var(confidence, method)
        
        return cvar
    
    # =========================================================================
    # RISK METRICS
    # =========================================================================
    
    def calculate_metrics(self) -> RiskMetrics:
        """Calculate all risk metrics."""
        metrics = RiskMetrics()
        
        # VaR
        metrics.var_95 = self.calculate_var(0.95)
        metrics.var_99 = self.calculate_var(0.99)
        metrics.cvar_95 = self.calculate_cvar(0.95)
        metrics.cvar_99 = self.calculate_cvar(0.99)
        
        # Volatility
        if len(self.daily_returns) >= 2:
            daily_vol = statistics.stdev(self.daily_returns)
            metrics.portfolio_volatility = daily_vol * math.sqrt(252) * 100
        
        # Drawdown
        if self.peak_value > 0:
            metrics.current_drawdown = ((self.peak_value - self.portfolio_value) / 
                                        self.peak_value) * 100
        metrics.max_drawdown = self._calculate_max_drawdown()
        
        # Exposure
        total_long = sum(p.market_value for p in self.positions.values() if p.quantity > 0)
        total_short = abs(sum(p.market_value for p in self.positions.values() if p.quantity < 0))
        
        metrics.total_exposure = total_long + total_short
        metrics.net_exposure = total_long - total_short
        metrics.gross_exposure = total_long + total_short
        
        if self.portfolio_value > 0:
            metrics.leverage = metrics.gross_exposure / self.portfolio_value
        
        # Largest position
        if self.positions and self.portfolio_value > 0:
            largest = max(p.market_value for p in self.positions.values())
            metrics.largest_position_pct = (largest / self.portfolio_value) * 100
        
        # Total risk
        metrics.total_risk_amount = sum(p.risk_amount for p in self.positions.values())
        
        # Sharpe/Sortino
        if len(self.daily_returns) >= 20:
            daily_rf = self.risk_free_rate / 252
            excess_returns = [r - daily_rf for r in self.daily_returns]
            
            if statistics.stdev(self.daily_returns) > 0:
                metrics.sharpe_ratio = (statistics.mean(excess_returns) / 
                                       statistics.stdev(self.daily_returns)) * math.sqrt(252)
            
            downside_returns = [r for r in self.daily_returns if r < 0]
            if len(downside_returns) >= 2 and statistics.stdev(downside_returns) > 0:
                metrics.sortino_ratio = (statistics.mean(excess_returns) * 252 /
                                        (statistics.stdev(downside_returns) * math.sqrt(252)))
        
        return metrics
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity history."""
        if not self.equity_history:
            return 0
        
        peak = self.equity_history[0][1]
        max_dd = 0
        
        for _, value in self.equity_history:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd * 100
    
    # =========================================================================
    # RISK LIMITS AND ALERTS
    # =========================================================================
    
    def check_risk_limits(self) -> List[RiskAlert]:
        """Check all risk limits and generate alerts."""
        self.alerts = []
        metrics = self.calculate_metrics()
        
        # Position size limits
        for symbol, pos in self.positions.items():
            pos_pct = pos.market_value / self.portfolio_value if self.portfolio_value > 0 else 0
            
            if pos_pct > self.limits.max_position_size_pct:
                self.alerts.append(RiskAlert(
                    level="warning",
                    category="position",
                    message=f"{symbol} exceeds position size limit",
                    value=pos_pct * 100,
                    limit=self.limits.max_position_size_pct * 100,
                ))
        
        # Sector exposure
        sector_exposure = self._get_sector_exposure()
        for sector, exposure in sector_exposure.items():
            if exposure > self.limits.max_sector_exposure_pct:
                self.alerts.append(RiskAlert(
                    level="warning",
                    category="exposure",
                    message=f"{sector} sector exceeds limit",
                    value=exposure * 100,
                    limit=self.limits.max_sector_exposure_pct * 100,
                ))
        
        # Drawdown limit
        if metrics.current_drawdown > self.limits.max_drawdown_pct * 100:
            self.alerts.append(RiskAlert(
                level="critical",
                category="drawdown",
                message="Drawdown exceeds maximum limit",
                value=metrics.current_drawdown,
                limit=self.limits.max_drawdown_pct * 100,
            ))
        
        # Leverage limit
        if metrics.leverage > self.limits.max_leverage:
            self.alerts.append(RiskAlert(
                level="critical",
                category="exposure",
                message="Leverage exceeds limit",
                value=metrics.leverage,
                limit=self.limits.max_leverage,
            ))
        
        # Cash minimum
        cash_pct = self.cash / self.portfolio_value if self.portfolio_value > 0 else 0
        if cash_pct < self.limits.min_cash_pct:
            self.alerts.append(RiskAlert(
                level="warning",
                category="exposure",
                message="Cash below minimum",
                value=cash_pct * 100,
                limit=self.limits.min_cash_pct * 100,
            ))
        
        return self.alerts
    
    def _get_sector_exposure(self) -> Dict[str, float]:
        """Calculate exposure by sector."""
        sector_values = {}
        
        for pos in self.positions.values():
            sector = pos.sector or "Unknown"
            if sector not in sector_values:
                sector_values[sector] = 0
            sector_values[sector] += pos.market_value
        
        # Convert to percentages
        if self.portfolio_value > 0:
            return {s: v / self.portfolio_value for s, v in sector_values.items()}
        return sector_values
    
    def _get_asset_class_exposure(self) -> Dict[str, float]:
        """Calculate exposure by asset class."""
        class_values = {}
        
        for pos in self.positions.values():
            ac = pos.asset_class or "equity"
            if ac not in class_values:
                class_values[ac] = 0
            class_values[ac] += pos.market_value
        
        if self.portfolio_value > 0:
            return {c: v / self.portfolio_value for c, v in class_values.items()}
        return class_values
    
    # =========================================================================
    # STOP LOSS CALCULATIONS
    # =========================================================================
    
    def calculate_stop_loss(self, entry_price: float, method: str = "percent",
                           percent: float = 0.05, atr: float = None,
                           atr_multiplier: float = 2.0,
                           support_level: float = None) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            method: "percent", "atr", "support"
            percent: Percentage below entry (for percent method)
            atr: Average True Range (for ATR method)
            atr_multiplier: ATR multiplier (for ATR method)
            support_level: Support level (for support method)
        
        Returns:
            Stop loss price
        """
        if method == "percent":
            return entry_price * (1 - percent)
        
        elif method == "atr" and atr:
            return entry_price - (atr * atr_multiplier)
        
        elif method == "support" and support_level:
            # Place stop slightly below support
            return support_level * 0.99
        
        # Default: 5% below entry
        return entry_price * 0.95
    
    def calculate_take_profit(self, entry_price: float, stop_loss: float,
                             risk_reward: float = 2.0) -> float:
        """Calculate take profit based on risk/reward ratio."""
        risk = entry_price - stop_loss
        reward = risk * risk_reward
        return entry_price + reward
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_risk_report(self):
        """Print comprehensive risk report."""
        metrics = self.calculate_metrics()
        alerts = self.check_risk_limits()
        
        print(f"\n{'='*70}")
        print("[WARN]  RISK MANAGEMENT REPORT")
        print(f"{'='*70}")
        
        print(f"\n    PORTFOLIO OVERVIEW")
        print(f"   {'-'*50}")
        print(f"   Portfolio Value:      ${self.portfolio_value:>14,.2f}")
        print(f"   Cash:                 ${self.cash:>14,.2f}")
        print(f"   Positions Value:      ${self.portfolio_value - self.cash:>14,.2f}")
        print(f"   Number of Positions:  {len(self.positions):>14}")
        
        print(f"\n    VALUE AT RISK")
        print(f"   {'-'*50}")
        print(f"   VaR (95%, 1-day):     ${metrics.var_95:>14,.2f}")
        print(f"   VaR (99%, 1-day):     ${metrics.var_99:>14,.2f}")
        print(f"   CVaR (95%, 1-day):    ${metrics.cvar_95:>14,.2f}")
        print(f"   CVaR (99%, 1-day):    ${metrics.cvar_99:>14,.2f}")
        
        print(f"\n    RISK METRICS")
        print(f"   {'-'*50}")
        print(f"   Portfolio Volatility: {metrics.portfolio_volatility:>13.2f}%")
        print(f"   Sharpe Ratio:         {metrics.sharpe_ratio:>14.2f}")
        print(f"   Sortino Ratio:        {metrics.sortino_ratio:>14.2f}")
        
        print(f"\n    DRAWDOWN")
        print(f"   {'-'*50}")
        print(f"   Current Drawdown:     {metrics.current_drawdown:>13.2f}%")
        print(f"   Maximum Drawdown:     {metrics.max_drawdown:>13.2f}%")
        print(f"   Max DD Limit:         {self.limits.max_drawdown_pct * 100:>13.2f}%")
        
        print(f"\n   💼 EXPOSURE")
        print(f"   {'-'*50}")
        print(f"   Gross Exposure:       ${metrics.gross_exposure:>14,.2f}")
        print(f"   Net Exposure:         ${metrics.net_exposure:>14,.2f}")
        print(f"   Leverage:             {metrics.leverage:>14.2f}x")
        print(f"   Largest Position:     {metrics.largest_position_pct:>13.2f}%")
        
        # Sector exposure
        sector_exp = self._get_sector_exposure()
        if sector_exp:
            print(f"\n   🏢 SECTOR EXPOSURE")
            print(f"   {'-'*50}")
            for sector, exp in sorted(sector_exp.items(), key=lambda x: x[1], reverse=True):
                bar = "█" * int(exp * 20)
                print(f"   {sector:<15} {exp*100:>6.1f}% {bar}")
        
        # Alerts
        if alerts:
            print(f"\n   🚨 ALERTS ({len(alerts)})")
            print(f"   {'-'*50}")
            for alert in alerts:
                emoji = "[-]" if alert.level == "critical" else "[WARN]"
                print(f"   {emoji} {alert.message}")
                print(f"      Value: {alert.value:.2f} | Limit: {alert.limit:.2f}")
        else:
            print(f"\n   [Y] No risk alerts")
        
        print(f"\n{'='*70}\n")
    
    def print_positions(self):
        """Print current positions with risk info."""
        if not self.positions:
            print("\n   No open positions.\n")
            return
        
        print(f"\n{'='*90}")
        print(" POSITION RISK SUMMARY")
        print(f"{'='*90}")
        
        print(f"\n   {'Symbol':<8} {'Qty':>8} {'Entry':>10} {'Current':>10} {'P&L':>12} {'Risk $':>12} {'Stop':>10}")
        print(f"   {'-'*82}")
        
        for pos in sorted(self.positions.values(), key=lambda p: p.market_value, reverse=True):
            pnl_emoji = "[+]" if pos.unrealized_pnl > 0 else "[-]" if pos.unrealized_pnl < 0 else "[.]"
            stop_str = f"${pos.stop_loss:.2f}" if pos.stop_loss > 0 else "None"
            
            print(f"   {pos.symbol:<8} {pos.quantity:>8.0f} ${pos.entry_price:>9.2f} ${pos.current_price:>9.2f} "
                  f"{pnl_emoji}${pos.unrealized_pnl:>+10,.2f} ${pos.risk_amount:>11,.2f} {stop_str:>10}")
        
        print(f"\n{'='*90}\n")
    
    def print_position_sizing(self, symbol: str, entry_price: float, stop_loss: float):
        """Print position sizing comparison for all methods."""
        print(f"\n{'='*60}")
        print(f"📐 POSITION SIZING: {symbol}")
        print(f"{'='*60}")
        print(f"\n   Entry: ${entry_price:.2f} | Stop: ${stop_loss:.2f}")
        print(f"   Risk per share: ${abs(entry_price - stop_loss):.2f}")
        
        print(f"\n   {'Method':<20} {'Shares':>10} {'Amount':>12} {'Risk $':>12} {'Risk %':>8}")
        print(f"   {'-'*62}")
        
        methods = [
            PositionSizingMethod.FIXED_FRACTIONAL,
            PositionSizingMethod.KELLY,
            PositionSizingMethod.HALF_KELLY,
            PositionSizingMethod.VOLATILITY,
        ]
        
        for method in methods:
            result = self.calculate_position_size(symbol, entry_price, stop_loss, method)
            print(f"   {method.value:<20} {result.shares:>10,} ${result.dollar_amount:>11,.2f} "
                  f"${result.risk_amount:>11,.2f} {result.risk_percent:>7.2f}%")
        
        print(f"\n{'='*60}\n")
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def to_dict(self) -> Dict:
        """Export risk data as dictionary."""
        metrics = self.calculate_metrics()
        return {
            "portfolio_value": self.portfolio_value,
            "cash": self.cash,
            "metrics": metrics.to_dict(),
            "positions": {s: p.to_dict() for s, p in self.positions.items()},
            "alerts": [{"level": a.level, "message": a.message} for a in self.alerts],
        }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Risk Manager")
    parser.add_argument("--demo", action="store_true", help="Run demo")
    parser.add_argument("--portfolio", "-p", type=float, default=100000, help="Portfolio value")
    
    args = parser.parse_args()
    
    if args.demo:
        print("\n🎮 RISK MANAGER DEMO")
        print("="*50)
        
        # Create risk manager
        rm = RiskManager(portfolio_value=100000)
        
        # Set trade stats for Kelly
        rm.set_trade_stats(win_rate=0.55, avg_win_loss_ratio=1.8)
        
        # Add some positions
        print("\n Adding sample positions...")
        rm.add_position("AAPL", 50, 175, 180, stop_loss=165, sector="Technology")
        rm.add_position("MSFT", 30, 380, 390, stop_loss=360, sector="Technology")
        rm.add_position("JPM", 40, 150, 155, stop_loss=140, sector="Financials")
        rm.add_position("XOM", 60, 100, 105, stop_loss=92, sector="Energy")
        rm.add_position("BND", 100, 72, 73, sector="Bonds", asset_class="bond")
        
        # Simulate some history
        print("   Simulating 30 days of returns...")
        for i in range(30):
            daily_return = random.gauss(0.0005, 0.012)
            rm.daily_returns.append(daily_return)
            new_value = rm.portfolio_value * (1 + daily_return)
            rm.update_portfolio_value(new_value)
        
        # Print reports
        rm.print_risk_report()
        rm.print_positions()
        
        # Position sizing example
        print("="*50)
        print("📐 POSITION SIZING EXAMPLE")
        print("="*50)
        rm.print_position_sizing("GOOGL", entry_price=140, stop_loss=130)
        
        # Calculate various stop losses
        print("="*50)
        print("🛑 STOP LOSS CALCULATIONS")
        print("="*50)
        entry = 150.0
        print(f"\n   Entry Price: ${entry:.2f}")
        print(f"   {'-'*40}")
        print(f"   5% Stop:      ${rm.calculate_stop_loss(entry, 'percent', percent=0.05):.2f}")
        print(f"   10% Stop:     ${rm.calculate_stop_loss(entry, 'percent', percent=0.10):.2f}")
        print(f"   2x ATR Stop:  ${rm.calculate_stop_loss(entry, 'atr', atr=3.5):.2f}")
        
        # Risk/reward
        stop = rm.calculate_stop_loss(entry, 'percent', percent=0.05)
        print(f"\n   Take Profit (2:1 R/R): ${rm.calculate_take_profit(entry, stop, 2.0):.2f}")
        print(f"   Take Profit (3:1 R/R): ${rm.calculate_take_profit(entry, stop, 3.0):.2f}")
        
        print("\n" + "="*50)
        print("Usage in code:")
        print("-"*40)
        print("""
from trading.risk_manager import RiskManager, PositionSizingMethod

rm = RiskManager(portfolio_value=100000)

# Set your trading stats for Kelly
rm.set_trade_stats(win_rate=0.55, avg_win_loss_ratio=1.8)

# Calculate position size
size = rm.calculate_position_size(
    symbol="AAPL",
    entry_price=150,
    stop_loss=140,
    method=PositionSizingMethod.HALF_KELLY
)
print(f"Buy {size.shares} shares (${size.dollar_amount:,.2f})")

# Add position
rm.add_position("AAPL", size.shares, 150, 155, stop_loss=140)

# Calculate VaR
var_95 = rm.calculate_var(confidence=0.95)
print(f"95% VaR: ${var_95:,.2f}")

# Check risk limits
alerts = rm.check_risk_limits()

# Print full report
rm.print_risk_report()
""")
    
    else:
        print("\nUsage: python -m trading.risk_manager --demo")


if __name__ == "__main__":
    main()
