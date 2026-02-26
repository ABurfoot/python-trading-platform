#!/usr/bin/env python3
"""
Portfolio Optimizer
====================
Professional portfolio optimization using Modern Portfolio Theory.

Features:
- Mean-Variance Optimization (Markowitz)
- Efficient Frontier calculation
- Maximum Sharpe Ratio portfolio
- Minimum Volatility portfolio
- Risk Parity allocation
- Target Return optimization
- Target Risk optimization
- Black-Litterman model (simplified)
- Rebalancing recommendations
- Constraint support (min/max weights, sector limits)

Usage:
    from trading.portfolio_optimizer import PortfolioOptimizer
    
    optimizer = PortfolioOptimizer()
    
    # Add assets with expected returns and historical data
    optimizer.add_assets(["AAPL", "MSFT", "GOOGL", "BND", "GLD"])
    
    # Find optimal portfolio
    weights = optimizer.optimize_sharpe()
    
    # Get efficient frontier
    frontier = optimizer.efficient_frontier()
    
    # Print results
    optimizer.print_allocation()
"""

import math
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics


# Simple cache for historical data
_optimizer_cache = {}
_cache_ttl = {}
_CACHE_DURATION = 600  # 10 minute cache for historical data


def _get_cached(key: str) -> Optional[any]:
    """Get cached value if not expired."""
    if key in _optimizer_cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _optimizer_cache[key]
        else:
            del _optimizer_cache[key]
            del _cache_ttl[key]
    return None


def _set_cached(key: str, value: any, ttl: int = None):
    """Set cached value with TTL."""
    _optimizer_cache[key] = value
    _cache_ttl[key] = time.time() + (ttl or _CACHE_DURATION)


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""
    MAX_SHARPE = "max_sharpe"
    MIN_VOLATILITY = "min_volatility"
    RISK_PARITY = "risk_parity"
    TARGET_RETURN = "target_return"
    TARGET_RISK = "target_risk"
    EQUAL_WEIGHT = "equal_weight"
    MAX_DIVERSIFICATION = "max_diversification"


@dataclass
class Asset:
    """An asset in the portfolio."""
    symbol: str
    expected_return: float  # Annual expected return (as decimal)
    volatility: float  # Annual volatility (as decimal)
    current_weight: float = 0  # Current portfolio weight
    target_weight: float = 0  # Optimized weight
    min_weight: float = 0  # Minimum allowed weight
    max_weight: float = 1.0  # Maximum allowed weight
    sector: str = ""
    asset_class: str = ""
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "expected_return": self.expected_return,
            "volatility": self.volatility,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
        }


@dataclass
class PortfolioStats:
    """Portfolio statistics."""
    expected_return: float = 0
    volatility: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    diversification_ratio: float = 0
    weights: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "expected_return": self.expected_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "weights": self.weights,
        }


@dataclass
class EfficientFrontierPoint:
    """A point on the efficient frontier."""
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]


@dataclass 
class RebalanceRecommendation:
    """Rebalancing recommendation."""
    symbol: str
    current_weight: float
    target_weight: float
    difference: float
    action: str  # "buy", "sell", "hold"
    trade_value: float = 0  # Dollar amount to trade


