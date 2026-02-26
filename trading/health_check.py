#!/usr/bin/env python3
"""
Health Check Utility
=====================
Verify all trading platform components are working correctly.

Usage:
    python3 -m trading.health_check
    python3 trading/health_check.py
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_imports() -> List[Tuple[str, bool, str]]:
    """Check that all modules can be imported."""
    results = []
    
    modules = [
        ("trading.config", "Configuration"),
        ("trading.exchanges", "Exchange Support"),
        ("trading.alpaca_client", "Alpaca Client"),
        ("trading.data_sources", "Data Sources"),
        ("trading.analyzer", "Stock Analyzer"),
        ("trading.watchlist", "Watchlist Manager"),
        ("trading.alerts", "Alert Manager"),
        ("trading.portfolio", "Portfolio Manager"),
        ("trading.comparison", "Stock Comparison"),
        ("trading.news", "News Manager"),
        ("trading.earnings", "Earnings Calendar"),
        ("trading.sectors", "Sector Heatmap"),
        ("trading.screener", "Stock Screener"),
        ("trading.export", "Report Exporter"),
        ("trading.dashboard", "Dashboard"),
    ]
    
    for module, name in modules:
        try:
            __import__(module)
            results.append((name, True, "OK"))
        except ImportError as e:
            results.append((name, False, str(e)))
        except Exception as e:
            results.append((name, False, f"Error: {e}"))
    
    return results


def check_api_keys() -> List[Tuple[str, bool, str]]:
    """Check API key configuration."""
    results = []
    
    keys = [
        ("ALPACA_API_KEY", "Alpaca API"),
        ("ALPACA_SECRET_KEY", "Alpaca Secret"),
        ("FMP_API_KEY", "Financial Modeling Prep"),
        ("FINNHUB_API_KEY", "Finnhub"),
        ("ALPHAVANTAGE_API_KEY", "Alpha Vantage"),
    ]
    
    for env_var, name in keys:
        value = os.environ.get(env_var)
        if value:
            # Mask the key
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            results.append((name, True, f"Set ({masked})"))
        else:
            results.append((name, False, "Not configured"))
    
    return results


def check_data_sources() -> List[Tuple[str, bool, str]]:
    """Check that data sources are reachable."""
    results = []
    
    # Check Data Sources module
    try:
        from trading.data_sources import DataFetcher
        fetcher = DataFetcher()
        results.append(("Data Sources", True, "Available"))
    except Exception as e:
        results.append(("Data Sources", False, str(e)[:50]))
    
    # Check Alpaca
    try:
        from trading.alpaca_client import AlpacaClient
        client = AlpacaClient()
        account = client.get_account()
        if account:
            results.append(("Alpaca API", True, f"Equity: ${account.equity:,.2f}"))
        else:
            results.append(("Alpaca API", False, "No account data"))
    except Exception as e:
        results.append(("Alpaca API", False, str(e)[:50]))
    
    # Check Yahoo Finance (no key needed)
    try:
        import urllib.request
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                results.append(("Yahoo Finance", True, "Reachable"))
            else:
                results.append(("Yahoo Finance", False, f"HTTP {resp.status}"))
    except Exception as e:
        results.append(("Yahoo Finance", False, str(e)[:50]))
    
    return results


def check_storage() -> List[Tuple[str, bool, str]]:
    """Check storage directories and files."""
    results = []
    
    from trading.config import config
    from pathlib import Path
    
    # Data directory
    data_path = Path(config.data_dir)
    if data_path.exists():
        results.append(("Data Directory", True, str(data_path)))
    else:
        try:
            data_path.mkdir(parents=True)
            results.append(("Data Directory", True, f"Created: {data_path}"))
        except Exception as e:
            results.append(("Data Directory", False, str(e)))
    
    # Exports directory
    exports_path = Path(config.exports_dir)
    if exports_path.exists():
        results.append(("Exports Directory", True, str(exports_path)))
    else:
        try:
            exports_path.mkdir(parents=True)
            results.append(("Exports Directory", True, f"Created: {exports_path}"))
        except Exception as e:
            results.append(("Exports Directory", False, str(e)))
    
    # Check writable
    try:
        test_file = data_path / ".health_check"
        test_file.write_text("test")
        test_file.unlink()
        results.append(("Storage Writable", True, "OK"))
    except Exception as e:
        results.append(("Storage Writable", False, str(e)))
    
    return results


def check_analysis() -> List[Tuple[str, bool, str]]:
    """Run a quick analysis check."""
    results = []
    
    try:
        from trading.analyzer import StockAnalyzer
        
        start = time.time()
        analyzer = StockAnalyzer()
        result = analyzer.analyze("AAPL")
        elapsed = time.time() - start
        
        if result:
            results.append(("Stock Analysis", True, 
                          f"AAPL Score: {result.overall_score:.0f} ({elapsed:.1f}s)"))
        else:
            results.append(("Stock Analysis", False, "No result returned"))
    except Exception as e:
        results.append(("Stock Analysis", False, str(e)[:50]))
    
    return results


def run_health_check(verbose: bool = True, skip_analysis: bool = False) -> Dict:
    """Run all health checks."""
    
    if verbose:
        print("\n" + "="*70)
        print("🏥 TRADING PLATFORM HEALTH CHECK")
        print("="*70)
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
    
    all_results = {}
    total_pass = 0
    total_fail = 0
    
    def print_section(name: str, results: List[Tuple[str, bool, str]]):
        nonlocal total_pass, total_fail
        
        if verbose:
            print(f"\n {name}")
            print("-" * 50)
        
        section_results = []
        for item, passed, message in results:
            icon = "[OK]" if passed else "[X]"
            if verbose:
                print(f"   {icon} {item}: {message}")
            section_results.append({"item": item, "passed": passed, "message": message})
            if passed:
                total_pass += 1
            else:
                total_fail += 1
        
        all_results[name] = section_results
    
    # Run checks
    print_section("Module Imports", check_imports())
    print_section("API Keys", check_api_keys())
    print_section("Storage", check_storage())
    
    if not skip_analysis:
        print_section("Data Sources", check_data_sources())
        print_section("Analysis", check_analysis())
    
    # Summary
    if verbose:
        print("\n" + "="*70)
        print(" SUMMARY")
        print("="*70)
        print(f"   [OK] Passed: {total_pass}")
        print(f"   [X] Failed: {total_fail}")
        print(f"   Total:   {total_pass + total_fail}")
        
        if total_fail == 0:
            print("\n   🎉 All checks passed! Platform is healthy.")
        else:
            print(f"\n   [WARN]  {total_fail} check(s) failed. See details above.")
        
        print("="*70 + "\n")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "passed": total_pass,
        "failed": total_fail,
        "results": all_results
    }


def quick_check() -> bool:
    """Quick check - returns True if platform is functional."""
    try:
        # Just check critical imports
        from trading.analyzer import StockAnalyzer
        from trading.watchlist import WatchlistManager
        from trading.portfolio import PortfolioManager
        from trading.dashboard import DashboardHandler
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading Platform Health Check")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (JSON output)")
    parser.add_argument("-s", "--skip-analysis", action="store_true", help="Skip analysis test")
    args = parser.parse_args()
    
    if args.quiet:
        import json
        results = run_health_check(verbose=False, skip_analysis=args.skip_analysis)
        print(json.dumps(results, indent=2))
    else:
        results = run_health_check(verbose=True, skip_analysis=args.skip_analysis)
        
        # Exit with error code if failures
        sys.exit(0 if results["failed"] == 0 else 1)
