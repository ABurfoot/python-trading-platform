#!/usr/bin/env python3
"""
Correlation Matrix Module
==========================
Analyze correlations between assets in your portfolio.

Features:
- Calculate correlation matrix for any list of symbols
- Support for different time periods (1M, 3M, 6M, 1Y, 2Y)
- Identify highly correlated and negatively correlated pairs
- Diversification score
- Heatmap visualization (ASCII and data for plotting)
- Rolling correlation analysis
- Portfolio risk analysis based on correlations

Usage:
    from trading.correlation import CorrelationAnalyzer
    
    analyzer = CorrelationAnalyzer()
    
    # Analyze correlations
    matrix = analyzer.calculate_correlation(["AAPL", "MSFT", "GOOGL", "AMZN"])
    
    # Print results
    analyzer.print_matrix()
    analyzer.print_insights()
    
    # Get diversification score
    score = analyzer.get_diversification_score()
"""

import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics


# Simple cache for price data
_corr_cache = {}
_cache_ttl = {}
_CACHE_DURATION = 600  # 10 minute cache for historical prices


def _get_cached(key: str) -> Optional[any]:
    """Get cached value if not expired."""
    if key in _corr_cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _corr_cache[key]
        else:
            del _corr_cache[key]
            del _cache_ttl[key]
    return None


def _set_cached(key: str, value: any, ttl: int = None):
    """Set cached value with TTL."""
    _corr_cache[key] = value
    _cache_ttl[key] = time.time() + (ttl or _CACHE_DURATION)


@dataclass
class CorrelationPair:
    """A pair of assets with their correlation."""
    symbol1: str
    symbol2: str
    correlation: float
    strength: str = ""  # strong_positive, moderate_positive, weak, moderate_negative, strong_negative
    
    def __post_init__(self):
        if not self.strength:
            self.strength = self._get_strength()
    
    def _get_strength(self) -> str:
        """Categorize correlation strength."""
        c = abs(self.correlation)
        if c >= 0.7:
            prefix = "strong"
        elif c >= 0.4:
            prefix = "moderate"
        else:
            prefix = "weak"
        
        if self.correlation >= 0:
            return f"{prefix}_positive"
        else:
            return f"{prefix}_negative"


@dataclass
class CorrelationInsights:
    """Insights from correlation analysis."""
    total_pairs: int = 0
    avg_correlation: float = 0
    
    # Highly correlated pairs (> 0.7)
    highly_correlated: List[CorrelationPair] = field(default_factory=list)
    
    # Negatively correlated pairs (< -0.3)
    negatively_correlated: List[CorrelationPair] = field(default_factory=list)
    
    # Diversification
    diversification_score: float = 0  # 0-100, higher is better
    diversification_rating: str = ""  # Poor, Fair, Good, Excellent
    
    # Risk
    concentration_risk: str = ""
    suggestions: List[str] = field(default_factory=list)


