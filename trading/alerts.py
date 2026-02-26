#!/usr/bin/env python3
"""
Alert System
============
Price and signal alerts with notifications.

Features:
- Price alerts (above/below threshold)
- Signal alerts (buy/sell recommendations)
- Percent change alerts
- Desktop notifications (macOS/Linux)
- Persistent storage

Usage:
    from trading.alerts import AlertManager
    
    am = AlertManager()
    am.add_price_alert("AAPL", "above", 200)
    am.add_signal_alert("AAPL", "STRONG BUY")
    triggered = am.check_alerts()
"""

import os
import json
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class AlertType(Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PERCENT_CHANGE = "percent_change"
    SIGNAL = "signal"
    VOLUME_SPIKE = "volume_spike"


class AlertStatus(Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    DISABLED = "disabled"


@dataclass
class Alert:
    id: str
    symbol: str
    alert_type: str
    condition: str
    value: float | str
    status: str
    created: str
    triggered_at: str = None
    message: str = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Alert':
        return cls(**data)


class AlertManager:
    """Manage stock alerts with notifications."""
    
    def __init__(self, storage_path: str = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".trading_platform" / "alerts.json"
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.alerts: List[Alert] = self._load()
        self._next_id = max([int(a.id.split("_")[1]) for a in self.alerts], default=0) + 1
    
    def _load(self) -> List[Alert]:
        """Load alerts from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    return [Alert.from_dict(a) for a in data]
            except Exception:
                pass
        return []
    
    def _save(self):
        """Save alerts to disk."""
        with open(self.storage_path, 'w') as f:
            json.dump([a.to_dict() for a in self.alerts], f, indent=2)
    
    def _generate_id(self) -> str:
        """Generate unique alert ID."""
        alert_id = f"alert_{self._next_id}"
        self._next_id += 1
        return alert_id
    
    def add_price_alert(self, symbol: str, condition: str, price: float, message: str = None) -> Alert:
        """
        Add a price alert.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            condition: "above" or "below"
            price: Target price
            message: Optional custom message
        """
        symbol = symbol.upper().strip().replace(" ", "")
        condition = condition.lower()
        
        if condition not in ("above", "below"):
            raise ValueError("Condition must be 'above' or 'below'")
        
        alert_type = AlertType.PRICE_ABOVE.value if condition == "above" else AlertType.PRICE_BELOW.value
        
        alert = Alert(
            id=self._generate_id(),
            symbol=symbol,
            alert_type=alert_type,
            condition=condition,
            value=price,
            status=AlertStatus.ACTIVE.value,
            created=datetime.now().isoformat(),
            message=message or f"{symbol} price {condition} ${price:.2f}"
        )
        
        self.alerts.append(alert)
        self._save()
        return alert
    
    def add_percent_alert(self, symbol: str, percent: float, message: str = None) -> Alert:
        """
        Add a percent change alert.
        
        Args:
            symbol: Stock symbol
            percent: Percent change threshold (e.g., 5.0 for +/-5%)
        """
        symbol = symbol.upper().strip().replace(" ", "")
        
        alert = Alert(
            id=self._generate_id(),
            symbol=symbol,
            alert_type=AlertType.PERCENT_CHANGE.value,
            condition="change",
            value=abs(percent),
            status=AlertStatus.ACTIVE.value,
            created=datetime.now().isoformat(),
            message=message or f"{symbol} moved {percent:.1f}%"
        )
        
        self.alerts.append(alert)
        self._save()
        return alert
    
    def add_signal_alert(self, symbol: str, signal: str, message: str = None) -> Alert:
        """
        Add a signal alert (triggers when stock gets specific recommendation).
        
        Args:
            symbol: Stock symbol
            signal: Target signal (e.g., "STRONG BUY", "BUY", "SELL")
        """
        symbol = symbol.upper().strip().replace(" ", "")
        signal = signal.upper()
        
        alert = Alert(
            id=self._generate_id(),
            symbol=symbol,
            alert_type=AlertType.SIGNAL.value,
            condition="equals",
            value=signal,
            status=AlertStatus.ACTIVE.value,
            created=datetime.now().isoformat(),
            message=message or f"{symbol} signal: {signal}"
        )
        
        self.alerts.append(alert)
        self._save()
        return alert
    
    def add_volume_alert(self, symbol: str, multiplier: float = 2.0, message: str = None) -> Alert:
        """
        Add a volume spike alert.
        
        Args:
            symbol: Stock symbol
            multiplier: Volume multiplier vs average (e.g., 2.0 for 2x average)
        """
        symbol = symbol.upper().strip().replace(" ", "")
        
        alert = Alert(
            id=self._generate_id(),
            symbol=symbol,
            alert_type=AlertType.VOLUME_SPIKE.value,
            condition="above",
            value=multiplier,
            status=AlertStatus.ACTIVE.value,
            created=datetime.now().isoformat(),
            message=message or f"{symbol} volume spike ({multiplier}x average)"
        )
        
        self.alerts.append(alert)
        self._save()
        return alert
    
    def remove(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        for i, alert in enumerate(self.alerts):
            if alert.id == alert_id:
                self.alerts.pop(i)
                self._save()
                return True
        return False
    
    def disable(self, alert_id: str) -> bool:
        """Disable an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.DISABLED.value
                self._save()
                return True
        return False
    
    def enable(self, alert_id: str) -> bool:
        """Enable a disabled alert."""
        for alert in self.alerts:
            if alert.id == alert_id and alert.status == AlertStatus.DISABLED.value:
                alert.status = AlertStatus.ACTIVE.value
                self._save()
                return True
        return False
    
    def get_active(self, symbol: str = None) -> List[Alert]:
        """Get active alerts, optionally filtered by symbol."""
        alerts = [a for a in self.alerts if a.status == AlertStatus.ACTIVE.value]
        if symbol:
            symbol = symbol.upper().strip()
            alerts = [a for a in alerts if a.symbol == symbol]
        return alerts
    
    def get_triggered(self) -> List[Alert]:
        """Get all triggered alerts."""
        return [a for a in self.alerts if a.status == AlertStatus.TRIGGERED.value]
    
    def get_all(self) -> List[Alert]:
        """Get all alerts."""
        return self.alerts.copy()
    
    def clear_triggered(self):
        """Remove all triggered alerts."""
        self.alerts = [a for a in self.alerts if a.status != AlertStatus.TRIGGERED.value]
        self._save()
    
    def check_alerts(self, price_data: Dict[str, Dict] = None, 
                     analysis_data: Dict[str, Dict] = None) -> List[Alert]:
        """
        Check all active alerts against current data.
        
        Args:
            price_data: Dict of symbol -> {"price": float, "change_pct": float, "volume_ratio": float}
            analysis_data: Dict of symbol -> {"recommendation": str, "score": int}
        
        Returns:
            List of triggered alerts
        """
        triggered = []
        
        for alert in self.alerts:
            if alert.status != AlertStatus.ACTIVE.value:
                continue
            
            symbol = alert.symbol
            was_triggered = False
            
            # Check price alerts
            if alert.alert_type in (AlertType.PRICE_ABOVE.value, AlertType.PRICE_BELOW.value):
                if price_data and symbol in price_data:
                    price = price_data[symbol].get("price", 0)
                    if alert.alert_type == AlertType.PRICE_ABOVE.value and price >= alert.value:
                        was_triggered = True
                        alert.message = f"🔔 {symbol} is now ${price:.2f} (above ${alert.value:.2f})"
                    elif alert.alert_type == AlertType.PRICE_BELOW.value and price <= alert.value:
                        was_triggered = True
                        alert.message = f"🔔 {symbol} is now ${price:.2f} (below ${alert.value:.2f})"
            
            # Check percent change alerts
            elif alert.alert_type == AlertType.PERCENT_CHANGE.value:
                if price_data and symbol in price_data:
                    change = abs(price_data[symbol].get("change_pct", 0))
                    if change >= alert.value:
                        was_triggered = True
                        sign = "+" if price_data[symbol].get("change_pct", 0) >= 0 else ""
                        alert.message = f"🔔 {symbol} moved {sign}{price_data[symbol].get('change_pct', 0):.2f}%"
            
            # Check signal alerts
            elif alert.alert_type == AlertType.SIGNAL.value:
                if analysis_data and symbol in analysis_data:
                    rec = analysis_data[symbol].get("recommendation", "")
                    if alert.value in rec:
                        was_triggered = True
                        alert.message = f"🔔 {symbol} signal: {rec}"
            
            # Check volume alerts
            elif alert.alert_type == AlertType.VOLUME_SPIKE.value:
                if price_data and symbol in price_data:
                    vol_ratio = price_data[symbol].get("volume_ratio", 0)
                    if vol_ratio >= alert.value:
                        was_triggered = True
                        alert.message = f"🔔 {symbol} volume spike: {vol_ratio:.1f}x average"
            
            if was_triggered:
                alert.status = AlertStatus.TRIGGERED.value
                alert.triggered_at = datetime.now().isoformat()
                triggered.append(alert)
        
        if triggered:
            self._save()
        
        return triggered
    
    def notify(self, alert: Alert):
        """Send desktop notification for an alert."""
        title = f"Trading Alert: {alert.symbol}"
        message = alert.message or f"Alert triggered for {alert.symbol}"
        
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{message}" with title "{title}"'
                ], capture_output=True)
            elif system == "Linux":
                subprocess.run(["notify-send", title, message], capture_output=True)
            elif system == "Windows":
                # Windows toast notification via PowerShell
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $textNodes = $template.GetElementsByTagName("text")
                $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
                $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Trading Platform").Show($toast)
                '''
                subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        except Exception:
            pass  # Silently fail if notification not supported


# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Alert Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all alerts")
    list_parser.add_argument("-a", "--active", action="store_true", help="Show only active")
    
    # Add price alert
    price_parser = subparsers.add_parser("price", help="Add price alert")
    price_parser.add_argument("symbol", help="Stock symbol")
    price_parser.add_argument("condition", choices=["above", "below"], help="Condition")
    price_parser.add_argument("value", type=float, help="Target price")
    
    # Add signal alert
    signal_parser = subparsers.add_parser("signal", help="Add signal alert")
    signal_parser.add_argument("symbol", help="Stock symbol")
    signal_parser.add_argument("signal", help="Target signal (e.g., 'STRONG BUY')")
    
    # Remove alert
    rm_parser = subparsers.add_parser("remove", help="Remove alert")
    rm_parser.add_argument("alert_id", help="Alert ID")
    
    # Clear triggered
    clear_parser = subparsers.add_parser("clear", help="Clear triggered alerts")
    
    args = parser.parse_args()
    am = AlertManager()
    
    if args.command == "list":
        alerts = am.get_active() if args.active else am.get_all()
        print(f"\n🔔 Alerts ({len(alerts)}):")
        for a in alerts:
            status_icon = "[OK]" if a.status == "active" else "[!]" if a.status == "triggered" else "[ ]"
            print(f"  {status_icon} [{a.id}] {a.symbol}: {a.alert_type} {a.condition} {a.value}")
        print()
    
    elif args.command == "price":
        alert = am.add_price_alert(args.symbol, args.condition, args.value)
        print(f"[OK] Added price alert: {alert.symbol} {alert.condition} ${alert.value:.2f}")
    
    elif args.command == "signal":
        alert = am.add_signal_alert(args.symbol, args.signal)
        print(f"[OK] Added signal alert: {alert.symbol} = {alert.value}")
    
    elif args.command == "remove":
        if am.remove(args.alert_id):
            print(f"[OK] Removed alert: {args.alert_id}")
        else:
            print(f"Alert not found: {args.alert_id}")
    
    elif args.command == "clear":
        am.clear_triggered()
        print("[OK] Cleared all triggered alerts")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
