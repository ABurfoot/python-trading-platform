#!/usr/bin/env python3
"""
Real-Time Streaming Module
===========================
WebSocket-based real-time price streaming and updates.

Features:
- Real-time price streaming via WebSocket
- Multiple data source support (Alpaca, Finnhub, Polygon)
- Price change callbacks
- Alert triggering
- Portfolio value updates
- Reconnection handling

Usage:
    from trading.streaming import StreamingManager, PriceUpdate
    
    # Create streaming manager
    stream = StreamingManager()
    
    # Subscribe to symbols
    stream.subscribe(["AAPL", "MSFT", "GOOGL"])
    
    # Add callback for price updates
    stream.on_price_update(my_callback)
    
    # Start streaming
    stream.start()
    
    # Or use the simple interface
    from trading.streaming import stream_prices
    for update in stream_prices(["AAPL", "MSFT"]):
        print(f"{update.symbol}: ${update.price}")
"""

import os
import sys
import json
import time
import threading
import queue
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Generator, Any
from enum import Enum
import urllib.request
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import websocket library
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client not installed. Install with: pip install websocket-client")


class StreamSource(Enum):
    """Streaming data sources."""
    ALPACA = "alpaca"
    FINNHUB = "finnhub"
    POLYGON = "polygon"
    SIMULATED = "simulated"  # For testing


class UpdateType(Enum):
    """Type of streaming update."""
    TRADE = "trade"
    QUOTE = "quote"
    BAR = "bar"
    STATUS = "status"
    ERROR = "error"


@dataclass
class PriceUpdate:
    """Real-time price update."""
    symbol: str
    price: float
    timestamp: datetime
    volume: int = 0
    bid: float = 0
    ask: float = 0
    change: float = 0
    change_pct: float = 0
    source: str = ""
    update_type: UpdateType = UpdateType.TRADE
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "change": round(self.change, 2),
            "change_pct": round(self.change_pct, 2),
            "source": self.source,
            "type": self.update_type.value
        }


@dataclass
class StreamStatus:
    """Streaming connection status."""
    connected: bool
    source: str
    subscribed_symbols: List[str]
    last_update: Optional[datetime]
    error_message: str = ""
    reconnect_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "connected": self.connected,
            "source": self.source,
            "subscribed_symbols": self.subscribed_symbols,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "error_message": self.error_message,
            "reconnect_count": self.reconnect_count
        }


