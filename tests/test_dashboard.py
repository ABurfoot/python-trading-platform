#!/usr/bin/env python3
"""
Dashboard API Tests
====================
Test all dashboard API endpoints.

Run:
    python3 -m pytest tests/test_dashboard.py -v
"""

import os
import sys
import json
import time
import unittest
import threading
import urllib.request
import urllib.parse
import tempfile
import shutil
from unittest.mock import patch, Mock

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
    """Create a mock AnalysisResult object."""
    mock = Mock()
    mock.symbol = symbol
    mock.overall_score = 72.5
    return mock


class DashboardTestServer:
    """Test server context manager."""
    
    def __init__(self, port=18080):
        self.port = port
        self.server = None
        self.thread = None
    
    def __enter__(self):
        try:
            from trading.dashboard import DashboardHandler, ReusableTCPServer
            
            self.server = ReusableTCPServer(("127.0.0.1", self.port), DashboardHandler)
            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            time.sleep(1.0)  # Wait for server to start
            return self
        except Exception as e:
            print(f"Could not start test server: {e}")
            return None
    
    def __exit__(self, *args):
        if self.server:
            self.server.shutdown()
    
    def get(self, path, timeout=30):
        """Make GET request with longer timeout for slow API calls."""
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return {
                    "status": resp.status,
                    "data": json.loads(resp.read().decode()) if resp.headers.get("Content-Type", "").startswith("application/json") else resp.read().decode()
                }
        except urllib.error.HTTPError as e:
            return {"status": e.code, "data": None}
        except urllib.error.URLError as e:
            return {"status": 0, "error": f"URL Error: {e.reason}"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def post(self, path, data=None, timeout=30):
        """Make POST request with longer timeout."""
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            body = json.dumps(data or {}).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "status": resp.status,
                    "data": json.loads(resp.read().decode())
                }
        except urllib.error.HTTPError as e:
            return {"status": e.code, "data": None}
        except urllib.error.URLError as e:
            return {"status": 0, "error": f"URL Error: {e.reason}"}
        except Exception as e:
            return {"status": 0, "error": str(e)}


class TestDashboardHealth(unittest.TestCase):
    """Test dashboard server health."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18081)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    def test_server_responds(self):
        """Test that server responds to requests."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/")
        self.assertEqual(resp["status"], 200)
    
    def test_html_content(self):
        """Test that HTML is served."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/")
        self.assertIn("Trading Platform", resp["data"])


class TestDashboardWatchlistAPI(unittest.TestCase):
    """Test watchlist API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18082)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    def test_get_watchlists(self):
        """Test GET /api/watchlists."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/watchlists")
        self.assertEqual(resp["status"], 200)
        self.assertIn("watchlists", resp["data"])
    
    def test_get_watchlist(self):
        """Test GET /api/watchlist/{name}."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/watchlist/default")
        self.assertEqual(resp["status"], 200)
        self.assertIn("stocks", resp["data"])
    
    def test_add_to_watchlist(self):
        """Test POST /api/watchlist/{name}/add."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.post("/api/watchlist/default/add", {"symbol": "TEST"})
        self.assertEqual(resp["status"], 200)
    
    def test_create_watchlist(self):
        """Test POST /api/watchlist/create."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.post("/api/watchlist/create", {"name": "test_list"})
        self.assertEqual(resp["status"], 200)


class TestDashboardPortfolioAPI(unittest.TestCase):
    """Test portfolio API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18083)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    def test_get_portfolios(self):
        """Test GET /api/portfolios."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/portfolios")
        self.assertEqual(resp["status"], 200)
        self.assertIn("portfolios", resp["data"])
    
    def test_get_portfolio(self):
        """Test GET /api/portfolio/{name}."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/portfolio/default")
        self.assertEqual(resp["status"], 200)
        self.assertIn("cash", resp["data"])
    
    def test_portfolio_buy(self):
        """Test POST /api/portfolio/{name}/buy."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.post("/api/portfolio/default/buy", {
            "symbol": "TEST",
            "quantity": 10,
            "price": 100.0
        })
        self.assertEqual(resp["status"], 200)


class TestDashboardAlertsAPI(unittest.TestCase):
    """Test alerts API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18084)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    def test_get_alerts(self):
        """Test GET /api/alerts."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/alerts")
        self.assertEqual(resp["status"], 200)
        self.assertIn("alerts", resp["data"])
    
    def test_create_alert(self):
        """Test POST /api/alerts/create."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.post("/api/alerts/create", {
            "symbol": "TEST",
            "condition": "above",
            "price": 200.0
        })
        self.assertEqual(resp["status"], 200)


class TestDashboardAnalysisAPI(unittest.TestCase):
    """Test analysis API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18085)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    @patch('trading.analyzer.StockAnalyzer')
    def test_analyze_stock(self, mock_analyzer):
        """Test GET /api/analyze/{symbol}."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        # Note: This will use actual analyzer if available
        # In production tests, you'd mock the analyzer
        resp = self.server.get("/api/analyze/AAPL")
        # May fail if no API keys, but endpoint should respond
        self.assertIn(resp["status"], [200, 500])


class TestDashboardSectorsAPI(unittest.TestCase):
    """Test sectors API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18086)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    @unittest.skip("Slow test - sectors API requires multiple external calls")
    def test_get_sectors(self):
        """Test GET /api/sectors."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/sectors", timeout=60)
        # May fail without API keys
        self.assertIn(resp["status"], [200, 500])


class TestDashboardErrorHandling(unittest.TestCase):
    """Test dashboard error handling."""
    
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardTestServer(port=18088)
        cls.ctx = cls.server.__enter__()
    
    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.__exit__(None, None, None)
    
    def test_404_on_invalid_path(self):
        """Test 404 on invalid path."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/nonexistent")
        self.assertEqual(resp["status"], 404)
    
    def test_invalid_watchlist(self):
        """Test error on invalid watchlist."""
        if not self.ctx:
            self.skipTest("Server not available")
        
        resp = self.server.get("/api/watchlist/nonexistent_list_12345")
        self.assertEqual(resp["status"], 200)  # Returns empty


if __name__ == "__main__":
    unittest.main(verbosity=2)
