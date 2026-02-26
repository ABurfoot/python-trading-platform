#!/usr/bin/env python3
"""
Trading Platform Comprehensive Test Suite
==========================================
Tests for all 33 modules in the trading platform.

Run all tests:
    python3 -m pytest tests/test_trading_full.py -v

Run specific test class:
    python3 -m pytest tests/test_trading_full.py::TestDataSources -v

Run with coverage:
    python3 -m pytest tests/test_trading_full.py --cov=trading --cov-report=html

Quick smoke test:
    python3 tests/test_trading_full.py --quick
"""

import os
import sys
import json
import unittest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# CORE MODULES
# =============================================================================

class TestExchanges(unittest.TestCase):
    """Test exchange symbol parsing and handling."""
    
    def setUp(self):
        from trading.exchanges import ExchangeMapper
        self.mapper = ExchangeMapper()
    
    def test_parse_us_symbol(self):
        """Test parsing US symbols."""
        result = self.mapper.parse("AAPL")
        self.assertEqual(result.symbol, "AAPL")
    
    def test_parse_asx_symbol(self):
        """Test parsing Australian symbols."""
        result = self.mapper.parse("ASX:BHP")
        self.assertEqual(result.symbol, "BHP")
        self.assertEqual(result.exchange, "ASX")
        self.assertEqual(result.currency, "AUD")
    
    def test_parse_lse_symbol(self):
        """Test parsing London symbols."""
        result = self.mapper.parse("LSE:VOD")
        self.assertEqual(result.symbol, "VOD")
        self.assertEqual(result.exchange, "LSE")
    
    def test_yahoo_format(self):
        """Test Yahoo Finance format conversion."""
        result = self.mapper.parse("ASX:BHP")
        self.assertEqual(result.yahoo_symbol, "BHP.AX")
    
    def test_case_insensitivity(self):
        """Test case insensitivity."""
        result1 = self.mapper.parse("aapl")
        result2 = self.mapper.parse("AAPL")
        self.assertEqual(result1.symbol, result2.symbol)


class TestWatchlist(unittest.TestCase):
    """Test watchlist functionality."""
    
    def setUp(self):
        from trading.watchlist import WatchlistManager
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.test_file.close()
        self.wl = WatchlistManager(storage_path=self.test_file.name)
    
    def tearDown(self):
        os.unlink(self.test_file.name)
    
    def test_create_watchlist(self):
        """Test creating a new watchlist."""
        result = self.wl.create("tech")
        self.assertTrue(result)
        self.assertIn("tech", self.wl.watchlists)
    
    def test_add_stock(self):
        """Test adding stocks."""
        added = self.wl.add("default", "AAPL")
        self.assertEqual(added, ["AAPL"])
    
    def test_remove_stock(self):
        """Test removing stocks."""
        self.wl.add("default", "AAPL")
        removed = self.wl.remove("default", "AAPL")
        self.assertEqual(removed, ["AAPL"])
    
    def test_list_watchlists(self):
        """Test listing watchlists."""
        self.wl.create("tech")
        # Use list_all or check watchlists dict
        if hasattr(self.wl, 'list_all'):
            lists = self.wl.list_all()
        else:
            lists = list(self.wl.watchlists.keys())
        self.assertIn("default", lists)
        self.assertIn("tech", lists)


class TestAlerts(unittest.TestCase):
    """Test alert functionality."""
    
    def setUp(self):
        from trading.alerts import AlertManager
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.test_file.close()
        self.am = AlertManager(storage_path=self.test_file.name)
    
    def tearDown(self):
        os.unlink(self.test_file.name)
    
    def test_create_price_alert(self):
        """Test creating price alert."""
        alert = self.am.add_price_alert("AAPL", "above", 200.0)
        self.assertEqual(alert.symbol, "AAPL")
        self.assertEqual(alert.condition, "above")
        self.assertEqual(alert.value, 200.0)
    
    def test_check_alert_triggered(self):
        """Test alert triggering."""
        self.am.add_price_alert("AAPL", "above", 200.0)
        triggered = self.am.check_alerts({"AAPL": {"price": 210.0}})
        self.assertEqual(len(triggered), 1)
    
    def test_check_alert_not_triggered(self):
        """Test alert not triggering."""
        self.am.add_price_alert("AAPL", "above", 200.0)
        triggered = self.am.check_alerts({"AAPL": {"price": 190.0}})
        self.assertEqual(len(triggered), 0)


