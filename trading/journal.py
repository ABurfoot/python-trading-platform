#!/usr/bin/env python3
"""
Trade Journal Module
=====================
Log trades with notes, emotions, lessons learned, and track improvement.

Features:
- Log every trade with detailed notes
- Track emotions and psychology
- Record entry/exit reasoning
- Tag trades for filtering
- Attach screenshots/charts (file paths)
- Track lessons learned
- Review and search past trades
- Performance by setup/strategy
- Export to CSV/JSON

Usage:
    from trading.journal import TradeJournal
    
    journal = TradeJournal()
    
    # Log a trade
    journal.log_trade(
        symbol="AAPL",
        side="long",
        entry_price=150.00,
        exit_price=165.00,
        quantity=100,
        entry_date="2024-01-15",
        exit_date="2024-02-01",
        setup="breakout",
        entry_reason="Breaking out of consolidation with volume",
        exit_reason="Hit profit target",
        emotions_entry="confident",
        emotions_exit="satisfied",
        lessons="Patience paid off, held through minor pullback",
        tags=["momentum", "earnings"],
        rating=5
    )
    
    # Review trades
    journal.print_journal()
    journal.print_trade("trade_id")
    
    # Analyze
    journal.analyze_by_setup()
    journal.analyze_by_emotion()
"""

import os
import json
import uuid
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum


class Emotion(Enum):
    """Trading emotions."""
    CONFIDENT = "confident"
    FEARFUL = "fearful"
    GREEDY = "greedy"
    ANXIOUS = "anxious"
    CALM = "calm"
    EXCITED = "excited"
    FRUSTRATED = "frustrated"
    HESITANT = "hesitant"
    IMPULSIVE = "impulsive"
    PATIENT = "patient"
    NEUTRAL = "neutral"
    FOMO = "fomo"
    REVENGE = "revenge"
    HOPEFUL = "hopeful"
    SATISFIED = "satisfied"
    REGRETFUL = "regretful"


class SetupType(Enum):
    """Common trade setups."""
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    PULLBACK = "pullback"
    REVERSAL = "reversal"
    TREND_FOLLOW = "trend_follow"
    RANGE_TRADE = "range_trade"
    GAP_FILL = "gap_fill"
    EARNINGS_PLAY = "earnings_play"
    NEWS_CATALYST = "news_catalyst"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    SCALP = "scalp"
    SWING = "swing"
    POSITION = "position"
    OTHER = "other"


@dataclass
class JournalEntry:
    """A single trade journal entry."""
    id: str
    
    # Trade details
    symbol: str
    side: str  # long or short
    entry_price: float
    exit_price: float
    quantity: float
    entry_date: str
    exit_date: str
    
    # Calculated fields
    pnl: float = 0
    pnl_pct: float = 0
    holding_days: int = 0
    
    # Journal fields
    setup: str = ""
    timeframe: str = ""  # 1m, 5m, 15m, 1h, 4h, daily, weekly
    entry_reason: str = ""
    exit_reason: str = ""
    
    # Psychology
    emotions_entry: str = ""
    emotions_during: str = ""
    emotions_exit: str = ""
    
    # Analysis
    what_went_well: str = ""
    what_went_wrong: str = ""
    lessons: str = ""
    would_take_again: bool = True
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)  # File paths
    rating: int = 3  # 1-5 stars
    notes: str = ""
    
    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        # Calculate P&L
        if self.side.lower() in ['long', 'buy']:
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
            self.pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - self.exit_price) * self.quantity
            self.pnl_pct = ((self.entry_price - self.exit_price) / self.entry_price) * 100
        
        # Calculate holding days
        try:
            entry = datetime.fromisoformat(self.entry_date[:10])
            exit = datetime.fromisoformat(self.exit_date[:10])
            self.holding_days = (exit - entry).days
        except Exception:
            pass
    
    @property
    def is_winner(self) -> bool:
        return self.pnl > 0
    
    @property
    def is_loser(self) -> bool:
        return self.pnl < 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'JournalEntry':
        # Handle tags field
        if 'tags' in data and isinstance(data['tags'], str):
            data['tags'] = data['tags'].split(',') if data['tags'] else []
        if 'screenshots' in data and isinstance(data['screenshots'], str):
            data['screenshots'] = data['screenshots'].split(',') if data['screenshots'] else []
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class JournalStats:
    """Statistics from journal entries."""
    total_entries: int = 0
    winning_entries: int = 0
    losing_entries: int = 0
    breakeven_entries: int = 0
    
    total_pnl: float = 0
    avg_pnl: float = 0
    avg_winner: float = 0
    avg_loser: float = 0
    
    win_rate: float = 0
    profit_factor: float = 0
    
    avg_holding_days: float = 0
    avg_rating: float = 0
    
    most_common_setup: str = ""
    most_profitable_setup: str = ""
    most_common_emotion: str = ""
    
    lessons_count: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


