#!/usr/bin/env python3
"""
Test Configuration and Fixtures
================================
Shared test utilities, mocks, and fixtures.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Test Data Fixtures
# ============================================================================

@dataclass
class MockQuote:
    """Mock stock quote data."""
    symbol: str = "AAPL"
    price: float = 175.50
    change: float = 2.50
    change_pct: float = 1.45
    volume: int = 50000000
    open: float = 173.00
    high: float = 176.00
    low: float = 172.50
    prev_close: float = 173.00
    market_cap: float = 2.8e12
    pe_ratio: float = 28.5
    beta: float = 1.2
    week_52_high: float = 180.00
    week_52_low: float = 140.00


@dataclass 
class MockHistoricalBar:
    """Mock historical price bar."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


def create_mock_historical_data(symbol: str = "AAPL", days: int = 100) -> list:
    """Create mock historical price data."""
    import random
    from datetime import datetime, timedelta
    
    bars = []
    price = 170.0
    
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i)
        change = random.uniform(-3, 3)
        price = max(100, price + change)
        
        bars.append(MockHistoricalBar(
            timestamp=date.strftime("%Y-%m-%d"),
            open=price - random.uniform(0, 2),
            high=price + random.uniform(0, 2),
            low=price - random.uniform(0, 3),
            close=price,
            volume=random.randint(30000000, 80000000)
        ))
    
    return bars


def create_mock_analysis_result(symbol: str = "AAPL") -> Mock:
    """Create a mock AnalysisResult object."""
    from trading.analyzer import Recommendation, Trend
    
    mock = Mock()
    mock.symbol = symbol
    mock.display_symbol = symbol
    mock.company_name = "Apple Inc."
    mock.sector = "Technology"
    mock.industry = "Consumer Electronics"
    mock.country = "US"
    mock.currency = "USD"
    mock.currency_symbol = "$"
    mock.price_divisor = 1
    mock.current_price = 175.50
    mock.change = 2.50
    mock.change_pct = 1.45
    mock.market_cap = 2.8e12
    mock.pe_ratio = 28.5
    mock.beta = 1.2
    mock.week_52_high = 180.0
    mock.week_52_low = 140.0
    
    mock.overall_score = 72.5
    mock.technical_score = 70.0
    mock.fundamental_score = 75.0
    mock.analyst_score = 80.0
    mock.risk_score = 65.0
    
    mock.recommendation = Recommendation.BUY
    mock.confidence = 85.0
    mock.trend = Trend.BULLISH
    
    mock.target_low = 160.0
    mock.target_mid = 185.0
    mock.target_high = 210.0
    
    mock.risk_metrics = Mock()
    mock.risk_metrics.volatility_annual = 25.0
    mock.risk_metrics.volatility_rating = "Medium"
    mock.risk_metrics.var_95 = -2.5
    mock.risk_metrics.max_drawdown = -15.0
    mock.risk_metrics.sharpe_ratio = 1.8
    mock.risk_metrics.sortino_ratio = 2.1
    mock.risk_metrics.beta = 1.2
    
    mock.technical_signals = [
        Mock(name="RSI", signal="BUY", description="RSI at 45 (neutral zone)"),
        Mock(name="MACD", signal="BUY", description="MACD crossed above signal"),
        Mock(name="SMA 50/200", signal="BUY", description="Price above both SMAs"),
    ]
    
    mock.fundamental_signals = [
        Mock(name="P/E Ratio", signal="HOLD", description="P/E of 28.5 vs sector avg 25"),
        Mock(name="Revenue Growth", signal="BUY", description="15% YoY growth"),
    ]
    
    mock.analyst_signals = [
        Mock(name="Consensus", signal="BUY", description="85% buy ratings"),
        Mock(name="Price Target", signal="BUY", description="5% upside to avg target"),
    ]
    
    mock.summary = "Apple shows strong momentum with solid fundamentals."
    mock.key_factors = ["Strong earnings", "Services growth", "iPhone demand"]
    
    return mock


# ============================================================================
# Mock API Clients
# ============================================================================