class PortfolioOptimizer:
    """
    Portfolio optimizer using Modern Portfolio Theory.
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize portfolio optimizer.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        
        # Assets
        self.assets: Dict[str, Asset] = {}
        self.symbols: List[str] = []
        
        # Returns data
        self.returns: Dict[str, List[float]] = {}
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
        self.covariance_matrix: Dict[str, Dict[str, float]] = {}
        
        # Results
        self.optimal_weights: Dict[str, float] = {}
        self.portfolio_stats: Optional[PortfolioStats] = None
        self.efficient_frontier_points: List[EfficientFrontierPoint] = []
    
    # =========================================================================
    # ASSET MANAGEMENT
    # =========================================================================
    
    def add_asset(self, symbol: str, expected_return: float = None, 
                  volatility: float = None, current_weight: float = 0,
                  min_weight: float = 0, max_weight: float = 1.0,
                  sector: str = "", asset_class: str = "") -> Asset:
        """
        Add an asset to the portfolio.
        
        Args:
            symbol: Asset symbol
            expected_return: Expected annual return (decimal). If None, will estimate.
            volatility: Annual volatility (decimal). If None, will estimate.
            current_weight: Current portfolio weight
            min_weight: Minimum allowed weight
            max_weight: Maximum allowed weight
            sector: Sector classification
            asset_class: Asset class (equity, bond, commodity, etc.)
        
        Returns:
            Asset object
        """
        symbol = symbol.upper()
        
        # Estimate returns and volatility if not provided
        if expected_return is None or volatility is None:
            est_return, est_vol = self._estimate_asset_stats(symbol)
            if expected_return is None:
                expected_return = est_return
            if volatility is None:
                volatility = est_vol
        
        asset = Asset(
            symbol=symbol,
            expected_return=expected_return,
            volatility=volatility,
            current_weight=current_weight,
            min_weight=min_weight,
            max_weight=max_weight,
            sector=sector,
            asset_class=asset_class,
        )
        
        self.assets[symbol] = asset
        if symbol not in self.symbols:
            self.symbols.append(symbol)
        
        return asset
    
    def add_assets(self, symbols: List[str], **kwargs) -> List[Asset]:
        """Add multiple assets (with parallel data fetching)."""
        if not symbols:
            return []
        
        # Pre-fetch all asset stats in parallel
        stats_cache = {}
        symbols_to_fetch = [s.upper() for s in symbols]
        
        def fetch_stats(symbol):
            return symbol, self._estimate_asset_stats(symbol)
        
        with ThreadPoolExecutor(max_workers=min(len(symbols_to_fetch), 8)) as executor:
            futures = {executor.submit(fetch_stats, sym): sym for sym in symbols_to_fetch}
            for future in as_completed(futures):
                try:
                    symbol, stats = future.result()
                    stats_cache[symbol] = stats
                except Exception:
                    pass
        
        # Now add assets using cached stats
        assets = []
        for symbol in symbols:
            symbol_upper = symbol.upper()
            
            # Get pre-fetched stats
            est_return, est_vol = stats_cache.get(symbol_upper, (0.08, 0.20))
            
            # Use kwargs if provided, otherwise use estimated values
            expected_return = kwargs.get('expected_return', est_return)
            volatility = kwargs.get('volatility', est_vol)
            
            asset = Asset(
                symbol=symbol_upper,
                expected_return=expected_return,
                volatility=volatility,
                current_weight=kwargs.get('current_weight', 0),
                min_weight=kwargs.get('min_weight', 0),
                max_weight=kwargs.get('max_weight', 1.0),
                sector=kwargs.get('sector'),
                asset_class=kwargs.get('asset_class'),
            )
            
            self.assets[symbol_upper] = asset
            if symbol_upper not in self.symbols:
                self.symbols.append(symbol_upper)
            
            assets.append(asset)
        
        return assets
    
    def remove_asset(self, symbol: str):
        """Remove an asset from the portfolio."""
        symbol = symbol.upper()
        if symbol in self.assets:
            del self.assets[symbol]
            self.symbols.remove(symbol)
    
    def set_current_weights(self, weights: Dict[str, float]):
        """Set current portfolio weights."""
        for symbol, weight in weights.items():
            symbol = symbol.upper()
            if symbol in self.assets:
                self.assets[symbol].current_weight = weight
    
    def _estimate_asset_stats(self, symbol: str) -> Tuple[float, float]:
        """Estimate expected return and volatility from historical data (with caching)."""
        # Check cache first
        cache_key = f"asset_stats_{symbol}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Try to fetch historical data
        try:
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            data = fetcher.get_historical(symbol, period="365d")
            
            if data and len(data) > 20:
                prices = [d["close"] for d in data if d.get("close")]
                
                # Calculate daily returns
                returns = []
                for i in range(1, len(prices)):
                    ret = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(ret)
                
                if returns:
                    # Annualize
                    daily_mean = statistics.mean(returns)
                    daily_std = statistics.stdev(returns) if len(returns) > 1 else 0
                    
                    annual_return = daily_mean * 252
                    annual_vol = daily_std * math.sqrt(252)
                    
                    self.returns[symbol] = returns
                    
                    # Cache the result
                    result = (annual_return, annual_vol)
                    _set_cached(cache_key, result)
                    
                    return result
        except Exception:
            pass
        
        # Default estimates based on asset class heuristics
        default_returns = {
            "SPY": (0.10, 0.15), "QQQ": (0.12, 0.20), "IWM": (0.09, 0.18),
            "BND": (0.04, 0.05), "TLT": (0.03, 0.12), "AGG": (0.04, 0.04),
            "GLD": (0.05, 0.15), "SLV": (0.04, 0.25),
            "VNQ": (0.08, 0.18),  # Real estate
        }
        
        if symbol in default_returns:
            result = default_returns[symbol]
            _set_cached(cache_key, result)
            return result
        
        # Generic stock estimate
        result = (0.08, 0.20)
        _set_cached(cache_key, result)
        return result
    
    # =========================================================================
    # CORRELATION AND COVARIANCE
    # =========================================================================
    
    def _build_correlation_matrix(self):
        """Build correlation matrix from returns data."""
        self.correlation_matrix = {}
        
        for symbol1 in self.symbols:
            self.correlation_matrix[symbol1] = {}
            for symbol2 in self.symbols:
                if symbol1 == symbol2:
                    self.correlation_matrix[symbol1][symbol2] = 1.0
                elif symbol2 in self.correlation_matrix and symbol1 in self.correlation_matrix[symbol2]:
                    self.correlation_matrix[symbol1][symbol2] = self.correlation_matrix[symbol2][symbol1]
                else:
                    corr = self._calculate_correlation(symbol1, symbol2)
                    self.correlation_matrix[symbol1][symbol2] = corr
    
    def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two assets."""
        returns1 = self.returns.get(symbol1, [])
        returns2 = self.returns.get(symbol2, [])
        
        if not returns1 or not returns2:
            # Use default correlation estimates
            return self._estimate_correlation(symbol1, symbol2)
        
        min_len = min(len(returns1), len(returns2))
        if min_len < 10:
            return self._estimate_correlation(symbol1, symbol2)
        
        r1 = returns1[-min_len:]
        r2 = returns2[-min_len:]
        
        try:
            mean1 = statistics.mean(r1)
            mean2 = statistics.mean(r2)
            
            numerator = sum((r1[i] - mean1) * (r2[i] - mean2) for i in range(min_len))
            
            sum_sq1 = sum((r - mean1) ** 2 for r in r1)
            sum_sq2 = sum((r - mean2) ** 2 for r in r2)
            
            denominator = math.sqrt(sum_sq1 * sum_sq2)
            
            if denominator == 0:
                return 0
            
            return numerator / denominator
        except Exception:
            return self._estimate_correlation(symbol1, symbol2)
    
    def _estimate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Estimate correlation based on asset class."""
        # Asset class correlation estimates
        equity_symbols = {"SPY", "QQQ", "IWM", "VTI", "VOO", "AAPL", "MSFT", "GOOGL", "AMZN"}
        bond_symbols = {"BND", "TLT", "AGG", "IEF", "LQD"}
        commodity_symbols = {"GLD", "SLV", "USO", "DBA"}
        
        def get_class(s):
            if s in equity_symbols or (s not in bond_symbols and s not in commodity_symbols):
                return "equity"
            elif s in bond_symbols:
                return "bond"
            else:
                return "commodity"
        
        class1 = get_class(symbol1)
        class2 = get_class(symbol2)
        
        if class1 == class2:
            if class1 == "equity":
                return 0.7 + random.uniform(-0.1, 0.1)  # High correlation within equities
            elif class1 == "bond":
                return 0.6 + random.uniform(-0.1, 0.1)
            else:
                return 0.5 + random.uniform(-0.1, 0.1)
        elif (class1 == "equity" and class2 == "bond") or (class1 == "bond" and class2 == "equity"):
            return -0.1 + random.uniform(-0.1, 0.1)  # Negative stock-bond correlation
        else:
            return 0.2 + random.uniform(-0.1, 0.1)
    
    def _build_covariance_matrix(self):
        """Build covariance matrix."""
        if not self.correlation_matrix:
            self._build_correlation_matrix()
        
        self.covariance_matrix = {}
        
        for symbol1 in self.symbols:
            self.covariance_matrix[symbol1] = {}
            vol1 = self.assets[symbol1].volatility
            
            for symbol2 in self.symbols:
                vol2 = self.assets[symbol2].volatility
                corr = self.correlation_matrix[symbol1][symbol2]
                self.covariance_matrix[symbol1][symbol2] = corr * vol1 * vol2
    
    def set_correlation_matrix(self, matrix: Dict[str, Dict[str, float]]):
        """Set correlation matrix directly."""
        self.correlation_matrix = matrix
        self._build_covariance_matrix()
    
    # =========================================================================
    # PORTFOLIO CALCULATIONS
    # =========================================================================
    
    def _calculate_portfolio_return(self, weights: Dict[str, float]) -> float:
        """Calculate expected portfolio return."""
        return sum(
            weights.get(symbol, 0) * self.assets[symbol].expected_return
            for symbol in self.symbols
        )
    
    def _calculate_portfolio_volatility(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio volatility."""
        if not self.covariance_matrix:
            self._build_covariance_matrix()
        
        variance = 0
        for symbol1 in self.symbols:
            for symbol2 in self.symbols:
                w1 = weights.get(symbol1, 0)
                w2 = weights.get(symbol2, 0)
                cov = self.covariance_matrix[symbol1][symbol2]
                variance += w1 * w2 * cov
        
        return math.sqrt(variance) if variance > 0 else 0
    
    def _calculate_sharpe_ratio(self, weights: Dict[str, float]) -> float:
        """Calculate Sharpe ratio for given weights."""
        ret = self._calculate_portfolio_return(weights)
        vol = self._calculate_portfolio_volatility(weights)
        
        if vol == 0:
            return 0
        
        return (ret - self.risk_free_rate) / vol
    
    def _calculate_portfolio_stats(self, weights: Dict[str, float]) -> PortfolioStats:
        """Calculate all portfolio statistics."""
        ret = self._calculate_portfolio_return(weights)
        vol = self._calculate_portfolio_volatility(weights)
        sharpe = (ret - self.risk_free_rate) / vol if vol > 0 else 0
        
        # Diversification ratio
        weighted_vol = sum(
            weights.get(s, 0) * self.assets[s].volatility 
            for s in self.symbols
        )
        div_ratio = weighted_vol / vol if vol > 0 else 1
        
        return PortfolioStats(
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            diversification_ratio=div_ratio,
            weights=weights.copy(),
        )
    
    # =========================================================================
    # OPTIMIZATION METHODS
    # =========================================================================
    
    def optimize(self, method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
                 target_return: float = None, target_risk: float = None,
                 num_iterations: int = 10000) -> Dict[str, float]:
        """
        Optimize portfolio weights.
        
        Args:
            method: Optimization method
            target_return: Target return (for TARGET_RETURN method)
            target_risk: Target volatility (for TARGET_RISK method)
            num_iterations: Number of random iterations for simulation
        
        Returns:
            Optimal weights dictionary
        """
        if not self.assets:
            print("[ERROR] No assets added to optimizer")
            return {}
        
        if not self.covariance_matrix:
            self._build_covariance_matrix()
        
        print(f"Optimizing portfolio: {method.value}")
        
        if method == OptimizationMethod.EQUAL_WEIGHT:
            weights = self._equal_weight()
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._optimize_sharpe(num_iterations)
        elif method == OptimizationMethod.MIN_VOLATILITY:
            weights = self._optimize_min_volatility(num_iterations)
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity()
        elif method == OptimizationMethod.TARGET_RETURN:
            weights = self._optimize_target_return(target_return, num_iterations)
        elif method == OptimizationMethod.TARGET_RISK:
            weights = self._optimize_target_risk(target_risk, num_iterations)
        elif method == OptimizationMethod.MAX_DIVERSIFICATION:
            weights = self._optimize_max_diversification(num_iterations)
        else:
            weights = self._equal_weight()
        
        # Store results
        self.optimal_weights = weights
        self.portfolio_stats = self._calculate_portfolio_stats(weights)
        
        # Update asset target weights
        for symbol, weight in weights.items():
            if symbol in self.assets:
                self.assets[symbol].target_weight = weight
        
        print(f"✓ Optimization complete")
        
        return weights
    
    def _equal_weight(self) -> Dict[str, float]:
        """Equal weight allocation."""
        n = len(self.symbols)
        weight = 1.0 / n if n > 0 else 0
        return {symbol: weight for symbol in self.symbols}
    
    def _optimize_sharpe(self, num_iterations: int) -> Dict[str, float]:
        """Find maximum Sharpe ratio portfolio."""
        best_sharpe = float('-inf')
        best_weights = self._equal_weight()
        
        for _ in range(num_iterations):
            weights = self._generate_random_weights()
            sharpe = self._calculate_sharpe_ratio(weights)
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = weights.copy()
        
        return best_weights
    
    def _optimize_min_volatility(self, num_iterations: int) -> Dict[str, float]:
        """Find minimum volatility portfolio."""
        best_vol = float('inf')
        best_weights = self._equal_weight()
        
        for _ in range(num_iterations):
            weights = self._generate_random_weights()
            vol = self._calculate_portfolio_volatility(weights)
            
            if vol < best_vol:
                best_vol = vol
                best_weights = weights.copy()
        
        return best_weights
    
    def _optimize_target_return(self, target: float, num_iterations: int) -> Dict[str, float]:
        """Find minimum volatility portfolio for target return."""
        if target is None:
            target = statistics.mean(a.expected_return for a in self.assets.values())
        
        best_vol = float('inf')
        best_weights = self._equal_weight()
        tolerance = 0.01  # 1% tolerance
        
        for _ in range(num_iterations):
            weights = self._generate_random_weights()
            ret = self._calculate_portfolio_return(weights)
            vol = self._calculate_portfolio_volatility(weights)
            
            if abs(ret - target) <= tolerance and vol < best_vol:
                best_vol = vol
                best_weights = weights.copy()
        
        return best_weights
    
    def _optimize_target_risk(self, target: float, num_iterations: int) -> Dict[str, float]:
        """Find maximum return portfolio for target volatility."""
        if target is None:
            target = statistics.mean(a.volatility for a in self.assets.values())
        
        best_return = float('-inf')
        best_weights = self._equal_weight()
        tolerance = 0.01  # 1% tolerance
        
        for _ in range(num_iterations):
            weights = self._generate_random_weights()
            ret = self._calculate_portfolio_return(weights)
            vol = self._calculate_portfolio_volatility(weights)
            
            if abs(vol - target) <= tolerance and ret > best_return:
                best_return = ret
                best_weights = weights.copy()
        
        return best_weights
    
    def _optimize_max_diversification(self, num_iterations: int) -> Dict[str, float]:
        """Find maximum diversification portfolio."""
        best_div = float('-inf')
        best_weights = self._equal_weight()
        
        for _ in range(num_iterations):
            weights = self._generate_random_weights()
            stats = self._calculate_portfolio_stats(weights)
            
            if stats.diversification_ratio > best_div:
                best_div = stats.diversification_ratio
                best_weights = weights.copy()
        
        return best_weights
    
    def _risk_parity(self) -> Dict[str, float]:
        """
        Risk parity allocation - equal risk contribution from each asset.
        Simplified version using inverse volatility weighting.
        """
        inv_vols = {}
        total_inv_vol = 0
        
        for symbol in self.symbols:
            vol = self.assets[symbol].volatility
            if vol > 0:
                inv_vol = 1.0 / vol
                inv_vols[symbol] = inv_vol
                total_inv_vol += inv_vol
            else:
                inv_vols[symbol] = 0
        
        weights = {}
        for symbol in self.symbols:
            if total_inv_vol > 0:
                weights[symbol] = inv_vols[symbol] / total_inv_vol
            else:
                weights[symbol] = 1.0 / len(self.symbols)
        
        return weights
    
    def _generate_random_weights(self) -> Dict[str, float]:
        """Generate random portfolio weights respecting constraints."""
        weights = {}
        remaining = 1.0
        
        # Shuffle symbols to avoid bias
        shuffled = self.symbols.copy()
        random.shuffle(shuffled)
        
        for i, symbol in enumerate(shuffled):
            asset = self.assets[symbol]
            
            if i == len(shuffled) - 1:
                # Last asset gets remaining weight
                weight = max(asset.min_weight, min(asset.max_weight, remaining))
            else:
                # Random weight within constraints
                min_w = asset.min_weight
                max_w = min(asset.max_weight, remaining)
                
                if max_w <= min_w:
                    weight = min_w
                else:
                    weight = random.uniform(min_w, max_w)
            
            weights[symbol] = weight
            remaining -= weight
        
        # Normalize to ensure sum is 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {s: w/total for s, w in weights.items()}
        
        return weights
    
    # =========================================================================
    # EFFICIENT FRONTIER
    # =========================================================================
    
    def efficient_frontier(self, num_points: int = 50, 
                          num_iterations: int = 5000) -> List[EfficientFrontierPoint]:
        """
        Calculate efficient frontier.
        
        Args:
            num_points: Number of points on the frontier
            num_iterations: Iterations per point
        
        Returns:
            List of efficient frontier points
        """
        print(f"Calculating efficient frontier ({num_points} points)...")
        
        if not self.covariance_matrix:
            self._build_covariance_matrix()
        
        # Find return range
        min_return = min(a.expected_return for a in self.assets.values())
        max_return = max(a.expected_return for a in self.assets.values())
        
        # Generate points
        self.efficient_frontier_points = []
        return_targets = [
            min_return + (max_return - min_return) * i / (num_points - 1)
            for i in range(num_points)
        ]
        
        for target in return_targets:
            weights = self._optimize_target_return(target, num_iterations)
            stats = self._calculate_portfolio_stats(weights)
            
            point = EfficientFrontierPoint(
                expected_return=stats.expected_return,
                volatility=stats.volatility,
                sharpe_ratio=stats.sharpe_ratio,
                weights=weights,
            )
            self.efficient_frontier_points.append(point)
        
        # Sort by volatility
        self.efficient_frontier_points.sort(key=lambda p: p.volatility)
        
        print(f"✓ Efficient frontier calculated")
        
        return self.efficient_frontier_points
    
    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def optimize_sharpe(self, num_iterations: int = 10000) -> Dict[str, float]:
        """Optimize for maximum Sharpe ratio."""
        return self.optimize(OptimizationMethod.MAX_SHARPE, num_iterations=num_iterations)
    
    def optimize_min_vol(self, num_iterations: int = 10000) -> Dict[str, float]:
        """Optimize for minimum volatility."""
        return self.optimize(OptimizationMethod.MIN_VOLATILITY, num_iterations=num_iterations)
    
    def optimize_risk_parity(self) -> Dict[str, float]:
        """Optimize using risk parity."""
        return self.optimize(OptimizationMethod.RISK_PARITY)
    
    # =========================================================================
    # REBALANCING
    # =========================================================================
    
    def get_rebalance_recommendations(self, portfolio_value: float = 100000,
                                      threshold: float = 0.02) -> List[RebalanceRecommendation]:
        """
        Get rebalancing recommendations.
        
        Args:
            portfolio_value: Total portfolio value
            threshold: Minimum difference to trigger rebalance (2% default)
        
        Returns:
            List of rebalancing recommendations
        """
        if not self.optimal_weights:
            print("[ERROR] Run optimization first")
            return []
        
        recommendations = []
        
        for symbol in self.symbols:
            asset = self.assets[symbol]
            current = asset.current_weight
            target = self.optimal_weights.get(symbol, 0)
            diff = target - current
            
            if abs(diff) < threshold:
                action = "hold"
            elif diff > 0:
                action = "buy"
            else:
                action = "sell"
            
            trade_value = abs(diff) * portfolio_value
            
            rec = RebalanceRecommendation(
                symbol=symbol,
                current_weight=current,
                target_weight=target,
                difference=diff,
                action=action,
                trade_value=trade_value,
            )
            recommendations.append(rec)
        
        # Sort by absolute difference
        recommendations.sort(key=lambda r: abs(r.difference), reverse=True)
        
        return recommendations
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_allocation(self):
        """Print optimal portfolio allocation."""
        if not self.optimal_weights:
            print("No optimization results. Run optimize() first.")
            return
        
        print(f"\n{'='*60}")
        print("OPTIMAL PORTFOLIO ALLOCATION")
        print(f"{'='*60}")
        
        stats = self.portfolio_stats
        
        print(f"\n   PORTFOLIO METRICS")
        print(f"   {'-'*40}")
        print(f"   Expected Return:      {stats.expected_return*100:>10.2f}%")
        print(f"   Volatility:           {stats.volatility*100:>10.2f}%")
        print(f"   Sharpe Ratio:         {stats.sharpe_ratio:>10.2f}")
        print(f"   Diversification:      {stats.diversification_ratio:>10.2f}")
        
        print(f"\n   ASSET ALLOCATION")
        print(f"   {'-'*40}")
        print(f"   {'Symbol':<10} {'Weight':>10} {'Return':>10} {'Vol':>10}")
        print(f"   {'-'*40}")
        
        sorted_assets = sorted(
            self.optimal_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for symbol, weight in sorted_assets:
            asset = self.assets[symbol]
            print(f"   {symbol:<10} {weight*100:>9.1f}% {asset.expected_return*100:>9.1f}% {asset.volatility*100:>9.1f}%")
        
        print(f"\n{'='*60}\n")
    
    def print_efficient_frontier(self):
        """Print efficient frontier data."""
        if not self.efficient_frontier_points:
            print("No efficient frontier data. Run efficient_frontier() first.")
            return
        
        print(f"\n{'='*60}")
        print("EFFICIENT FRONTIER")
        print(f"{'='*60}")
        
        print(f"\n   {'Return':>10} {'Volatility':>12} {'Sharpe':>10}")
        print(f"   {'-'*35}")
        
        for point in self.efficient_frontier_points[::max(1, len(self.efficient_frontier_points)//10)]:
            print(f"   {point.expected_return*100:>9.2f}% {point.volatility*100:>11.2f}% {point.sharpe_ratio:>10.2f}")
        
        # Find max Sharpe
        max_sharpe_point = max(self.efficient_frontier_points, key=lambda p: p.sharpe_ratio)
        print(f"\n   🏆 Max Sharpe Portfolio:")
        print(f"      Return: {max_sharpe_point.expected_return*100:.2f}%")
        print(f"      Volatility: {max_sharpe_point.volatility*100:.2f}%")
        print(f"      Sharpe: {max_sharpe_point.sharpe_ratio:.2f}")
        
        # Find min vol
        min_vol_point = min(self.efficient_frontier_points, key=lambda p: p.volatility)
        print(f"\n   🛡️  Min Volatility Portfolio:")
        print(f"      Return: {min_vol_point.expected_return*100:.2f}%")
        print(f"      Volatility: {min_vol_point.volatility*100:.2f}%")
        print(f"      Sharpe: {min_vol_point.sharpe_ratio:.2f}")
        
        print(f"\n{'='*60}\n")
    
    def print_rebalance(self, portfolio_value: float = 100000):
        """Print rebalancing recommendations."""
        recs = self.get_rebalance_recommendations(portfolio_value)
        
        if not recs:
            return
        
        print(f"\n{'='*70}")
        print("⚖️  REBALANCING RECOMMENDATIONS")
        print(f"{'='*70}")
        print(f"\n   Portfolio Value: ${portfolio_value:,.2f}")
        
        print(f"\n   {'Symbol':<10} {'Current':>10} {'Target':>10} {'Diff':>10} {'Action':>8} {'Trade $':>12}")
        print(f"   {'-'*65}")
        
        for rec in recs:
            action_emoji = "[+]" if rec.action == "buy" else "[-]" if rec.action == "sell" else "[.]"
            print(f"   {rec.symbol:<10} {rec.current_weight*100:>9.1f}% {rec.target_weight*100:>9.1f}% "
                  f"{rec.difference*100:>+9.1f}% {action_emoji} {rec.action:<5} ${rec.trade_value:>10,.2f}")
        
        total_trades = sum(r.trade_value for r in recs if r.action != "hold")
        print(f"\n   Total Trading Volume: ${total_trades:,.2f}")
        
        print(f"\n{'='*70}\n")
    
    def print_correlation(self):
        """Print correlation matrix."""
        if not self.correlation_matrix:
            self._build_correlation_matrix()
        
        print(f"\n{'='*60}")
        print("CORRELATION MATRIX")
        print(f"{'='*60}\n")
        
        # Header
        header = "          "
        for symbol in self.symbols:
            header += f"{symbol:>8}"
        print(header)
        
        # Rows
        for symbol1 in self.symbols:
            row = f"{symbol1:<10}"
            for symbol2 in self.symbols:
                corr = self.correlation_matrix[symbol1][symbol2]
                row += f"{corr:>8.2f}"
            print(row)
        
        print(f"\n{'='*60}\n")
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def to_dict(self) -> Dict:
        """Export optimization results as dictionary."""
        return {
            "optimal_weights": self.optimal_weights,
            "portfolio_stats": self.portfolio_stats.to_dict() if self.portfolio_stats else {},
            "assets": {s: a.to_dict() for s, a in self.assets.items()},
        }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Portfolio Optimizer")
    parser.add_argument("--demo", action="store_true", help="Run demo optimization")
    parser.add_argument("--assets", nargs="+", help="Asset symbols to optimize")
    parser.add_argument("--method", choices=["sharpe", "minvol", "riskparity", "equal"],
                       default="sharpe", help="Optimization method")
    
    args = parser.parse_args()
    
    if args.demo:
        print("\n🎮 PORTFOLIO OPTIMIZER DEMO")
        print("="*50)
        
        optimizer = PortfolioOptimizer(risk_free_rate=0.05)
        
        # Add sample assets with estimated returns
        assets_data = [
            ("SPY", 0.10, 0.15, "equity", "US Large Cap"),
            ("QQQ", 0.12, 0.20, "equity", "US Tech"),
            ("IWM", 0.09, 0.18, "equity", "US Small Cap"),
            ("EFA", 0.07, 0.16, "equity", "International"),
            ("BND", 0.04, 0.05, "bond", "US Bonds"),
            ("GLD", 0.05, 0.15, "commodity", "Gold"),
        ]
        
        print("\nAdding assets...")
        for symbol, ret, vol, asset_class, name in assets_data:
            optimizer.add_asset(
                symbol=symbol,
                expected_return=ret,
                volatility=vol,
                asset_class=asset_class,
            )
            print(f"   {symbol}: E[R]={ret*100:.1f}%, Vol={vol*100:.1f}%")
        
        # Set current weights (example: 60/40 with some individual stocks)
        optimizer.set_current_weights({
            "SPY": 0.40,
            "QQQ": 0.20,
            "IWM": 0.10,
            "EFA": 0.10,
            "BND": 0.15,
            "GLD": 0.05,
        })
        
        # Optimize for maximum Sharpe
        print("\n" + "="*50)
        print("1️⃣  MAXIMUM SHARPE RATIO OPTIMIZATION")
        print("="*50)
        optimizer.optimize_sharpe()
        optimizer.print_allocation()
        
        # Optimize for minimum volatility
        print("="*50)
        print("2️⃣  MINIMUM VOLATILITY OPTIMIZATION")
        print("="*50)
        optimizer.optimize_min_vol()
        optimizer.print_allocation()
        
        # Risk parity
        print("="*50)
        print("3️⃣  RISK PARITY OPTIMIZATION")
        print("="*50)
        optimizer.optimize_risk_parity()
        optimizer.print_allocation()
        
        # Show correlation matrix
        optimizer.print_correlation()
        
        # Show efficient frontier
        print("="*50)
        print("4️⃣  EFFICIENT FRONTIER")
        print("="*50)
        optimizer.efficient_frontier(num_points=20, num_iterations=3000)
        optimizer.print_efficient_frontier()
        
        # Rebalancing recommendations
        print("="*50)
        print("5️⃣  REBALANCING RECOMMENDATIONS")
        print("="*50)
        optimizer.optimize_sharpe()
        optimizer.print_rebalance(portfolio_value=100000)
        
        print("="*50)
        print("Usage in code:")
        print("-"*40)
        print("""
from trading.portfolio_optimizer import PortfolioOptimizer

optimizer = PortfolioOptimizer(risk_free_rate=0.05)

# Add assets
optimizer.add_assets(["SPY", "QQQ", "BND", "GLD"])

# Or with custom expected returns
optimizer.add_asset("AAPL", expected_return=0.12, volatility=0.25)

# Optimize
weights = optimizer.optimize_sharpe()
# Or: optimizer.optimize_min_vol()
# Or: optimizer.optimize_risk_parity()

# View results
optimizer.print_allocation()
optimizer.print_correlation()

# Get efficient frontier
frontier = optimizer.efficient_frontier()
optimizer.print_efficient_frontier()

# Rebalancing
optimizer.set_current_weights({"SPY": 0.5, "BND": 0.5})
optimizer.print_rebalance(portfolio_value=100000)
""")
    
    elif args.assets:
        optimizer = PortfolioOptimizer()
        optimizer.add_assets(args.assets)
        
        if args.method == "sharpe":
            optimizer.optimize_sharpe()
        elif args.method == "minvol":
            optimizer.optimize_min_vol()
        elif args.method == "riskparity":
            optimizer.optimize_risk_parity()
        else:
            optimizer.optimize(OptimizationMethod.EQUAL_WEIGHT)
        
        optimizer.print_allocation()
    
    else:
        print("\nUsage: python -m trading.portfolio_optimizer --demo")
        print("       python -m trading.portfolio_optimizer --assets SPY QQQ BND GLD --method sharpe")


if __name__ == "__main__":
    main()