class TradeJournal:
    """
    Trade journal for logging and analyzing trades.
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialize trade journal.
        
        Args:
            storage_path: Path to save journal data
        """
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".trading_platform" / "trade_journal.json"
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Journal entries
        self.entries: Dict[str, JournalEntry] = {}
        
        # Load existing entries
        self._load()
    
    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    def log_trade(self,
                  symbol: str,
                  side: str,
                  entry_price: float,
                  exit_price: float,
                  quantity: float,
                  entry_date: str,
                  exit_date: str,
                  setup: str = "",
                  timeframe: str = "",
                  entry_reason: str = "",
                  exit_reason: str = "",
                  emotions_entry: str = "",
                  emotions_during: str = "",
                  emotions_exit: str = "",
                  what_went_well: str = "",
                  what_went_wrong: str = "",
                  lessons: str = "",
                  would_take_again: bool = True,
                  tags: List[str] = None,
                  screenshots: List[str] = None,
                  rating: int = 3,
                  notes: str = "") -> JournalEntry:
        """
        Log a trade to the journal.
        
        Args:
            symbol: Stock/crypto symbol
            side: 'long' or 'short'
            entry_price: Entry price
            exit_price: Exit price
            quantity: Number of shares/units
            entry_date: Entry date (YYYY-MM-DD)
            exit_date: Exit date (YYYY-MM-DD)
            setup: Trade setup type
            timeframe: Chart timeframe used
            entry_reason: Why you entered
            exit_reason: Why you exited
            emotions_entry: How you felt entering
            emotions_during: How you felt during the trade
            emotions_exit: How you felt exiting
            what_went_well: What worked
            what_went_wrong: What didn't work
            lessons: Key takeaways
            would_take_again: Would you take this trade again?
            tags: List of tags for filtering
            screenshots: List of screenshot file paths
            rating: Trade quality rating 1-5
            notes: Additional notes
        
        Returns:
            JournalEntry object
        """
        entry_id = str(uuid.uuid4())[:8]
        
        entry = JournalEntry(
            id=entry_id,
            symbol=symbol.upper(),
            side=side.lower(),
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            entry_date=entry_date,
            exit_date=exit_date,
            setup=setup.lower() if setup else "",
            timeframe=timeframe,
            entry_reason=entry_reason,
            exit_reason=exit_reason,
            emotions_entry=emotions_entry.lower() if emotions_entry else "",
            emotions_during=emotions_during.lower() if emotions_during else "",
            emotions_exit=emotions_exit.lower() if emotions_exit else "",
            what_went_well=what_went_well,
            what_went_wrong=what_went_wrong,
            lessons=lessons,
            would_take_again=would_take_again,
            tags=tags or [],
            screenshots=screenshots or [],
            rating=max(1, min(5, rating)),
            notes=notes,
        )
        
        self.entries[entry_id] = entry
        self._save()
        
        result_emoji = "[+]" if entry.is_winner else "[-]" if entry.is_loser else "[.]"
        print(f"{result_emoji} Trade logged: {symbol} | P&L: ${entry.pnl:+,.2f} ({entry.pnl_pct:+.2f}%)")
        
        return entry
    
    def update_trade(self, entry_id: str, **kwargs) -> Optional[JournalEntry]:
        """Update an existing journal entry."""
        if entry_id not in self.entries:
            print(f"[X] Entry not found: {entry_id}")
            return None
        
        entry = self.entries[entry_id]
        
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        entry.updated_at = datetime.now().isoformat()
        
        # Recalculate P&L if prices changed
        if 'entry_price' in kwargs or 'exit_price' in kwargs or 'quantity' in kwargs:
            if entry.side.lower() in ['long', 'buy']:
                entry.pnl = (entry.exit_price - entry.entry_price) * entry.quantity
                entry.pnl_pct = ((entry.exit_price - entry.entry_price) / entry.entry_price) * 100
            else:
                entry.pnl = (entry.entry_price - entry.exit_price) * entry.quantity
                entry.pnl_pct = ((entry.entry_price - entry.exit_price) / entry.entry_price) * 100
        
        self._save()
        print(f"[OK] Entry {entry_id} updated")
        
        return entry
    
    def delete_trade(self, entry_id: str) -> bool:
        """Delete a journal entry."""
        if entry_id not in self.entries:
            print(f"[X] Entry not found: {entry_id}")
            return False
        
        del self.entries[entry_id]
        self._save()
        print(f"[OK] Entry {entry_id} deleted")
        return True
    
    def get_trade(self, entry_id: str) -> Optional[JournalEntry]:
        """Get a specific journal entry."""
        return self.entries.get(entry_id)
    
    def get_all_trades(self) -> List[JournalEntry]:
        """Get all journal entries sorted by date."""
        return sorted(self.entries.values(), key=lambda e: e.exit_date, reverse=True)
    
    # =========================================================================
    # FILTERING & SEARCH
    # =========================================================================
    
    def filter_trades(self,
                      symbol: str = None,
                      setup: str = None,
                      side: str = None,
                      winners_only: bool = False,
                      losers_only: bool = False,
                      tags: List[str] = None,
                      min_pnl: float = None,
                      max_pnl: float = None,
                      start_date: str = None,
                      end_date: str = None,
                      min_rating: int = None,
                      emotion: str = None) -> List[JournalEntry]:
        """
        Filter journal entries by various criteria.
        """
        results = list(self.entries.values())
        
        if symbol:
            results = [e for e in results if e.symbol == symbol.upper()]
        
        if setup:
            results = [e for e in results if e.setup == setup.lower()]
        
        if side:
            results = [e for e in results if e.side == side.lower()]
        
        if winners_only:
            results = [e for e in results if e.is_winner]
        
        if losers_only:
            results = [e for e in results if e.is_loser]
        
        if tags:
            results = [e for e in results if any(t in e.tags for t in tags)]
        
        if min_pnl is not None:
            results = [e for e in results if e.pnl >= min_pnl]
        
        if max_pnl is not None:
            results = [e for e in results if e.pnl <= max_pnl]
        
        if start_date:
            results = [e for e in results if e.exit_date >= start_date]
        
        if end_date:
            results = [e for e in results if e.exit_date <= end_date]
        
        if min_rating:
            results = [e for e in results if e.rating >= min_rating]
        
        if emotion:
            emotion = emotion.lower()
            results = [e for e in results if 
                      emotion in e.emotions_entry.lower() or
                      emotion in e.emotions_during.lower() or
                      emotion in e.emotions_exit.lower()]
        
        return sorted(results, key=lambda e: e.exit_date, reverse=True)
    
    def search(self, query: str) -> List[JournalEntry]:
        """Search journal entries by text."""
        query = query.lower()
        results = []
        
        for entry in self.entries.values():
            searchable = " ".join([
                entry.symbol,
                entry.setup,
                entry.entry_reason,
                entry.exit_reason,
                entry.lessons,
                entry.notes,
                entry.what_went_well,
                entry.what_went_wrong,
                " ".join(entry.tags),
            ]).lower()
            
            if query in searchable:
                results.append(entry)
        
        return sorted(results, key=lambda e: e.exit_date, reverse=True)
    
    # =========================================================================
    # STATISTICS & ANALYSIS
    # =========================================================================
    
    def get_stats(self, entries: List[JournalEntry] = None) -> JournalStats:
        """Calculate statistics from journal entries."""
        if entries is None:
            entries = list(self.entries.values())
        
        stats = JournalStats()
        
        if not entries:
            return stats
        
        stats.total_entries = len(entries)
        
        winners = [e for e in entries if e.is_winner]
        losers = [e for e in entries if e.is_loser]
        
        stats.winning_entries = len(winners)
        stats.losing_entries = len(losers)
        stats.breakeven_entries = stats.total_entries - stats.winning_entries - stats.losing_entries
        
        # P&L stats
        stats.total_pnl = sum(e.pnl for e in entries)
        stats.avg_pnl = stats.total_pnl / stats.total_entries if entries else 0
        
        if winners:
            stats.avg_winner = sum(e.pnl for e in winners) / len(winners)
        if losers:
            stats.avg_loser = sum(e.pnl for e in losers) / len(losers)
        
        # Win rate and profit factor
        stats.win_rate = (len(winners) / len(entries)) * 100 if entries else 0
        
        total_wins = sum(e.pnl for e in winners) if winners else 0
        total_losses = abs(sum(e.pnl for e in losers)) if losers else 0
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Averages
        holding_days = [e.holding_days for e in entries if e.holding_days > 0]
        stats.avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0
        
        ratings = [e.rating for e in entries]
        stats.avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Most common setup
        setups = [e.setup for e in entries if e.setup]
        if setups:
            stats.most_common_setup = max(set(setups), key=setups.count)
        
        # Most profitable setup
        setup_pnl = {}
        for e in entries:
            if e.setup:
                setup_pnl[e.setup] = setup_pnl.get(e.setup, 0) + e.pnl
        if setup_pnl:
            stats.most_profitable_setup = max(setup_pnl, key=setup_pnl.get)
        
        # Most common emotion
        emotions = []
        for e in entries:
            if e.emotions_entry:
                emotions.append(e.emotions_entry)
            if e.emotions_exit:
                emotions.append(e.emotions_exit)
        if emotions:
            stats.most_common_emotion = max(set(emotions), key=emotions.count)
        
        # Lessons count
        stats.lessons_count = len([e for e in entries if e.lessons])
        
        return stats
    
    def analyze_by_setup(self) -> Dict[str, Dict]:
        """Analyze performance by setup type."""
        setups = {}
        
        for entry in self.entries.values():
            setup = entry.setup or "unknown"
            
            if setup not in setups:
                setups[setup] = {
                    "trades": 0,
                    "winners": 0,
                    "losers": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "win_rate": 0,
                }
            
            setups[setup]["trades"] += 1
            setups[setup]["total_pnl"] += entry.pnl
            
            if entry.is_winner:
                setups[setup]["winners"] += 1
            elif entry.is_loser:
                setups[setup]["losers"] += 1
        
        # Calculate averages and win rates
        for setup in setups:
            trades = setups[setup]["trades"]
            setups[setup]["avg_pnl"] = setups[setup]["total_pnl"] / trades if trades else 0
            setups[setup]["win_rate"] = (setups[setup]["winners"] / trades * 100) if trades else 0
        
        return setups
    
    def analyze_by_emotion(self) -> Dict[str, Dict]:
        """Analyze performance by entry emotion."""
        emotions = {}
        
        for entry in self.entries.values():
            emotion = entry.emotions_entry or "unknown"
            
            if emotion not in emotions:
                emotions[emotion] = {
                    "trades": 0,
                    "winners": 0,
                    "losers": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "win_rate": 0,
                }
            
            emotions[emotion]["trades"] += 1
            emotions[emotion]["total_pnl"] += entry.pnl
            
            if entry.is_winner:
                emotions[emotion]["winners"] += 1
            elif entry.is_loser:
                emotions[emotion]["losers"] += 1
        
        # Calculate averages and win rates
        for emotion in emotions:
            trades = emotions[emotion]["trades"]
            emotions[emotion]["avg_pnl"] = emotions[emotion]["total_pnl"] / trades if trades else 0
            emotions[emotion]["win_rate"] = (emotions[emotion]["winners"] / trades * 100) if trades else 0
        
        return emotions
    
    def analyze_by_symbol(self) -> Dict[str, Dict]:
        """Analyze performance by symbol."""
        symbols = {}
        
        for entry in self.entries.values():
            symbol = entry.symbol
            
            if symbol not in symbols:
                symbols[symbol] = {
                    "trades": 0,
                    "winners": 0,
                    "losers": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "win_rate": 0,
                }
            
            symbols[symbol]["trades"] += 1
            symbols[symbol]["total_pnl"] += entry.pnl
            
            if entry.is_winner:
                symbols[symbol]["winners"] += 1
            elif entry.is_loser:
                symbols[symbol]["losers"] += 1
        
        # Calculate averages and win rates
        for symbol in symbols:
            trades = symbols[symbol]["trades"]
            symbols[symbol]["avg_pnl"] = symbols[symbol]["total_pnl"] / trades if trades else 0
            symbols[symbol]["win_rate"] = (symbols[symbol]["winners"] / trades * 100) if trades else 0
        
        return symbols
    
    def analyze_by_day_of_week(self) -> Dict[str, Dict]:
        """Analyze performance by day of week."""
        days = {
            "Monday": {"trades": 0, "total_pnl": 0, "winners": 0},
            "Tuesday": {"trades": 0, "total_pnl": 0, "winners": 0},
            "Wednesday": {"trades": 0, "total_pnl": 0, "winners": 0},
            "Thursday": {"trades": 0, "total_pnl": 0, "winners": 0},
            "Friday": {"trades": 0, "total_pnl": 0, "winners": 0},
        }
        
        for entry in self.entries.values():
            try:
                exit_date = datetime.fromisoformat(entry.exit_date[:10])
                day_name = exit_date.strftime("%A")
                
                if day_name in days:
                    days[day_name]["trades"] += 1
                    days[day_name]["total_pnl"] += entry.pnl
                    if entry.is_winner:
                        days[day_name]["winners"] += 1
            except Exception:
                pass
        
        # Calculate win rates
        for day in days:
            trades = days[day]["trades"]
            days[day]["win_rate"] = (days[day]["winners"] / trades * 100) if trades else 0
            days[day]["avg_pnl"] = days[day]["total_pnl"] / trades if trades else 0
        
        return days
    
    def get_lessons(self, limit: int = 20) -> List[Tuple[str, str, str]]:
        """Get all recorded lessons."""
        lessons = []
        
        for entry in sorted(self.entries.values(), key=lambda e: e.exit_date, reverse=True):
            if entry.lessons:
                lessons.append((entry.exit_date, entry.symbol, entry.lessons))
        
        return lessons[:limit]
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_journal(self, limit: int = 20):
        """Print journal overview."""
        entries = self.get_all_trades()[:limit]
        
        print(f"\n{'='*80}")
        print("📓 TRADE JOURNAL")
        print(f"{'='*80}")
        
        if not entries:
            print("\n   No entries yet. Use journal.log_trade() to add trades.\n")
            return
        
        stats = self.get_stats()
        
        print(f"\n SUMMARY ({stats.total_entries} trades)")
        print("-"*50)
        print(f"   Win Rate: {stats.win_rate:.1f}% | Profit Factor: {stats.profit_factor:.2f}")
        print(f"   Total P&L: ${stats.total_pnl:+,.2f} | Avg P&L: ${stats.avg_pnl:+,.2f}")
        print(f"   Avg Rating: {'*' * int(stats.avg_rating)} ({stats.avg_rating:.1f}/5)")
        
        print(f"\n📝 RECENT ENTRIES")
        print("-"*80)
        print(f"   {'ID':<10} {'Date':<12} {'Symbol':<8} {'Side':<6} {'P&L':>12} {'Setup':<12} {'Rating':<6}")
        print(f"   {'-'*76}")
        
        for entry in entries:
            result = "[+]" if entry.is_winner else "[-]" if entry.is_loser else "[.]"
            rating = "*" * entry.rating
            pnl_str = f"${entry.pnl:+,.2f}"
            
            print(f"   {entry.id:<10} {entry.exit_date[:10]:<12} {result} {entry.symbol:<6} {entry.side:<6} {pnl_str:>12} {entry.setup:<12} {rating}")
        
        if len(self.entries) > limit:
            print(f"\n   ... and {len(self.entries) - limit} more entries")
        
        print(f"\n{'='*80}\n")
    
    def print_trade(self, entry_id: str):
        """Print detailed view of a single trade."""
        entry = self.entries.get(entry_id)
        
        if not entry:
            print(f"[X] Entry not found: {entry_id}")
            return
        
        result = "[+] WINNER" if entry.is_winner else "[-] LOSER" if entry.is_loser else "[.] BREAKEVEN"
        
        print(f"\n{'='*70}")
        print(f"📓 TRADE DETAIL: {entry.symbol} | {result}")
        print(f"{'='*70}")
        
        print(f"\n TRADE INFO")
        print("-"*50)
        print(f"   Symbol:        {entry.symbol}")
        print(f"   Side:          {entry.side.upper()}")
        print(f"   Entry:         ${entry.entry_price:,.2f} on {entry.entry_date}")
        print(f"   Exit:          ${entry.exit_price:,.2f} on {entry.exit_date}")
        print(f"   Quantity:      {entry.quantity}")
        print(f"   Holding:       {entry.holding_days} days")
        print(f"   P&L:           ${entry.pnl:+,.2f} ({entry.pnl_pct:+.2f}%)")
        
        print(f"\n SETUP & REASONING")
        print("-"*50)
        print(f"   Setup:         {entry.setup or 'Not specified'}")
        print(f"   Timeframe:     {entry.timeframe or 'Not specified'}")
        print(f"   Entry Reason:  {entry.entry_reason or 'Not specified'}")
        print(f"   Exit Reason:   {entry.exit_reason or 'Not specified'}")
        
        print(f"\n PSYCHOLOGY")
        print("-"*50)
        print(f"   Entry Emotion: {entry.emotions_entry or 'Not recorded'}")
        print(f"   During Trade:  {entry.emotions_during or 'Not recorded'}")
        print(f"   Exit Emotion:  {entry.emotions_exit or 'Not recorded'}")
        
        print(f"\n📝 REVIEW")
        print("-"*50)
        print(f"   What Went Well:  {entry.what_went_well or 'Not recorded'}")
        print(f"   What Went Wrong: {entry.what_went_wrong or 'Not recorded'}")
        print(f"   Lessons:         {entry.lessons or 'Not recorded'}")
        print(f"   Would Repeat:    {'Yes [OK]' if entry.would_take_again else 'No [X]'}")
        
        print(f"\n* RATING & TAGS")
        print("-"*50)
        print(f"   Rating:        {'*' * entry.rating} ({entry.rating}/5)")
        print(f"   Tags:          {', '.join(entry.tags) if entry.tags else 'None'}")
        
        if entry.notes:
            print(f"\n📌 NOTES")
            print("-"*50)
            print(f"   {entry.notes}")
        
        if entry.screenshots:
            print(f"\n📸 SCREENSHOTS")
            print("-"*50)
            for ss in entry.screenshots:
                print(f"   • {ss}")
        
        print(f"\n{'='*70}\n")
    
    def print_setup_analysis(self):
        """Print analysis by setup type."""
        setups = self.analyze_by_setup()
        
        print(f"\n{'='*70}")
        print(" PERFORMANCE BY SETUP")
        print(f"{'='*70}")
        
        if not setups:
            print("\n   No data available\n")
            return
        
        print(f"\n   {'Setup':<15} {'Trades':>8} {'Win Rate':>10} {'Total P&L':>14} {'Avg P&L':>12}")
        print(f"   {'-'*62}")
        
        for setup, data in sorted(setups.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
            print(f"   {setup:<15} {data['trades']:>8} {data['win_rate']:>9.1f}% ${data['total_pnl']:>+12,.2f} ${data['avg_pnl']:>+10,.2f}")
        
        print(f"\n{'='*70}\n")
    
    def print_emotion_analysis(self):
        """Print analysis by emotion."""
        emotions = self.analyze_by_emotion()
        
        print(f"\n{'='*70}")
        print(" PERFORMANCE BY EMOTION (Entry)")
        print(f"{'='*70}")
        
        if not emotions:
            print("\n   No data available\n")
            return
        
        print(f"\n   {'Emotion':<15} {'Trades':>8} {'Win Rate':>10} {'Total P&L':>14} {'Avg P&L':>12}")
        print(f"   {'-'*62}")
        
        for emotion, data in sorted(emotions.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
            print(f"   {emotion:<15} {data['trades']:>8} {data['win_rate']:>9.1f}% ${data['total_pnl']:>+12,.2f} ${data['avg_pnl']:>+10,.2f}")
        
        print(f"\n{'='*70}\n")
    
    def print_lessons(self, limit: int = 10):
        """Print recorded lessons."""
        lessons = self.get_lessons(limit)
        
        print(f"\n{'='*70}")
        print("📚 LESSONS LEARNED")
        print(f"{'='*70}")
        
        if not lessons:
            print("\n   No lessons recorded yet\n")
            return
        
        for date, symbol, lesson in lessons:
            print(f"\n   📅 {date[:10]} | {symbol}")
            print(f"   💡 {lesson}")
        
        print(f"\n{'='*70}\n")
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def export_csv(self, filepath: str = None) -> str:
        """Export journal to CSV."""
        if not filepath:
            filepath = str(self.storage_path.parent / "trade_journal.csv")
        
        entries = self.get_all_trades()
        
        if not entries:
            print("No entries to export")
            return ""
        
        fieldnames = [
            'id', 'symbol', 'side', 'entry_date', 'exit_date',
            'entry_price', 'exit_price', 'quantity', 'pnl', 'pnl_pct',
            'holding_days', 'setup', 'timeframe', 'entry_reason', 'exit_reason',
            'emotions_entry', 'emotions_during', 'emotions_exit',
            'what_went_well', 'what_went_wrong', 'lessons',
            'would_take_again', 'tags', 'rating', 'notes'
        ]
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for entry in entries:
                row = entry.to_dict()
                row['tags'] = ','.join(row['tags'])
                writer.writerow({k: row.get(k, '') for k in fieldnames})
        
        print(f"[OK] Exported {len(entries)} entries to {filepath}")
        return filepath
    
    def export_json(self, filepath: str = None) -> str:
        """Export journal to JSON."""
        if not filepath:
            filepath = str(self.storage_path.parent / "trade_journal_export.json")
        
        entries = [e.to_dict() for e in self.get_all_trades()]
        
        with open(filepath, 'w') as f:
            json.dump(entries, f, indent=2)
        
        print(f"[OK] Exported {len(entries)} entries to {filepath}")
        return filepath
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _save(self):
        """Save journal to disk."""
        data = {
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "saved_at": datetime.now().isoformat(),
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load journal from disk."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            self.entries = {
                k: JournalEntry.from_dict(v)
                for k, v in data.get("entries", {}).items()
            }
            
            print(f" Loaded {len(self.entries)} journal entries")
            
        except Exception as e:
            print(f"Warning: Could not load journal: {e}")
    
    def clear(self, confirm: bool = False):
        """Clear all journal entries."""
        if not confirm:
            print("[WARN]  This will delete all journal entries!")
            print("   Call clear(confirm=True) to confirm.")
            return
        
        self.entries = {}
        self._save()
        print("🗑️ Journal cleared")


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trade Journal")
    parser.add_argument("--list", "-l", action="store_true", help="List recent entries")
    parser.add_argument("--view", "-v", help="View specific entry by ID")
    parser.add_argument("--setups", action="store_true", help="Analyze by setup")
    parser.add_argument("--emotions", action="store_true", help="Analyze by emotion")
    parser.add_argument("--lessons", action="store_true", help="Show lessons learned")
    parser.add_argument("--export-csv", action="store_true", help="Export to CSV")
    parser.add_argument("--export-json", action="store_true", help="Export to JSON")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample data")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    journal = TradeJournal()
    
    if args.demo:
        print("\n🎮 TRADE JOURNAL DEMO")
        print("="*50)
        
        # Create a temporary journal for demo
        import tempfile
        demo_journal = TradeJournal(storage_path=tempfile.mktemp(suffix='.json'))
        
        # Add sample trades
        demo_journal.log_trade(
            symbol="AAPL", side="long",
            entry_price=150, exit_price=165, quantity=100,
            entry_date="2024-01-15", exit_date="2024-02-01",
            setup="breakout", timeframe="daily",
            entry_reason="Breaking out of 3-month consolidation with strong volume",
            exit_reason="Hit 10% profit target",
            emotions_entry="confident", emotions_exit="satisfied",
            what_went_well="Patience waiting for breakout confirmation",
            lessons="Volume confirmation is key for breakouts",
            tags=["momentum", "breakout"], rating=5
        )
        
        demo_journal.log_trade(
            symbol="MSFT", side="long",
            entry_price=400, exit_price=380, quantity=50,
            entry_date="2024-02-05", exit_date="2024-02-15",
            setup="pullback", timeframe="4h",
            entry_reason="Buying dip in uptrend",
            exit_reason="Stop loss hit",
            emotions_entry="fearful", emotions_exit="frustrated",
            what_went_wrong="Entered too early before support confirmation",
            lessons="Wait for support to hold before entering pullback trades",
            tags=["pullback"], rating=2
        )
        
        demo_journal.log_trade(
            symbol="NVDA", side="long",
            entry_price=800, exit_price=920, quantity=25,
            entry_date="2024-03-01", exit_date="2024-03-20",
            setup="trend_follow", timeframe="daily",
            entry_reason="Strong uptrend, AI momentum",
            exit_reason="Trailing stop hit after extended move",
            emotions_entry="excited", emotions_exit="satisfied",
            what_went_well="Held through volatility, let winner run",
            lessons="Trailing stops help capture big moves",
            tags=["momentum", "tech", "ai"], rating=5
        )
        
        demo_journal.log_trade(
            symbol="TSLA", side="long",
            entry_price=200, exit_price=185, quantity=60,
            entry_date="2024-03-10", exit_date="2024-03-18",
            setup="reversal", timeframe="1h",
            entry_reason="Thought it was bottoming",
            exit_reason="Cut loss as it kept falling",
            emotions_entry="hopeful", emotions_exit="regretful",
            what_went_wrong="Caught falling knife, no confirmation",
            lessons="Never try to catch falling knives without confirmation",
            tags=["reversal"], rating=1
        )
        
        print("\n")
        demo_journal.print_journal()
        demo_journal.print_setup_analysis()
        demo_journal.print_emotion_analysis()
        demo_journal.print_lessons()
        
        # Show single trade detail
        entries = demo_journal.get_all_trades()
        if entries:
            demo_journal.print_trade(entries[0].id)
    
    elif args.list:
        journal.print_journal()
    
    elif args.view:
        journal.print_trade(args.view)
    
    elif args.setups:
        journal.print_setup_analysis()
    
    elif args.emotions:
        journal.print_emotion_analysis()
    
    elif args.lessons:
        journal.print_lessons()
    
    elif args.export_csv:
        journal.export_csv()
    
    elif args.export_json:
        journal.export_json()
    
    elif args.interactive:
        print(f"\n{'='*60}")
        print("📓 TRADE JOURNAL - Interactive Mode")
        print(f"{'='*60}")
        print("\nCommands:")
        print("  log                    - Log new trade (guided)")
        print("  list                   - Show recent entries")
        print("  view <id>              - View entry details")
        print("  setups                 - Analyze by setup")
        print("  emotions               - Analyze by emotion")
        print("  lessons                - Show lessons learned")
        print("  search <query>         - Search entries")
        print("  export                 - Export to CSV")
        print("  quit                   - Exit")
        print()
        
        while True:
            try:
                cmd = input("📓 > ").strip().split()
                
                if not cmd:
                    continue
                
                if cmd[0] in ["quit", "q", "exit"]:
                    break
                
                elif cmd[0] == "log":
                    # Guided trade logging
                    print("\n📝 Log New Trade")
                    print("-"*30)
                    
                    symbol = input("  Symbol: ").strip().upper()
                    side = input("  Side (long/short): ").strip() or "long"
                    entry_price = float(input("  Entry Price: $"))
                    exit_price = float(input("  Exit Price: $"))
                    quantity = float(input("  Quantity: "))
                    entry_date = input("  Entry Date (YYYY-MM-DD): ").strip()
                    exit_date = input("  Exit Date (YYYY-MM-DD): ").strip()
                    
                    setup = input("  Setup (breakout/pullback/reversal/etc): ").strip()
                    entry_reason = input("  Why did you enter? ").strip()
                    exit_reason = input("  Why did you exit? ").strip()
                    emotions_entry = input("  Emotion at entry: ").strip()
                    emotions_exit = input("  Emotion at exit: ").strip()
                    lessons = input("  Lessons learned: ").strip()
                    rating = int(input("  Rating (1-5): ") or "3")
                    
                    journal.log_trade(
                        symbol=symbol, side=side,
                        entry_price=entry_price, exit_price=exit_price,
                        quantity=quantity,
                        entry_date=entry_date, exit_date=exit_date,
                        setup=setup,
                        entry_reason=entry_reason, exit_reason=exit_reason,
                        emotions_entry=emotions_entry, emotions_exit=emotions_exit,
                        lessons=lessons, rating=rating
                    )
                
                elif cmd[0] == "list":
                    journal.print_journal()
                
                elif cmd[0] == "view" and len(cmd) > 1:
                    journal.print_trade(cmd[1])
                
                elif cmd[0] == "setups":
                    journal.print_setup_analysis()
                
                elif cmd[0] == "emotions":
                    journal.print_emotion_analysis()
                
                elif cmd[0] == "lessons":
                    journal.print_lessons()
                
                elif cmd[0] == "search" and len(cmd) > 1:
                    query = " ".join(cmd[1:])
                    results = journal.search(query)
                    print(f"\nFound {len(results)} results for '{query}':")
                    for entry in results[:10]:
                        result = "[+]" if entry.is_winner else "[-]"
                        print(f"  {result} {entry.id} | {entry.symbol} | ${entry.pnl:+,.2f}")
                
                elif cmd[0] == "export":
                    journal.export_csv()
                
                else:
                    print("Unknown command")
            
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("\nGoodbye! 👋")
    
    else:
        journal.print_journal()


if __name__ == "__main__":
    main()
