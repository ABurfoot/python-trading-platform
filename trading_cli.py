#!/usr/bin/env python3
"""
Trading Platform CLI - Comprehensive Commands
==============================================

All trading platform commands in one place.

Usage:
    python3 trading_cli.py [command] [options]

Commands:
    analyze     - Analyze stocks
    compare     - Compare multiple stocks
    watchlist   - Manage watchlists
    alerts      - Manage price alerts
    portfolio   - Track paper portfolios
    news        - Get stock news
    earnings    - Earnings calendar
    sectors     - Sector heatmap
    screen      - Stock screener
    export      - Export reports
    dashboard   - Start web dashboard
"""

import sys
import argparse
import os

# Add trading module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_analyze(args):
    """Analyze stocks."""
    from trading.analyzer import StockAnalyzer, print_analysis, print_brief
    
    analyzer = StockAnalyzer()
    
    for symbol in args.symbols:
        print(f"\n{'='*70}")
        print(f"Analyzing {symbol}...")
        print('='*70)
        
        try:
            result = analyzer.analyze(symbol)
            if args.brief:
                print_brief(result)
            else:
                print_analysis(result)
            
            # Export if requested
            if args.export:
                from trading.export import export_analysis
                path = export_analysis(result, args.export)
                print(f"📄 Exported to: {path}")
                
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")


def cmd_compare(args):
    """Compare multiple stocks."""
    from trading.comparison import compare_stocks
    compare_stocks(args.symbols)


def cmd_watchlist(args):
    """Manage watchlists."""
    from trading.watchlist import WatchlistManager
    
    wl = WatchlistManager()
    
    if args.action == "list":
        lists = wl.list_watchlists()
        print("\n Watchlists:")
        for l in lists:
            print(f"  • {l['name']} ({l['key']}): {l['count']} stocks")
        print()
    
    elif args.action == "show":
        stocks = wl.get(args.name)
        info = wl.watchlists.get(args.name.lower(), {})
        print(f"\n {info.get('name', args.name)} ({len(stocks)} stocks):")
        for s in stocks:
            print(f"  • {s}")
        print()
    
    elif args.action == "add":
        added = wl.add(args.name, args.symbols)
        if added:
            print(f"[OK] Added to {args.name}: {', '.join(added)}")
        else:
            print("No new stocks added")
    
    elif args.action == "remove":
        removed = wl.remove(args.name, args.symbols)
        if removed:
            print(f"[OK] Removed from {args.name}: {', '.join(removed)}")
    
    elif args.action == "create":
        if wl.create(args.name):
            print(f"[OK] Created watchlist: {args.name}")
        else:
            print(f"Watchlist already exists: {args.name}")
    
    elif args.action == "analyze":
        stocks = wl.get(args.name)
        if stocks:
            print(f"\n Analyzing watchlist: {args.name}")
            from trading.analyzer import StockAnalyzer, print_brief
            analyzer = StockAnalyzer()
            for symbol in stocks:
                try:
                    result = analyzer.analyze(symbol)
                    print_brief(result)
                except Exception as e:
                    print(f"  [WARN] {symbol}: {e}")


def cmd_alerts(args):
    """Manage price alerts."""
    from trading.alerts import AlertManager
    
    am = AlertManager()
    
    if args.action == "list":
        alerts = am.get_active() if args.active else am.get_all()
        print(f"\n🔔 Alerts ({len(alerts)}):")
        for a in alerts:
            status = "[OK]" if a.status == "active" else "[!]" if a.status == "triggered" else "[ ]"
            print(f"  {status} [{a.id}] {a.symbol}: {a.alert_type} {a.condition} {a.value}")
        print()
    
    elif args.action == "price":
        alert = am.add_price_alert(args.symbol, args.condition, args.value)
        print(f"[OK] Added alert: {alert.symbol} {alert.condition} ${alert.value:.2f}")
    
    elif args.action == "remove":
        if am.remove(args.alert_id):
            print(f"[OK] Removed alert: {args.alert_id}")
        else:
            print(f"Alert not found: {args.alert_id}")
    
    elif args.action == "clear":
        am.clear_triggered()
        print("[OK] Cleared all triggered alerts")