class AlpacaStreamer:
    """
    Alpaca WebSocket streaming client.
    Requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
    """
    
    STREAM_URL = "wss://stream.data.alpaca.markets/v2/iex"  # IEX (free)
    # STREAM_URL = "wss://stream.data.alpaca.markets/v2/sip"  # SIP (paid)
    
    def __init__(self, on_update: Callable[[PriceUpdate], None],
                 on_status: Callable[[StreamStatus], None] = None):
        self.api_key = os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        
        self.on_update = on_update
        self.on_status = on_status or (lambda x: None)
        
        self.ws: Optional[websocket.WebSocketApp] = None
        self.subscribed_symbols: List[str] = []
        self.connected = False
        self.reconnect_count = 0
        self.last_update: Optional[datetime] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Previous prices for change calculation
        self._prev_prices: Dict[str, float] = {}
    
    def _on_open(self, ws):
        """Handle connection open."""
        logger.info("Alpaca WebSocket connected")
        
        # Authenticate
        auth_msg = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        ws.send(json.dumps(auth_msg))
    
    def _on_message(self, ws, message):
        """Handle incoming message."""
        try:
            data = json.loads(message)
            
            for item in data:
                msg_type = item.get("T")
                
                if msg_type == "success":
                    if item.get("msg") == "authenticated":
                        logger.info("Alpaca authenticated successfully")
                        self.connected = True
                        self._subscribe()
                        self._send_status()
                    elif item.get("msg") == "subscribed":
                        logger.info(f"Subscribed to: {item.get('trades', [])}")
                
                elif msg_type == "t":  # Trade
                    symbol = item.get("S")
                    price = float(item.get("p", 0))
                    volume = int(item.get("s", 0))
                    
                    # Calculate change
                    prev_price = self._prev_prices.get(symbol, price)
                    change = price - prev_price
                    change_pct = (change / prev_price * 100) if prev_price > 0 else 0
                    self._prev_prices[symbol] = price
                    
                    update = PriceUpdate(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.now(),
                        volume=volume,
                        change=change,
                        change_pct=change_pct,
                        source="alpaca",
                        update_type=UpdateType.TRADE
                    )
                    
                    self.last_update = datetime.now()
                    self.on_update(update)
                
                elif msg_type == "q":  # Quote
                    symbol = item.get("S")
                    bid = float(item.get("bp", 0))
                    ask = float(item.get("ap", 0))
                    
                    update = PriceUpdate(
                        symbol=symbol,
                        price=(bid + ask) / 2,
                        timestamp=datetime.now(),
                        bid=bid,
                        ask=ask,
                        source="alpaca",
                        update_type=UpdateType.QUOTE
                    )
                    
                    self.last_update = datetime.now()
                    self.on_update(update)
                
                elif msg_type == "error":
                    logger.error(f"Alpaca error: {item.get('msg')}")
                    self._send_status(error=item.get('msg', 'Unknown error'))
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_error(self, ws, error):
        """Handle error."""
        logger.error(f"Alpaca WebSocket error: {error}")
        self._send_status(error=str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle connection close."""
        logger.info(f"Alpaca WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
        self._send_status()
        
        # Attempt reconnection
        if self._running:
            self.reconnect_count += 1
            logger.info(f"Attempting reconnection ({self.reconnect_count})...")
            time.sleep(min(30, 2 ** self.reconnect_count))  # Exponential backoff
            self._connect()
    
    def _subscribe(self):
        """Subscribe to symbols."""
        if not self.subscribed_symbols:
            return
        
        subscribe_msg = {
            "action": "subscribe",
            "trades": self.subscribed_symbols,
            "quotes": self.subscribed_symbols
        }
        self.ws.send(json.dumps(subscribe_msg))
    
    def _send_status(self, error: str = ""):
        """Send status update."""
        status = StreamStatus(
            connected=self.connected,
            source="alpaca",
            subscribed_symbols=self.subscribed_symbols,
            last_update=self.last_update,
            error_message=error,
            reconnect_count=self.reconnect_count
        )
        self.on_status(status)
    
    def _connect(self):
        """Establish WebSocket connection."""
        if not WEBSOCKET_AVAILABLE:
            logger.error("websocket-client not installed")
            return
        
        self.ws = websocket.WebSocketApp(
            self.STREAM_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.ws.run_forever()
    
    def subscribe(self, symbols: List[str]):
        """Subscribe to symbols."""
        self.subscribed_symbols = [s.upper() for s in symbols]
        
        if self.connected and self.ws:
            self._subscribe()
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        symbols = [s.upper() for s in symbols]
        
        if self.connected and self.ws:
            unsubscribe_msg = {
                "action": "unsubscribe",
                "trades": symbols,
                "quotes": symbols
            }
            self.ws.send(json.dumps(unsubscribe_msg))
        
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]
    
    def start(self):
        """Start streaming in background thread."""
        if not self.api_key or not self.secret_key:
            logger.error("Alpaca API credentials not set")
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()
        return True
    
    def stop(self):
        """Stop streaming."""
        self._running = False
        if self.ws:
            self.ws.close()
        self.connected = False


class FinnhubStreamer:
    """
    Finnhub WebSocket streaming client.
    Requires FINNHUB_API_KEY environment variable.
    """
    
    STREAM_URL = "wss://ws.finnhub.io"
    
    def __init__(self, on_update: Callable[[PriceUpdate], None],
                 on_status: Callable[[StreamStatus], None] = None):
        self.api_key = os.environ.get("FINNHUB_API_KEY", "")
        
        self.on_update = on_update
        self.on_status = on_status or (lambda x: None)
        
        self.ws: Optional[websocket.WebSocketApp] = None
        self.subscribed_symbols: List[str] = []
        self.connected = False
        self.reconnect_count = 0
        self.last_update: Optional[datetime] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._prev_prices: Dict[str, float] = {}
    
    def _on_open(self, ws):
        """Handle connection open."""
        logger.info("Finnhub WebSocket connected")
        self.connected = True
        self._subscribe()
        self._send_status()
    
    def _on_message(self, ws, message):
        """Handle incoming message."""
        try:
            data = json.loads(message)
            
            if data.get("type") == "trade":
                for trade in data.get("data", []):
                    symbol = trade.get("s")
                    price = float(trade.get("p", 0))
                    volume = int(trade.get("v", 0))
                    
                    # Calculate change
                    prev_price = self._prev_prices.get(symbol, price)
                    change = price - prev_price
                    change_pct = (change / prev_price * 100) if prev_price > 0 else 0
                    self._prev_prices[symbol] = price
                    
                    update = PriceUpdate(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.fromtimestamp(trade.get("t", 0) / 1000),
                        volume=volume,
                        change=change,
                        change_pct=change_pct,
                        source="finnhub",
                        update_type=UpdateType.TRADE
                    )
                    
                    self.last_update = datetime.now()
                    self.on_update(update)
            
            elif data.get("type") == "ping":
                # Respond to ping
                ws.send(json.dumps({"type": "pong"}))
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_error(self, ws, error):
        """Handle error."""
        logger.error(f"Finnhub WebSocket error: {error}")
        self._send_status(error=str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle connection close."""
        logger.info(f"Finnhub WebSocket closed")
        self.connected = False
        self._send_status()
        
        if self._running:
            self.reconnect_count += 1
            time.sleep(min(30, 2 ** self.reconnect_count))
            self._connect()
    
    def _subscribe(self):
        """Subscribe to symbols."""
        for symbol in self.subscribed_symbols:
            subscribe_msg = {"type": "subscribe", "symbol": symbol}
            self.ws.send(json.dumps(subscribe_msg))
    
    def _send_status(self, error: str = ""):
        """Send status update."""
        status = StreamStatus(
            connected=self.connected,
            source="finnhub",
            subscribed_symbols=self.subscribed_symbols,
            last_update=self.last_update,
            error_message=error,
            reconnect_count=self.reconnect_count
        )
        self.on_status(status)
    
    def _connect(self):
        """Establish WebSocket connection."""
        if not WEBSOCKET_AVAILABLE:
            logger.error("websocket-client not installed")
            return
        
        url = f"{self.STREAM_URL}?token={self.api_key}"
        
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.ws.run_forever()
    
    def subscribe(self, symbols: List[str]):
        """Subscribe to symbols."""
        self.subscribed_symbols = [s.upper() for s in symbols]
        
        if self.connected and self.ws:
            self._subscribe()
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        symbols = [s.upper() for s in symbols]
        
        if self.connected and self.ws:
            for symbol in symbols:
                unsubscribe_msg = {"type": "unsubscribe", "symbol": symbol}
                self.ws.send(json.dumps(unsubscribe_msg))
        
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]
    
    def start(self):
        """Start streaming."""
        if not self.api_key:
            logger.error("Finnhub API key not set")
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()
        return True
    
    def stop(self):
        """Stop streaming."""
        self._running = False
        if self.ws:
            self.ws.close()
        self.connected = False


