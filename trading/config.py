#!/usr/bin/env python3
"""
Configuration Manager
======================
Centralized configuration for the trading platform.

Supports:
- Environment variables
- Config file (~/.trading_platform/config.json)
- Command line overrides

Usage:
    from trading.config import config
    
    api_key = config.get("FMP_API_KEY")
    is_paper = config.get("ALPACA_PAPER", True)
"""

import os
import json
from pathlib import Path
from typing import Any, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class TradingConfig:
    """Trading platform configuration."""
    
    # Paths
    data_dir: str = field(default_factory=lambda: os.path.expanduser("~/.trading_platform"))
    exports_dir: str = field(default_factory=lambda: os.path.expanduser("~/Documents/trading_reports"))
    
    # API Keys (loaded from env)
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    alphavantage_api_key: str = ""
    
    # Dashboard
    dashboard_port: int = 8080
    dashboard_host: str = "localhost"
    
    # Analysis defaults
    default_history_days: int = 100
    confidence_threshold: float = 60.0
    
    # Portfolio defaults
    default_starting_cash: float = 100000.0
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Feature flags
    enable_live_trading: bool = False
    enable_notifications: bool = True
    
    def __post_init__(self):
        """Load configuration from sources."""
        self._load_from_env()
        self._load_from_file()
        self._ensure_directories()
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        env_mapping = {
            "ALPACA_API_KEY": "alpaca_api_key",
            "ALPACA_SECRET_KEY": "alpaca_secret_key",
            "ALPACA_PAPER": "alpaca_paper",
            "FMP_API_KEY": "fmp_api_key",
            "FINNHUB_API_KEY": "finnhub_api_key",
            "ALPHAVANTAGE_API_KEY": "alphavantage_api_key",
            "TRADING_DATA_DIR": "data_dir",
            "TRADING_EXPORTS_DIR": "exports_dir",
            "TRADING_DASHBOARD_PORT": "dashboard_port",
            "TRADING_LOG_LEVEL": "log_level",
            "TRADING_ENABLE_LIVE": "enable_live_trading",
        }
        
        for env_var, attr in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type conversion
                current = getattr(self, attr)
                if isinstance(current, bool):
                    setattr(self, attr, value.lower() in ("true", "1", "yes"))
                elif isinstance(current, int):
                    setattr(self, attr, int(value))
                elif isinstance(current, float):
                    setattr(self, attr, float(value))
                else:
                    setattr(self, attr, value)
    
    def _load_from_file(self):
        """Load configuration from config file."""
        config_path = Path(self.data_dir) / "config.json"
        
        if config_path.exists():
            try:
                with open(config_path) as f:
                    file_config = json.load(f)
                
                for key, value in file_config.items():
                    if hasattr(self, key):
                        # Don't override env vars with file config for sensitive items
                        if key in ("alpaca_api_key", "alpaca_secret_key", "fmp_api_key"):
                            if not getattr(self, key):  # Only if not set
                                setattr(self, key, value)
                        else:
                            setattr(self, key, value)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.exports_dir).mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        if hasattr(self, key):
            setattr(self, key, value)
    
    def save(self):
        """Save configuration to file."""
        config_path = Path(self.data_dir) / "config.json"
        
        # Don't save sensitive keys to file
        sensitive = {"alpaca_api_key", "alpaca_secret_key", "fmp_api_key", 
                    "finnhub_api_key", "alphavantage_api_key"}
        
        data = {k: v for k, v in self.__dict__.items() 
                if not k.startswith("_") and k not in sensitive}
        
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (hides sensitive values)."""
        sensitive = {"alpaca_api_key", "alpaca_secret_key", "fmp_api_key",
                    "finnhub_api_key", "alphavantage_api_key"}
        
        return {
            k: ("***" if k in sensitive and v else v)
            for k, v in self.__dict__.items()
            if not k.startswith("_")
        }
    
    def print_status(self):
        """Print configuration status."""
        print("\n" + "="*60)
        print("TRADING PLATFORM CONFIGURATION")
        print("="*60)
        
        # API Keys status
        print("\n📡 API Keys:")
        print(f"   Alpaca:      {'[OK] Configured' if self.alpaca_api_key else '[X] Not set'}")
        print(f"   FMP:         {'[OK] Configured' if self.fmp_api_key else '[X] Not set'}")
        print(f"   Finnhub:     {'[OK] Configured' if self.finnhub_api_key else '[X] Not set'}")
        print(f"   AlphaVantage:{'[OK] Configured' if self.alphavantage_api_key else '[X] Not set'}")
        
        # Paths
        print("\n📁 Paths:")
        print(f"   Data:    {self.data_dir}")
        print(f"   Exports: {self.exports_dir}")
        
        # Features
        print("\n⚙️  Features:")
        print(f"   Live Trading:  {'Enabled [WARN]' if self.enable_live_trading else 'Disabled'}")
        print(f"   Notifications: {'Enabled' if self.enable_notifications else 'Disabled'}")
        print(f"   Paper Trading: {'Yes' if self.alpaca_paper else 'No (REAL MONEY!)'}")
        
        print("\n" + "="*60)


# Global config instance
config = TradingConfig()


def get_config() -> TradingConfig:
    """Get the global configuration instance."""
    return config


def reload_config():
    """Reload configuration from sources."""
    global config
    config = TradingConfig()
    return config


if __name__ == "__main__":
    # Print current configuration
    config.print_status()