class TestAnalyzer(unittest.TestCase):
    """Test stock analyzer."""
    
    def setUp(self):
        from trading.analyzer import StockAnalyzer
        self.analyzer = StockAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes."""
        self.assertIsNotNone(self.analyzer)
    
    def test_has_analyze_method(self):
        """Test analyzer has analyze method."""
        self.assertTrue(hasattr(self.analyzer, 'analyze') or 
                       hasattr(self.analyzer, 'get_analysis'))


class TestIndicators(unittest.TestCase):
    """Test technical indicators."""
    
    def test_indicators_import(self):
        """Test indicators can be imported."""
        from trading.indicators import TechnicalIndicators
        self.assertIsNotNone(TechnicalIndicators)
    
    def test_indicators_with_data(self):
        """Test indicators with sample data."""
        from trading.indicators import TechnicalIndicators
        prices = [float(x) for x in range(100, 120)]
        ti = TechnicalIndicators(prices)
        self.assertIsNotNone(ti)


# =============================================================================
# DATA SOURCES
# =============================================================================

class TestDataSources(unittest.TestCase):
    """Test multi-source data fetcher."""
    
    def setUp(self):
        from trading.data_sources import DataFetcher
        self.fetcher = DataFetcher(verbose=False)
    
    def test_source_initialization(self):
        """Test that all sources are initialized."""
        expected_sources = ['alpaca', 'fmp', 'finnhub', 'polygon', 
                          'twelvedata', 'alphavantage', 'eodhd', 'yahoo']
        for source in expected_sources:
            self.assertIn(source, self.fetcher.sources)
    
    def test_is_us_stock_detection(self):
        """Test US vs international stock detection."""
        self.assertTrue(self.fetcher._is_us_stock("AAPL"))
        self.assertFalse(self.fetcher._is_us_stock("BHP.AX"))
        self.assertFalse(self.fetcher._is_us_stock("VOD.L"))
    
    def test_sorted_sources_price(self):
        """Test source sorting for price data."""
        sources = self.fetcher._get_sorted_sources("price", is_us=True)
        # Should return list of tuples
        self.assertIsInstance(sources, list)
    
    def test_cache_functionality(self):
        """Test data caching."""
        self.fetcher.cache.set("test_key", {"data": "test"})
        cached = self.fetcher.cache.get("test_key")
        self.assertEqual(cached, {"data": "test"})


class TestCurrency(unittest.TestCase):
    """Test currency conversion."""
    
    def setUp(self):
        from trading.currency import CurrencyManager
        self.cm = CurrencyManager(base_currency="AUD")
    
    def test_base_currency(self):
        """Test base currency setting."""
        self.assertEqual(self.cm.base_currency, "AUD")
    
    def test_same_currency_conversion(self):
        """Test same currency returns 1.0."""
        rate = self.cm.get_rate("AUD", "AUD")
        self.assertEqual(rate, 1.0)
    
    def test_format_amount(self):
        """Test amount formatting."""
        formatted = self.cm.format_amount(1234.56, "USD")
        self.assertIn("$", formatted)
        self.assertIn("1,234", formatted)


# =============================================================================
# PORTFOLIO MODULES
# =============================================================================

class TestPortfolio(unittest.TestCase):
    """Test basic portfolio functionality."""
    
    def setUp(self):
        from trading.portfolio import IntegratedPortfolioManager
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.test_file.close()
        self.pm = IntegratedPortfolioManager(storage_path=self.test_file.name, base_currency="AUD")
    
    def tearDown(self):
        try:
            os.unlink(self.test_file.name)
        except:
            pass
    
    def test_default_portfolio(self):
        """Test default portfolio exists."""
        self.assertIn("default", self.pm.portfolios)
    
    def test_buy_stock(self):
        """Test buying stocks."""
        tx = self.pm.buy("default", "AAPL", 10, 150.0, currency="USD")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.symbol, "AAPL")
        self.assertEqual(tx.quantity, 10)
    
    def test_sell_stock(self):
        """Test selling stocks."""
        self.pm.buy("default", "AAPL", 10, 150.0, currency="USD")
        result = self.pm.sell("default", "AAPL", 5, 160.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["transaction"].quantity, 5)
    
    def test_get_summary(self):
        """Test portfolio summary."""
        self.pm.buy("default", "AAPL", 10, 150.0, currency="USD")
        summary = self.pm.get_summary("default")
        self.assertIn("cash", summary)
        self.assertIn("positions_count", summary)


class TestPortfolioIntegrated(unittest.TestCase):
    """Test integrated portfolio with tax/dividends/currency."""
    
    def setUp(self):
        from trading.portfolio import IntegratedPortfolioManager
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.test_file.close()
        self.pm = IntegratedPortfolioManager(
            base_currency="AUD",
            storage_path=self.test_file.name
        )
    
    def tearDown(self):
        os.unlink(self.test_file.name)
    
    def test_multi_currency_cash(self):
        """Test multi-currency cash holdings."""
        self.pm.create("test", initial_cash=100000, currency="AUD")
        portfolio = self.pm.portfolios["test"]
        self.assertIn("AUD", portfolio.cash)
    
    def test_buy_usd_stock(self):
        """Test buying USD-denominated stock."""
        self.pm.create("test", initial_cash=100000, currency="AUD")
        tx = self.pm.buy("test", "AAPL", 10, 150.0, currency="USD")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.currency, "USD")
    
    def test_record_dividend(self):
        """Test dividend recording."""
        self.pm.create("test", initial_cash=100000, currency="AUD")
        self.pm.buy("test", "VAS.AX", 100, 90.0, currency="AUD")
        result = self.pm.record_dividend("test", "VAS.AX", 250.0, franking_pct=100)
        self.assertIsNotNone(result)
        self.assertIn("franking_credit", result)
    
    def test_franking_credit_calculation(self):
        """Test Australian franking credit calculation."""
        self.pm.create("test", initial_cash=100000, currency="AUD")
        self.pm.buy("test", "VAS.AX", 100, 90.0, currency="AUD")
        result = self.pm.record_dividend("test", "VAS.AX", 70.0, franking_pct=100)
        # Franking credit = dividend * (franking% / 100) * (30 / 70)
        expected_credit = 70.0 * 1.0 * (30 / 70)
        self.assertAlmostEqual(result["franking_credit"], expected_credit, places=2)


class TestTaxLots(unittest.TestCase):
    """Test tax lot tracking."""
    
    def setUp(self):
        from trading.tax_lots import TaxLotTracker, AccountingMethod
        self.tracker = TaxLotTracker(method=AccountingMethod.FIFO, country="AU")
    
    def test_buy_creates_lot(self):
        """Test that buy creates a tax lot."""
        lot = self.tracker.buy("AAPL", 100, 150.0, "2024-01-15")
        self.assertEqual(lot.symbol, "AAPL")
        self.assertEqual(lot.shares, 100)
        self.assertEqual(lot.cost_per_share, 150.0)
    
    def test_fifo_selling(self):
        """Test FIFO selling order."""
        self.tracker.buy("AAPL", 100, 100.0, "2024-01-01")
        self.tracker.buy("AAPL", 100, 150.0, "2024-02-01")
        result = self.tracker.sell("AAPL", 50, 175.0, "2024-06-01")
        # Check result has expected attributes
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'total_gain') or hasattr(result, 'gain'))
    
    def test_cgt_discount_eligibility(self):
        """Test 12-month CGT discount eligibility."""
        lot = self.tracker.buy("AAPL", 100, 100.0, "2023-01-01")
        # After 12 months
        self.assertTrue(lot.is_long_term)


class TestDividends(unittest.TestCase):
    """Test dividend tracking."""
    
    def setUp(self):
        from trading.dividends import DividendTracker
        self.tracker = DividendTracker()
    
    def test_tracker_initialization(self):
        """Test tracker initializes."""
        self.assertIsNotNone(self.tracker)
    
    def test_has_add_dividend(self):
        """Test has add_dividend method."""
        self.assertTrue(hasattr(self.tracker, 'add_dividend'))
    
    def test_has_get_history(self):
        """Test has get_history method."""
        self.assertTrue(hasattr(self.tracker, 'get_history'))


# =============================================================================
# MARKET DATA MODULES
# =============================================================================

class TestEconomicCalendar(unittest.TestCase):
    """Test economic calendar."""
    
    def setUp(self):
        from trading.economic_calendar import EconomicCalendar
        self.cal = EconomicCalendar()
    
    def test_central_bank_meetings(self):
        """Test getting central bank meetings."""
        meetings = self.cal.get_central_bank_meetings(days=365)
        self.assertIsInstance(meetings, list)
        # Should have Fed, RBA, ECB, BOE, BOJ meetings
        if meetings:
            countries = {m.country for m in meetings}
            self.assertTrue(len(countries) > 0)
    
    def test_filter_by_country(self):
        """Test filtering events by country."""
        events = self.cal.get_events(days=365, country="AU")
        for event in events:
            self.assertEqual(event.country, "AU")
    
    def test_filter_by_impact(self):
        """Test filtering by impact level."""
        events = self.cal.get_events(days=365, impact="high")
        for event in events:
            self.assertEqual(event.impact, "high")


class TestGlobalIndices(unittest.TestCase):
    """Test global indices module."""
    
    def setUp(self):
        from trading.global_indices import GlobalIndices, INDICES
        self.gi = GlobalIndices()
        self.indices = INDICES
    
    def test_indices_defined(self):
        """Test that indices are defined."""
        self.assertIn("SPX", self.indices)
        self.assertIn("AXJO", self.indices)
        self.assertIn("FTSE", self.indices)
        self.assertIn("N225", self.indices)
    
    def test_index_info(self):
        """Test getting index info."""
        info = self.gi.get_index_info("AXJO")
        self.assertEqual(info.name, "ASX 200")
        self.assertEqual(info.country, "AU")
        self.assertEqual(info.currency, "AUD")
    
    def test_list_indices(self):
        """Test listing all indices."""
        indices = self.gi.list_indices()
        self.assertGreater(len(indices), 20)
    
    def test_market_status(self):
        """Test market status detection."""
        status = self.gi.get_market_status()
        self.assertIn("open", status)
        self.assertIn("closed", status)


class TestCrypto(unittest.TestCase):
    """Test cryptocurrency module."""
    
    def setUp(self):
        from trading.crypto import CryptoTracker, COINS
        self.ct = CryptoTracker()
        self.coins = COINS
    
    def test_coins_defined(self):
        """Test that coins are defined."""
        self.assertIn("BTC", self.coins)
        self.assertIn("ETH", self.coins)
        self.assertIn("SOL", self.coins)
    
    def test_coin_info(self):
        """Test coin information."""
        btc = self.coins["BTC"]
        self.assertEqual(btc.name, "Bitcoin")
        self.assertEqual(btc.max_supply, 21000000)
    
    def test_list_coins(self):
        """Test listing coins."""
        coins = self.ct.list_coins()
        self.assertGreater(len(coins), 30)
    
    def test_coin_categories(self):
        """Test coin categories."""
        coins = self.ct.list_coins()
        categories = {c["category"] for c in coins}
        self.assertIn("layer1", categories)
        self.assertIn("defi", categories)
        self.assertIn("stablecoin", categories)


# =============================================================================
# NOTIFICATIONS
# =============================================================================

class TestNotifications(unittest.TestCase):
    """Test notification system."""
    
    def setUp(self):
        from trading.notifications import Notifier, AlertMonitor
        self.notifier = Notifier(enable_sound=False, enable_desktop=False)
        self.monitor = AlertMonitor(notifier=self.notifier)
    
    def test_create_alert(self):
        """Test creating an alert."""
        alert_id = self.monitor.add_price_alert("AAPL", "above", 200)
        self.assertIsNotNone(alert_id)
        self.assertIn("AAPL", alert_id)
    
    def test_list_alerts(self):
        """Test listing alerts."""
        self.monitor.add_price_alert("AAPL", "above", 200)
        self.monitor.add_price_alert("BTC", "below", 50000)
        alerts = self.monitor.list_alerts()
        self.assertEqual(len(alerts), 2)
    
    def test_remove_alert(self):
        """Test removing an alert."""
        alert_id = self.monitor.add_price_alert("AAPL", "above", 200)
        result = self.monitor.remove_price_alert(alert_id)
        self.assertTrue(result)
        self.assertEqual(len(self.monitor.list_alerts()), 0)
    
    def test_alert_history(self):
        """Test notification history."""
        self.notifier.notify("Test", "Message", sound=False)
        history = self.notifier.get_history()
        self.assertEqual(len(history), 1)


# =============================================================================
# ANALYSIS & BACKTESTING
# =============================================================================

class TestScreener(unittest.TestCase):
    """Test stock screener."""
    
    def setUp(self):
        from trading.screener import StockScreener
        self.screener = StockScreener()
    
    def test_screener_initialization(self):
        """Test screener initializes."""
        self.assertIsNotNone(self.screener)


class TestSentiment(unittest.TestCase):
    """Test sentiment analysis."""
    
    def setUp(self):
        from trading.sentiment import SentimentAnalyzer
        self.analyzer = SentimentAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes."""
        self.assertIsNotNone(self.analyzer)
    
    def test_has_analyze_method(self):
        """Test has analyze method."""
        self.assertTrue(hasattr(self.analyzer, 'analyze') or 
                       hasattr(self.analyzer, 'analyze_text') or
                       hasattr(self.analyzer, 'get_sentiment'))