class SimulatedStreamer:
    """
    Simulated price streamer for testing without API keys.
    Generates realistic-looking price movements.
    """
    
    def __init__(self, on_update: Callable[[PriceUpdate], None],
                 on_status: Callable[[StreamStatus], None] = None,
                 update_interval: float = 1.0):
        self.on_update = on_update
        self.on_status = on_status or (lambda x: None)
        self.update_interval = update_interval
        
        self.subscribed_symbols: List[str] = []
        self.connected = False
        self.last_update: Optional[datetime] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Simulated prices
        self._prices: Dict[str, float] = {}
        self._base_prices = {
            "AAPL": 175.0, "MSFT": 380.0, "GOOGL": 140.0, "AMZN": 175.0,
            "META": 485.0, "NVDA": 850.0, "TSLA": 240.0, "AMD": 155.0,
            "VAS.AX": 92.0, "BHP.AX": 45.0, "CBA.AX": 115.0, "CSL.AX": 290.0,
        }
    
    def _generate_update(self, symbol: str) -> PriceUpdate:
        """Generate a simulated price update."""
        import random
        
        # Get or initialize price
        if symbol not in self._prices:
            self._prices[symbol] = self._base_prices.get(symbol, 100.0)
        
        prev_price = self._prices[symbol]
        
        # Random walk with mean reversion
        change_pct = random.gauss(0, 0.001)  # 0.1% typical move
        
        # Mean reversion toward base price
        base = self._base_prices.get(symbol, 100.0)
        reversion = (base - prev_price) / base * 0.001
        change_pct += reversion
        
        new_price = prev_price * (1 + change_pct)
        self._prices[symbol] = new_price
        
        change = new_price - prev_price
        
        return PriceUpdate(
            symbol=symbol,
            price=round(new_price, 2),
            timestamp=datetime.now(),
            volume=random.randint(100, 10000),
            bid=round(new_price - 0.01, 2),
            ask=round(new_price + 0.01, 2),
            change=round(change, 2),
            change_pct=round(change_pct * 100, 4),
            source="simulated",
            update_type=UpdateType.TRADE
        )
    
    def _stream_loop(self):
        """Main streaming loop."""
        import random
        
        self.connected = True
        self._send_status()
        
        while self._running:
            if self.subscribed_symbols:
                # Pick random symbol to update
                symbol = random.choice(self.subscribed_symbols)
                update = self._generate_update(symbol)
                
                self.last_update = datetime.now()
                self.on_update(update)
            
            time.sleep(self.update_interval)
        
        self.connected = False
        self._send_status()
    
    def _send_status(self, error: str = ""):
        """Send status update."""
        status = StreamStatus(
            connected=self.connected,
            source="simulated",
            subscribed_symbols=self.subscribed_symbols,
            last_update=self.last_update,
            error_message=error,
            reconnect_count=0
        )
        self.on_status(status)
    
    def subscribe(self, symbols: List[str]):
        """Subscribe to symbols."""
        self.subscribed_symbols = [s.upper() for s in symbols]
        self._send_status()
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        symbols = [s.upper() for s in symbols]
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]
        self._send_status()
    
    def start(self):
        """Start simulated streaming."""
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        return True
    
    def stop(self):
        """Stop streaming."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


class StreamingManager:
    """
    High-level streaming manager that handles multiple sources
    and provides a unified interface.
    
    Usage:
        stream = StreamingManager()
        stream.subscribe(["AAPL", "MSFT"])
        stream.on_price_update(my_callback)
        stream.start()
    """
    
    def __init__(self, source: StreamSource = None, update_interval: float = 1.0):
        # Auto-detect source based on available API keys
        if source is None:
            source = self._detect_source()
        
        self.source = source
        self._callbacks: List[Callable[[PriceUpdate], None]] = []
        self._status_callbacks: List[Callable[[StreamStatus], None]] = []
        self._update_queue: queue.Queue = queue.Queue()
        self._streamer = None
        self._running = False
        
        # Alert integration
        self._alerts_enabled = False
        self._alert_manager = None
        
        # Portfolio integration
        self._portfolio_enabled = False
        self._portfolio_manager = None
        
        # Create appropriate streamer
        if source == StreamSource.ALPACA:
            self._streamer = AlpacaStreamer(self._handle_update, self._handle_status)
        elif source == StreamSource.FINNHUB:
            self._streamer = FinnhubStreamer(self._handle_update, self._handle_status)
        else:
            self._streamer = SimulatedStreamer(self._handle_update, self._handle_status,
                                               update_interval=update_interval)
    
    def _detect_source(self) -> StreamSource:
        """Detect best available streaming source."""
        if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
            return StreamSource.ALPACA
        elif os.environ.get("FINNHUB_API_KEY"):
            return StreamSource.FINNHUB
        else:
            return StreamSource.SIMULATED
    
    def _handle_update(self, update: PriceUpdate):
        """Handle incoming price update."""
        # Put in queue for processing
        self._update_queue.put(update)
        
        # Call registered callbacks
        for callback in self._callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        # Check alerts
        if self._alerts_enabled and self._alert_manager:
            try:
                self._check_alerts(update)
            except Exception as e:
                logger.error(f"Alert check error: {e}")
    
    def _handle_status(self, status: StreamStatus):
        """Handle status update."""
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def _check_alerts(self, update: PriceUpdate):
        """Check if update triggers any alerts."""
        if not self._alert_manager:
            try:
                from trading.alerts import AlertManager
                self._alert_manager = AlertManager()
            except ImportError:
                return
        
        # Check all alerts for this symbol
        try:
            triggered = self._alert_manager.check_symbol(update.symbol, update.price)
            for alert in triggered:
                logger.info(f"🔔 Alert triggered: {alert.symbol} {alert.condition} ${alert.value}")
        except AttributeError:
            # Fallback if method doesn't exist
            pass
    
    def subscribe(self, symbols: List[str]):
        """Subscribe to price updates for symbols."""
        self._streamer.subscribe(symbols)
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        self._streamer.unsubscribe(symbols)
    
    def on_price_update(self, callback: Callable[[PriceUpdate], None]):
        """Register callback for price updates."""
        self._callbacks.append(callback)
    
    def on_status_change(self, callback: Callable[[StreamStatus], None]):
        """Register callback for status changes."""
        self._status_callbacks.append(callback)
    
    def enable_alerts(self, enabled: bool = True):
        """Enable/disable alert checking."""
        self._alerts_enabled = enabled
        if enabled:
            try:
                from trading.alerts import AlertManager
                self._alert_manager = AlertManager()
            except ImportError:
                logger.warning("Alerts module not available")
    
    def enable_portfolio_updates(self, enabled: bool = True):
        """Enable/disable portfolio value updates."""
        self._portfolio_enabled = enabled
    
    def start(self) -> bool:
        """Start streaming."""
        self._running = True
        return self._streamer.start()
    
    def stop(self):
        """Stop streaming."""
        self._running = False
        self._streamer.stop()
    
    def get_status(self) -> Dict:
        """Get current streaming status."""
        return {
            "source": self.source.value,
            "running": self._running,
            "connected": self._streamer.connected if self._streamer else False,
            "subscribed_symbols": self._streamer.subscribed_symbols if self._streamer else [],
            "alerts_enabled": self._alerts_enabled,
            "websocket_available": WEBSOCKET_AVAILABLE
        }
    
    def get_latest_price(self, symbol: str, timeout: float = 5.0) -> Optional[PriceUpdate]:
        """
        Get the latest price for a symbol (blocking).
        
        Args:
            symbol: Symbol to get price for
            timeout: Max time to wait in seconds
        """
        symbol = symbol.upper()
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                update = self._update_queue.get(timeout=0.1)
                if update.symbol == symbol:
                    return update
            except queue.Empty:
                pass
        
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def stream_prices(symbols: List[str], source: StreamSource = None,
                  duration: float = None) -> Generator[PriceUpdate, None, None]:
    """
    Generator that yields price updates.
    
    Args:
        symbols: Symbols to stream
        source: Data source (auto-detected if None)
        duration: How long to stream in seconds (None = forever)
    
    Yields:
        PriceUpdate objects
    
    Example:
        for update in stream_prices(["AAPL", "MSFT"], duration=60):
            print(f"{update.symbol}: ${update.price}")
    """
    update_queue = queue.Queue()
    
    def callback(update: PriceUpdate):
        update_queue.put(update)
    
    manager = StreamingManager(source=source)
    manager.on_price_update(callback)
    manager.subscribe(symbols)
    manager.start()
    
    start_time = time.time()
    
    try:
        while True:
            if duration and (time.time() - start_time) > duration:
                break
            
            try:
                update = update_queue.get(timeout=1.0)
                yield update
            except queue.Empty:
                pass
    finally:
        manager.stop()


def print_stream(symbols: List[str], duration: float = 30.0):
    """
    Print streaming prices to console.
    
    Args:
        symbols: Symbols to stream
        duration: How long to stream
    """
    print(f"\n Streaming prices for: {', '.join(symbols)}")
    print(f"   Duration: {duration}s")
    print("-" * 60)
    
    for update in stream_prices(symbols, duration=duration):
        change_color = "\033[92m" if update.change >= 0 else "\033[91m"
        reset = "\033[0m"
        
        print(f"   {update.timestamp.strftime('%H:%M:%S')} | "
              f"{update.symbol:<6} | "
              f"${update.price:>8.2f} | "
              f"{change_color}{update.change:>+6.2f} ({update.change_pct:>+5.2f}%){reset} | "
              f"Vol: {update.volume:>6}")
    
    print("-" * 60)
    print("Streaming ended")


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI for testing streaming."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time price streaming")
    parser.add_argument("symbols", nargs="+", help="Symbols to stream")
    parser.add_argument("-d", "--duration", type=float, default=30, help="Duration in seconds")
    parser.add_argument("-s", "--source", choices=["alpaca", "finnhub", "simulated"],
                       default=None, help="Data source")
    
    args = parser.parse_args()
    
    source = None
    if args.source:
        source = StreamSource(args.source)
    
    print_stream(args.symbols, duration=args.duration)


if __name__ == "__main__":
    main()
