#!/usr/bin/env python3
"""
Portfolio Optimization Module
==============================
Modern Portfolio Theory optimization and risk analysis.

Features:
- Mean-Variance Optimization (Markowitz)
- Efficient Frontier calculation
- Risk Parity portfolios
- Maximum Sharpe Ratio portfolio
- Minimum Volatility portfolio
- Black-Litterman model
- Monte Carlo simulation
- Rebalancing recommendations

Usage:
    from trading.optimizer import PortfolioOptimizer
    
    optimizer = PortfolioOptimizer(symbols=["AAPL", "MSFT", "GOOGL", "AMZN"])
    
    # Get optimal portfolio
    result = optimizer.optimize()
    
    # Get efficient frontier
    frontier = optimizer.efficient_frontier()
    
    # Risk parity
    rp = optimizer.risk_parity()
"""

import numpy as np
from scipy import optimize
from scipy import stats
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import os
import json
import urllib.request


@dataclass
class PortfolioAllocation:
    """Portfolio allocation result."""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    
    def to_dict(self) -> Dict:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "expected_return": round(self.expected_return * 100, 2),
            "volatility": round(self.volatility * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3)
        }


@dataclass
class OptimizationResult:
    """Full optimization result."""
    optimal_portfolio: PortfolioAllocation
    min_volatility: PortfolioAllocation
    max_sharpe: PortfolioAllocation
    risk_parity: PortfolioAllocation
    efficient_frontier: List[Dict]
    correlation_matrix: Dict[str, Dict[str, float]]
    individual_stats: Dict[str, Dict]
    
    def to_dict(self) -> Dict:
        return {
            "optimal_portfolio": self.optimal_portfolio.to_dict(),
            "min_volatility": self.min_volatility.to_dict(),
            "max_sharpe": self.max_sharpe.to_dict(),
            "risk_parity": self.risk_parity.to_dict(),
            "efficient_frontier": self.efficient_frontier,
            "correlation_matrix": self.correlation_matrix,
            "individual_stats": self.individual_stats
        }