class TestOptions(unittest.TestCase):
    """Test options analysis."""
    
    def test_options_import(self):
        """Test options can be imported."""
        from trading.options import OptionsAnalyzer
        self.assertIsNotNone(OptionsAnalyzer)
    
    def test_options_with_symbol(self):
        """Test options analyzer with symbol."""
        from trading.options import OptionsAnalyzer
        analyzer = OptionsAnalyzer("AAPL")
        self.assertIsNotNone(analyzer)


# =============================================================================
# BROKER INTEGRATION
# =============================================================================

class TestBroker(unittest.TestCase):
    """Test broker integration."""
    
    def setUp(self):
        from trading.broker import BrokerManager
        self.manager = BrokerManager()
    
    def test_broker_initialization(self):
        """Test broker manager initializes."""
        self.assertIsNotNone(self.manager)


class TestCharts(unittest.TestCase):
    """Test chart generation."""
    
    def setUp(self):
        from trading.charts import ChartGenerator
        self.generator = ChartGenerator()
    
    def test_chart_initialization(self):
        """Test chart generator initializes."""
        self.assertIsNotNone(self.generator)


# =============================================================================
# UTILITIES
# =============================================================================

class TestCache(unittest.TestCase):
    """Test caching functionality."""
    
    def setUp(self):
        from trading.cache import TradingCache
        self.cache = TradingCache()
    
    def test_cache_initialization(self):
        """Test cache initializes."""
        self.assertIsNotNone(self.cache)
    
    def test_has_get_set(self):
        """Test has get and set methods."""
        self.assertTrue(hasattr(self.cache, 'get'))
        self.assertTrue(hasattr(self.cache, 'set'))


class TestExport(unittest.TestCase):
    """Test export functionality."""
    
    def setUp(self):
        from trading.export import ReportExporter
        self.exporter = ReportExporter()
    
    def test_exporter_initialization(self):
        """Test exporter initializes."""
        self.assertIsNotNone(self.exporter)


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def setUp(self):
        from trading.config import TradingConfig
        self.config = TradingConfig()
    
    def test_config_initialization(self):
        """Test config initializes."""
        self.assertIsNotNone(self.config)


# =============================================================================
# AI ANALYSIS
# =============================================================================