class MockAlpacaClient:
    """Mock Alpaca API client for testing."""
    
    def __init__(self):
        self.orders = []
        self.positions = []
    
    def get_account(self):
        return Mock(
            equity=100000.0,
            cash=50000.0,
            buying_power=100000.0,
            daily_pnl=250.0,
            daily_pnl_pct=0.25
        )
    
    def get_positions(self):
        return self.positions
    
    def get_orders(self, status="all"):
        return self.orders
    
    def get_quote(self, symbol):
        return MockQuote(symbol=symbol)
    
    def get_bars(self, symbol, timeframe="1D", limit=100):
        return create_mock_historical_data(symbol, limit)
    
    def place_order(self, symbol, qty, side, order_type="market"):
        order = Mock(
            id="test-order-123",
            symbol=symbol,
            qty=qty,
            side=side,
            status="filled",
            filled_avg_price=175.50
        )
        self.orders.append(order)
        return order


class MockFMPClient:
    """Mock Financial Modeling Prep client."""
    
    def get_quote(self, symbol):
        return {
            "symbol": symbol,
            "price": 175.50,
            "change": 2.50,
            "changesPercentage": 1.45,
            "volume": 50000000,
            "marketCap": 2800000000000,
            "pe": 28.5,
            "beta": 1.2,
        }
    
    def get_profile(self, symbol):
        return {
            "symbol": symbol,
            "companyName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "US",
            "currency": "USD",
        }
    
    def get_ratios(self, symbol):
        return {
            "peRatioTTM": 28.5,
            "pegRatioTTM": 2.1,
            "priceToBookRatioTTM": 45.0,
            "dividendYieldTTM": 0.005,
        }
    
    def get_analyst_ratings(self, symbol):
        return {
            "symbol": symbol,
            "targetHigh": 210.0,
            "targetLow": 160.0,
            "targetConsensus": 185.0,
            "strongBuy": 25,
            "buy": 15,
            "hold": 5,
            "sell": 2,
            "strongSell": 1,
        }


# ============================================================================
# Test Helpers
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
        import shutil
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


def assert_valid_analysis(result: Any) -> bool:
    """Validate that an analysis result has all required fields."""
    required_fields = [
        "symbol", "company_name", "current_price", "change", "change_pct",
        "overall_score", "technical_score", "fundamental_score",
        "recommendation", "confidence", "summary"
    ]
    
    for field in required_fields:
        if not hasattr(result, field):
            raise AssertionError(f"Missing required field: {field}")
    
    # Validate ranges
    if not 0 <= result.overall_score <= 100:
        raise AssertionError(f"Invalid overall_score: {result.overall_score}")
    
    if not 0 <= result.confidence <= 100:
        raise AssertionError(f"Invalid confidence: {result.confidence}")
    
    return True


def assert_valid_portfolio(portfolio: Dict) -> bool:
    """Validate portfolio data structure."""
    required = ["cash", "positions", "total_value"]
    for field in required:
        if field not in portfolio:
            raise AssertionError(f"Missing portfolio field: {field}")
    return True


# ============================================================================
# Integration Test Base
# ============================================================================

class IntegrationTestBase:
    """Base class for integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.temp_storage = TempStorage()
        cls.temp_storage.__enter__()
        
        # Set environment for testing
        os.environ["TRADING_TEST_MODE"] = "1"
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        cls.temp_storage.__exit__(None, None, None)
        os.environ.pop("TRADING_TEST_MODE", None)


# ============================================================================
# CLI Test Helpers
# ============================================================================

def capture_cli_output(func, *args, **kwargs):
    """Capture stdout/stderr from CLI function."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            result = func(*args, **kwargs)
        except SystemExit as e:
            result = e.code
    
    return {
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "result": result
    }


def parse_cli_table(output: str) -> list:
    """Parse CLI table output into list of dicts."""
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return []
    
    # Find header line (usually has dashes below it)
    header_idx = 0
    for i, line in enumerate(lines):
        if "─" in line or "-" in line:
            header_idx = i - 1
            break
    
    if header_idx < 0:
        return []
    
    headers = lines[header_idx].split()
    rows = []
    
    for line in lines[header_idx + 2:]:
        if not line.strip() or "─" in line:
            continue
        values = line.split()
        if len(values) >= len(headers):
            rows.append(dict(zip(headers, values[:len(headers)])))
    
    return rows
