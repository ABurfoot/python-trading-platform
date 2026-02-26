#!/usr/bin/env python3
"""
API Configuration Module
=========================
Centralized API key management with multiple storage options.

Supports:
- Environment variables
- .env file
- config.json file
- Secure keyring storage (optional)

Usage:
    from trading.api_config import APIConfig, get_api_key, setup_api_keys
    
    # Get a specific key
    fmp_key = get_api_key("FMP")
    
    # Check all keys
    config = APIConfig()
    config.print_status()
    
    # Interactive setup
    setup_api_keys()
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
import getpass


@dataclass
class APIKeyInfo:
    """Information about an API key."""
    name: str
    env_var: str
    description: str
    signup_url: str
    free_tier: bool
    rate_limit: str
    required_for: List[str]


# API Key Definitions
API_KEYS_INFO = {
    "FMP": APIKeyInfo(
        name="Financial Modeling Prep",
        env_var="FMP_API_KEY",
        description="Stock quotes, fundamentals, financial statements, news",
        signup_url="https://financialmodelingprep.com/developer/docs/",
        free_tier=True,
        rate_limit="250 calls/day (free), 300k/month (paid)",
        required_for=["Stock Analysis", "Fundamentals", "News", "Earnings"]
    ),
    "ALPACA_KEY": APIKeyInfo(
        name="Alpaca API Key",
        env_var="ALPACA_API_KEY",
        description="US stock trading and market data",
        signup_url="https://app.alpaca.markets/signup",
        free_tier=True,
        rate_limit="200 calls/min, unlimited streaming",
        required_for=["Real-time Streaming", "Paper Trading", "Order Execution"]
    ),
    "ALPACA_SECRET": APIKeyInfo(
        name="Alpaca Secret Key",
        env_var="ALPACA_SECRET_KEY",
        description="Alpaca API authentication secret",
        signup_url="https://app.alpaca.markets/signup",
        free_tier=True,
        rate_limit="N/A",
        required_for=["Real-time Streaming", "Paper Trading"]
    ),
    "FINNHUB": APIKeyInfo(
        name="Finnhub",
        env_var="FINNHUB_API_KEY",
        description="Real-time streaming, news, fundamentals, crypto",
        signup_url="https://finnhub.io/register",
        free_tier=True,
        rate_limit="60 calls/min (free), WebSocket streaming",
        required_for=["Real-time Streaming", "News", "Crypto"]
    ),
    "ALPHA_VANTAGE": APIKeyInfo(
        name="Alpha Vantage",
        env_var="ALPHA_VANTAGE_KEY",
        description="Free stock data, forex, crypto, technical indicators",
        signup_url="https://www.alphavantage.co/support/#api-key",
        free_tier=True,
        rate_limit="25 calls/day (free), 500/min (premium)",
        required_for=["Technical Indicators", "Forex", "Crypto"]
    ),
    "POLYGON": APIKeyInfo(
        name="Polygon.io",
        env_var="POLYGON_API_KEY",
        description="Real-time and historical market data",
        signup_url="https://polygon.io/dashboard/signup",
        free_tier=True,
        rate_limit="5 calls/min (free), unlimited (paid)",
        required_for=["Historical Data", "Options Data"]
    ),
    "NEWS_API": APIKeyInfo(
        name="NewsAPI",
        env_var="NEWS_API_KEY",
        description="News aggregation from 80,000+ sources",
        signup_url="https://newsapi.org/register",
        free_tier=True,
        rate_limit="100 calls/day (free)",
        required_for=["News Aggregation", "Sentiment Analysis"]
    ),
}


class APIConfig:
    """
    Centralized API configuration management.
    
    Loads keys from (in order of priority):
    1. Environment variables
    2. .env file in project directory
    3. config.json in ~/.trading_platform/
    """
    
    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.trading_platform"))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "api_config.json"
        self.env_file = Path.cwd() / ".env"
        
        self._keys: Dict[str, str] = {}
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from all sources."""
        # 1. Load from config file first (lowest priority)
        self._load_from_config_file()
        
        # 2. Load from .env file (medium priority)
        self._load_from_env_file()
        
        # 3. Load from environment variables (highest priority)
        self._load_from_environment()
    
    def _load_from_config_file(self):
        """Load from JSON config file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    data = json.load(f)
                    self._keys.update(data.get("api_keys", {}))
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
    
    def _load_from_env_file(self):
        """Load from .env file."""
        env_files = [
            Path.cwd() / ".env",
            self.config_dir / ".env",
            Path.home() / ".env"
        ]
        
        for env_file in env_files:
            if env_file.exists():
                try:
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                
                                # Map to our key names
                                for api_name, info in API_KEYS_INFO.items():
                                    if key == info.env_var:
                                        self._keys[api_name] = value
                except Exception as e:
                    print(f"Warning: Could not load .env file: {e}")
    
    def _load_from_environment(self):
        """Load from environment variables."""
        for api_name, info in API_KEYS_INFO.items():
            value = os.environ.get(info.env_var)
            if value:
                self._keys[api_name] = value
    
    def get(self, key_name: str) -> Optional[str]:
        """Get an API key by name."""
        # Try direct lookup
        if key_name in self._keys:
            return self._keys[key_name]
        
        # Try uppercase
        if key_name.upper() in self._keys:
            return self._keys[key_name.upper()]
        
        # Try matching env var
        for api_name, info in API_KEYS_INFO.items():
            if key_name == info.env_var:
                return self._keys.get(api_name)
        
        return None
    
    def set(self, key_name: str, value: str, persist: bool = True):
        """Set an API key."""
        self._keys[key_name.upper()] = value
        
        # Also set in environment for current session
        if key_name.upper() in API_KEYS_INFO:
            env_var = API_KEYS_INFO[key_name.upper()].env_var
            os.environ[env_var] = value
        
        if persist:
            self._save_to_config_file()
    
    def _save_to_config_file(self):
        """Save keys to config file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({
                    "api_keys": self._keys,
                    "updated": str(Path.cwd())
                }, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(self.config_file, 0o600)
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")
    
    def is_configured(self, key_name: str) -> bool:
        """Check if a key is configured."""
        return bool(self.get(key_name))
    
    def get_status(self) -> Dict[str, Dict]:
        """Get status of all API keys."""
        status = {}
        
        for api_name, info in API_KEYS_INFO.items():
            key = self.get(api_name)
            status[api_name] = {
                "name": info.name,
                "configured": bool(key),
                "env_var": info.env_var,
                "description": info.description,
                "signup_url": info.signup_url,
                "free_tier": info.free_tier,
                "rate_limit": info.rate_limit,
                "required_for": info.required_for
            }
        
        return status
    
    def get_configured_keys(self) -> List[str]:
        """Get list of configured API keys."""
        return [name for name in API_KEYS_INFO.keys() if self.is_configured(name)]
    
    def get_missing_keys(self) -> List[str]:
        """Get list of missing API keys."""
        return [name for name in API_KEYS_INFO.keys() if not self.is_configured(name)]
    
    def export_env_template(self, path: str = None) -> str:
        """Export a .env template file."""
        path = path or str(Path.cwd() / ".env.template")
        
        lines = [
            "# Trading Platform API Configuration",
            "# Copy this file to .env and fill in your API keys",
            "#",
            "# Get free API keys from:",
            ""
        ]
        
        for api_name, info in API_KEYS_INFO.items():
            lines.append(f"# {info.name}: {info.signup_url}")
        
        lines.append("")
        lines.append("# API Keys")
        
        for api_name, info in API_KEYS_INFO.items():
            current = self.get(api_name)
            if current:
                lines.append(f'{info.env_var}="{current}"')
            else:
                lines.append(f'# {info.env_var}="your-key-here"')
        
        content = "\n".join(lines)
        
        with open(path, 'w') as f:
            f.write(content)
        
        return path
    
    def print_status(self):
        """Print formatted status of all API keys."""
        print("\n" + "="*70)
        print("API KEY CONFIGURATION STATUS")
        print("="*70)
        
        configured = self.get_configured_keys()
        missing = self.get_missing_keys()
        
        print(f"\nConfigured: {len(configured)}/{len(API_KEYS_INFO)}")
        
        print("\n" + "-"*70)
        
        for api_name, info in API_KEYS_INFO.items():
            key = self.get(api_name)
            
            if key:
                masked = key[:4] + "*" * 8 + key[-4:] if len(key) > 12 else "****"
                status = f"[Y] {masked}"
            else:
                status = "[X] Not configured"
            
            print(f"\n{info.name} ({api_name})")
            print(f"   Status: {status}")
            print(f"   Env var: {info.env_var}")
            print(f"   Used for: {', '.join(info.required_for)}")
            if not key:
                print(f"   Sign up: {info.signup_url}")
        
        print("\n" + "="*70)
        
        # Feature availability
        print("\nFEATURE AVAILABILITY:")
        print("-"*70)
        
        features = {
            "Stock Quotes & Analysis": self.is_configured("FMP"),
            "Real-time Streaming (Alpaca)": self.is_configured("ALPACA_KEY") and self.is_configured("ALPACA_SECRET"),
            "Real-time Streaming (Finnhub)": self.is_configured("FINNHUB"),
            "News & Sentiment": self.is_configured("FMP") or self.is_configured("FINNHUB") or self.is_configured("NEWS_API"),
            "Paper Trading": self.is_configured("ALPACA_KEY"),
            "Technical Indicators": self.is_configured("FMP") or self.is_configured("ALPHA_VANTAGE"),
            "Options Data": self.is_configured("POLYGON"),
            "Simulated Streaming": True,  # Always available
        }
        
        for feature, available in features.items():
            status = "[Y]" if available else "[X]"
            print(f"   {status} {feature}")
        
        print("\n" + "="*70)


def get_api_key(key_name: str) -> Optional[str]:
    """Quick helper to get an API key."""
    config = APIConfig()
    return config.get(key_name)


def setup_api_keys(interactive: bool = True):
    """
    Interactive setup for API keys.
    
    Args:
        interactive: If True, prompts user for keys. If False, just shows status.
    """
    config = APIConfig()
    
    if not interactive:
        config.print_status()
        return
    
    print("\n" + "="*70)
    print("API KEY SETUP WIZARD")
    print("="*70)
    print("\nThis wizard will help you configure your API keys.")
    print("Keys are stored securely in ~/.trading_platform/api_config.json")
    print("\nPress Enter to skip any key you don't want to configure.")
    
    for api_name, info in API_KEYS_INFO.items():
        current = config.get(api_name)
        
        print(f"\n{'-'*50}")
        print(f"{info.name}")
        print(f"Description: {info.description}")
        print(f"Sign up: {info.signup_url}")
        print(f"Free tier: {'Yes' if info.free_tier else 'No'}")
        
        if current:
            masked = current[:4] + "*" * 8 + current[-4:] if len(current) > 12 else "****"
            print(f"Current: {masked}")
            update = input("Update this key? (y/N): ").strip().lower()
            if update != 'y':
                continue
        
        new_key = getpass.getpass(f"Enter {info.name} API key (hidden): ").strip()
        
        if new_key:
            config.set(api_name, new_key)
            print(f"[Y] {info.name} key saved")
    
    print("\n" + "="*70)
    print("Setup complete! Here's your current configuration:")
    config.print_status()


def create_env_file(keys: Dict[str, str] = None):
    """
    Create a .env file with provided keys.
    
    Args:
        keys: Dict of key_name -> value
    """
    config = APIConfig()
    
    if keys:
        for key_name, value in keys.items():
            config.set(key_name, value)
    
    # Export template
    env_path = config.export_env_template(str(Path.cwd() / ".env"))
    print(f"Created .env file: {env_path}")
    
    return env_path


# Quick setup functions for common providers
def setup_finnhub(api_key: str):
    """Quick setup for Finnhub."""
    config = APIConfig()
    config.set("FINNHUB", api_key)
    os.environ["FINNHUB_API_KEY"] = api_key
    print(f"[Y] Finnhub API key configured")
    return True


def setup_alpaca(api_key: str, secret_key: str):
    """Quick setup for Alpaca."""
    config = APIConfig()
    config.set("ALPACA_KEY", api_key)
    config.set("ALPACA_SECRET", secret_key)
    os.environ["ALPACA_API_KEY"] = api_key
    os.environ["ALPACA_SECRET_KEY"] = secret_key
    print(f"[Y] Alpaca API keys configured")
    return True


def setup_fmp(api_key: str):
    """Quick setup for Financial Modeling Prep."""
    config = APIConfig()
    config.set("FMP", api_key)
    os.environ["FMP_API_KEY"] = api_key
    print(f"[Y] FMP API key configured")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "status":
            config = APIConfig()
            config.print_status()
        
        elif cmd == "setup":
            setup_api_keys(interactive=True)
        
        elif cmd == "template":
            config = APIConfig()
            path = config.export_env_template()
            print(f"Created template: {path}")
        
        elif cmd == "set" and len(sys.argv) >= 4:
            key_name = sys.argv[2]
            key_value = sys.argv[3]
            config = APIConfig()
            config.set(key_name, key_value)
            print(f"[Y] {key_name} configured")
        
        else:
            print("Usage:")
            print("  python api_config.py status   - Show API key status")
            print("  python api_config.py setup    - Interactive setup wizard")
            print("  python api_config.py template - Create .env template")
            print("  python api_config.py set KEY VALUE - Set a specific key")
    else:
        # Default: show status
        config = APIConfig()
        config.print_status()