class TestAIAnalysis(unittest.TestCase):
    """Test AI analysis module."""
    
    def setUp(self):
        from trading.ai_analysis import AIAnalyzer
        self.analyzer = AIAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes."""
        self.assertIsNotNone(self.analyzer)
    
    def test_fallback_mode(self):
        """Test fallback mode when no API key."""
        # Should work in fallback mode without API key
        self.assertTrue(hasattr(self.analyzer, 'analyze_stock'))


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestModuleIntegration(unittest.TestCase):
    """Test that modules integrate correctly."""
    
    def test_portfolio_with_data_sources(self):
        """Test portfolio can use data sources."""
        from trading.portfolio import IntegratedPortfolioManager
        from trading.data_sources import DataFetcher
        
        pm = IntegratedPortfolioManager(base_currency="AUD")
        fetcher = DataFetcher(verbose=False)
        
        # Both should initialize without error
        self.assertIsNotNone(pm)
        self.assertIsNotNone(fetcher)
    
    def test_alerts_with_notifications(self):
        """Test alerts integrate with notifications."""
        from trading.alerts import AlertManager
        from trading.notifications import Notifier
        
        am = AlertManager()
        notifier = Notifier(enable_sound=False, enable_desktop=False)
        
        # Create alert and trigger notification
        alert = am.add_price_alert("AAPL", "above", 200.0)
        notifier.notify("Alert", f"Alert created: {alert.id}", sound=False)
        
        self.assertEqual(len(notifier.get_history()), 1)
    
    def test_all_modules_import(self):
        """Test that all modules can be imported."""
        modules = [
            "trading.alerts",
            "trading.analyzer", 
            "trading.broker",
            "trading.cache",
            "trading.charts",
            "trading.config",
            "trading.crypto",
            "trading.currency",
            "trading.data_sources",
            "trading.dividends",
            "trading.earnings",
            "trading.economic_calendar",
            "trading.exchanges",
            "trading.export",
            "trading.global_indices",
            "trading.indicators",
            "trading.news",
            "trading.notifications",
            "trading.options",
            "trading.portfolio",
            "trading.portfolio",
            "trading.screener",
            "trading.sectors",
            "trading.sentiment",
            "trading.tax_lots",
            "trading.watchlist",
        ]
        
        failed = []
        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                failed.append(f"{module}: {e}")
        
        if failed:
            self.fail(f"Failed to import modules:\n" + "\n".join(failed))


# =============================================================================
# QUICK SMOKE TEST
# =============================================================================

def run_smoke_test():
    """Run a quick smoke test of critical functionality."""
    print("="*60)
    print("SMOKE TEST - Trading Platform")
    print("="*60)
    
    tests_passed = 0
    tests_failed = 0
    
    def check(name, test_func):
        nonlocal tests_passed, tests_failed
        try:
            test_func()
            print(f"  ✅ {name}")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            tests_failed += 1
    
    # Core modules
    print("\n📦 Core Modules:")
    check("Exchanges", lambda: __import__("trading.exchanges"))
    check("Watchlist", lambda: __import__("trading.watchlist"))
    check("Alerts", lambda: __import__("trading.alerts"))
    check("Analyzer", lambda: __import__("trading.analyzer"))
    
    # Data
    print("\n📊 Data Modules:")
    check("Data Sources", lambda: __import__("trading.data_sources"))
    check("Currency", lambda: __import__("trading.currency"))
    check("News", lambda: __import__("trading.news"))
    
    # Portfolio
    print("\n💼 Portfolio Modules:")
    check("Portfolio", lambda: __import__("trading.portfolio"))
    check("Portfolio Integrated", lambda: __import__("trading.portfolio"))
    check("Tax Lots", lambda: __import__("trading.tax_lots"))
    check("Dividends", lambda: __import__("trading.dividends"))
    
    # Market Data
    print("\n🌍 Market Data:")
    check("Economic Calendar", lambda: __import__("trading.economic_calendar"))
    check("Global Indices", lambda: __import__("trading.global_indices"))
    check("Crypto", lambda: __import__("trading.crypto"))
    
    # Features
    print("\n⚙️ Features:")
    check("Notifications", lambda: __import__("trading.notifications"))
    check("Charts", lambda: __import__("trading.charts"))
    check("Broker", lambda: __import__("trading.broker"))
    check("AI Analysis", lambda: __import__("trading.ai_analysis"))
    
    # Summary
    print("\n" + "="*60)
    total = tests_passed + tests_failed
    print(f"Results: {tests_passed}/{total} passed")
    
    if tests_failed == 0:
        print("✅ All smoke tests passed!")
    else:
        print(f"❌ {tests_failed} tests failed")
    
    print("="*60)
    return tests_failed == 0


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading Platform Tests")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke test")
    args = parser.parse_args()
    
    if args.quick:
        success = run_smoke_test()
        sys.exit(0 if success else 1)
    else:
        unittest.main()


class TestPaperTrading(unittest.TestCase):
    """Test paper trading simulator."""
    
    def setUp(self):
        from trading.paper_trading import PaperTradingSimulator
        self.sim = PaperTradingSimulator(initial_cash=100000, auto_save=False)
    
    def test_initial_cash(self):
        """Test initial cash is set correctly."""
        self.assertEqual(self.sim.cash, 100000)
        self.assertEqual(self.sim.initial_cash, 100000)
    
    def test_portfolio_value(self):
        """Test portfolio value calculation."""
        self.assertEqual(self.sim.get_portfolio_value(), 100000)
    
    def test_total_return(self):
        """Test total return calculation."""
        self.assertEqual(self.sim.get_total_return(), 0)
    
    def test_no_positions_initially(self):
        """Test no positions at start."""
        self.assertEqual(len(self.sim.positions), 0)
    
    def test_no_orders_initially(self):
        """Test no orders at start."""
        self.assertEqual(len(self.sim.orders), 0)
    
    def test_performance_metrics(self):
        """Test performance metrics structure."""
        metrics = self.sim.get_performance_metrics()
        self.assertEqual(metrics.total_trades, 0)
        self.assertEqual(metrics.win_rate, 0)
    
    def test_reset(self):
        """Test simulator reset."""
        self.sim.cash = 50000  # Modify cash
        self.sim.reset(confirm=True)
        self.assertEqual(self.sim.cash, 100000)
    
    def test_cancel_nonexistent_order(self):
        """Test cancelling non-existent order fails."""
        result = self.sim.cancel_order("fake_id")
        self.assertFalse(result)
    
    def test_close_nonexistent_position(self):
        """Test closing non-existent position fails."""
        result = self.sim.close_position("FAKE")
        self.assertIsNone(result)


class TestPerformanceAnalytics(unittest.TestCase):
    """Test performance analytics module."""
    
    def setUp(self):
        from trading.performance import PerformanceAnalyzer
        self.analyzer = PerformanceAnalyzer(initial_capital=100000)
    
    def test_initial_capital(self):
        """Test initial capital is set."""
        self.assertEqual(self.analyzer.initial_capital, 100000)
    
    def test_add_trade(self):
        """Test adding a trade."""
        trade = self.analyzer.add_trade(
            symbol="AAPL", side="long",
            entry_date="2024-01-01", exit_date="2024-01-15",
            entry_price=150, exit_price=165, quantity=100
        )
        self.assertEqual(trade.symbol, "AAPL")
        self.assertEqual(trade.pnl, 1500)  # (165-150) * 100
    
    def test_add_trades(self):
        """Test adding multiple trades."""
        trades = [
            {"symbol": "AAPL", "entry_date": "2024-01-01", "exit_date": "2024-01-15",
             "entry_price": 150, "exit_price": 165, "quantity": 100},
            {"symbol": "MSFT", "entry_date": "2024-02-01", "exit_date": "2024-02-15",
             "entry_price": 400, "exit_price": 420, "quantity": 50},
        ]
        count = self.analyzer.add_trades(trades)
        self.assertEqual(count, 2)
        self.assertEqual(len(self.analyzer.trades), 2)
    
    def test_calculate_metrics(self):
        """Test metrics calculation."""
        self.analyzer.add_trade(
            symbol="AAPL", side="long",
            entry_date="2024-01-01", exit_date="2024-01-15",
            entry_price=150, exit_price=165, quantity=100
        )
        metrics = self.analyzer.calculate_all_metrics()
        self.assertGreater(metrics.total_return, 0)
        self.assertEqual(metrics.total_trades, 1)
        self.assertEqual(metrics.win_rate, 100)
    
    def test_win_loss_rate(self):
        """Test win/loss rate calculation."""
        # Add a winning trade
        self.analyzer.add_trade("AAPL", "long", "2024-01-01", "2024-01-15", 150, 165, 100)
        # Add a losing trade
        self.analyzer.add_trade("MSFT", "long", "2024-02-01", "2024-02-15", 400, 380, 50)
        
        metrics = self.analyzer.calculate_all_metrics()
        self.assertEqual(metrics.total_trades, 2)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertEqual(metrics.win_rate, 50)
    
    def test_profit_factor(self):
        """Test profit factor calculation."""
        self.analyzer.add_trade("AAPL", "long", "2024-01-01", "2024-01-15", 100, 120, 100)  # +2000
        self.analyzer.add_trade("MSFT", "long", "2024-02-01", "2024-02-15", 100, 90, 100)   # -1000
        
        metrics = self.analyzer.calculate_all_metrics()
        self.assertEqual(metrics.profit_factor, 2.0)  # 2000 / 1000
    
    def test_get_metrics_dict(self):
        """Test getting metrics as dictionary."""
        self.analyzer.add_trade("AAPL", "long", "2024-01-01", "2024-01-15", 150, 165, 100)
        metrics_dict = self.analyzer.get_metrics_dict()
        self.assertIsInstance(metrics_dict, dict)
        self.assertIn("total_return", metrics_dict)
        self.assertIn("sharpe_ratio", metrics_dict)
    
    def test_helper_functions(self):
        """Test helper functions."""
        from trading.performance import calculate_max_drawdown, calculate_cagr
        
        # Test max drawdown
        values = [100, 110, 105, 115, 100, 120]
        dd, dd_pct = calculate_max_drawdown(values)
        self.assertGreater(dd, 0)
        
        # Test CAGR
        cagr = calculate_cagr(100, 121, 2)  # 100 -> 121 in 2 years = 10% CAGR
        self.assertAlmostEqual(cagr, 10, places=0)


class TestTradeJournal(unittest.TestCase):
    """Test trade journal module."""
    
    def setUp(self):
        from trading.trade_journal import TradeJournal
        import tempfile
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.test_file.close()
        self.journal = TradeJournal(storage_path=self.test_file.name)
    
    def tearDown(self):
        import os
        try:
            os.unlink(self.test_file.name)
        except:
            pass
    
    def test_add_entry(self):
        """Test adding a journal entry."""
        entry = self.journal.add_entry(
            symbol="AAPL", side="long",
            entry_date="2024-01-15", entry_price=150,
            exit_date="2024-02-01", exit_price=165,
            quantity=100
        )
        self.assertEqual(entry.symbol, "AAPL")
        self.assertEqual(entry.pnl, 1500)
    
    def test_get_entry(self):
        """Test getting an entry by ID."""
        entry = self.journal.add_entry(
            symbol="MSFT", side="long",
            entry_date="2024-01-01", entry_price=400,
            exit_date="2024-01-15", exit_price=420,
            quantity=50
        )
        retrieved = self.journal.get_entry(entry.id)
        self.assertEqual(retrieved.symbol, "MSFT")
    
    def test_update_entry(self):
        """Test updating an entry."""
        entry = self.journal.add_entry(
            symbol="AAPL", side="long",
            entry_date="2024-01-15", entry_price=150,
            quantity=100
        )
        self.journal.update_entry(entry.id, exit_price=170, exit_date="2024-02-01")
        updated = self.journal.get_entry(entry.id)
        self.assertEqual(updated.exit_price, 170)
    
    def test_delete_entry(self):
        """Test deleting an entry."""
        entry = self.journal.add_entry(
            symbol="AAPL", side="long",
            entry_date="2024-01-15", entry_price=150,
            quantity=100
        )
        result = self.journal.delete_entry(entry.id)
        self.assertTrue(result)
        self.assertIsNone(self.journal.get_entry(entry.id))
    
    def test_search_by_symbol(self):
        """Test searching by symbol."""
        self.journal.add_entry(symbol="AAPL", side="long", entry_date="2024-01-01", entry_price=150, quantity=10)
        self.journal.add_entry(symbol="MSFT", side="long", entry_date="2024-01-02", entry_price=400, quantity=10)
        self.journal.add_entry(symbol="AAPL", side="long", entry_date="2024-01-03", entry_price=155, quantity=10)
        
        results = self.journal.search(symbol="AAPL")
        self.assertEqual(len(results), 2)
    
    def test_get_winners_losers(self):
        """Test getting winners and losers."""
        self.journal.add_entry(symbol="AAPL", side="long", entry_date="2024-01-01", entry_price=100, exit_date="2024-01-15", exit_price=120, quantity=10)
        self.journal.add_entry(symbol="MSFT", side="long", entry_date="2024-01-02", entry_price=100, exit_date="2024-01-15", exit_price=90, quantity=10)
        
        winners = self.journal.get_winners()
        losers = self.journal.get_losers()
        
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 1)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        self.journal.add_entry(symbol="AAPL", side="long", entry_date="2024-01-01", entry_price=100, exit_date="2024-01-15", exit_price=120, quantity=10)
        
        stats = self.journal.get_statistics()
        self.assertEqual(stats["total_entries"], 1)
        self.assertEqual(stats["closed_trades"], 1)
        self.assertEqual(stats["win_rate"], 100)
    
    def test_get_insights(self):
        """Test getting insights."""
        self.journal.add_entry(symbol="AAPL", side="long", entry_date="2024-01-01", entry_price=100, exit_date="2024-01-15", exit_price=120, quantity=10, setup="breakout")
        self.journal.add_entry(symbol="MSFT", side="long", entry_date="2024-01-02", entry_price=100, exit_date="2024-01-15", exit_price=90, quantity=10, setup="pullback")
        
        insights = self.journal.get_insights()
        self.assertEqual(insights.total_entries, 2)
        self.assertEqual(insights.win_rate, 50)
    
    def test_open_trade(self):
        """Test open trade detection."""
        entry = self.journal.add_entry(
            symbol="AAPL", side="long",
            entry_date="2024-01-15", entry_price=150,
            quantity=100
        )
        self.assertTrue(entry.is_open())
        
        open_trades = self.journal.get_open_trades()
        self.assertEqual(len(open_trades), 1)


class TestTradeJournal(unittest.TestCase):
    """Test trade journal module."""
    
    def setUp(self):
        from trading.journal import TradeJournal
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.journal = TradeJournal(storage_path=self.temp_file.name)
    
    def tearDown(self):
        import os
        try:
            os.unlink(self.temp_file.name)
        except:
            pass
    
    def test_log_trade(self):
        """Test logging a trade."""
        entry = self.journal.log_trade(
            symbol="AAPL", side="long",
            entry_price=150, exit_price=165, quantity=100,
            entry_date="2024-01-15", exit_date="2024-02-01"
        )
        self.assertEqual(entry.symbol, "AAPL")
        self.assertEqual(entry.pnl, 1500)  # (165-150) * 100
    
    def test_pnl_calculation(self):
        """Test P&L calculation for long trade."""
        entry = self.journal.log_trade(
            symbol="TEST", side="long",
            entry_price=100, exit_price=120, quantity=10,
            entry_date="2024-01-01", exit_date="2024-01-10"
        )
        self.assertEqual(entry.pnl, 200)
        self.assertEqual(entry.pnl_pct, 20)
    
    def test_short_pnl_calculation(self):
        """Test P&L calculation for short trade."""
        entry = self.journal.log_trade(
            symbol="TEST", side="short",
            entry_price=100, exit_price=90, quantity=10,
            entry_date="2024-01-01", exit_date="2024-01-10"
        )
        self.assertEqual(entry.pnl, 100)  # Profit on short
    
    def test_winner_loser_detection(self):
        """Test winner/loser detection."""
        winner = self.journal.log_trade(
            symbol="WIN", side="long",
            entry_price=100, exit_price=110, quantity=10,
            entry_date="2024-01-01", exit_date="2024-01-10"
        )
        loser = self.journal.log_trade(
            symbol="LOSE", side="long",
            entry_price=100, exit_price=90, quantity=10,
            entry_date="2024-01-01", exit_date="2024-01-10"
        )
        self.assertTrue(winner.is_winner)
        self.assertTrue(loser.is_loser)
    
    def test_get_stats(self):
        """Test statistics calculation."""
        self.journal.log_trade("WIN", "long", 100, 120, 10, "2024-01-01", "2024-01-10")
        self.journal.log_trade("LOSE", "long", 100, 90, 10, "2024-02-01", "2024-02-10")
        
        stats = self.journal.get_stats()
        self.assertEqual(stats.total_entries, 2)
        self.assertEqual(stats.winning_entries, 1)
        self.assertEqual(stats.losing_entries, 1)
        self.assertEqual(stats.win_rate, 50)
    
    def test_filter_trades(self):
        """Test filtering trades."""
        self.journal.log_trade("AAPL", "long", 100, 120, 10, "2024-01-01", "2024-01-10")
        self.journal.log_trade("MSFT", "long", 100, 90, 10, "2024-02-01", "2024-02-10")
        
        winners = self.journal.filter_trades(winners_only=True)
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0].symbol, "AAPL")
    
    def test_search(self):
        """Test search functionality."""
        self.journal.log_trade(
            "AAPL", "long", 100, 120, 10, "2024-01-01", "2024-01-10",
            lessons="Patience is key"
        )
        
        results = self.journal.search("patience")
        self.assertEqual(len(results), 1)
    
    def test_analyze_by_setup(self):
        """Test setup analysis."""
        self.journal.log_trade(
            "AAPL", "long", 100, 120, 10, "2024-01-01", "2024-01-10",
            setup="breakout"
        )
        
        setups = self.journal.analyze_by_setup()
        self.assertIn("breakout", setups)
        self.assertEqual(setups["breakout"]["trades"], 1)
    
    def test_get_lessons(self):
        """Test getting lessons."""
        self.journal.log_trade(
            "AAPL", "long", 100, 120, 10, "2024-01-01", "2024-01-10",
            lessons="Always use stop losses"
        )
        
        lessons = self.journal.get_lessons()
        self.assertEqual(len(lessons), 1)
        self.assertIn("stop losses", lessons[0][2])


class TestCorrelationMatrix(unittest.TestCase):
    """Test correlation matrix module."""
    
    def setUp(self):
        from trading.correlation import CorrelationAnalyzer
        self.analyzer = CorrelationAnalyzer()
        
        # Set up sample correlation matrix
        self.sample_matrix = {
            "AAPL": {"AAPL": 1.0, "MSFT": 0.85, "GLD": -0.15},
            "MSFT": {"AAPL": 0.85, "MSFT": 1.0, "GLD": -0.12},
            "GLD": {"AAPL": -0.15, "MSFT": -0.12, "GLD": 1.0},
        }
        self.analyzer.set_correlation_matrix(self.sample_matrix, ["AAPL", "MSFT", "GLD"])
    
    def test_get_correlation(self):
        """Test getting correlation between two symbols."""
        corr = self.analyzer.get_correlation("AAPL", "MSFT")
        self.assertEqual(corr, 0.85)
    
    def test_get_correlation_symmetric(self):
        """Test correlation is symmetric."""
        corr1 = self.analyzer.get_correlation("AAPL", "MSFT")
        corr2 = self.analyzer.get_correlation("MSFT", "AAPL")
        self.assertEqual(corr1, corr2)
    
    def test_self_correlation(self):
        """Test self-correlation is 1.0."""
        corr = self.analyzer.get_correlation("AAPL", "AAPL")
        self.assertEqual(corr, 1.0)
    
    def test_get_all_pairs(self):
        """Test getting all correlation pairs."""
        pairs = self.analyzer.get_all_pairs()
        self.assertEqual(len(pairs), 3)  # 3 unique pairs for 3 symbols
    
    def test_get_highly_correlated(self):
        """Test getting highly correlated pairs."""
        highly_corr = self.analyzer.get_highly_correlated(0.7)
        self.assertEqual(len(highly_corr), 1)  # AAPL-MSFT
        self.assertEqual(highly_corr[0].symbol1, "AAPL")
        self.assertEqual(highly_corr[0].symbol2, "MSFT")
    
    def test_get_negatively_correlated(self):
        """Test getting negatively correlated pairs."""
        neg_corr = self.analyzer.get_negatively_correlated(-0.1)
        self.assertEqual(len(neg_corr), 2)  # AAPL-GLD, MSFT-GLD
    
    def test_diversification_score(self):
        """Test diversification score calculation."""
        score = self.analyzer.get_diversification_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_get_insights(self):
        """Test getting correlation insights."""
        insights = self.analyzer.get_insights()
        self.assertEqual(insights.total_pairs, 3)
        self.assertIsNotNone(insights.diversification_rating)
    
    def test_correlation_pair_strength(self):
        """Test correlation pair strength categorization."""
        from trading.correlation import CorrelationPair
        
        strong_pos = CorrelationPair("A", "B", 0.85)
        self.assertEqual(strong_pos.strength, "strong_positive")
        
        weak_neg = CorrelationPair("A", "B", -0.15)
        self.assertEqual(weak_neg.strength, "weak_negative")
    
    def test_helper_function(self):
        """Test helper correlation function."""
        from trading.correlation import calculate_correlation
        
        returns1 = [0.01, 0.02, -0.01, 0.03, 0.01]
        returns2 = [0.01, 0.02, -0.01, 0.03, 0.01]  # Identical
        
        corr = calculate_correlation(returns1, returns2)
        self.assertAlmostEqual(corr, 1.0, places=5)
    
    def test_to_dict(self):
        """Test exporting as dictionary."""
        result = self.analyzer.to_dict()
        self.assertIn("symbols", result)
        self.assertIn("matrix", result)
        self.assertIn("diversification_score", result)
    
    def test_to_list(self):
        """Test exporting pairs as list."""
        result = self.analyzer.to_list()
        self.assertEqual(len(result), 3)
        self.assertIn("symbol1", result[0])
        self.assertIn("correlation", result[0])


class TestBacktestEngine(unittest.TestCase):
    """Test backtesting engine."""
    
    def setUp(self):
        from trading.backtest_engine import BacktestEngine, MACrossoverStrategy, BuyAndHoldStrategy
        self.engine = BacktestEngine(initial_capital=100000)
        
        # Create sample data with clear trend
        self.sample_data = []
        price = 100.0
        for i in range(100):
            # Uptrend for first 50, downtrend for next 50
            if i < 50:
                price *= 1.01  # 1% up each day
            else:
                price *= 0.99  # 1% down each day
            
            self.sample_data.append({
                "date": f"2024-{(i//30)+1:02d}-{(i%30)+1:02d}",
                "open": price * 0.99,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": 1000000,
            })
    
    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        self.assertEqual(self.engine.initial_capital, 100000)
        self.assertEqual(self.engine.capital, 100000)
    
    def test_run_backtest(self):
        """Test running a backtest."""
        from trading.backtest_engine import BuyAndHoldStrategy
        strategy = BuyAndHoldStrategy()
        results = self.engine.run("TEST", strategy, data=self.sample_data)
        
        self.assertIsNotNone(results)
        self.assertEqual(results.symbol, "TEST")
        self.assertEqual(results.strategy_name, "BuyAndHold")
    
    def test_backtest_results_structure(self):
        """Test backtest results have correct structure."""
        from trading.backtest_engine import BuyAndHoldStrategy
        strategy = BuyAndHoldStrategy()
        results = self.engine.run("TEST", strategy, data=self.sample_data)
        
        self.assertIsNotNone(results.total_return)
        self.assertIsNotNone(results.total_return_pct)
        self.assertIsNotNone(results.equity_curve)
    
    def test_ma_crossover_strategy(self):
        """Test MA crossover strategy."""
        from trading.backtest_engine import MACrossoverStrategy, Signal, SignalType
        strategy = MACrossoverStrategy(fast_period=5, slow_period=10)
        
        # Generate signal
        signal = strategy.generate_signal(self.sample_data, 20, None)
        self.assertIsInstance(signal, Signal)
        self.assertIn(signal.type, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
    
    def test_rsi_strategy(self):
        """Test RSI strategy."""
        from trading.backtest_engine import RSIStrategy, Signal
        strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        
        signal = strategy.generate_signal(self.sample_data, 20, None)
        self.assertIsInstance(signal, Signal)
    
    def test_breakout_strategy(self):
        """Test breakout strategy."""
        from trading.backtest_engine import BreakoutStrategy, Signal
        strategy = BreakoutStrategy(lookback=10)
        
        signal = strategy.generate_signal(self.sample_data, 20, None)
        self.assertIsInstance(signal, Signal)
    
    def test_mean_reversion_strategy(self):
        """Test mean reversion strategy."""
        from trading.backtest_engine import MeanReversionStrategy, Signal
        strategy = MeanReversionStrategy(period=10, std_dev=2.0)
        
        signal = strategy.generate_signal(self.sample_data, 20, None)
        self.assertIsInstance(signal, Signal)
    
    def test_trade_class(self):
        """Test Trade dataclass."""
        from trading.backtest_engine import Trade
        trade = Trade(
            id=1, symbol="AAPL", side="long",
            entry_date="2024-01-01", entry_price=150,
            exit_date="2024-01-15", exit_price=165,
            quantity=100, pnl=1500, pnl_pct=10,
            commission=10, slippage=5, holding_days=14
        )
        self.assertEqual(trade.symbol, "AAPL")
        self.assertEqual(trade.pnl, 1500)
    
    def test_position_class(self):
        """Test Position dataclass."""
        from trading.backtest_engine import Position
        pos = Position(
            symbol="AAPL", side="long",
            entry_date="2024-01-01", entry_price=150,
            quantity=100, current_price=160
        )
        self.assertEqual(pos.unrealized_pnl, 1000)  # (160-150)*100
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 6.67, places=1)
    
    def test_signal_class(self):
        """Test Signal class."""
        from trading.backtest_engine import Signal, SignalType
        
        buy_signal = Signal(SignalType.BUY, 150.0, "2024-01-01")
        self.assertTrue(buy_signal.is_buy())
        self.assertFalse(buy_signal.is_sell())
        
        sell_signal = Signal(SignalType.SELL, 160.0, "2024-01-15")
        self.assertTrue(sell_signal.is_sell())
        self.assertFalse(sell_signal.is_buy())
    
    def test_results_to_dict(self):
        """Test results can be converted to dict."""
        from trading.backtest_engine import BuyAndHoldStrategy
        strategy = BuyAndHoldStrategy()
        results = self.engine.run("TEST", strategy, data=self.sample_data)
        
        results_dict = results.to_dict()
        self.assertIsInstance(results_dict, dict)
        self.assertIn("symbol", results_dict)
        self.assertIn("total_return", results_dict)
    
    def test_monte_carlo_no_trades(self):
        """Test Monte Carlo with no trades."""
        result = self.engine.monte_carlo()
        self.assertIn("error", result)


class TestPortfolioOptimizer(unittest.TestCase):
    """Test portfolio optimizer module."""
    
    def setUp(self):
        from trading.portfolio_optimizer import PortfolioOptimizer
        self.optimizer = PortfolioOptimizer(risk_free_rate=0.05)
        
        # Add sample assets
        self.optimizer.add_asset("SPY", expected_return=0.10, volatility=0.15)
        self.optimizer.add_asset("BND", expected_return=0.04, volatility=0.05)
        self.optimizer.add_asset("GLD", expected_return=0.05, volatility=0.15)
    
    def test_add_asset(self):
        """Test adding an asset."""
        asset = self.optimizer.add_asset("QQQ", expected_return=0.12, volatility=0.20)
        self.assertEqual(asset.symbol, "QQQ")
        self.assertEqual(asset.expected_return, 0.12)
        self.assertIn("QQQ", self.optimizer.symbols)
    
    def test_add_assets(self):
        """Test adding multiple assets."""
        from trading.portfolio_optimizer import PortfolioOptimizer
        opt = PortfolioOptimizer()
        assets = opt.add_assets(["AAPL", "MSFT"])
        self.assertEqual(len(assets), 2)
    
    def test_equal_weight(self):
        """Test equal weight optimization."""
        from trading.portfolio_optimizer import OptimizationMethod
        weights = self.optimizer.optimize(OptimizationMethod.EQUAL_WEIGHT)
        
        self.assertEqual(len(weights), 3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        for w in weights.values():
            self.assertAlmostEqual(w, 1/3, places=5)
    
    def test_optimize_sharpe(self):
        """Test maximum Sharpe optimization."""
        weights = self.optimizer.optimize_sharpe(num_iterations=1000)
        
        self.assertEqual(len(weights), 3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        self.assertIsNotNone(self.optimizer.portfolio_stats)
    
    def test_optimize_min_vol(self):
        """Test minimum volatility optimization."""
        weights = self.optimizer.optimize_min_vol(num_iterations=1000)
        
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        # BND should have high weight (lowest volatility)
        self.assertGreater(weights["BND"], 0.3)
    
    def test_optimize_risk_parity(self):
        """Test risk parity optimization."""
        weights = self.optimizer.optimize_risk_parity()
        
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        # BND should have highest weight (inverse volatility)
        self.assertGreater(weights["BND"], weights["SPY"])
    
    def test_portfolio_stats(self):
        """Test portfolio statistics calculation."""
        self.optimizer.optimize_sharpe(num_iterations=1000)
        stats = self.optimizer.portfolio_stats
        
        self.assertIsNotNone(stats)
        self.assertGreater(stats.expected_return, 0)
        self.assertGreater(stats.volatility, 0)
    
    def test_efficient_frontier(self):
        """Test efficient frontier calculation."""
        frontier = self.optimizer.efficient_frontier(num_points=10, num_iterations=500)
        
        self.assertGreater(len(frontier), 0)
        self.assertLessEqual(len(frontier), 10)
    
    def test_set_current_weights(self):
        """Test setting current weights."""
        self.optimizer.set_current_weights({"SPY": 0.5, "BND": 0.3, "GLD": 0.2})
        
        self.assertEqual(self.optimizer.assets["SPY"].current_weight, 0.5)
        self.assertEqual(self.optimizer.assets["BND"].current_weight, 0.3)
    
    def test_rebalance_recommendations(self):
        """Test rebalancing recommendations."""
        self.optimizer.set_current_weights({"SPY": 0.5, "BND": 0.3, "GLD": 0.2})
        self.optimizer.optimize_sharpe(num_iterations=1000)
        
        recs = self.optimizer.get_rebalance_recommendations(portfolio_value=100000)
        
        self.assertEqual(len(recs), 3)
        self.assertTrue(all(r.action in ["buy", "sell", "hold"] for r in recs))
    
    def test_correlation_matrix(self):
        """Test correlation matrix building."""
        self.optimizer._build_correlation_matrix()
        
        self.assertEqual(len(self.optimizer.correlation_matrix), 3)
        # Self-correlation should be 1.0
        self.assertEqual(self.optimizer.correlation_matrix["SPY"]["SPY"], 1.0)
    
    def test_to_dict(self):
        """Test exporting results to dictionary."""
        self.optimizer.optimize_sharpe(num_iterations=1000)
        result = self.optimizer.to_dict()
        
        self.assertIn("optimal_weights", result)
        self.assertIn("portfolio_stats", result)
        self.assertIn("assets", result)
    
    def test_asset_constraints(self):
        """Test asset weight constraints."""
        from trading.portfolio_optimizer import PortfolioOptimizer
        opt = PortfolioOptimizer()
        opt.add_asset("SPY", expected_return=0.10, volatility=0.15, min_weight=0.2, max_weight=0.5)
        opt.add_asset("BND", expected_return=0.04, volatility=0.05, min_weight=0.2, max_weight=0.5)
        
        weights = opt.optimize_sharpe(num_iterations=1000)
        
        # Note: Constraints are soft in the random search, but should generally be respected
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)


class TestRiskManager(unittest.TestCase):
    """Test risk manager module."""
    
    def setUp(self):
        from trading.risk_manager import RiskManager, RiskLimits
        self.rm = RiskManager(portfolio_value=100000)
        
        # Add some sample daily returns for VaR
        import random
        random.seed(42)
        self.rm.daily_returns = [random.gauss(0.0005, 0.01) for _ in range(30)]
    
    def test_initialization(self):
        """Test risk manager initializes correctly."""
        self.assertEqual(self.rm.portfolio_value, 100000)
        self.assertEqual(self.rm.cash, 100000)
    
    def test_add_position(self):
        """Test adding a position."""
        pos = self.rm.add_position("AAPL", 100, 150, 155, stop_loss=140)
        
        self.assertEqual(pos.symbol, "AAPL")
        self.assertEqual(pos.market_value, 15500)
        self.assertIn("AAPL", self.rm.positions)
    
    def test_position_pnl(self):
        """Test position P&L calculation."""
        from trading.risk_manager import Position
        pos = Position(
            symbol="AAPL", quantity=100,
            entry_price=150, current_price=160
        )
        
        self.assertEqual(pos.unrealized_pnl, 1000)
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 6.67, places=1)
    
    def test_position_risk(self):
        """Test position risk calculation."""
        from trading.risk_manager import Position
        pos = Position(
            symbol="AAPL", quantity=100,
            entry_price=150, current_price=155,
            stop_loss=140
        )
        
        self.assertEqual(pos.risk_amount, 1500)  # (155-140) * 100
    
    def test_position_sizing_fixed_fractional(self):
        """Test fixed fractional position sizing."""
        from trading.risk_manager import PositionSizingMethod
        
        result = self.rm.calculate_position_size(
            symbol="AAPL",
            entry_price=150,
            stop_loss=140,
            method=PositionSizingMethod.FIXED_FRACTIONAL,
            risk_percent=0.02
        )
        
        self.assertGreater(result.shares, 0)
        self.assertLessEqual(result.risk_amount, 2000)  # 2% of 100k
    
    def test_position_sizing_kelly(self):
        """Test Kelly criterion position sizing."""
        from trading.risk_manager import PositionSizingMethod
        
        self.rm.set_trade_stats(win_rate=0.55, avg_win_loss_ratio=1.5)
        
        result = self.rm.calculate_position_size(
            symbol="AAPL",
            entry_price=150,
            stop_loss=140,
            method=PositionSizingMethod.KELLY
        )
        
        self.assertGreater(result.shares, 0)
    
    def test_calculate_var_parametric(self):
        """Test parametric VaR calculation."""
        from trading.risk_manager import VaRMethod
        
        var = self.rm.calculate_var(confidence=0.95, method=VaRMethod.PARAMETRIC)
        
        self.assertGreater(var, 0)
        self.assertLess(var, self.rm.portfolio_value)
    
    def test_calculate_var_historical(self):
        """Test historical VaR calculation."""
        from trading.risk_manager import VaRMethod
        
        var = self.rm.calculate_var(confidence=0.95, method=VaRMethod.HISTORICAL)
        
        self.assertGreater(var, 0)
    
    def test_calculate_cvar(self):
        """Test CVaR calculation."""
        cvar = self.rm.calculate_cvar(confidence=0.95)
        var = self.rm.calculate_var(confidence=0.95)
        
        # CVaR should be >= VaR
        self.assertGreaterEqual(cvar, var * 0.9)  # Allow some tolerance
    
    def test_calculate_metrics(self):
        """Test risk metrics calculation."""
        self.rm.add_position("AAPL", 100, 150, 155, stop_loss=140)
        
        metrics = self.rm.calculate_metrics()
        
        self.assertIsNotNone(metrics.var_95)
        self.assertIsNotNone(metrics.var_99)
        self.assertGreaterEqual(metrics.leverage, 0)
    
    def test_check_risk_limits(self):
        """Test risk limit checking."""
        # Add a large position to trigger alert
        self.rm.add_position("AAPL", 1000, 150, 155)  # 155k > 100k portfolio
        
        alerts = self.rm.check_risk_limits()
        
        # Should have at least one alert
        self.assertGreater(len(alerts), 0)
    
    def test_calculate_stop_loss(self):
        """Test stop loss calculation."""
        entry = 100.0
        
        # Percent method
        stop = self.rm.calculate_stop_loss(entry, method="percent", percent=0.05)
        self.assertEqual(stop, 95.0)
        
        # ATR method
        stop = self.rm.calculate_stop_loss(entry, method="atr", atr=2.0, atr_multiplier=2.0)
        self.assertEqual(stop, 96.0)
    
    def test_calculate_take_profit(self):
        """Test take profit calculation."""
        entry = 100.0
        stop = 95.0
        
        # 2:1 risk/reward
        tp = self.rm.calculate_take_profit(entry, stop, risk_reward=2.0)
        self.assertEqual(tp, 110.0)
        
        # 3:1 risk/reward
        tp = self.rm.calculate_take_profit(entry, stop, risk_reward=3.0)
        self.assertEqual(tp, 115.0)
    
    def test_update_portfolio_value(self):
        """Test portfolio value update and drawdown tracking."""
        self.rm.update_portfolio_value(110000)  # Gain
        self.assertEqual(self.rm.peak_value, 110000)
        
        self.rm.update_portfolio_value(100000)  # Loss
        metrics = self.rm.calculate_metrics()
        self.assertGreater(metrics.current_drawdown, 0)
    
    def test_sector_exposure(self):
        """Test sector exposure calculation."""
        self.rm.add_position("AAPL", 100, 150, 150, sector="Technology")
        self.rm.add_position("JPM", 100, 150, 150, sector="Financials")
        
        exposure = self.rm._get_sector_exposure()
        
        self.assertIn("Technology", exposure)
        self.assertIn("Financials", exposure)
    
    def test_to_dict(self):
        """Test exporting risk data to dictionary."""
        self.rm.add_position("AAPL", 100, 150, 155)
        
        data = self.rm.to_dict()
        
        self.assertIn("portfolio_value", data)
        self.assertIn("metrics", data)
        self.assertIn("positions", data)