def cmd_portfolio(args):
    """Manage paper portfolios."""
    from trading.portfolio import PortfolioManager
    
    pm = PortfolioManager()
    
    if args.action == "list":
        portfolios = pm.list_portfolios()
        print("\n Portfolios:")
        for p in portfolios:
            print(f"  • {p['name']} ({p['key']}): ${p['cash']:,.2f} cash, {p['positions']} positions")
        print()
    
    elif args.action == "show":
        summary = pm.get_summary(args.name)
        if summary:
            print(f"\n {summary['name']}")
            print("=" * 40)
            print(f"  Cash:            ${summary['cash']:>12,.2f}")
            print(f"  Positions Value: ${summary['positions_value']:>12,.2f}")
            print(f"  Total Value:     ${summary['total_value']:>12,.2f}")
            print(f"  ─────────────────────────────────")
            print(f"  Unrealized P&L:  ${summary['unrealized_pnl']:>+12,.2f}")
            print(f"  Realized P&L:    ${summary['realized_pnl']:>+12,.2f}")
            print(f"  Total Return:    ${summary['total_return']:>+12,.2f} ({summary['total_return_pct']:+.2f}%)")
            print()
    
    elif args.action == "buy":
        tx = pm.buy(args.portfolio, args.symbol, args.quantity, args.price)
        if tx:
            print(f"[OK] Bought {tx.quantity} {tx.symbol} @ ${tx.price:.2f}")
        else:
            print("Failed (insufficient cash?)")
    
    elif args.action == "sell":
        tx = pm.sell(args.portfolio, args.symbol, args.quantity, args.price)
        if tx:
            print(f"[OK] Sold {tx.quantity} {tx.symbol} @ ${tx.price:.2f}")
        else:
            print("Failed (insufficient shares?)")
    
    elif args.action == "positions":
        positions = pm.get_positions(args.name)
        print(f"\n Positions ({args.name}):")
        for p in positions:
            print(f"  • {p.symbol}: {p.quantity} @ ${p.avg_cost:.2f}")
        print()
    
    elif args.action == "create":
        if pm.create(args.name, args.cash):
            print(f"[OK] Created portfolio: {args.name}")


def cmd_news(args):
    """Get stock news."""
    from trading.news import print_news
    print_news(args.symbol, args.limit)


def cmd_earnings(args):
    """Earnings calendar."""
    from trading.earnings import print_earnings, print_calendar
    
    if args.symbol:
        print_earnings(args.symbol)
    else:
        print_calendar(args.weeks)


def cmd_sectors(args):
    """Sector heatmap."""
    from trading.sectors import SectorHeatmap
    sh = SectorHeatmap()
    sh.print_heatmap()


def cmd_screen(args):
    """Stock screener."""
    from trading.screener import StockScreener, PRESET_SCREENS
    
    if args.list_presets:
        print("\n Available Screens:")
        for name, criteria in PRESET_SCREENS.items():
            print(f"  • {name}: {criteria.name}")
        print()
        return
    
    screener = StockScreener()
    
    if args.preset:
        results = screener.run_screen(args.preset, args.limit)
        screener.print_results(results, PRESET_SCREENS[args.preset].name)
    else:
        results = screener.custom_screen(
            pe_max=args.pe_max,
            div_min=args.div_min,
            market_cap_min=args.cap_min,
            limit=args.limit
        )
        screener.print_results(results, "Custom Screen")


def cmd_export(args):
    """Export analysis to file."""
    from trading.analyzer import StockAnalyzer
    from trading.export import ReportExporter
    
    analyzer = StockAnalyzer()
    exporter = ReportExporter()
    
    print(f"Analyzing {args.symbol}...")
    result = analyzer.analyze(args.symbol)
    
    if args.format == "html":
        path = exporter.to_html(result)
    elif args.format == "csv":
        path = exporter.to_csv(result)
    elif args.format == "json":
        path = exporter.to_json(result)
    elif args.format == "txt":
        path = exporter.to_text(result)
    
    print(f"[OK] Exported to: {path}")


