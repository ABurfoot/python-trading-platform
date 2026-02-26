#!/usr/bin/env python3
"""
Stock Comparison
================
Compare multiple stocks side by side.

Features:
- Compare 2-5 stocks
- Technical, fundamental, risk metrics
- Visual comparison in terminal
- Ranking by various criteria

Usage:
    from trading.comparison import StockComparison
    
    comp = StockComparison()
    result = comp.compare(["AAPL", "MSFT", "GOOGL"])
    comp.print_comparison(result)
"""

import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from trading.analyzer import StockAnalyzer, AnalysisResult, Signal
except ImportError:
    StockAnalyzer = None


@dataclass
class ComparisonResult:
    """Result of comparing multiple stocks."""
    symbols: List[str]
    analyses: Dict[str, AnalysisResult]
    rankings: Dict[str, List[str]]  # metric -> [symbol1, symbol2, ...]
    winner: str
    summary: str


class StockComparison:
    """Compare multiple stocks."""
    
    def __init__(self):
        if StockAnalyzer is None:
            raise ImportError("StockAnalyzer not available")
        self.analyzer = StockAnalyzer()
    
    def compare(self, symbols: List[str], verbose: bool = True) -> ComparisonResult:
        """
        Compare multiple stocks (with parallel analysis).
        
        Args:
            symbols: List of stock symbols (2-8 recommended)
            verbose: Print progress
        
        Returns:
            ComparisonResult with analyses and rankings
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if len(symbols) < 2:
            raise ValueError("Need at least 2 symbols to compare")
        
        if len(symbols) > 8:
            symbols = symbols[:8]
            if verbose:
                print(f"[WARN] Limiting to 8 stocks for comparison")
        
        analyses = {}
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Analyzing {len(symbols)} stocks in parallel...")
            print('='*60)
        
        # Analyze all stocks in parallel
        def analyze_symbol(sym):
            try:
                return sym, self.analyzer.analyze(sym)
            except Exception as e:
                return sym, None
        
        with ThreadPoolExecutor(max_workers=min(len(symbols), 6)) as executor:
            futures = {executor.submit(analyze_symbol, sym): sym for sym in symbols}
            
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    symbol, result = future.result()
                    if result:
                        analyses[symbol] = result
                        if verbose:
                            print(f"   [OK] {symbol}")
                    elif verbose:
                        print(f"   [WARN] Failed to analyze {symbol}")
                except Exception as e:
                    if verbose:
                        print(f"   [WARN] Error analyzing {sym}: {e}")
        
        if len(analyses) < 2:
            raise ValueError("Could not analyze enough stocks for comparison")
        
        # Calculate rankings
        rankings = self._calculate_rankings(analyses)
        
        # Determine overall winner
        winner = self._determine_winner(analyses, rankings)
        
        # Generate summary
        summary = self._generate_summary(analyses, rankings, winner)
        
        return ComparisonResult(
            symbols=list(analyses.keys()),
            analyses=analyses,
            rankings=rankings,
            winner=winner,
            summary=summary
        )
    
    def _calculate_rankings(self, analyses: Dict[str, AnalysisResult]) -> Dict[str, List[str]]:
        """Calculate rankings for each metric."""
        rankings = {}
        
        # Overall score (higher is better)
        rankings["overall_score"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].overall_score,
            reverse=True
        )
        
        # Technical score
        rankings["technical"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].technical_score,
            reverse=True
        )
        
        # Fundamental score
        rankings["fundamental"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].fundamental_score,
            reverse=True
        )
        
        # Risk (lower is better)
        rankings["risk"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].risk_metrics.risk_score
        )
        
        # P/E ratio (lower is better, but skip 0)
        pe_valid = {s: a for s, a in analyses.items() if a.pe_ratio and a.pe_ratio > 0}
        if pe_valid:
            rankings["pe_ratio"] = sorted(
                pe_valid.keys(),
                key=lambda s: pe_valid[s].pe_ratio
            )
        
        # Upside potential (higher is better)
        rankings["upside"] = sorted(
            analyses.keys(),
            key=lambda s: (analyses[s].target_mid - analyses[s].current_price) / analyses[s].current_price if analyses[s].current_price > 0 else 0,
            reverse=True
        )
        
        # Sharpe ratio (higher is better)
        rankings["sharpe"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].risk_metrics.sharpe_ratio,
            reverse=True
        )
        
        # Volatility (lower is better)
        rankings["volatility"] = sorted(
            analyses.keys(),
            key=lambda s: analyses[s].risk_metrics.volatility_annual
        )
        
        return rankings
    
    def _determine_winner(self, analyses: Dict[str, AnalysisResult], rankings: Dict[str, List[str]]) -> str:
        """Determine the overall best stock based on rankings."""
        # Score each stock based on rankings
        scores = {s: 0 for s in analyses.keys()}
        
        weights = {
            "overall_score": 3,
            "technical": 2,
            "fundamental": 2,
            "risk": 2,
            "upside": 1,
            "sharpe": 1,
        }
        
        for metric, ranked in rankings.items():
            weight = weights.get(metric, 1)
            for i, symbol in enumerate(ranked):
                # Higher rank (lower index) = more points
                scores[symbol] += (len(ranked) - i) * weight
        
        return max(scores.keys(), key=lambda s: scores[s])
    
    def _generate_summary(self, analyses: Dict[str, AnalysisResult], rankings: Dict[str, List[str]], winner: str) -> str:
        """Generate comparison summary."""
        winner_analysis = analyses[winner]
        
        parts = [f"{winner} ranks best overall"]
        
        # Add key advantages
        if rankings["overall_score"][0] == winner:
            parts.append(f"highest score ({winner_analysis.overall_score:.0f}/100)")
        
        if rankings.get("pe_ratio") and rankings["pe_ratio"][0] == winner:
            parts.append(f"best value (P/E: {winner_analysis.pe_ratio:.1f})")
        
        if rankings["risk"][0] == winner:
            parts.append("lowest risk")
        
        return "; ".join(parts)
    
    def print_comparison(self, result: ComparisonResult):
        """Print comparison table to terminal."""
        analyses = result.analyses
        symbols = result.symbols
        w = 80
        col_w = max(12, (w - 20) // len(symbols))
        
        def fmt_val(val, fmt=".1f"):
            if val is None:
                return "N/A"
            if isinstance(val, float):
                return f"{val:{fmt}}"
            return str(val)
        
        def rank_indicator(symbol: str, ranking: List[str]) -> str:
            if not ranking:
                return ""
            idx = ranking.index(symbol) if symbol in ranking else -1
            if idx == 0:
                return " 🥇"
            elif idx == 1:
                return " 🥈"
            elif idx == 2:
                return " 🥉"
            return ""
        
        print()
        print("╔" + "═" * w + "╗")
        print("║" + "STOCK COMPARISON".center(w) + "║")
        print("╠" + "═" * w + "╣")
        
        # Header row
        header = "  Metric".ljust(20)
        for s in symbols:
            header += s.center(col_w)
        print("║" + header.ljust(w) + "║")
        print("╠" + "═" * w + "╣")
        
        # Price
        row = "  Price".ljust(20)
        for s in symbols:
            a = analyses[s]
            cs = getattr(a, 'currency_symbol', '$')
            row += f"{cs}{a.current_price:.2f}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Change %
        row = "  Change %".ljust(20)
        for s in symbols:
            a = analyses[s]
            row += f"{a.change_pct:+.2f}%".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "─" * w + "╣")
        
        # Overall Score
        row = "  Overall Score".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["overall_score"])
            row += f"{a.overall_score:.0f}/100{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Recommendation
        row = "  Recommendation".ljust(20)
        for s in symbols:
            a = analyses[s]
            rec = a.recommendation.value.split()[0]  # Just first word
            row += rec.center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Confidence
        row = "  Confidence".ljust(20)
        for s in symbols:
            a = analyses[s]
            row += f"{a.confidence:.0f}%".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "─" * w + "╣")
        
        # Technical Score
        row = "  Technical".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["technical"])
            row += f"{a.technical_score:.0f}{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Fundamental Score
        row = "  Fundamental".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["fundamental"])
            row += f"{a.fundamental_score:.0f}{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "─" * w + "╣")
        
        # P/E Ratio
        row = "  P/E Ratio".ljust(20)
        for s in symbols:
            a = analyses[s]
            pe = f"{a.pe_ratio:.1f}" if a.pe_ratio else "N/A"
            rank = rank_indicator(s, result.rankings.get("pe_ratio", []))
            row += f"{pe}{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Beta
        row = "  Beta".ljust(20)
        for s in symbols:
            a = analyses[s]
            row += f"{a.beta:.2f}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Market Cap
        row = "  Market Cap".ljust(20)
        for s in symbols:
            a = analyses[s]
            mc = a.market_cap
            if mc >= 1e12:
                mc_str = f"${mc/1e12:.1f}T"
            elif mc >= 1e9:
                mc_str = f"${mc/1e9:.1f}B"
            else:
                mc_str = f"${mc/1e6:.0f}M"
            row += mc_str.center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "─" * w + "╣")
        
        # Volatility
        row = "  Volatility".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["volatility"])
            row += f"{a.risk_metrics.volatility_annual:.1f}%{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Sharpe Ratio
        row = "  Sharpe Ratio".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["sharpe"])
            row += f"{a.risk_metrics.sharpe_ratio:.2f}{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # Risk Score
        row = "  Risk Score".ljust(20)
        for s in symbols:
            a = analyses[s]
            rank = rank_indicator(s, result.rankings["risk"])
            row += f"{a.risk_metrics.risk_score:.0f}/10{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "─" * w + "╣")
        
        # Upside to Target
        row = "  Target Upside".ljust(20)
        for s in symbols:
            a = analyses[s]
            upside = (a.target_mid - a.current_price) / a.current_price * 100 if a.current_price > 0 else 0
            rank = rank_indicator(s, result.rankings["upside"])
            row += f"{upside:+.1f}%{rank}".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        # 52w Position
        row = "  52w Position".ljust(20)
        for s in symbols:
            a = analyses[s]
            row += f"{a.week_52_position:.0f}%".center(col_w)
        print("║" + row.ljust(w) + "║")
        
        print("╠" + "═" * w + "╣")
        
        # Winner
        print("║" + f"  🏆 WINNER: {result.winner}".ljust(w) + "║")
        print("║" + f"  {result.summary[:w-4]}".ljust(w) + "║")
        
        print("╚" + "═" * w + "╝")
        print()


def compare_stocks(symbols: List[str]):
    """Quick comparison function."""
    comp = StockComparison()
    result = comp.compare(symbols)
    comp.print_comparison(result)
    return result


# CLI
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare stocks")
    parser.add_argument("symbols", nargs="+", help="Stock symbols to compare")
    
    args = parser.parse_args()
    
    try:
        compare_stocks(args.symbols)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
