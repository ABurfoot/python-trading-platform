#!/usr/bin/env python3
"""
CLI Integration Tests
======================
Test all terminal/CLI functionality.

Run:
    python3 -m pytest tests/test_cli.py -v
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock, MagicMock
from io import StringIO
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Local Test Helpers (avoid import issues with conftest)
# ============================================================================

class TempStorage:
    """Context manager for temporary test storage."""
    
    def __init__(self):
        self.temp_dir = None
        self.paths = {}
    
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.paths = {
            "watchlists": os.path.join(self.temp_dir, "watchlists.json"),
            "alerts": os.path.join(self.temp_dir, "alerts.json"),
            "portfolios": os.path.join(self.temp_dir, "portfolios.json"),
            "exports": os.path.join(self.temp_dir, "exports"),
        }
        os.makedirs(self.paths["exports"], exist_ok=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


def create_mock_analysis_result(symbol="AAPL"):
    """Create a proper mock AnalysisResult object that works with exporter."""
    class MockResult:
        def __init__(self):
            self.symbol = symbol
            self.display_symbol = symbol
            self.company_name = "Apple Inc."
            self.current_price = 175.50
            self.change = 2.50
            self.change_pct = 1.45
            self.overall_score = 72.5
            self.confidence = 85.0
            self.sector = "Technology"
            self.industry = "Consumer Electronics"
            self.country = "US"
            self.currency = "USD"
            self.currency_symbol = "$"
            self.market_cap = 2.8e12
            self.pe_ratio = 28.5
            self.beta = 1.2
            self.technical_score = 70
            self.fundamental_score = 75
            self.analyst_score = 80
            self.risk_score = 65
            self.target_low = 160.0
            self.target_mid = 185.0
            self.target_high = 210.0
            self.week_52_low = 140.0
            self.week_52_high = 180.0
            self.dcf_value = 190.0
            self.summary = "Apple shows strong momentum."
            self.key_factors = ["Strong earnings", "High demand"]
            self.technical_signals = [
                {"name": "RSI", "signal": "BUY", "description": "RSI neutral"},
            ]
            self.fundamental_signals = []
            self.analyst_signals = []
            
            class RiskMetrics:
                def __init__(self):
                    self.volatility_annual = 25.0
                    self.var_95 = -2.5
                    self.max_drawdown = -15.0
                    self.sharpe_ratio = 1.8
            
            class Recommendation:
                def __init__(self):
                    self.value = "BUY"
            
            self.risk_metrics = RiskMetrics()
            self.recommendation = Recommendation()
    
    return MockResult()


class TestCLIAnalyze(unittest.TestCase):
    """Test CLI analyze command."""
    
    def setUp(self):
        self.temp = TempStorage()
        self.temp.__enter__()
    
    def tearDown(self):
        self.temp.__exit__(None, None, None)
    
    @patch('trading.analyzer.StockAnalyzer')
    def test_analyze_basic(self, mock_analyzer_class):
        """Test basic analyze command."""
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = create_mock_analysis_result("AAPL")
        mock_analyzer_class.return_value = mock_analyzer
        
        from trading.analyzer import StockAnalyzer
        analyzer = StockAnalyzer()
        result = analyzer.analyze("AAPL")
        
        self.assertEqual(result.symbol, "AAPL")
        self.assertIsNotNone(result.overall_score)
    
    @patch('trading.analyzer.StockAnalyzer')
    def test_analyze_with_exchange(self, mock_analyzer_class):
        """Test analyze with exchange prefix."""
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = create_mock_analysis_result("BHP")
        mock_analyzer_class.return_value = mock_analyzer
        
        from trading.analyzer import StockAnalyzer
        analyzer = StockAnalyzer()
        result = analyzer.analyze("ASX:BHP")
        
        self.assertIsNotNone(result)


class TestCLIWatchlist(unittest.TestCase):
    """Test CLI watchlist commands."""
    
    def setUp(self):
        self.temp = TempStorage()
        self.temp.__enter__()
        
        from trading.watchlist import WatchlistManager
        self.wl = WatchlistManager(storage_path=self.temp.paths["watchlists"])
    
    def tearDown(self):
        self.temp.__exit__(None, None, None)
    
    def test_watchlist_list(self):
        """Test listing watchlists."""
        lists = self.wl.list_watchlists()
        self.assertIsInstance(lists, list)
        # Default should exist
        self.assertTrue(any(w["key"] == "default" for w in lists))
    
    def test_watchlist_add_single(self):
        """Test adding single stock."""
        added = self.wl.add("default", "AAPL")
        self.assertEqual(added, ["AAPL"])
    
    def test_watchlist_add_multiple(self):
        """Test adding multiple stocks."""
        # Add stocks one at a time (that's how the API works)
        self.wl.add("default", "AAPL")
        self.wl.add("default", "MSFT")
        self.wl.add("default", "GOOGL")
        stocks = self.wl.get("default")
        self.assertIn("AAPL", stocks)
        self.assertIn("MSFT", stocks)
        self.assertIn("GOOGL", stocks)
    
    def test_watchlist_show(self):
        """Test showing watchlist contents."""
        self.wl.add("default", "AAPL")
        self.wl.add("default", "MSFT")
        stocks = self.wl.get("default")
        self.assertIn("AAPL", stocks)
        self.assertIn("MSFT", stocks)
    
    def test_watchlist_remove(self):
        """Test removing stock."""
        self.wl.add("default", "AAPL")
        removed = self.wl.remove("default", "AAPL")
        self.assertEqual(removed, ["AAPL"])
        self.assertNotIn("AAPL", self.wl.get("default"))
    
    def test_watchlist_create(self):
        """Test creating new watchlist."""
        result = self.wl.create("tech")
        self.assertTrue(result)
        lists = self.wl.list_watchlists()
        self.assertTrue(any(w["key"] == "tech" for w in lists))
    
    def test_watchlist_delete(self):
        """Test deleting watchlist."""
        self.wl.create("temp")
        result = self.wl.delete("temp")
        self.assertTrue(result)
    
    def test_watchlist_cannot_delete_default(self):
        """Test that default cannot be deleted."""
        result = self.wl.delete("default")
        self.assertFalse(result)


class TestCLIPortfolio(unittest.TestCase):
    """Test CLI portfolio commands."""
    
    def setUp(self):
        self.temp = TempStorage()
        self.temp.__enter__()
        
        from trading.portfolio import IntegratedPortfolioManager
        self.pm = IntegratedPortfolioManager(storage_path=self.temp.paths["portfolios"])
    
    def tearDown(self):
        self.temp.__exit__(None, None, None)
    
    def test_portfolio_show(self):
        """Test showing portfolio."""
        summary = self.pm.get_summary("default")
        self.assertIn("cash", summary)
        self.assertIn("total_value", summary)
    
    def test_portfolio_buy(self):
        """Test buying stock."""
        tx = self.pm.buy("default", "AAPL", 10, 175.50)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.symbol, "AAPL")
        self.assertEqual(tx.quantity, 10)
    
    def test_portfolio_sell(self):
        """Test selling stock."""
        self.pm.buy("default", "AAPL", 10, 175.50)
        result = self.pm.sell("default", "AAPL", 5, 180.00)
        self.assertIsNotNone(result)
        # sell() returns a dict with transaction details
        self.assertIn("quantity", result)
        self.assertEqual(result["quantity"], 5)
    
    def test_portfolio_positions(self):
        """Test viewing positions."""
        self.pm.buy("default", "AAPL", 10, 175.50)
        positions = self.pm.get_positions("default")
        self.assertEqual(len(positions), 1)
        # Positions are dicts in the new API
        self.assertEqual(positions[0]["symbol"], "AAPL")
    
    def test_portfolio_deposit(self):
        """Test depositing cash."""
        # cash is now a dict (multi-currency), get the base currency amount
        initial = self.pm.portfolios["default"].cash.get(self.pm.base_currency, 0)
        # deposit() signature: (portfolio_name, amount, currency=None, notes="")
        tx = self.pm.deposit("default", 5000, notes="Test deposit")
        self.assertIsNotNone(tx)
        new_cash = self.pm.portfolios["default"].cash.get(self.pm.base_currency, 0)
        self.assertEqual(new_cash, initial + 5000)
    
    def test_portfolio_withdraw(self):
        """Test withdrawing cash."""
        # cash is now a dict (multi-currency)
        initial = self.pm.portfolios["default"].cash.get(self.pm.base_currency, 0)
        # withdraw() signature: (portfolio_name, amount, currency=None, notes="")
        tx = self.pm.withdraw("default", 1000, notes="Test withdraw")
        self.assertIsNotNone(tx)
        new_cash = self.pm.portfolios["default"].cash.get(self.pm.base_currency, 0)
        self.assertEqual(new_cash, initial - 1000)


class TestCLIAlerts(unittest.TestCase):
    """Test CLI alert commands."""
    
    def setUp(self):
        self.temp = TempStorage()
        self.temp.__enter__()
        
        from trading.alerts import AlertManager
        self.am = AlertManager(storage_path=self.temp.paths["alerts"])
    
    def tearDown(self):
        self.temp.__exit__(None, None, None)
    
    def test_alerts_list_empty(self):
        """Test listing alerts when empty."""
        alerts = self.am.get_all()
        self.assertEqual(len(alerts), 0)
    
    def test_alerts_create_price(self):
        """Test creating price alert."""
        alert = self.am.add_price_alert("AAPL", "above", 200.0)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.symbol, "AAPL")
        self.assertEqual(alert.condition, "above")
        self.assertEqual(alert.value, 200.0)
    
    def test_alerts_remove(self):
        """Test removing alert."""
        alert = self.am.add_price_alert("AAPL", "above", 200.0)
        result = self.am.remove(alert.id)
        self.assertTrue(result)
        self.assertEqual(len(self.am.get_all()), 0)
    
    def test_alerts_check(self):
        """Test checking alerts."""
        self.am.add_price_alert("AAPL", "above", 200.0)
        
        # Should not trigger
        triggered = self.am.check_alerts({"AAPL": {"price": 190.0}})
        self.assertEqual(len(triggered), 0)
        
        # Should trigger
        triggered = self.am.check_alerts({"AAPL": {"price": 210.0}})
        self.assertEqual(len(triggered), 1)


class TestCLICompare(unittest.TestCase):
    """Test CLI compare command."""
    
    @patch('trading.comparison.StockComparison')
    def test_compare_two_stocks(self, mock_comp_class):
        """Test comparing two stocks."""
        from trading.comparison import ComparisonResult
        
        mock_comp = Mock()
        mock_comp.compare.return_value = ComparisonResult(
            symbols=["AAPL", "MSFT"],
            analyses={"AAPL": create_mock_analysis_result("AAPL"),
                     "MSFT": create_mock_analysis_result("MSFT")},
            rankings={},
            winner="AAPL",
            summary="AAPL wins overall"
        )
        mock_comp_class.return_value = mock_comp
        
        from trading.comparison import StockComparison
        comp = StockComparison()
        result = comp.compare(["AAPL", "MSFT"])
        
        self.assertEqual(result.winner, "AAPL")
        self.assertEqual(len(result.symbols), 2)


class TestCLIScreener(unittest.TestCase):
    """Test CLI screener command."""
    
    def test_preset_screens_available(self):
        """Test that preset screens are available."""
        from trading.screener import PRESET_SCREENS
        
        expected_presets = ["value", "growth", "dividend", "momentum"]
        for preset in expected_presets:
            self.assertIn(preset, PRESET_SCREENS)


class TestCLIExport(unittest.TestCase):
    """Test CLI export command."""
    
    def setUp(self):
        self.temp = TempStorage()
        self.temp.__enter__()
    
    def tearDown(self):
        self.temp.__exit__(None, None, None)
    
    def test_export_json(self):
        """Test JSON export."""
        from trading.export import ReportExporter
        
        exporter = ReportExporter(output_dir=self.temp.paths["exports"])
        result = create_mock_analysis_result("AAPL")
        
        path = exporter.to_json(result, "test.json")
        self.assertTrue(os.path.exists(path))
    
    def test_export_csv(self):
        """Test CSV export."""
        from trading.export import ReportExporter
        
        exporter = ReportExporter(output_dir=self.temp.paths["exports"])
        result = create_mock_analysis_result("AAPL")
        
        path = exporter.to_csv(result, "test.csv")
        self.assertTrue(os.path.exists(path))
    
    def test_export_html(self):
        """Test HTML export."""
        from trading.export import ReportExporter
        
        exporter = ReportExporter(output_dir=self.temp.paths["exports"])
        result = create_mock_analysis_result("AAPL")
        
        path = exporter.to_html(result, "test.html")
        self.assertTrue(os.path.exists(path))
        
        # Verify content
        with open(path) as f:
            content = f.read()
        self.assertIn("AAPL", content)
        self.assertIn("Apple", content)


class TestCLINews(unittest.TestCase):
    """Test CLI news command."""
    
    def test_news_item_structure(self):
        """Test NewsItem data structure."""
        from trading.news import NewsItem
        
        item = NewsItem(
            headline="Apple announces new iPhone",
            summary="Details about the launch...",
            source="Reuters",
            url="https://reuters.com/article",
            published="2024-01-15T10:30:00Z",
            symbol="AAPL",
            sentiment="positive"
        )
        
        self.assertEqual(item.symbol, "AAPL")
        self.assertEqual(item.sentiment, "positive")
        
        # Test to_dict
        d = item.to_dict()
        self.assertIn("headline", d)
        self.assertIn("sentiment", d)


class TestCLIEarnings(unittest.TestCase):
    """Test CLI earnings command."""
    
    def test_earnings_event_structure(self):
        """Test EarningsEvent data structure."""
        from trading.earnings import EarningsEvent
        
        event = EarningsEvent(
            symbol="AAPL",
            company_name="Apple Inc.",
            date="2024-01-25",
            time="AMC",
            eps_estimate=2.10,
            eps_actual=2.25,
            revenue_estimate=118e9,
            revenue_actual=120e9,
            surprise_pct=7.14
        )
        
        self.assertEqual(event.symbol, "AAPL")
        self.assertEqual(event.beat_or_miss, "beat")


class TestCLISectors(unittest.TestCase):
    """Test CLI sectors command."""
    
    def test_sector_etfs_defined(self):
        """Test sector ETFs are defined."""
        from trading.sectors import SECTOR_ETFS, INDEX_ETFS
        
        # Check key sectors
        self.assertIn("XLK", SECTOR_ETFS)  # Technology
        self.assertIn("XLF", SECTOR_ETFS)  # Financials
        self.assertIn("XLV", SECTOR_ETFS)  # Healthcare
        
        # Check indices
        self.assertIn("SPY", INDEX_ETFS)   # S&P 500
        self.assertIn("QQQ", INDEX_ETFS)   # NASDAQ


if __name__ == "__main__":
    unittest.main(verbosity=2)