def cmd_predict(args):
    """Advanced ML price prediction with ensemble methods."""
    # Try advanced predictor first, fall back to basic
    try:
        from trading.ml_predictor_v2 import AdvancedMLPredictor, print_advanced_result
        use_advanced = True
    except ImportError:
        try:
            from trading.ml_predictor import MLPredictor, print_prediction_report
            use_advanced = False
        except ImportError as e:
            print(f"[X] ML Prediction requires PyTorch: {e}")
            print("   Install with: pip install torch --break-system-packages")
            return
    
    try:
        if use_advanced and not args.basic:
            print(" Using Advanced ML Predictor (Ensemble + Hyperparameter Tuning)")
            predictor = AdvancedMLPredictor(
                sequence_length=args.sequence_length,
                transaction_cost_bps=args.transaction_cost,
                n_tune_trials=args.tune_trials
            )
            
            result = predictor.predict(
                args.symbol,
                days=args.days,
                n_cv_splits=args.cv_splits,
                tune_hyperparameters=not args.no_tune,
                verbose=not args.quiet
            )
            
            print_advanced_result(result)
        else:
            # Basic predictor
            predictor = MLPredictor(
                sequence_length=args.sequence_length,
                epochs=args.epochs
            )
            
            result = predictor.predict(
                args.symbol,
                days=args.days,
                n_validation_windows=args.windows,
                verbose=not args.quiet
            )
            
            print_prediction_report(result)
        
        # Export if requested
        if args.json:
            import json
            output_path = f"prediction_{args.symbol.replace(':', '_')}_{result.prediction_date.replace(' ', '_').replace(':', '-')}.json"
            with open(output_path, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"\n📄 Exported to: {output_path}")
            
    except Exception as e:
        print(f"[X] Prediction failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()


def cmd_dashboard(args):
    """Start web dashboard."""
    from trading.dashboard import run_dashboard
    run_dashboard(args.port)


def main():
    parser = argparse.ArgumentParser(
        description="Trading Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 trading_cli.py analyze AAPL
  python3 trading_cli.py analyze AAPL MSFT --brief
  python3 trading_cli.py compare AAPL MSFT GOOGL
  python3 trading_cli.py watchlist add default AAPL MSFT
  python3 trading_cli.py screen value
  python3 trading_cli.py news AAPL
  python3 trading_cli.py sectors
  python3 trading_cli.py export AAPL --format html
  python3 trading_cli.py dashboard
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze stocks")
    p_analyze.add_argument("symbols", nargs="+", help="Stock symbols")
    p_analyze.add_argument("-b", "--brief", action="store_true", help="Brief output")
    p_analyze.add_argument("-e", "--export", choices=["html", "csv", "json", "txt"], help="Export format")
    
    # Compare
    p_compare = subparsers.add_parser("compare", help="Compare stocks")
    p_compare.add_argument("symbols", nargs="+", help="2-5 stock symbols")
    
    # Watchlist
    p_watchlist = subparsers.add_parser("watchlist", help="Manage watchlists")
    p_watchlist.add_argument("action", choices=["list", "show", "add", "remove", "create", "analyze"])
    p_watchlist.add_argument("name", nargs="?", default="default", help="Watchlist name")
    p_watchlist.add_argument("symbols", nargs="*", help="Stock symbols")
    
    # Alerts
    p_alerts = subparsers.add_parser("alerts", help="Manage alerts")
    p_alerts.add_argument("action", choices=["list", "price", "remove", "clear"])
    p_alerts.add_argument("symbol", nargs="?", help="Stock symbol")
    p_alerts.add_argument("condition", nargs="?", choices=["above", "below"], help="Condition")
    p_alerts.add_argument("value", nargs="?", type=float, help="Price value")
    p_alerts.add_argument("--alert-id", help="Alert ID for removal")
    p_alerts.add_argument("-a", "--active", action="store_true", help="Show only active")
    
    # Portfolio
    p_portfolio = subparsers.add_parser("portfolio", help="Paper portfolio")
    p_portfolio.add_argument("action", choices=["list", "show", "buy", "sell", "positions", "create"])
    p_portfolio.add_argument("name", nargs="?", default="default", help="Portfolio name")
    p_portfolio.add_argument("--symbol", "-s", help="Stock symbol")
    p_portfolio.add_argument("--quantity", "-q", type=float, help="Quantity")
    p_portfolio.add_argument("--price", "-p", type=float, help="Price")
    p_portfolio.add_argument("--cash", "-c", type=float, default=100000, help="Initial cash")
    p_portfolio.add_argument("--portfolio", default="default", help="Portfolio for buy/sell")
    
    # News
    p_news = subparsers.add_parser("news", help="Stock news")
    p_news.add_argument("symbol", help="Stock symbol")
    p_news.add_argument("-n", "--limit", type=int, default=10, help="Number of articles")
    
    # Earnings
    p_earnings = subparsers.add_parser("earnings", help="Earnings calendar")
    p_earnings.add_argument("symbol", nargs="?", help="Stock symbol")
    p_earnings.add_argument("-w", "--weeks", type=int, default=0, help="Week offset")
    
    # Sectors
    p_sectors = subparsers.add_parser("sectors", help="Sector heatmap")
    
    # Screen
    p_screen = subparsers.add_parser("screen", help="Stock screener")
    p_screen.add_argument("preset", nargs="?", help="Preset screen name")
    p_screen.add_argument("--list-presets", action="store_true", help="List available presets")
    p_screen.add_argument("-n", "--limit", type=int, default=15, help="Max results")
    p_screen.add_argument("--pe-max", type=float, help="Max P/E ratio")
    p_screen.add_argument("--div-min", type=float, help="Min dividend yield")
    p_screen.add_argument("--cap-min", type=float, help="Min market cap (billions)")
    
    # Export
    p_export = subparsers.add_parser("export", help="Export analysis")
    p_export.add_argument("symbol", help="Stock symbol")
    p_export.add_argument("-f", "--format", default="html", choices=["html", "csv", "json", "txt"])
    
    # Dashboard
    p_dashboard = subparsers.add_parser("dashboard", help="Start web dashboard")
    p_dashboard.add_argument("-p", "--port", type=int, default=8080, help="Port number")
    
    # Predict (ML)
    p_predict = subparsers.add_parser("predict", help="Advanced ML price prediction (Ensemble)")
    p_predict.add_argument("symbol", help="Stock symbol (e.g., AAPL, ASX:BHP)")
    p_predict.add_argument("-d", "--days", type=int, default=30, help="Days to predict (default: 30)")
    p_predict.add_argument("-w", "--windows", type=int, default=5, help="Walk-forward validation windows (default: 5)")
    p_predict.add_argument("-s", "--sequence-length", type=int, default=60, help="LSTM sequence length (default: 60)")
    p_predict.add_argument("-e", "--epochs", type=int, default=50, help="Training epochs (default: 50)")
    p_predict.add_argument("-c", "--cv-splits", type=int, default=5, help="Cross-validation splits (default: 5)")
    p_predict.add_argument("-t", "--tune-trials", type=int, default=20, help="Hyperparameter tuning trials (default: 20)")
    p_predict.add_argument("--transaction-cost", type=float, default=10.0, help="Transaction cost in basis points (default: 10)")
    p_predict.add_argument("--no-tune", action="store_true", help="Skip hyperparameter tuning")
    p_predict.add_argument("--basic", action="store_true", help="Use basic LSTM predictor (skip ensemble)")
    p_predict.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    p_predict.add_argument("--json", action="store_true", help="Export results to JSON")
    p_predict.add_argument("--debug", action="store_true", help="Show debug info on error")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "watchlist":
        cmd_watchlist(args)
    elif args.command == "alerts":
        cmd_alerts(args)
    elif args.command == "portfolio":
        cmd_portfolio(args)
    elif args.command == "news":
        cmd_news(args)
    elif args.command == "earnings":
        cmd_earnings(args)
    elif args.command == "sectors":
        cmd_sectors(args)
    elif args.command == "screen":
        cmd_screen(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "predict":
        cmd_predict(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