class CorrelationAnalyzer:
    """
    Analyze correlations between assets.
    """
    
    def __init__(self):
        """Initialize correlation analyzer."""
        self.symbols: List[str] = []
        self.returns: Dict[str, List[float]] = {}
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
        self.period: str = "1Y"
        self._price_data: Dict[str, List[Tuple[str, float]]] = {}
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    def _fetch_prices(self, symbol: str, days: int = 252) -> List[Tuple[str, float]]:
        """Fetch historical prices for a symbol."""
        # Try data sources
        try:
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            data = fetcher.get_historical(symbol, period=f"{days}d")
            if data and len(data) > 0:
                return [(d.get("date", ""), d.get("close", 0)) for d in data if d.get("close")]
        except Exception:
            pass
        
        # Try Yahoo Finance directly
        try:
            import subprocess
            # This would need yfinance, fallback to empty
            pass
        except Exception:
            pass
        
        return []
    
    def _calculate_returns(self, prices: List[Tuple[str, float]]) -> List[float]:
        """Calculate daily returns from prices."""
        if len(prices) < 2:
            return []
        
        returns = []
        for i in range(1, len(prices)):
            prev_price = prices[i-1][1]
            curr_price = prices[i][1]
            if prev_price > 0:
                daily_return = (curr_price - prev_price) / prev_price
                returns.append(daily_return)
        
        return returns
    
    def _get_period_days(self, period: str) -> int:
        """Convert period string to number of days."""
        periods = {
            "1M": 21,
            "3M": 63,
            "6M": 126,
            "1Y": 252,
            "2Y": 504,
            "5Y": 1260,
        }
        return periods.get(period.upper(), 252)
    
    # =========================================================================
    # CORRELATION CALCULATION
    # =========================================================================
    
    def calculate_correlation(self, symbols: List[str], period: str = "1Y") -> Dict[str, Dict[str, float]]:
        """
        Calculate correlation matrix for a list of symbols (with parallel fetching).
        
        Args:
            symbols: List of stock/ETF symbols
            period: Time period (1M, 3M, 6M, 1Y, 2Y)
        
        Returns:
            Correlation matrix as nested dictionary
        """
        self.symbols = [s.upper() for s in symbols]
        self.period = period
        days = self._get_period_days(period)
        
        print(f"Calculating correlations for {len(symbols)} assets over {period}...")
        
        # Fetch prices and calculate returns - IN PARALLEL
        self.returns = {}
        self._price_data = {}
        
        def fetch_and_process(symbol):
            """Fetch prices and calculate returns for a symbol."""
            # Check cache first
            cache_key = f"corr_prices_{symbol}_{days}"
            cached = _get_cached(cache_key)
            if cached is not None:
                return symbol, cached, self._calculate_returns(cached)
            
            prices = self._fetch_prices(symbol, days)
            if prices:
                _set_cached(cache_key, prices)
                returns = self._calculate_returns(prices)
                return symbol, prices, returns
            return symbol, None, None
        
        # Parallel fetch
        with ThreadPoolExecutor(max_workers=min(len(self.symbols), 8)) as executor:
            futures = {executor.submit(fetch_and_process, sym): sym for sym in self.symbols}
            
            for future in as_completed(futures):
                try:
                    symbol, prices, returns = future.result()
                    self._price_data[symbol] = prices
                    if returns:
                        self.returns[symbol] = returns
                        print(f"   [OK] {symbol}: {len(returns)} data points")
                    else:
                        print(f"   ⚠ {symbol}: No data available")
                except Exception as e:
                    symbol = futures[future]
                    print(f"   ⚠ {symbol}: Error - {e}")
            else:
                print(f"   ⚠ {symbol}: No data available")
        
        # Calculate correlation matrix
        self.correlation_matrix = {}
        
        for symbol1 in self.symbols:
            self.correlation_matrix[symbol1] = {}
            
            for symbol2 in self.symbols:
                if symbol1 == symbol2:
                    self.correlation_matrix[symbol1][symbol2] = 1.0
                elif symbol2 in self.correlation_matrix and symbol1 in self.correlation_matrix[symbol2]:
                    # Use already calculated value
                    self.correlation_matrix[symbol1][symbol2] = self.correlation_matrix[symbol2][symbol1]
                else:
                    corr = self._calculate_pair_correlation(symbol1, symbol2)
                    self.correlation_matrix[symbol1][symbol2] = corr
        
        print(f"[OK] Correlation matrix calculated")
        return self.correlation_matrix
    
    def _calculate_pair_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate Pearson correlation between two assets."""
        returns1 = self.returns.get(symbol1, [])
        returns2 = self.returns.get(symbol2, [])
        
        if not returns1 or not returns2:
            return 0.0
        
        # Align returns (use minimum length)
        min_len = min(len(returns1), len(returns2))
        r1 = returns1[-min_len:]
        r2 = returns2[-min_len:]
        
        if min_len < 10:
            return 0.0
        
        # Calculate Pearson correlation
        try:
            mean1 = statistics.mean(r1)
            mean2 = statistics.mean(r2)
            
            numerator = sum((r1[i] - mean1) * (r2[i] - mean2) for i in range(min_len))
            
            sum_sq1 = sum((r - mean1) ** 2 for r in r1)
            sum_sq2 = sum((r - mean2) ** 2 for r in r2)
            
            denominator = math.sqrt(sum_sq1 * sum_sq2)
            
            if denominator == 0:
                return 0.0
            
            correlation = numerator / denominator
            return round(correlation, 4)
        
        except Exception:
            return 0.0
    
    def set_correlation_matrix(self, matrix: Dict[str, Dict[str, float]], symbols: List[str] = None):
        """
        Set correlation matrix directly (for testing or pre-calculated data).
        
        Args:
            matrix: Correlation matrix as nested dictionary
            symbols: List of symbols (optional, inferred from matrix)
        """
        self.correlation_matrix = matrix
        self.symbols = symbols or list(matrix.keys())
    
    def set_returns(self, returns: Dict[str, List[float]]):
        """
        Set returns data directly.
        
        Args:
            returns: Dictionary mapping symbols to list of returns
        """
        self.returns = returns
        if not self.symbols:
            self.symbols = list(returns.keys())
    
    # =========================================================================
    # ANALYSIS
    # =========================================================================
    
    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two specific symbols."""
        symbol1 = symbol1.upper()
        symbol2 = symbol2.upper()
        
        if symbol1 in self.correlation_matrix and symbol2 in self.correlation_matrix[symbol1]:
            return self.correlation_matrix[symbol1][symbol2]
        return 0.0
    
    def get_all_pairs(self) -> List[CorrelationPair]:
        """Get all unique pairs with their correlations."""
        pairs = []
        seen = set()
        
        for symbol1 in self.symbols:
            for symbol2 in self.symbols:
                if symbol1 != symbol2:
                    pair_key = tuple(sorted([symbol1, symbol2]))
                    if pair_key not in seen:
                        seen.add(pair_key)
                        corr = self.correlation_matrix.get(symbol1, {}).get(symbol2, 0)
                        pairs.append(CorrelationPair(symbol1, symbol2, corr))
        
        return pairs
    
    def get_highly_correlated(self, threshold: float = 0.7) -> List[CorrelationPair]:
        """Get pairs with correlation above threshold."""
        pairs = self.get_all_pairs()
        return [p for p in pairs if p.correlation >= threshold]
    
    def get_negatively_correlated(self, threshold: float = -0.3) -> List[CorrelationPair]:
        """Get pairs with negative correlation below threshold."""
        pairs = self.get_all_pairs()
        return [p for p in pairs if p.correlation <= threshold]
    
    def get_diversification_score(self) -> float:
        """
        Calculate diversification score (0-100).
        
        Higher score = better diversification (lower average correlation)
        """
        pairs = self.get_all_pairs()
        
        if not pairs:
            return 0.0
        
        avg_corr = statistics.mean(abs(p.correlation) for p in pairs)
        
        # Score: 100 when avg_corr = 0, 0 when avg_corr = 1
        score = (1 - avg_corr) * 100
        return round(score, 1)
    
    def get_insights(self) -> CorrelationInsights:
        """Generate insights from correlation analysis."""
        insights = CorrelationInsights()
        
        pairs = self.get_all_pairs()
        insights.total_pairs = len(pairs)
        
        if not pairs:
            return insights
        
        # Average correlation
        insights.avg_correlation = statistics.mean(p.correlation for p in pairs)
        
        # Highly correlated
        insights.highly_correlated = sorted(
            self.get_highly_correlated(0.7),
            key=lambda p: p.correlation,
            reverse=True
        )
        
        # Negatively correlated
        insights.negatively_correlated = sorted(
            self.get_negatively_correlated(-0.3),
            key=lambda p: p.correlation
        )
        
        # Diversification score
        insights.diversification_score = self.get_diversification_score()
        
        if insights.diversification_score >= 70:
            insights.diversification_rating = "Excellent"
        elif insights.diversification_score >= 50:
            insights.diversification_rating = "Good"
        elif insights.diversification_score >= 30:
            insights.diversification_rating = "Fair"
        else:
            insights.diversification_rating = "Poor"
        
        # Concentration risk
        highly_correlated_count = len(insights.highly_correlated)
        total_pairs = len(pairs)
        
        if total_pairs > 0:
            concentration_pct = (highly_correlated_count / total_pairs) * 100
            if concentration_pct > 50:
                insights.concentration_risk = "High"
            elif concentration_pct > 25:
                insights.concentration_risk = "Moderate"
            else:
                insights.concentration_risk = "Low"
        
        # Suggestions
        if insights.highly_correlated:
            symbols_in_high_corr = set()
            for p in insights.highly_correlated[:3]:
                symbols_in_high_corr.add(p.symbol1)
                symbols_in_high_corr.add(p.symbol2)
            insights.suggestions.append(
                f"Consider reducing overlap: {', '.join(symbols_in_high_corr)} are highly correlated"
            )
        
        if not insights.negatively_correlated:
            insights.suggestions.append(
                "Consider adding negatively correlated assets (e.g., bonds, gold) for better hedging"
            )
        
        if insights.diversification_score < 50:
            insights.suggestions.append(
                "Portfolio may benefit from more diverse sectors/asset classes"
            )
        
        return insights
    
    # =========================================================================
    # ROLLING CORRELATION
    # =========================================================================
    
    def calculate_rolling_correlation(self, symbol1: str, symbol2: str, 
                                      window: int = 30) -> List[Tuple[str, float]]:
        """
        Calculate rolling correlation between two assets.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            window: Rolling window size (days)
        
        Returns:
            List of (date, correlation) tuples
        """
        symbol1 = symbol1.upper()
        symbol2 = symbol2.upper()
        
        returns1 = self.returns.get(symbol1, [])
        returns2 = self.returns.get(symbol2, [])
        
        if len(returns1) < window or len(returns2) < window:
            return []
        
        min_len = min(len(returns1), len(returns2))
        r1 = returns1[-min_len:]
        r2 = returns2[-min_len:]
        
        rolling_corr = []
        
        for i in range(window, min_len + 1):
            window_r1 = r1[i-window:i]
            window_r2 = r2[i-window:i]
            
            try:
                mean1 = statistics.mean(window_r1)
                mean2 = statistics.mean(window_r2)
                
                numerator = sum((window_r1[j] - mean1) * (window_r2[j] - mean2) 
                               for j in range(window))
                
                sum_sq1 = sum((r - mean1) ** 2 for r in window_r1)
                sum_sq2 = sum((r - mean2) ** 2 for r in window_r2)
                
                denominator = math.sqrt(sum_sq1 * sum_sq2)
                
                if denominator > 0:
                    corr = numerator / denominator
                else:
                    corr = 0
                
                # Get date if available
                if symbol1 in self._price_data and i < len(self._price_data[symbol1]):
                    date = self._price_data[symbol1][i][0]
                else:
                    date = str(i)
                
                rolling_corr.append((date, round(corr, 4)))
            except Exception:
                continue
        
        return rolling_corr
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_matrix(self):
        """Print correlation matrix."""
        if not self.correlation_matrix:
            print("No correlation data. Run calculate_correlation() first.")
            return
        
        print(f"\n{'='*70}")
        print(f"CORRELATION MATRIX ({self.period})")
        print(f"{'='*70}")
        
        # Calculate column width
        col_width = max(8, max(len(s) for s in self.symbols) + 1)
        
        # Header row
        header = " " * col_width
        for symbol in self.symbols:
            header += f"{symbol:>{col_width}}"
        print(f"\n{header}")
        print("-" * len(header))
        
        # Data rows
        for symbol1 in self.symbols:
            row = f"{symbol1:<{col_width}}"
            for symbol2 in self.symbols:
                corr = self.correlation_matrix.get(symbol1, {}).get(symbol2, 0)
                
                # Color coding (using emoji)
                if symbol1 == symbol2:
                    cell = "  1.00"
                elif corr >= 0.7:
                    cell = f"{corr:>6.2f}"  # High positive
                elif corr <= -0.3:
                    cell = f"{corr:>6.2f}"  # Negative
                else:
                    cell = f"{corr:>6.2f}"
                
                row += f"{cell:>{col_width}}"
            print(row)
        
        print(f"\n{'='*70}\n")
    
    def print_heatmap(self):
        """Print ASCII heatmap of correlations."""
        if not self.correlation_matrix:
            print("No correlation data. Run calculate_correlation() first.")
            return
        
        print(f"\n{'='*60}")
        print("🗺️  CORRELATION HEATMAP")
        print(f"{'='*60}")
        print("\n   Legend: ██ > 0.7 | ▓▓ > 0.4 | ░░ > 0 | ▒▒ < 0 | ▄▄ < -0.3\n")
        
        col_width = max(6, max(len(s) for s in self.symbols) + 1)
        
        # Header
        header = " " * col_width
        for symbol in self.symbols:
            header += f"{symbol:>{col_width}}"
        print(header)
        
        # Rows
        for symbol1 in self.symbols:
            row = f"{symbol1:<{col_width}}"
            for symbol2 in self.symbols:
                corr = self.correlation_matrix.get(symbol1, {}).get(symbol2, 0)
                
                if symbol1 == symbol2:
                    cell = " ●●"
                elif corr >= 0.7:
                    cell = " ██"
                elif corr >= 0.4:
                    cell = " ▓▓"
                elif corr >= 0:
                    cell = " ░░"
                elif corr >= -0.3:
                    cell = " ▒▒"
                else:
                    cell = " ▄▄"
                
                row += f"{cell:>{col_width}}"
            print(row)
        
        print(f"\n{'='*60}\n")
    
    def print_insights(self):
        """Print correlation insights."""
        insights = self.get_insights()
        
        print(f"\n{'='*60}")
        print("CORRELATION INSIGHTS")
        print(f"{'='*60}")
        
        # Summary
        print(f"\n   SUMMARY")
        print(f"   {'-'*40}")
        print(f"   Assets Analyzed:      {len(self.symbols):>10}")
        print(f"   Total Pairs:          {insights.total_pairs:>10}")
        print(f"   Avg Correlation:      {insights.avg_correlation:>10.2f}")
        
        # Diversification
        print(f"\n   DIVERSIFICATION")
        print(f"   {'-'*40}")
        print(f"   Score:                {insights.diversification_score:>10.1f}/100")
        print(f"   Rating:               {insights.diversification_rating:>10}")
        print(f"   Concentration Risk:   {insights.concentration_risk:>10}")
        
        # Highly correlated
        if insights.highly_correlated:
            print(f"\n   HIGHLY CORRELATED PAIRS (>0.7)")
            print(f"   {'-'*40}")
            for pair in insights.highly_correlated[:5]:
                print(f"   {pair.symbol1} - {pair.symbol2}: {pair.correlation:>6.2f}")
        
        # Negatively correlated
        if insights.negatively_correlated:
            print(f"\n   ✅ NEGATIVELY CORRELATED PAIRS (<-0.3)")
            print(f"   {'-'*40}")
            for pair in insights.negatively_correlated[:5]:
                print(f"   {pair.symbol1} - {pair.symbol2}: {pair.correlation:>6.2f}")
        
        # Suggestions
        if insights.suggestions:
            print(f"\n   💡 SUGGESTIONS")
            print(f"   {'-'*40}")
            for suggestion in insights.suggestions:
                print(f"   • {suggestion}")
        
        print(f"\n{'='*60}\n")
    
    def print_pair_analysis(self, symbol1: str, symbol2: str):
        """Print detailed analysis of a specific pair."""
        symbol1 = symbol1.upper()
        symbol2 = symbol2.upper()
        
        corr = self.get_correlation(symbol1, symbol2)
        pair = CorrelationPair(symbol1, symbol2, corr)
        
        print(f"\n{'='*50}")
        print(f"PAIR ANALYSIS: {symbol1} vs {symbol2}")
        print(f"{'='*50}")
        
        print(f"\n   Correlation:     {corr:>10.4f}")
        print(f"   Strength:        {pair.strength:>10}")
        
        # Interpretation
        print(f"\n   📝 INTERPRETATION")
        print(f"   {'-'*30}")
        
        if corr >= 0.7:
            print(f"   These assets move together strongly.")
            print(f"   Holding both provides little diversification.")
        elif corr >= 0.4:
            print(f"   These assets have moderate positive correlation.")
            print(f"   Some diversification benefit exists.")
        elif corr >= 0:
            print(f"   These assets have weak correlation.")
            print(f"   Good for diversification.")
        elif corr >= -0.3:
            print(f"   These assets have weak negative correlation.")
            print(f"   Provides some hedging benefit.")
        else:
            print(f"   These assets move in opposite directions.")
            print(f"   Excellent for hedging/diversification.")
        
        print(f"\n{'='*50}\n")
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def to_dict(self) -> Dict:
        """Export correlation matrix as dictionary."""
        return {
            "symbols": self.symbols,
            "period": self.period,
            "matrix": self.correlation_matrix,
            "diversification_score": self.get_diversification_score(),
        }
    
    def to_list(self) -> List[Dict]:
        """Export all pairs as list of dictionaries."""
        pairs = self.get_all_pairs()
        return [
            {
                "symbol1": p.symbol1,
                "symbol2": p.symbol2,
                "correlation": p.correlation,
                "strength": p.strength,
            }
            for p in pairs
        ]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_correlation(returns1: List[float], returns2: List[float]) -> float:
    """
    Calculate Pearson correlation between two return series.
    
    Args:
        returns1: First return series
        returns2: Second return series
    
    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(returns1) != len(returns2) or len(returns1) < 2:
        return 0.0
    
    n = len(returns1)
    mean1 = statistics.mean(returns1)
    mean2 = statistics.mean(returns2)
    
    numerator = sum((returns1[i] - mean1) * (returns2[i] - mean2) for i in range(n))
    
    sum_sq1 = sum((r - mean1) ** 2 for r in returns1)
    sum_sq2 = sum((r - mean2) ** 2 for r in returns2)
    
    denominator = math.sqrt(sum_sq1 * sum_sq2)
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator


def interpret_correlation(corr: float) -> str:
    """
    Interpret correlation value.
    
    Args:
        corr: Correlation coefficient
    
    Returns:
        Human-readable interpretation
    """
    if corr >= 0.7:
        return "Strong positive - assets move together"
    elif corr >= 0.4:
        return "Moderate positive - some co-movement"
    elif corr >= 0.1:
        return "Weak positive - slight co-movement"
    elif corr >= -0.1:
        return "No correlation - independent movement"
    elif corr >= -0.4:
        return "Weak negative - slight opposite movement"
    elif corr >= -0.7:
        return "Moderate negative - some hedging benefit"
    else:
        return "Strong negative - excellent hedge"


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Correlation Matrix Analyzer")
    parser.add_argument("symbols", nargs="*", help="Symbols to analyze")
    parser.add_argument("--period", "-p", default="1Y", help="Period (1M, 3M, 6M, 1Y, 2Y)")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample data")
    
    args = parser.parse_args()
    
    analyzer = CorrelationAnalyzer()
    
    if args.demo:
        print("\n🎮 CORRELATION MATRIX DEMO")
        print("="*50)
        
        # Create sample correlation matrix (pre-calculated for demo)
        sample_matrix = {
            "AAPL": {"AAPL": 1.0, "MSFT": 0.85, "GOOGL": 0.78, "AMZN": 0.72, "GLD": -0.15},
            "MSFT": {"AAPL": 0.85, "MSFT": 1.0, "GOOGL": 0.82, "AMZN": 0.75, "GLD": -0.12},
            "GOOGL": {"AAPL": 0.78, "MSFT": 0.82, "GOOGL": 1.0, "AMZN": 0.80, "GLD": -0.08},
            "AMZN": {"AAPL": 0.72, "MSFT": 0.75, "GOOGL": 0.80, "AMZN": 1.0, "GLD": -0.05},
            "GLD": {"AAPL": -0.15, "MSFT": -0.12, "GOOGL": -0.08, "AMZN": -0.05, "GLD": 1.0},
        }
        
        analyzer.set_correlation_matrix(sample_matrix, ["AAPL", "MSFT", "GOOGL", "AMZN", "GLD"])
        analyzer.period = "1Y"
        
        analyzer.print_matrix()
        analyzer.print_heatmap()
        analyzer.print_insights()
        analyzer.print_pair_analysis("AAPL", "MSFT")
        analyzer.print_pair_analysis("AAPL", "GLD")
        
        print("\nUsage in code:")
        print("-"*40)
        print("""
from trading.correlation import CorrelationAnalyzer

analyzer = CorrelationAnalyzer()
matrix = analyzer.calculate_correlation(["AAPL", "MSFT", "GOOGL", "AMZN"])

analyzer.print_matrix()
analyzer.print_insights()

# Get specific correlation
corr = analyzer.get_correlation("AAPL", "MSFT")

# Get diversification score
score = analyzer.get_diversification_score()
""")
    
    elif args.symbols:
        analyzer.calculate_correlation(args.symbols, args.period)
        analyzer.print_matrix()
        analyzer.print_insights()
    
    else:
        print("\nUsage:")
        print("  python -m trading.correlation AAPL MSFT GOOGL AMZN")
        print("  python -m trading.correlation --demo")
        print("  python -m trading.correlation AAPL MSFT --period 6M")


if __name__ == "__main__":
    main()