class PortfolioOptimizer:
    """
    Portfolio optimization using Modern Portfolio Theory.
    
    Args:
        symbols: List of stock symbols
        risk_free_rate: Annual risk-free rate (default 4.5%)
        lookback_days: Historical data period (default 252 trading days)
    """
    
    def __init__(self, symbols: List[str], risk_free_rate: float = 0.045,
                 lookback_days: int = 252):
        self.symbols = [s.upper() for s in symbols]
        self.risk_free_rate = risk_free_rate
        self.lookback_days = lookback_days
        
        self.returns: Optional[np.ndarray] = None
        self.mean_returns: Optional[np.ndarray] = None
        self.cov_matrix: Optional[np.ndarray] = None
        
        # Fetch data
        self._fetch_data()
    
    def _fetch_data(self):
        """Fetch historical price data and calculate returns."""
        prices = {}
        
        for symbol in self.symbols:
            price_data = self._get_prices(symbol)
            if price_data:
                prices[symbol] = price_data
        
        if len(prices) < 2:
            # Use synthetic data for demonstration
            self._generate_synthetic_data()
            return
        
        # Align dates
        min_len = min(len(p) for p in prices.values())
        
        # Calculate returns
        returns_list = []
        for symbol in self.symbols:
            if symbol in prices:
                p = np.array(prices[symbol][-min_len:])
                ret = np.diff(p) / p[:-1]
                returns_list.append(ret)
        
        self.returns = np.array(returns_list).T  # Shape: (days, assets)
        self.mean_returns = np.mean(self.returns, axis=0) * 252  # Annualized
        self.cov_matrix = np.cov(self.returns.T) * 252  # Annualized
    
    def _generate_synthetic_data(self):
        """Generate synthetic return data for demonstration."""
        np.random.seed(42)
        n_assets = len(self.symbols)
        n_days = self.lookback_days
        
        # Base returns and volatilities
        base_returns = np.random.uniform(0.05, 0.15, n_assets)  # 5-15% annual
        base_vols = np.random.uniform(0.15, 0.35, n_assets)     # 15-35% annual
        
        # Generate correlated returns
        correlation = np.eye(n_assets)
        for i in range(n_assets):
            for j in range(i+1, n_assets):
                corr = np.random.uniform(0.2, 0.7)
                correlation[i, j] = corr
                correlation[j, i] = corr
        
        # Cholesky decomposition for correlated returns
        L = np.linalg.cholesky(correlation)
        
        daily_returns = np.random.randn(n_days, n_assets) / np.sqrt(252)
        daily_returns = daily_returns @ L.T
        daily_returns = daily_returns * base_vols + base_returns / 252
        
        self.returns = daily_returns
        self.mean_returns = np.mean(self.returns, axis=0) * 252
        self.cov_matrix = np.cov(self.returns.T) * 252
    
    def _get_prices(self, symbol: str) -> List[float]:
        """Fetch historical prices for a symbol."""
        try:
            api_key = os.environ.get("FMP_API_KEY", "")
            if not api_key:
                return []
            
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?timeseries={self.lookback_days}&apikey={api_key}"
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if "historical" in data:
                    prices = [d["close"] for d in reversed(data["historical"])]
                    return prices
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
        return []
    
    def portfolio_performance(self, weights: np.ndarray) -> Tuple[float, float, float]:
        """
        Calculate portfolio performance metrics.
        
        Returns:
            (expected_return, volatility, sharpe_ratio)
        """
        weights = np.array(weights)
        
        # Expected return
        portfolio_return = np.dot(weights, self.mean_returns)
        
        # Volatility
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        
        # Sharpe ratio
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        
        return portfolio_return, portfolio_vol, sharpe
    
    def _weights_to_dict(self, weights: np.ndarray) -> Dict[str, float]:
        """Convert weights array to dict."""
        return {self.symbols[i]: float(weights[i]) for i in range(len(self.symbols))}
    
    def max_sharpe_portfolio(self) -> PortfolioAllocation:
        """Find the portfolio with maximum Sharpe ratio."""
        n_assets = len(self.symbols)
        
        def neg_sharpe(weights):
            ret, vol, sharpe = self.portfolio_performance(weights)
            return -sharpe
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Weights sum to 1
        ]
        
        # Bounds (0 to 1 for each weight, long only)
        bounds = tuple((0, 1) for _ in range(n_assets))
        
        # Initial guess (equal weight)
        init_weights = np.array([1/n_assets] * n_assets)
        
        # Optimize
        result = optimize.minimize(
            neg_sharpe,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = result.x
        ret, vol, sharpe = self.portfolio_performance(weights)
        
        return PortfolioAllocation(
            weights=self._weights_to_dict(weights),
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe
        )
    
    def min_volatility_portfolio(self) -> PortfolioAllocation:
        """Find the minimum volatility portfolio."""
        n_assets = len(self.symbols)
        
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        bounds = tuple((0, 1) for _ in range(n_assets))
        init_weights = np.array([1/n_assets] * n_assets)
        
        result = optimize.minimize(
            portfolio_volatility,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = result.x
        ret, vol, sharpe = self.portfolio_performance(weights)
        
        return PortfolioAllocation(
            weights=self._weights_to_dict(weights),
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe
        )
    
    def risk_parity_portfolio(self) -> PortfolioAllocation:
        """
        Calculate risk parity portfolio.
        Each asset contributes equally to portfolio risk.
        """
        n_assets = len(self.symbols)
        
        def risk_contribution(weights):
            weights = np.array(weights)
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            
            # Marginal risk contribution
            marginal_contrib = np.dot(self.cov_matrix, weights) / portfolio_vol
            
            # Risk contribution
            risk_contrib = weights * marginal_contrib
            
            return risk_contrib
        
        def risk_parity_objective(weights):
            risk_contrib = risk_contribution(weights)
            target = np.mean(risk_contrib)
            return np.sum((risk_contrib - target) ** 2)
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        bounds = tuple((0.01, 1) for _ in range(n_assets))
        init_weights = np.array([1/n_assets] * n_assets)
        
        result = optimize.minimize(
            risk_parity_objective,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = result.x
        ret, vol, sharpe = self.portfolio_performance(weights)
        
        return PortfolioAllocation(
            weights=self._weights_to_dict(weights),
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe
        )
    
    def target_return_portfolio(self, target_return: float) -> PortfolioAllocation:
        """Find minimum volatility portfolio for a target return."""
        n_assets = len(self.symbols)
        
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'eq', 'fun': lambda x: np.dot(x, self.mean_returns) - target_return}
        ]
        
        bounds = tuple((0, 1) for _ in range(n_assets))
        init_weights = np.array([1/n_assets] * n_assets)
        
        result = optimize.minimize(
            portfolio_volatility,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = result.x
        ret, vol, sharpe = self.portfolio_performance(weights)
        
        return PortfolioAllocation(
            weights=self._weights_to_dict(weights),
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe
        )
    
    def efficient_frontier(self, n_points: int = 50) -> List[Dict]:
        """
        Calculate the efficient frontier.
        
        Returns list of (return, volatility, sharpe) points.
        """
        # Get return range
        min_ret = self.min_volatility_portfolio().expected_return
        max_ret = np.max(self.mean_returns)
        
        frontier = []
        
        for target_ret in np.linspace(min_ret, max_ret, n_points):
            try:
                portfolio = self.target_return_portfolio(target_ret)
                frontier.append({
                    "return": round(portfolio.expected_return * 100, 2),
                    "volatility": round(portfolio.volatility * 100, 2),
                    "sharpe": round(portfolio.sharpe_ratio, 3)
                })
            except Exception:
                continue
        
        return frontier
    
    def monte_carlo_simulation(self, n_portfolios: int = 5000) -> Dict:
        """
        Run Monte Carlo simulation to explore portfolio space.
        """
        n_assets = len(self.symbols)
        
        results = {
            "returns": [],
            "volatilities": [],
            "sharpes": [],
            "weights": []
        }
        
        for _ in range(n_portfolios):
            # Random weights
            weights = np.random.random(n_assets)
            weights /= np.sum(weights)
            
            ret, vol, sharpe = self.portfolio_performance(weights)
            
            results["returns"].append(ret)
            results["volatilities"].append(vol)
            results["sharpes"].append(sharpe)
            results["weights"].append(weights.tolist())
        
        # Find best portfolios
        best_sharpe_idx = np.argmax(results["sharpes"])
        min_vol_idx = np.argmin(results["volatilities"])
        
        return {
            "n_simulations": n_portfolios,
            "best_sharpe": {
                "return": round(results["returns"][best_sharpe_idx] * 100, 2),
                "volatility": round(results["volatilities"][best_sharpe_idx] * 100, 2),
                "sharpe": round(results["sharpes"][best_sharpe_idx], 3),
                "weights": {self.symbols[i]: round(results["weights"][best_sharpe_idx][i], 4) 
                          for i in range(n_assets)}
            },
            "min_volatility": {
                "return": round(results["returns"][min_vol_idx] * 100, 2),
                "volatility": round(results["volatilities"][min_vol_idx] * 100, 2),
                "sharpe": round(results["sharpes"][min_vol_idx], 3),
                "weights": {self.symbols[i]: round(results["weights"][min_vol_idx][i], 4) 
                          for i in range(n_assets)}
            },
            "stats": {
                "mean_return": round(np.mean(results["returns"]) * 100, 2),
                "mean_volatility": round(np.mean(results["volatilities"]) * 100, 2),
                "mean_sharpe": round(np.mean(results["sharpes"]), 3)
            }
        }
    
    def get_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get correlation matrix as nested dict."""
        corr = np.corrcoef(self.returns.T)
        
        result = {}
        for i, sym1 in enumerate(self.symbols):
            result[sym1] = {}
            for j, sym2 in enumerate(self.symbols):
                result[sym1][sym2] = round(corr[i, j], 3)
        
        return result
    
    def get_individual_stats(self) -> Dict[str, Dict]:
        """Get statistics for each individual asset."""
        stats = {}
        
        for i, symbol in enumerate(self.symbols):
            ret = self.mean_returns[i]
            vol = np.sqrt(self.cov_matrix[i, i])
            sharpe = (ret - self.risk_free_rate) / vol if vol > 0 else 0
            
            # Historical stats
            asset_returns = self.returns[:, i]
            
            stats[symbol] = {
                "expected_return": round(ret * 100, 2),
                "volatility": round(vol * 100, 2),
                "sharpe_ratio": round(sharpe, 3),
                "max_drawdown": round(self._max_drawdown(asset_returns) * 100, 2),
                "skewness": round(float(stats.skew(asset_returns)) if hasattr(stats, 'skew') else 0, 3),
                "kurtosis": round(float(stats.kurtosis(asset_returns)) if hasattr(stats, 'kurtosis') else 0, 3),
                "var_95": round(np.percentile(asset_returns, 5) * 100, 2)
            }
        
        return stats
    
    def _max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns."""
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(np.min(drawdown))
    
    def optimize(self) -> OptimizationResult:
        """Run full optimization and return results."""
        return OptimizationResult(
            optimal_portfolio=self.max_sharpe_portfolio(),
            min_volatility=self.min_volatility_portfolio(),
            max_sharpe=self.max_sharpe_portfolio(),
            risk_parity=self.risk_parity_portfolio(),
            efficient_frontier=self.efficient_frontier(30),
            correlation_matrix=self.get_correlation_matrix(),
            individual_stats=self.get_individual_stats()
        )
    
    def rebalancing_recommendation(self, current_weights: Dict[str, float],
                                   threshold: float = 0.05) -> Dict:
        """
        Generate rebalancing recommendations.
        
        Args:
            current_weights: Current portfolio weights
            threshold: Minimum deviation to trigger rebalancing
        """
        optimal = self.max_sharpe_portfolio()
        target_weights = optimal.weights
        
        recommendations = []
        total_turnover = 0
        
        for symbol in self.symbols:
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            diff = target - current
            
            if abs(diff) > threshold:
                action = "BUY" if diff > 0 else "SELL"
                recommendations.append({
                    "symbol": symbol,
                    "action": action,
                    "current_weight": round(current * 100, 2),
                    "target_weight": round(target * 100, 2),
                    "change": round(diff * 100, 2)
                })
                total_turnover += abs(diff)
        
        return {
            "needs_rebalancing": len(recommendations) > 0,
            "recommendations": recommendations,
            "total_turnover": round(total_turnover * 100, 2),
            "target_portfolio": optimal.to_dict()
        }
    
    def print_summary(self):
        """Print optimization summary."""
        result = self.optimize()
        
        print("\n" + "="*70)
        print("PORTFOLIO OPTIMIZATION RESULTS")
        print("="*70)
        print(f"Assets: {', '.join(self.symbols)}")
        print(f"Risk-free rate: {self.risk_free_rate*100:.1f}%")
        
        print("\n" + "-"*70)
        print("OPTIMAL PORTFOLIOS")
        print("-"*70)
        
        print("\n1. Maximum Sharpe Ratio Portfolio:")
        ms = result.max_sharpe
        print(f"   Expected Return: {ms.expected_return*100:.2f}%")
        print(f"   Volatility: {ms.volatility*100:.2f}%")
        print(f"   Sharpe Ratio: {ms.sharpe_ratio:.3f}")
        print("   Weights:")
        for sym, weight in sorted(ms.weights.items(), key=lambda x: -x[1]):
            if weight > 0.01:
                print(f"      {sym}: {weight*100:.1f}%")
        
        print("\n2. Minimum Volatility Portfolio:")
        mv = result.min_volatility
        print(f"   Expected Return: {mv.expected_return*100:.2f}%")
        print(f"   Volatility: {mv.volatility*100:.2f}%")
        print(f"   Sharpe Ratio: {mv.sharpe_ratio:.3f}")
        
        print("\n3. Risk Parity Portfolio:")
        rp = result.risk_parity
        print(f"   Expected Return: {rp.expected_return*100:.2f}%")
        print(f"   Volatility: {rp.volatility*100:.2f}%")
        print(f"   Sharpe Ratio: {rp.sharpe_ratio:.3f}")
        
        print("\n" + "-"*70)
        print("CORRELATION MATRIX")
        print("-"*70)
        corr = result.correlation_matrix
        print(f"{'':>8}", end="")
        for sym in self.symbols:
            print(f"{sym:>8}", end="")
        print()
        for sym1 in self.symbols:
            print(f"{sym1:>8}", end="")
            for sym2 in self.symbols:
                print(f"{corr[sym1][sym2]:>8.2f}", end="")
            print()
        
        print("\n" + "-"*70)
        print("INDIVIDUAL ASSET STATISTICS")
        print("-"*70)
        stats = result.individual_stats
        print(f"{'Symbol':>8} {'Return':>10} {'Vol':>10} {'Sharpe':>10} {'MaxDD':>10}")
        for sym, s in stats.items():
            print(f"{sym:>8} {s['expected_return']:>9.1f}% {s['volatility']:>9.1f}% "
                  f"{s['sharpe_ratio']:>10.2f} {s['max_drawdown']:>9.1f}%")
        
        print("\n" + "="*70)


if __name__ == "__main__":
    # Demo
    print("Portfolio Optimization Demo")
    
    # Example portfolio
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
    
    optimizer = PortfolioOptimizer(symbols)
    optimizer.print_summary()
    
    # Monte Carlo simulation
    print("\nMonte Carlo Simulation (5000 portfolios):")
    mc = optimizer.monte_carlo_simulation(5000)
    print(f"  Best Sharpe: {mc['best_sharpe']['sharpe']:.3f} "
          f"(Return: {mc['best_sharpe']['return']:.1f}%, Vol: {mc['best_sharpe']['volatility']:.1f}%)")
    print(f"  Min Vol: {mc['min_volatility']['volatility']:.1f}% "
          f"(Return: {mc['min_volatility']['return']:.1f}%, Sharpe: {mc['min_volatility']['sharpe']:.3f})")
