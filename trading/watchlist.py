#!/usr/bin/env python3
"""
Watchlist Manager
=================
Persistent watchlist storage for tracking favorite stocks.

Features:
- Multiple named watchlists
- Add/remove stocks
- Quick analysis of entire watchlist
- Persistent storage (JSON file)

Usage:
    from trading.watchlist import WatchlistManager
    
    wl = WatchlistManager()
    wl.add("default", "AAPL")
    wl.add("tech", ["MSFT", "GOOGL", "NVDA"])
    stocks = wl.get("default")
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class WatchlistManager:
    """Manage multiple stock watchlists with persistence."""
    
    def __init__(self, storage_path: str = None):
        """Initialize watchlist manager."""
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to user's home directory
            self.storage_path = Path.home() / ".trading_platform" / "watchlists.json"
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.watchlists: Dict[str, Dict] = self._load()
    
    def _load(self) -> Dict:
        """Load watchlists from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"default": {"name": "Default", "stocks": [], "created": datetime.now().isoformat()}}
    
    def _save(self):
        """Save watchlists to disk."""
        with open(self.storage_path, 'w') as f:
            json.dump(self.watchlists, f, indent=2)
    
    def create(self, list_name: str, display_name: str = None) -> bool:
        """Create a new watchlist."""
        key = list_name.lower().replace(" ", "_")
        if key in self.watchlists:
            return False
        
        self.watchlists[key] = {
            "name": display_name or list_name,
            "stocks": [],
            "created": datetime.now().isoformat()
        }
        self._save()
        return True
    
    def delete(self, list_name: str) -> bool:
        """Delete a watchlist."""
        key = list_name.lower().replace(" ", "_")
        if key in self.watchlists and key != "default":
            del self.watchlists[key]
            self._save()
            return True
        return False
    
    def add(self, list_name: str, symbols: str | List[str]) -> List[str]:
        """Add stock(s) to a watchlist. Returns list of added symbols."""
        key = list_name.lower().replace(" ", "_")
        
        if key not in self.watchlists:
            self.create(key)
        
        if isinstance(symbols, str):
            symbols = [symbols]
        
        added = []
        for symbol in symbols:
            # Clean and normalize symbol
            symbol = symbol.upper().strip().replace(" ", "")
            if symbol and symbol not in self.watchlists[key]["stocks"]:
                self.watchlists[key]["stocks"].append(symbol)
                added.append(symbol)
        
        if added:
            self._save()
        return added
    
    def remove(self, list_name: str, symbols: str | List[str]) -> List[str]:
        """Remove stock(s) from a watchlist. Returns list of removed symbols."""
        key = list_name.lower().replace(" ", "_")
        
        if key not in self.watchlists:
            return []
        
        if isinstance(symbols, str):
            symbols = [symbols]
        
        removed = []
        for symbol in symbols:
            symbol = symbol.upper().strip()
            if symbol in self.watchlists[key]["stocks"]:
                self.watchlists[key]["stocks"].remove(symbol)
                removed.append(symbol)
        
        if removed:
            self._save()
        return removed
    
    def get(self, list_name: str = "default") -> List[str]:
        """Get stocks in a watchlist."""
        key = list_name.lower().replace(" ", "_")
        if key in self.watchlists:
            return self.watchlists[key]["stocks"].copy()
        return []
    
    def get_all(self) -> Dict[str, List[str]]:
        """Get all watchlists."""
        return {k: v["stocks"].copy() for k, v in self.watchlists.items()}
    
    def list_watchlists(self) -> List[Dict]:
        """List all watchlist names and counts."""
        return [
            {
                "key": k,
                "name": v["name"],
                "count": len(v["stocks"]),
                "created": v.get("created", "")
            }
            for k, v in self.watchlists.items()
        ]
    
    def rename(self, list_name: str, new_name: str) -> bool:
        """Rename a watchlist."""
        key = list_name.lower().replace(" ", "_")
        if key in self.watchlists:
            self.watchlists[key]["name"] = new_name
            self._save()
            return True
        return False
    
    def move(self, symbol: str, from_list: str, to_list: str) -> bool:
        """Move a stock from one watchlist to another."""
        removed = self.remove(from_list, symbol)
        if removed:
            self.add(to_list, symbol)
            return True
        return False
    
    def search(self, symbol: str) -> List[str]:
        """Find which watchlists contain a symbol."""
        symbol = symbol.upper().strip()
        return [k for k, v in self.watchlists.items() if symbol in v["stocks"]]
    
    def export(self, list_name: str = None) -> Dict:
        """Export watchlist(s) as dict."""
        if list_name:
            key = list_name.lower().replace(" ", "_")
            if key in self.watchlists:
                return {key: self.watchlists[key]}
            return {}
        return self.watchlists.copy()
    
    def import_list(self, data: Dict) -> int:
        """Import watchlists from dict. Returns count of imported lists."""
        count = 0
        for key, value in data.items():
            if isinstance(value, dict) and "stocks" in value:
                self.watchlists[key] = value
                count += 1
            elif isinstance(value, list):
                self.watchlists[key] = {
                    "name": key.title(),
                    "stocks": value,
                    "created": datetime.now().isoformat()
                }
                count += 1
        if count:
            self._save()
        return count


# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Watchlist Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List watchlists")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show watchlist contents")
    show_parser.add_argument("name", nargs="?", default="default", help="Watchlist name")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add stocks to watchlist")
    add_parser.add_argument("symbols", nargs="+", help="Stock symbols")
    add_parser.add_argument("-l", "--list", default="default", help="Watchlist name")
    
    # Remove command
    rm_parser = subparsers.add_parser("remove", help="Remove stocks from watchlist")
    rm_parser.add_argument("symbols", nargs="+", help="Stock symbols")
    rm_parser.add_argument("-l", "--list", default="default", help="Watchlist name")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create new watchlist")
    create_parser.add_argument("name", help="Watchlist name")
    
    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete watchlist")
    del_parser.add_argument("name", help="Watchlist name")
    
    args = parser.parse_args()
    wl = WatchlistManager()
    
    if args.command == "list":
        lists = wl.list_watchlists()
        print("\n Watchlists:")
        for l in lists:
            print(f"  • {l['name']} ({l['key']}): {l['count']} stocks")
        print()
    
    elif args.command == "show":
        stocks = wl.get(args.name)
        info = wl.watchlists.get(args.name.lower(), {})
        print(f"\n {info.get('name', args.name)} ({len(stocks)} stocks):")
        if stocks:
            for s in stocks:
                print(f"  • {s}")
        else:
            print("  (empty)")
        print()
    
    elif args.command == "add":
        added = wl.add(args.list, args.symbols)
        if added:
            print(f"[OK] Added to {args.list}: {', '.join(added)}")
        else:
            print("No new stocks added (already in list)")
    
    elif args.command == "remove":
        removed = wl.remove(args.list, args.symbols)
        if removed:
            print(f"[OK] Removed from {args.list}: {', '.join(removed)}")
        else:
            print("No stocks removed (not in list)")
    
    elif args.command == "create":
        if wl.create(args.name):
            print(f"[OK] Created watchlist: {args.name}")
        else:
            print(f"Watchlist already exists: {args.name}")
    
    elif args.command == "delete":
        if wl.delete(args.name):
            print(f"[OK] Deleted watchlist: {args.name}")
        else:
            print(f"Cannot delete: {args.name}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
