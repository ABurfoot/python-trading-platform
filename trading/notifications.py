#!/usr/bin/env python3
"""
Desktop Notifications Module
=============================
Cross-platform desktop and terminal notifications with sound alerts.

Features:
- Desktop notifications (Mac, Linux, Windows)
- Terminal notifications with formatting
- Sound alerts (system beep or custom sounds)
- Integration with alerts.py for price monitoring
- Background alert monitoring daemon

No external services required - everything runs locally for security.

Usage:
    from trading.notifications import Notifier, AlertMonitor
    
    # Simple notification
    notifier = Notifier()
    notifier.notify("Price Alert", "AAPL crossed above $150")
    
    # With sound
    notifier.notify("Price Alert", "AAPL hit target!", sound=True)
    
    # Terminal only
    notifier.terminal_alert("AAPL", 152.34, "crossed above $150")
    
    # Start background monitoring
    monitor = AlertMonitor()
    monitor.start()
"""

import os
import sys
import platform
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AlertType(Enum):
    """Types of alerts."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE = "price_change"
    VOLUME_SPIKE = "volume_spike"
    NEWS = "news"
    ECONOMIC_EVENT = "economic_event"
    CUSTOM = "custom"


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """An alert to be displayed."""
    title: str
    message: str
    alert_type: str = "custom"
    priority: str = "medium"
    symbol: str = ""
    price: float = 0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Notifier:
    """
    Cross-platform notification system.
    
    Supports:
    - Desktop notifications (native OS)
    - Terminal alerts (formatted output)
    - Sound alerts (system beep)
    """
    
    def __init__(self, enable_sound: bool = True, enable_desktop: bool = True):
        self.enable_sound = enable_sound
        self.enable_desktop = enable_desktop
        self.system = platform.system()  # 'Darwin' (Mac), 'Linux', 'Windows'
        
        # Alert history
        self.history: List[Alert] = []
        self.max_history = 100
        
        # Callbacks for custom handling
        self.callbacks: List[Callable[[Alert], None]] = []
    
    def notify(self, title: str, message: str, sound: bool = True, 
               priority: str = "medium", alert_type: str = "custom",
               symbol: str = "", price: float = 0) -> bool:
        """
        Send notification to both terminal and desktop.
        
        Args:
            title: Notification title
            message: Notification message
            sound: Play sound alert
            priority: low, medium, high, critical
            alert_type: Type of alert
            symbol: Stock/crypto symbol (optional)
            price: Current price (optional)
        
        Returns:
            True if notification was sent successfully
        """
        # Create alert object
        alert = Alert(
            title=title,
            message=message,
            alert_type=alert_type,
            priority=priority,
            symbol=symbol,
            price=price,
        )
        
        # Store in history
        self.history.append(alert)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        # Send to terminal
        self.terminal_alert(title, message, priority, symbol, price)
        
        # Send to desktop
        if self.enable_desktop:
            self._desktop_notify(title, message, priority)
        
        # Play sound
        if sound and self.enable_sound:
            self._play_sound(priority)
        
        # Call registered callbacks
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                pass
        
        return True
    
    def terminal_alert(self, title: str, message: str, priority: str = "medium",
                       symbol: str = "", price: float = 0):
        """
        Display formatted alert in terminal.
        """
        # Colors (ANSI codes)
        colors = {
            "reset": "\033[0m",
            "bold": "\033[1m",
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "bg_red": "\033[41m",
            "bg_yellow": "\033[43m",
            "bg_blue": "\033[44m",
        }
        
        # Priority colors
        priority_colors = {
            "low": colors["cyan"],
            "medium": colors["yellow"],
            "high": colors["magenta"],
            "critical": colors["bg_red"] + colors["white"],
        }
        
        c = colors
        pc = priority_colors.get(priority, colors["yellow"])
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Build the alert box
        width = 60
        
        print()
        print(f"{pc}{c['bold']}{'═' * width}{c['reset']}")
        print(f"{pc}{c['bold']}║ 🔔 {title.upper():<{width-6}} ║{c['reset']}")
        print(f"{pc}{'═' * width}{c['reset']}")
        
        # Message lines
        print(f"{c['bold']}║{c['reset']} {message:<{width-4}} {c['bold']}║{c['reset']}")
        
        # Symbol and price if provided
        if symbol:
            if price > 0:
                price_str = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
                print(f"{c['bold']}║{c['reset']} {c['green']}{symbol}{c['reset']}: {price_str:<{width-len(symbol)-10}} {c['bold']}║{c['reset']}")
            else:
                print(f"{c['bold']}║{c['reset']} {c['green']}{symbol}{c['reset']:<{width-4}} {c['bold']}║{c['reset']}")
        
        # Timestamp
        print(f"{c['bold']}║{c['reset']} ⏰ {timestamp:<{width-7}} {c['bold']}║{c['reset']}")
        
        print(f"{pc}{'═' * width}{c['reset']}")
        print()
    
    def _desktop_notify(self, title: str, message: str, priority: str = "medium") -> bool:
        """Send desktop notification based on OS."""
        try:
            if self.system == "Darwin":  # macOS
                return self._notify_macos(title, message)
            elif self.system == "Linux":
                return self._notify_linux(title, message)
            elif self.system == "Windows":
                return self._notify_windows(title, message)
            else:
                return False
        except Exception as e:
            return False
    
    def _notify_macos(self, title: str, message: str) -> bool:
        """Send notification on macOS using osascript."""
        try:
            # Escape quotes in message
            title = title.replace('"', '\\"')
            message = message.replace('"', '\\"')
            
            script = f'display notification "{message}" with title "{title}" sound name "Glass"'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5
            )
            return True
        except Exception:
            # Fallback: try terminal-notifier if installed
            try:
                subprocess.run(
                    ["terminal-notifier", "-title", title, "-message", message, "-sound", "Glass"],
                    capture_output=True,
                    timeout=5
                )
                return True
            except Exception:
                return False
    
    def _notify_linux(self, title: str, message: str) -> bool:
        """Send notification on Linux using notify-send."""
        try:
            subprocess.run(
                ["notify-send", title, message, "-u", "normal", "-t", "5000"],
                capture_output=True,
                timeout=5
            )
            return True
        except Exception:
            # Fallback: try zenity
            try:
                subprocess.run(
                    ["zenity", "--notification", "--text", f"{title}\n{message}"],
                    capture_output=True,
                    timeout=5
                )
                return True
            except Exception:
                return False
    
    def _notify_windows(self, title: str, message: str) -> bool:
        """Send notification on Windows."""
        try:
            # Try using PowerShell (works on all Windows versions)
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = "<toast><visual><binding template='ToastText02'><text id='1'>{title}</text><text id='2'>{message}</text></binding></visual></toast>"
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Trading Platform").Show($toast)
            '''
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10
            )
            return True
        except Exception:
            # Fallback: try win10toast if available
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5, threaded=True)
                return True
            except Exception:
                # Last resort: use msg command
                try:
                    subprocess.run(
                        ["msg", "*", f"{title}: {message}"],
                        capture_output=True,
                        timeout=5
                    )
                    return True
                except Exception:
                    return False
    
    def _play_sound(self, priority: str = "medium"):
        """Play alert sound based on OS."""
        try:
            if self.system == "Darwin":  # macOS
                # Different sounds for different priorities
                sounds = {
                    "low": "Pop",
                    "medium": "Glass", 
                    "high": "Ping",
                    "critical": "Sosumi",
                }
                sound = sounds.get(priority, "Glass")
                subprocess.run(
                    ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
                    capture_output=True,
                    timeout=3
                )
            
            elif self.system == "Linux":
                # Try paplay (PulseAudio), then aplay, then beep
                sound_files = [
                    "/usr/share/sounds/freedesktop/stereo/complete.oga",
                    "/usr/share/sounds/freedesktop/stereo/bell.oga",
                    "/usr/share/sounds/sound-icons/bell.wav",
                ]
                
                played = False
                for sound_file in sound_files:
                    if os.path.exists(sound_file):
                        try:
                            subprocess.run(["paplay", sound_file], capture_output=True, timeout=3)
                            played = True
                            break
                        except Exception:
                            try:
                                subprocess.run(["aplay", sound_file], capture_output=True, timeout=3)
                                played = True
                                break
                            except Exception:
                                continue
                
                if not played:
                    # Fallback to terminal bell
                    print("\a", end="", flush=True)
            
            elif self.system == "Windows":
                # Use Windows system sounds
                try:
                    import winsound
                    if priority == "critical":
                        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                    else:
                        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                except Exception:
                    # Fallback to beep
                    print("\a", end="", flush=True)
            
            else:
                # Generic fallback - terminal bell
                print("\a", end="", flush=True)
        
        except Exception:
            # Ultimate fallback - terminal bell
            print("\a", end="", flush=True)
    
    def register_callback(self, callback: Callable[[Alert], None]):
        """Register a callback function to be called on each alert."""
        self.callbacks.append(callback)
    
    def get_history(self, limit: int = 20) -> List[Alert]:
        """Get recent alert history."""
        return self.history[-limit:]
    
    def clear_history(self):
        """Clear alert history."""
        self.history = []


class AlertMonitor:
    """
    Background monitor that checks alerts and sends notifications.
    
    Integrates with the alerts.py module to monitor price alerts.
    """
    
    def __init__(self, check_interval: int = 60, notifier: Notifier = None):
        """
        Args:
            check_interval: Seconds between alert checks
            notifier: Notifier instance (creates one if not provided)
        """
        self.check_interval = check_interval
        self.notifier = notifier or Notifier()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Custom alert conditions
        self.price_alerts: List[Dict] = []
        self.triggered_alerts: set = set()  # Track which alerts have fired
    
    def add_price_alert(self, symbol: str, condition: str, price: float,
                        message: str = None) -> str:
        """
        Add a price alert.
        
        Args:
            symbol: Stock/crypto symbol
            condition: 'above', 'below', 'cross_above', 'cross_below'
            price: Target price
            message: Custom message (optional)
        
        Returns:
            Alert ID
        """
        alert_id = f"{symbol}_{condition}_{price}_{len(self.price_alerts)}"
        
        self.price_alerts.append({
            "id": alert_id,
            "symbol": symbol.upper(),
            "condition": condition,
            "price": price,
            "message": message or f"{symbol} {condition} ${price:,.2f}",
            "created": datetime.now().isoformat(),
            "last_price": None,
        })
        
        return alert_id
    
    def remove_price_alert(self, alert_id: str) -> bool:
        """Remove a price alert by ID."""
        for i, alert in enumerate(self.price_alerts):
            if alert["id"] == alert_id:
                self.price_alerts.pop(i)
                self.triggered_alerts.discard(alert_id)
                return True
        return False
    
    def list_alerts(self) -> List[Dict]:
        """List all active price alerts."""
        return self.price_alerts.copy()
    
    def _check_price_condition(self, alert: Dict, current_price: float) -> bool:
        """Check if price condition is met."""
        condition = alert["condition"]
        target = alert["price"]
        last_price = alert.get("last_price")
        
        if condition == "above":
            return current_price >= target
        elif condition == "below":
            return current_price <= target
        elif condition == "cross_above":
            if last_price is None:
                return False
            return last_price < target <= current_price
        elif condition == "cross_below":
            if last_price is None:
                return False
            return last_price > target >= current_price
        
        return False
    
    def _fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch current price for a symbol."""
        try:
            # Try stock data sources first
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            quote, _ = fetcher.get_quote(symbol)
            if quote and quote.get("price"):
                return quote["price"]
        except Exception:
            pass
        
        try:
            # Try crypto
            from trading.crypto import CryptoTracker
            ct = CryptoTracker()
            coin = ct.get_coin(symbol)
            if coin:
                return coin.price
        except Exception:
            pass
        
        return None
    
    def _check_alerts(self):
        """Check all alerts against current prices."""
        for alert in self.price_alerts:
            # Skip if already triggered (one-time alerts)
            if alert["id"] in self.triggered_alerts:
                continue
            
            symbol = alert["symbol"]
            current_price = self._fetch_price(symbol)
            
            if current_price is None:
                continue
            
            # Check condition
            if self._check_price_condition(alert, current_price):
                # Send notification
                self.notifier.notify(
                    title=f"🚨 Price Alert: {symbol}",
                    message=alert["message"],
                    sound=True,
                    priority="high",
                    alert_type="price_alert",
                    symbol=symbol,
                    price=current_price,
                )
                
                # Mark as triggered
                self.triggered_alerts.add(alert["id"])
            
            # Update last price for cross conditions
            alert["last_price"] = current_price
    
    def _check_integrated_alerts(self):
        """Check alerts from the alerts.py module."""
        try:
            from trading.alerts import AlertManager
            am = AlertManager()
            
            # Get triggered alerts
            triggered = am.check_all_alerts()
            
            for alert in triggered:
                self.notifier.notify(
                    title=f"🚨 {alert.get('type', 'Alert')}: {alert.get('symbol', '')}",
                    message=alert.get("message", "Alert triggered"),
                    sound=True,
                    priority="high",
                    symbol=alert.get("symbol", ""),
                    price=alert.get("current_price", 0),
                )
        except ImportError:
            pass  # alerts.py not available
        except Exception as e:
            pass
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                # Check custom price alerts
                self._check_alerts()
                
                # Check integrated alerts
                self._check_integrated_alerts()
                
            except Exception as e:
                pass
            
            # Wait for next check
            time.sleep(self.check_interval)
    
    def start(self):
        """Start background monitoring."""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
        print(f"🔔 Alert monitor started (checking every {self.check_interval}s)")
    
    def stop(self):
        """Stop background monitoring."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("🔕 Alert monitor stopped")
    
    def check_now(self):
        """Manually trigger an alert check."""
        self._check_alerts()
        self._check_integrated_alerts()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def send_notification(title: str, message: str, sound: bool = True):
    """Quick function to send a notification."""
    notifier = Notifier()
    notifier.notify(title, message, sound=sound)


def price_alert(symbol: str, price: float, message: str = None, sound: bool = True):
    """Quick function to send a price alert."""
    notifier = Notifier()
    msg = message or f"{symbol} reached ${price:,.2f}"
    notifier.notify(
        title=f"Price Alert: {symbol}",
        message=msg,
        sound=sound,
        priority="high",
        symbol=symbol,
        price=price,
    )


# =============================================================================
# CLI INTERFACE  
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Desktop Notifications")
    parser.add_argument("--test", "-t", action="store_true", help="Send test notification")
    parser.add_argument("--message", "-m", help="Custom message to send")
    parser.add_argument("--title", default="Trading Alert", help="Notification title")
    parser.add_argument("--no-sound", action="store_true", help="Disable sound")
    parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"], 
                        default="medium", help="Alert priority")
    parser.add_argument("--monitor", action="store_true", help="Start alert monitor")
    parser.add_argument("--interval", type=int, default=60, help="Monitor check interval (seconds)")
    parser.add_argument("--demo", action="store_true", help="Run demo of all alert types")
    
    args = parser.parse_args()
    
    notifier = Notifier(enable_sound=not args.no_sound)
    
    if args.demo:
        print("\n🎬 Running notification demo...\n")
        
        # Demo different priority levels
        priorities = ["low", "medium", "high", "critical"]
        
        for i, priority in enumerate(priorities):
            time.sleep(2)
            notifier.notify(
                title=f"{priority.upper()} Priority Alert",
                message=f"This is a {priority} priority notification demo",
                priority=priority,
                sound=True,
                symbol="AAPL" if i % 2 == 0 else "BTC",
                price=150.00 + i * 10,
            )
        
        print("\n[Y] Demo complete!\n")
    
    elif args.test:
        notifier.notify(
            title="Test Notification",
            message="If you see this, notifications are working! 🎉",
            sound=not args.no_sound,
            priority=args.priority,
        )
        print("[Y] Test notification sent!")
    
    elif args.message:
        notifier.notify(
            title=args.title,
            message=args.message,
            sound=not args.no_sound,
            priority=args.priority,
        )
        print("[Y] Notification sent!")
    
    elif args.monitor:
        monitor = AlertMonitor(check_interval=args.interval, notifier=notifier)
        
        # Add some example alerts
        print("\n Add alerts using the AlertMonitor class in Python:")
        print("   monitor.add_price_alert('AAPL', 'above', 150)")
        print("   monitor.add_price_alert('BTC', 'below', 50000)")
        print()
        
        monitor.start()
        
        try:
            print("Press Ctrl+C to stop monitoring...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop()
    
    else:
        # Show help and system info
        print(f"\n{'='*60}")
        print("🔔 DESKTOP NOTIFICATIONS")
        print(f"{'='*60}")
        print(f"\nSystem: {platform.system()}")
        print(f"Sound:  {'Enabled' if notifier.enable_sound else 'Disabled'}")
        print(f"Desktop: {'Enabled' if notifier.enable_desktop else 'Disabled'}")
        
        print(f"\n{'='*60}")
        print("USAGE")
        print(f"{'='*60}")
        print("""
  Test notification:
    python -m trading.notifications --test
    
  Custom message:
    python -m trading.notifications -m "AAPL hit target!"
    
  High priority:
    python -m trading.notifications -m "Urgent!" -p critical
    
  Run demo:
    python -m trading.notifications --demo
    
  Start monitor:
    python -m trading.notifications --monitor --interval 30

  In Python:
    from trading.notifications import Notifier, price_alert
    
    # Quick alert
    price_alert("AAPL", 152.34, "Target reached!")
    
    # Full control
    notifier = Notifier()
    notifier.notify("Alert", "Message", sound=True, priority="high")
""")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
