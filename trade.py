#!/usr/bin/env python3
"""
Trading Platform CLI
====================
Unified command-line interface for all trading operations.

Usage:
    python trade.py backtest AAPL --years 5
    python trade.py paper --symbols AAPL MSFT --strategy ma_crossover
    python trade.py dashboard
    python trade.py status
    python trade.py buy AAPL 10
    python trade.py sell AAPL 10
    python trade.py positions

Setup:
    export ALPACA_API_KEY=your_key
    export ALPACA_SECRET_KEY=your_secret
"""

import sys
import os
import argparse

# Add trading module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_backtest(args):
    """Run backtest command."""
    from trading.backtest import main as backtest_main
    # Reconstruct sys.argv for the backtest module
    sys.argv = ['backtest'] + args.symbols
    if args.years:
        sys.argv.extend(['--years', str(args.years)])
    if args.strategy:
        sys.argv.extend(['--strategy', args.strategy])
    if args.all_strategies:
        sys.argv.append('--all-strategies')
    if args.fast:
        sys.argv.extend(['--fast', str(args.fast)])
    if args.slow:
        sys.argv.extend(['--slow', str(args.slow)])
    if args.list:
        sys.argv.extend(['--list', args.list])
    backtest_main()


def cmd_paper(args):
    """Run paper trading bot."""
    from trading.live_trader import main as trader_main
    sys.argv = ['live_trader', '--symbols'] + args.symbols
    if args.strategy:
        sys.argv.extend(['--strategy', args.strategy])
    if args.interval:
        sys.argv.extend(['--interval', str(args.interval)])
    if args.dry_run:
        sys.argv.append('--dry-run')
    trader_main()


def cmd_dashboard(args):
    """Launch web dashboard."""
    from trading.dashboard import run_dashboard
    run_dashboard(port=args.port)


def cmd_status(args):
    """Show account status."""
    from trading.alpaca_client import AlpacaClient, print_account, print_positions
    
    client = AlpacaClient()
    if not client.connect():
        print("\nFailed to connect. Check API keys.")
        return
    
    account = client.get_account()
    print_account(account)
    
    if args.positions:
        positions = client.get_positions()
        print_positions(positions)


def cmd_buy(args):
    """Buy shares."""
    from trading.alpaca_client import AlpacaClient
    
    client = AlpacaClient()
    if not client.connect():
        return
    
    order = client.buy(args.symbol, args.qty)
    print(f"\n✓ Buy order placed: {order.qty} {order.symbol}")
    print(f"  Status: {order.status}")
    print(f"  Order ID: {order.id}")


def cmd_sell(args):
    """Sell shares."""
    from trading.alpaca_client import AlpacaClient
    
    client = AlpacaClient()
    if not client.connect():
        return
    
    order = client.sell(args.symbol, args.qty)
    print(f"\n✓ Sell order placed: {order.qty} {order.symbol}")
    print(f"  Status: {order.status}")
    print(f"  Order ID: {order.id}")


def cmd_positions(args):
    """Show positions."""
    from trading.alpaca_client import AlpacaClient, print_positions
    
    client = AlpacaClient()
    if not client.connect():
        return
    
    positions = client.get_positions()
    print_positions(positions)


def cmd_close(args):
    """Close position(s)."""
    from trading.alpaca_client import AlpacaClient
    
    client = AlpacaClient()
    if not client.connect():
        return
    
    if args.all:
        orders = client.close_all_positions()
        print(f"\n✓ Closed {len(orders)} positions")
    else:
        order = client.close_position(args.symbol)
        print(f"\n✓ Closed position: {order.symbol}")


def cmd_quote(args):
    """Get price quote."""
    from trading.alpaca_client import AlpacaClient
    
    client = AlpacaClient()
    if not client.connect():
        return
    
    for symbol in args.symbols:
        quote = client.get_quote(symbol)
        mid = (quote.bid + quote.ask) / 2
        spread = quote.ask - quote.bid
        print(f"\n{symbol}:")
        print(f"  Bid: ${quote.bid:.2f} x {quote.bid_size}")
        print(f"  Ask: ${quote.ask:.2f} x {quote.ask_size}")
        print(f"  Mid: ${mid:.2f} (spread: ${spread:.2f})")


def cmd_analyze(args):
    """Analyze stocks and provide recommendations."""
    from trading.analyzer import StockAnalyzer, print_analysis
    
    analyzer = StockAnalyzer()
    
    for symbol in args.symbols:
        try:
            print(f"\n{'='*70}")
            print(f"Analyzing {symbol.upper()}...")
            print('='*70)
            
            result = analyzer.analyze(symbol.upper())
            
            if args.brief:
                rec_icon = "🟢" if "BUY" in result.recommendation.value else "🔴" if "SELL" in result.recommendation.value else "🟡"
                print(f"\n{rec_icon} {symbol.upper()}: {result.recommendation.value}")
                print(f"   Score: {result.overall_score:.0f}/100 | Confidence: {result.confidence:.0f}%")
                print(f"   Price: ${result.current_price:.2f} | Target: ${result.price_targets['mid']:.2f}")
            else:
                print_analysis(result)
                
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Trading Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trade.py backtest AAPL MSFT --years 5
  python trade.py paper --symbols AAPL --strategy rsi
  python trade.py dashboard
  python trade.py status --positions
  python trade.py buy AAPL 10
  python trade.py quote AAPL MSFT
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Backtest command
    bt = subparsers.add_parser("backtest", help="Run historical backtest")
    bt.add_argument("symbols", nargs="*", help="Symbols to backtest")
    bt.add_argument("--years", type=int, default=5, help="Years of data")
    bt.add_argument("--strategy", help="Strategy to use")
    bt.add_argument("--all-strategies", action="store_true", help="Compare all strategies")
    bt.add_argument("--fast", type=int, help="Fast MA period")
    bt.add_argument("--slow", type=int, help="Slow MA period")
    bt.add_argument("--list", help="Use predefined symbol list")
    bt.set_defaults(func=cmd_backtest)
    
    # Paper trading command
    paper = subparsers.add_parser("paper", help="Run paper trading bot")
    paper.add_argument("--symbols", nargs="+", required=True, help="Symbols to trade")
    paper.add_argument("--strategy", default="ma_crossover", help="Strategy")
    paper.add_argument("--interval", type=int, default=60, help="Check interval (sec)")
    paper.add_argument("--dry-run", action="store_true", help="Simulate without orders")
    paper.set_defaults(func=cmd_paper)
    
    # Dashboard command
    dash = subparsers.add_parser("dashboard", help="Launch web dashboard")
    dash.add_argument("--port", type=int, default=8080, help="Port")
    dash.set_defaults(func=cmd_dashboard)
    
    # Status command
    status = subparsers.add_parser("status", help="Show account status")
    status.add_argument("--positions", action="store_true", help="Show positions")
    status.set_defaults(func=cmd_status)
    
    # Buy command
    buy = subparsers.add_parser("buy", help="Buy shares")
    buy.add_argument("symbol", help="Symbol to buy")
    buy.add_argument("qty", type=int, help="Quantity")
    buy.set_defaults(func=cmd_buy)
    
    # Sell command
    sell = subparsers.add_parser("sell", help="Sell shares")
    sell.add_argument("symbol", help="Symbol to sell")
    sell.add_argument("qty", type=int, help="Quantity")
    sell.set_defaults(func=cmd_sell)
    
    # Positions command
    pos = subparsers.add_parser("positions", help="Show positions")
    pos.set_defaults(func=cmd_positions)
    
    # Close command
    close = subparsers.add_parser("close", help="Close position(s)")
    close.add_argument("symbol", nargs="?", help="Symbol to close")
    close.add_argument("--all", action="store_true", help="Close all positions")
    close.set_defaults(func=cmd_close)
    
    # Quote command
    quote = subparsers.add_parser("quote", help="Get price quotes")
    quote.add_argument("symbols", nargs="+", help="Symbols")
    quote.set_defaults(func=cmd_quote)
    
    # Analyze command
    analyze = subparsers.add_parser("analyze", help="Comprehensive stock analysis with recommendations")
    analyze.add_argument("symbols", nargs="+", help="Symbols to analyze")
    analyze.add_argument("--brief", action="store_true", help="Show brief summary only")
    analyze.set_defaults(func=cmd_analyze)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
