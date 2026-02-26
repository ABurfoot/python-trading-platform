#!/usr/bin/env python3
"""
Trade Journal Module
=====================
Log trades with notes, emotions, lessons learned, and detailed analysis.

Features:
- Record trades with entry/exit details
- Track emotions and mental state
- Log reasons for entry/exit
- Capture lessons learned
- Tag trades for categorization
- Add screenshots/chart references
- Search and filter journal entries
- Generate insights and patterns
- Export to various formats

Usage:
    from trading.trade_journal import TradeJournal
    
    journal = TradeJournal()
    
    # Add a trade entry
    entry = journal.add_entry(
        symbol="AAPL",
        side="long",
        entry_date="2024-01-15",
        entry_price=150.00,
        exit_date="2024-02-01",
        exit_price=165.00,
        quantity=100,
        setup="breakout",
        entry_reason="Breaking above resistance with volume",
        exit_reason="Hit profit target",
        emotions_entry="Confident, patient",
        emotions_exit="Satisfied",
        lessons="Patience paid off, waited for confirmation",
        tags=["breakout", "tech", "winner"]
    )
    
    # View journal
    journal.print_journal()
    journal.print_insights()
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import statistics


class Emotion(Enum):
    """Common trading emotions."""
    CONFIDENT = "confident"
    FEARFUL = "fearful"
    GREEDY = "greedy"
    ANXIOUS = "anxious"
    PATIENT = "patient"
    IMPULSIVE = "impulsive"
    FRUSTRATED = "frustrated"
    CALM = "calm"
    EXCITED = "excited"
    UNCERTAIN = "uncertain"
    DISCIPLINED = "disciplined"
    REVENGE = "revenge"
    FOMO = "fomo"
    HOPEFUL = "hopeful"
    REGRETFUL = "regretful"


class Setup(Enum):
    """Common trade setups."""
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    PULLBACK = "pullback"
    REVERSAL = "reversal"
    TREND_FOLLOW = "trend_follow"
    MEAN_REVERSION = "mean_reversion"
    GAP_FILL = "gap_fill"
    EARNINGS = "earnings"
    NEWS = "news"
    MOMENTUM = "momentum"
    VALUE = "value"
    SWING = "swing"
    SCALP = "scalp"
    POSITION = "position"
    OTHER = "other"


class Outcome(Enum):
    """Trade outcomes."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PARTIAL = "partial"


@dataclass
class JournalEntry:
    """A single trade journal entry."""
    id: str
    
    # Trade details
    symbol: str
    side: str  # long or short
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0
    quantity: float = 0
    position_size: float = 0  # Dollar amount
    
    # P&L
    pnl: float = 0
    pnl_pct: float = 0
    outcome: str = ""  # win, loss, breakeven
    
    # Setup and strategy
    setup: str = ""  # breakout, pullback, etc.
    timeframe: str = ""  # 1m, 5m, 1h, daily, etc.
    strategy: str = ""  # Name of strategy used
    
    # Reasons
    entry_reason: str = ""
    exit_reason: str = ""
    
    # Technical analysis
    support_level: float = 0
    resistance_level: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    risk_reward: float = 0
    
    # Mental state
    emotions_entry: str = ""
    emotions_exit: str = ""
    confidence_level: int = 0  # 1-10
    followed_plan: bool = True
    
    # Lessons and notes
    lessons: str = ""
    mistakes: str = ""
    what_went_well: str = ""
    notes: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)  # File paths or URLs
    chart_link: str = ""
    
    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    
    # Rating
    trade_rating: int = 0  # 1-5 stars
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        # Calculate P&L if we have exit info
        if self.exit_price > 0 and self.entry_price > 0:
            self._calculate_pnl()
        
        # Calculate position size
        if self.position_size == 0 and self.quantity > 0:
            self.position_size = self.entry_price * self.quantity
        
        # Calculate risk/reward
        if self.stop_loss > 0 and self.take_profit > 0:
            self._calculate_risk_reward()
    
    def _calculate_pnl(self):
        """Calculate P&L from prices."""
        if self.side.lower() in ["long", "buy"]:
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
            self.pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            self.pnl = (self.entry_price - self.exit_price) * self.quantity
            self.pnl_pct = ((self.entry_price - self.exit_price) / self.entry_price) * 100
        
        # Determine outcome
        if self.pnl > 0:
            self.outcome = "win"
        elif self.pnl < 0:
            self.outcome = "loss"
        else:
            self.outcome = "breakeven"
    
    def _calculate_risk_reward(self):
        """Calculate risk/reward ratio."""
        if self.side.lower() in ["long", "buy"]:
            risk = self.entry_price - self.stop_loss
            reward = self.take_profit - self.entry_price
        else:
            risk = self.stop_loss - self.entry_price
            reward = self.entry_price - self.take_profit
        
        if risk > 0:
            self.risk_reward = reward / risk
    
    def to_dict(self) -> dict:
        data = asdict(self)
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'JournalEntry':
        # Handle tags list
        if 'tags' not in data:
            data['tags'] = []
        if 'screenshots' not in data:
            data['screenshots'] = []
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def is_open(self) -> bool:
        """Check if trade is still open."""
        return self.exit_date == "" or self.exit_price == 0


@dataclass
class JournalInsights:
    """Insights derived from journal entries."""
    total_entries: int = 0
    total_pnl: float = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    
    # Best/worst
    best_trade: Optional[JournalEntry] = None
    worst_trade: Optional[JournalEntry] = None
    
    # By setup
    setup_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # By emotion
    emotion_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # By day of week
    day_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # Common patterns
    common_mistakes: List[str] = field(default_factory=list)
    common_lessons: List[str] = field(default_factory=list)
    
    # Streaks
    current_streak: int = 0
    best_streak: int = 0
    worst_streak: int = 0
    
    # Plan adherence
    plan_adherence_rate: float = 0
    plan_adherence_win_rate: float = 0
    no_plan_win_rate: float = 0


class TradeJournal:
    """
    Trade journal for tracking and analyzing trades.
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
        
        self.entries: Dict[str, JournalEntry] = {}
        self._load()
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    def add_entry(self, symbol: str, side: str, entry_date: str, entry_price: float,
                  exit_date: str = "", exit_price: float = 0, quantity: float = 0,
                  setup: str = "", entry_reason: str = "", exit_reason: str = "",
                  emotions_entry: str = "", emotions_exit: str = "",
                  lessons: str = "", mistakes: str = "", notes: str = "",
                  tags: List[str] = None, stop_loss: float = 0, take_profit: float = 0,
                  strategy: str = "", timeframe: str = "", confidence_level: int = 0,
                  followed_plan: bool = True, what_went_well: str = "",
                  trade_rating: int = 0, **kwargs) -> JournalEntry:
        """
        Add a new journal entry.
        
        Args:
            symbol: Stock/crypto symbol
            side: 'long' or 'short'
            entry_date: Entry date (YYYY-MM-DD)
            entry_price: Entry price
            exit_date: Exit date (optional, for open trades)
            exit_price: Exit price (optional)
            quantity: Number of shares/units
            setup: Trade setup type
            entry_reason: Why you entered
            exit_reason: Why you exited
            emotions_entry: How you felt entering
            emotions_exit: How you felt exiting
            lessons: What you learned
            mistakes: What went wrong
            notes: Additional notes
            tags: List of tags
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy: Strategy name
            timeframe: Chart timeframe
            confidence_level: 1-10
            followed_plan: Did you follow your plan?
            what_went_well: What worked
            trade_rating: 1-5 stars
        
        Returns:
            JournalEntry object
        """
        entry = JournalEntry(
            id=str(uuid.uuid4())[:8],
            symbol=symbol.upper(),
            side=side.lower(),
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            quantity=quantity,
            setup=setup.lower() if setup else "",
            entry_reason=entry_reason,
            exit_reason=exit_reason,
            emotions_entry=emotions_entry.lower() if emotions_entry else "",
            emotions_exit=emotions_exit.lower() if emotions_exit else "",
            lessons=lessons,
            mistakes=mistakes,
            notes=notes,
            tags=tags or [],
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            timeframe=timeframe,
            confidence_level=confidence_level,
            followed_plan=followed_plan,
            what_went_well=what_went_well,
            trade_rating=trade_rating,
        )
        
        self.entries[entry.id] = entry
        self._save()
        
        # Print confirmation
        outcome_emoji = "[+]" if entry.pnl > 0 else "[-]" if entry.pnl < 0 else "[.]"
        status = "OPEN" if entry.is_open() else f"P&L: ${entry.pnl:+,.2f}"
        print(f"📝 Journal entry added: {outcome_emoji} {entry.symbol} ({status})")
        
        return entry
    
    def update_entry(self, entry_id: str, **kwargs) -> Optional[JournalEntry]:
        """Update an existing entry."""
        if entry_id not in self.entries:
            print(f"[X] Entry not found: {entry_id}")
            return None
        
        entry = self.entries[entry_id]
        
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        # Recalculate P&L if prices changed
        if 'exit_price' in kwargs or 'entry_price' in kwargs:
            entry._calculate_pnl()
        
        entry.updated_at = datetime.now().isoformat()
        self._save()
        
        print(f"[OK] Entry {entry_id} updated")
        return entry
    
    def close_trade(self, entry_id: str, exit_date: str, exit_price: float,
                    exit_reason: str = "", emotions_exit: str = "",
                    lessons: str = "", mistakes: str = "", what_went_well: str = "",
                    trade_rating: int = 0) -> Optional[JournalEntry]:
        """Close an open trade."""
        return self.update_entry(
            entry_id,
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason,
            emotions_exit=emotions_exit,
            lessons=lessons,
            mistakes=mistakes,
            what_went_well=what_went_well,
            trade_rating=trade_rating,
        )
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete a journal entry."""
        if entry_id not in self.entries:
            print(f"[X] Entry not found: {entry_id}")
            return False
        
        del self.entries[entry_id]
        self._save()
        print(f"[OK] Entry {entry_id} deleted")
        return True
    
    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Get a specific entry."""
        return self.entries.get(entry_id)
    
    # =========================================================================
    # SEARCH AND FILTER
    # =========================================================================
    
    def get_all_entries(self, sort_by: str = "entry_date", reverse: bool = True) -> List[JournalEntry]:
        """Get all entries sorted by a field."""
        entries = list(self.entries.values())
        
        if sort_by and hasattr(JournalEntry, sort_by):
            entries.sort(key=lambda e: getattr(e, sort_by, ""), reverse=reverse)
        
        return entries
    
    def get_open_trades(self) -> List[JournalEntry]:
        """Get all open trades."""
        return [e for e in self.entries.values() if e.is_open()]
    
    def get_closed_trades(self) -> List[JournalEntry]:
        """Get all closed trades."""
        return [e for e in self.entries.values() if not e.is_open()]
    
    def search(self, symbol: str = None, setup: str = None, tag: str = None,
               outcome: str = None, start_date: str = None, end_date: str = None,
               emotion: str = None, min_pnl: float = None, max_pnl: float = None,
               strategy: str = None) -> List[JournalEntry]:
        """
        Search journal entries with filters.
        
        Args:
            symbol: Filter by symbol
            setup: Filter by setup type
            tag: Filter by tag
            outcome: Filter by outcome (win, loss, breakeven)
            start_date: Filter entries after this date
            end_date: Filter entries before this date
            emotion: Filter by emotion
            min_pnl: Minimum P&L
            max_pnl: Maximum P&L
            strategy: Filter by strategy
        
        Returns:
            List of matching entries
        """
        results = list(self.entries.values())
        
        if symbol:
            results = [e for e in results if e.symbol.upper() == symbol.upper()]
        
        if setup:
            results = [e for e in results if e.setup.lower() == setup.lower()]
        
        if tag:
            results = [e for e in results if tag.lower() in [t.lower() for t in e.tags]]
        
        if outcome:
            results = [e for e in results if e.outcome.lower() == outcome.lower()]
        
        if start_date:
            results = [e for e in results if e.entry_date >= start_date]
        
        if end_date:
            results = [e for e in results if e.entry_date <= end_date]
        
        if emotion:
            emotion_lower = emotion.lower()
            results = [e for e in results if emotion_lower in e.emotions_entry.lower() 
                      or emotion_lower in e.emotions_exit.lower()]
        
        if min_pnl is not None:
            results = [e for e in results if e.pnl >= min_pnl]
        
        if max_pnl is not None:
            results = [e for e in results if e.pnl <= max_pnl]
        
        if strategy:
            results = [e for e in results if e.strategy.lower() == strategy.lower()]
        
        return sorted(results, key=lambda e: e.entry_date, reverse=True)
    
    def get_by_symbol(self, symbol: str) -> List[JournalEntry]:
        """Get all entries for a symbol."""
        return self.search(symbol=symbol)
    
    def get_by_date_range(self, start_date: str, end_date: str) -> List[JournalEntry]:
        """Get entries within a date range."""
        return self.search(start_date=start_date, end_date=end_date)
    
    def get_winners(self) -> List[JournalEntry]:
        """Get all winning trades."""
        return self.search(outcome="win")
    
    def get_losers(self) -> List[JournalEntry]:
        """Get all losing trades."""
        return self.search(outcome="loss")
    
    # =========================================================================
    # INSIGHTS AND ANALYSIS
    # =========================================================================
    
    def get_insights(self) -> JournalInsights:
        """Generate insights from journal entries."""
        insights = JournalInsights()
        
        closed_trades = self.get_closed_trades()
        
        if not closed_trades:
            return insights
        
        insights.total_entries = len(closed_trades)
        insights.total_pnl = sum(e.pnl for e in closed_trades)
        
        # Win rate
        winners = [e for e in closed_trades if e.outcome == "win"]
        losers = [e for e in closed_trades if e.outcome == "loss"]
        
        insights.win_rate = (len(winners) / len(closed_trades)) * 100 if closed_trades else 0
        
        if winners:
            insights.avg_win = statistics.mean(e.pnl for e in winners)
        if losers:
            insights.avg_loss = statistics.mean(e.pnl for e in losers)
        
        # Best/worst trades
        if closed_trades:
            insights.best_trade = max(closed_trades, key=lambda e: e.pnl)
            insights.worst_trade = min(closed_trades, key=lambda e: e.pnl)
        
        # Performance by setup
        setups = {}
        for entry in closed_trades:
            if entry.setup:
                if entry.setup not in setups:
                    setups[entry.setup] = {"trades": 0, "wins": 0, "pnl": 0}
                setups[entry.setup]["trades"] += 1
                setups[entry.setup]["pnl"] += entry.pnl
                if entry.outcome == "win":
                    setups[entry.setup]["wins"] += 1
        
        for setup, data in setups.items():
            data["win_rate"] = (data["wins"] / data["trades"]) * 100 if data["trades"] > 0 else 0
        
        insights.setup_performance = setups
        
        # Performance by emotion
        emotions = {}
        for entry in closed_trades:
            if entry.emotions_entry:
                for emotion in entry.emotions_entry.split(","):
                    emotion = emotion.strip().lower()
                    if emotion:
                        if emotion not in emotions:
                            emotions[emotion] = {"trades": 0, "wins": 0, "pnl": 0}
                        emotions[emotion]["trades"] += 1
                        emotions[emotion]["pnl"] += entry.pnl
                        if entry.outcome == "win":
                            emotions[emotion]["wins"] += 1
        
        for emotion, data in emotions.items():
            data["win_rate"] = (data["wins"] / data["trades"]) * 100 if data["trades"] > 0 else 0
        
        insights.emotion_performance = emotions
        
        # Performance by day of week
        days = {}
        for entry in closed_trades:
            try:
                date = datetime.fromisoformat(entry.entry_date[:10])
                day_name = date.strftime("%A")
                if day_name not in days:
                    days[day_name] = {"trades": 0, "wins": 0, "pnl": 0}
                days[day_name]["trades"] += 1
                days[day_name]["pnl"] += entry.pnl
                if entry.outcome == "win":
                    days[day_name]["wins"] += 1
            except Exception:
                pass
        
        for day, data in days.items():
            data["win_rate"] = (data["wins"] / data["trades"]) * 100 if data["trades"] > 0 else 0
        
        insights.day_performance = days
        
        # Streaks
        sorted_trades = sorted(closed_trades, key=lambda e: e.exit_date)
        current = 0
        best = 0
        worst = 0
        
        for trade in sorted_trades:
            if trade.outcome == "win":
                if current >= 0:
                    current += 1
                else:
                    current = 1
                best = max(best, current)
            elif trade.outcome == "loss":
                if current <= 0:
                    current -= 1
                else:
                    current = -1
                worst = min(worst, current)
        
        insights.current_streak = current
        insights.best_streak = best
        insights.worst_streak = worst
        
        # Plan adherence
        followed = [e for e in closed_trades if e.followed_plan]
        not_followed = [e for e in closed_trades if not e.followed_plan]
        
        insights.plan_adherence_rate = (len(followed) / len(closed_trades)) * 100 if closed_trades else 0
        
        followed_wins = [e for e in followed if e.outcome == "win"]
        not_followed_wins = [e for e in not_followed if e.outcome == "win"]
        
        insights.plan_adherence_win_rate = (len(followed_wins) / len(followed)) * 100 if followed else 0
        insights.no_plan_win_rate = (len(not_followed_wins) / len(not_followed)) * 100 if not_followed else 0
        
        return insights
    
    def get_statistics(self) -> Dict:
        """Get summary statistics."""
        closed = self.get_closed_trades()
        open_trades = self.get_open_trades()
        
        if not closed:
            return {
                "total_entries": len(self.entries),
                "open_trades": len(open_trades),
                "closed_trades": 0,
            }
        
        winners = [e for e in closed if e.outcome == "win"]
        losers = [e for e in closed if e.outcome == "loss"]
        
        return {
            "total_entries": len(self.entries),
            "open_trades": len(open_trades),
            "closed_trades": len(closed),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": (len(winners) / len(closed)) * 100,
            "total_pnl": sum(e.pnl for e in closed),
            "avg_pnl": statistics.mean(e.pnl for e in closed),
            "best_trade": max(e.pnl for e in closed),
            "worst_trade": min(e.pnl for e in closed),
            "avg_winner": statistics.mean(e.pnl for e in winners) if winners else 0,
            "avg_loser": statistics.mean(e.pnl for e in losers) if losers else 0,
        }
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_journal(self, limit: int = 20):
        """Print journal entries."""
        entries = self.get_all_entries()[:limit]
        
        print(f"\n{'='*80}")
        print("📔 TRADE JOURNAL")
        print(f"{'='*80}")
        
        if not entries:
            print("\n   No journal entries yet.")
            print("   Use journal.add_entry() to add your first trade.\n")
            return
        
        print(f"\n   {'Date':<12} {'Symbol':<8} {'Side':<6} {'Entry':>10} {'Exit':>10} {'P&L':>12} {'Setup':<12}")
        print(f"   {'-'*76}")
        
        for entry in entries:
            outcome_emoji = "[+]" if entry.pnl > 0 else "[-]" if entry.pnl < 0 else "[.]"
            
            exit_str = f"${entry.exit_price:,.2f}" if entry.exit_price > 0 else "OPEN"
            pnl_str = f"${entry.pnl:+,.2f}" if not entry.is_open() else "-"
            
            print(f"   {entry.entry_date[:10]:<12} {outcome_emoji} {entry.symbol:<6} {entry.side:<6} "
                  f"${entry.entry_price:>9,.2f} {exit_str:>10} {pnl_str:>12} {entry.setup:<12}")
        
        total = len(self.entries)
        print(f"\n   Showing {len(entries)} of {total} entries")
        print(f"{'='*80}\n")
    
    def print_entry(self, entry_id: str):
        """Print detailed view of a single entry."""
        entry = self.get_entry(entry_id)
        
        if not entry:
            print(f"[X] Entry not found: {entry_id}")
            return
        
        outcome_emoji = "[+]" if entry.pnl > 0 else "[-]" if entry.pnl < 0 else "[.]"
        
        print(f"\n{'='*60}")
        print(f"📔 JOURNAL ENTRY: {entry.symbol} {outcome_emoji}")
        print(f"{'='*60}")
        
        print(f"\n    TRADE DETAILS")
        print(f"   {'-'*40}")
        print(f"   ID:           {entry.id}")
        print(f"   Symbol:       {entry.symbol}")
        print(f"   Side:         {entry.side.upper()}")
        print(f"   Entry Date:   {entry.entry_date}")
        print(f"   Entry Price:  ${entry.entry_price:,.2f}")
        
        if not entry.is_open():
            print(f"   Exit Date:    {entry.exit_date}")
            print(f"   Exit Price:   ${entry.exit_price:,.2f}")
            print(f"   Quantity:     {entry.quantity:,.2f}")
            print(f"   P&L:          ${entry.pnl:+,.2f} ({entry.pnl_pct:+.2f}%)")
        else:
            print(f"   Status:       OPEN")
        
        if entry.setup or entry.strategy:
            print(f"\n    SETUP")
            print(f"   {'-'*40}")
            if entry.setup:
                print(f"   Setup:        {entry.setup}")
            if entry.strategy:
                print(f"   Strategy:     {entry.strategy}")
            if entry.timeframe:
                print(f"   Timeframe:    {entry.timeframe}")
        
        if entry.stop_loss or entry.take_profit:
            print(f"\n    RISK MANAGEMENT")
            print(f"   {'-'*40}")
            if entry.stop_loss:
                print(f"   Stop Loss:    ${entry.stop_loss:,.2f}")
            if entry.take_profit:
                print(f"   Take Profit:  ${entry.take_profit:,.2f}")
            if entry.risk_reward:
                print(f"   Risk/Reward:  {entry.risk_reward:.2f}")
        
        if entry.entry_reason or entry.exit_reason:
            print(f"\n   💭 REASONING")
            print(f"   {'-'*40}")
            if entry.entry_reason:
                print(f"   Entry:        {entry.entry_reason}")
            if entry.exit_reason:
                print(f"   Exit:         {entry.exit_reason}")
        
        if entry.emotions_entry or entry.emotions_exit:
            print(f"\n   😊 EMOTIONS")
            print(f"   {'-'*40}")
            if entry.emotions_entry:
                print(f"   At Entry:     {entry.emotions_entry}")
            if entry.emotions_exit:
                print(f"   At Exit:      {entry.emotions_exit}")
            if entry.confidence_level:
                print(f"   Confidence:   {entry.confidence_level}/10")
            print(f"   Followed Plan: {'[Y] Yes' if entry.followed_plan else '[X] No'}")
        
        if entry.lessons or entry.mistakes or entry.what_went_well:
            print(f"\n   📝 REFLECTION")
            print(f"   {'-'*40}")
            if entry.what_went_well:
                print(f"   [Y] What went well:")
                print(f"      {entry.what_went_well}")
            if entry.mistakes:
                print(f"   [X] Mistakes:")
                print(f"      {entry.mistakes}")
            if entry.lessons:
                print(f"   💡 Lessons:")
                print(f"      {entry.lessons}")
        
        if entry.tags:
            print(f"\n   🏷️  Tags: {', '.join(entry.tags)}")
        
        if entry.trade_rating:
            stars = "*" * entry.trade_rating
            print(f"\n   Rating: {stars}")
        
        print(f"\n{'='*60}\n")
    
    def print_insights(self):
        """Print journal insights."""
        insights = self.get_insights()
        
        print(f"\n{'='*70}")
        print(" JOURNAL INSIGHTS")
        print(f"{'='*70}")
        
        if insights.total_entries == 0:
            print("\n   Not enough data for insights yet.")
            print("   Add more closed trades to see patterns.\n")
            return
        
        # Summary
        print(f"\n    SUMMARY")
        print(f"   {'-'*50}")
        print(f"   Total Trades:         {insights.total_entries:>10}")
        print(f"   Total P&L:           ${insights.total_pnl:>+10,.2f}")
        print(f"   Win Rate:             {insights.win_rate:>10.1f}%")
        print(f"   Avg Winner:          ${insights.avg_win:>+10,.2f}")
        print(f"   Avg Loser:           ${insights.avg_loss:>+10,.2f}")
        
        # Best/Worst
        if insights.best_trade:
            print(f"\n   🏆 BEST TRADE")
            print(f"   {'-'*50}")
            print(f"   {insights.best_trade.symbol}: ${insights.best_trade.pnl:+,.2f} "
                  f"({insights.best_trade.entry_date})")
        
        if insights.worst_trade:
            print(f"\n   💔 WORST TRADE")
            print(f"   {'-'*50}")
            print(f"   {insights.worst_trade.symbol}: ${insights.worst_trade.pnl:+,.2f} "
                  f"({insights.worst_trade.entry_date})")
        
        # Streaks
        print(f"\n   🔥 STREAKS")
        print(f"   {'-'*50}")
        streak_str = f"+{insights.current_streak}" if insights.current_streak > 0 else str(insights.current_streak)
        print(f"   Current Streak:       {streak_str:>10}")
        print(f"   Best Win Streak:      {insights.best_streak:>10}")
        print(f"   Worst Loss Streak:    {insights.worst_streak:>10}")
        
        # Plan adherence
        print(f"\n    PLAN ADHERENCE")
        print(f"   {'-'*50}")
        print(f"   Followed Plan:        {insights.plan_adherence_rate:>10.1f}%")
        print(f"   Win Rate (w/ plan):   {insights.plan_adherence_win_rate:>10.1f}%")
        print(f"   Win Rate (no plan):   {insights.no_plan_win_rate:>10.1f}%")
        
        # Performance by setup
        if insights.setup_performance:
            print(f"\n    PERFORMANCE BY SETUP")
            print(f"   {'-'*50}")
            print(f"   {'Setup':<15} {'Trades':>8} {'Win Rate':>10} {'P&L':>12}")
            
            for setup, data in sorted(insights.setup_performance.items(), 
                                      key=lambda x: x[1]["pnl"], reverse=True):
                print(f"   {setup:<15} {data['trades']:>8} {data['win_rate']:>9.1f}% ${data['pnl']:>+10,.2f}")
        
        # Performance by emotion
        if insights.emotion_performance:
            print(f"\n   😊 PERFORMANCE BY EMOTION")
            print(f"   {'-'*50}")
            print(f"   {'Emotion':<15} {'Trades':>8} {'Win Rate':>10} {'P&L':>12}")
            
            for emotion, data in sorted(insights.emotion_performance.items(),
                                        key=lambda x: x[1]["pnl"], reverse=True)[:5]:
                print(f"   {emotion:<15} {data['trades']:>8} {data['win_rate']:>9.1f}% ${data['pnl']:>+10,.2f}")
        
        # Performance by day
        if insights.day_performance:
            print(f"\n   📅 PERFORMANCE BY DAY")
            print(f"   {'-'*50}")
            print(f"   {'Day':<15} {'Trades':>8} {'Win Rate':>10} {'P&L':>12}")
            
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            for day in day_order:
                if day in insights.day_performance:
                    data = insights.day_performance[day]
                    print(f"   {day:<15} {data['trades']:>8} {data['win_rate']:>9.1f}% ${data['pnl']:>+10,.2f}")
        
        print(f"\n{'='*70}\n")
    
    def print_statistics(self):
        """Print summary statistics."""
        stats = self.get_statistics()
        
        print(f"\n{'='*50}")
        print(" JOURNAL STATISTICS")
        print(f"{'='*50}")
        
        print(f"\n   Total Entries:    {stats['total_entries']:>10}")
        print(f"   Open Trades:      {stats['open_trades']:>10}")
        print(f"   Closed Trades:    {stats['closed_trades']:>10}")
        
        if stats['closed_trades'] > 0:
            print(f"\n   Winners:          {stats['winners']:>10}")
            print(f"   Losers:           {stats['losers']:>10}")
            print(f"   Win Rate:         {stats['win_rate']:>9.1f}%")
            print(f"\n   Total P&L:       ${stats['total_pnl']:>+10,.2f}")
            print(f"   Avg P&L:         ${stats['avg_pnl']:>+10,.2f}")
            print(f"   Best Trade:      ${stats['best_trade']:>+10,.2f}")
            print(f"   Worst Trade:     ${stats['worst_trade']:>+10,.2f}")
        
        print(f"\n{'='*50}\n")
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def export_to_csv(self, filepath: str = None) -> str:
        """Export journal to CSV."""
        if filepath is None:
            filepath = str(self.storage_path.with_suffix('.csv'))
        
        entries = self.get_all_entries()
        
        if not entries:
            print("No entries to export")
            return ""
        
        # Get all fields
        fields = list(JournalEntry.__dataclass_fields__.keys())
        
        lines = [",".join(fields)]
        
        for entry in entries:
            data = entry.to_dict()
            row = []
            for field in fields:
                value = data.get(field, "")
                if isinstance(value, list):
                    value = "|".join(str(v) for v in value)
                value = str(value).replace(",", ";").replace("\n", " ")
                row.append(value)
            lines.append(",".join(row))
        
        csv_content = "\n".join(lines)
        
        with open(filepath, 'w') as f:
            f.write(csv_content)
        
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


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trade Journal")
    parser.add_argument("--list", "-l", action="store_true", help="List journal entries")
    parser.add_argument("--insights", "-i", action="store_true", help="Show insights")
    parser.add_argument("--stats", "-s", action="store_true", help="Show statistics")
    parser.add_argument("--view", "-v", help="View specific entry by ID")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample data")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    journal = TradeJournal()
    
    if args.demo:
        print("\n🎮 TRADE JOURNAL DEMO")
        print("="*50)
        
        # Add sample entries
        sample_entries = [
            {
                "symbol": "AAPL", "side": "long", "entry_date": "2024-01-15",
                "entry_price": 150, "exit_date": "2024-02-01", "exit_price": 165,
                "quantity": 100, "setup": "breakout",
                "entry_reason": "Breaking above resistance with volume",
                "exit_reason": "Hit profit target",
                "emotions_entry": "confident, patient",
                "emotions_exit": "satisfied",
                "lessons": "Patience paid off",
                "followed_plan": True, "trade_rating": 5,
                "tags": ["tech", "breakout", "winner"]
            },
            {
                "symbol": "MSFT", "side": "long", "entry_date": "2024-02-05",
                "entry_price": 400, "exit_date": "2024-02-20", "exit_price": 380,
                "quantity": 50, "setup": "pullback",
                "entry_reason": "Pullback to support",
                "exit_reason": "Stop loss hit",
                "emotions_entry": "uncertain",
                "emotions_exit": "frustrated",
                "mistakes": "Entered too early, didn't wait for confirmation",
                "lessons": "Wait for proper setup confirmation",
                "followed_plan": False, "trade_rating": 2,
                "tags": ["tech", "pullback", "loser"]
            },
            {
                "symbol": "GOOGL", "side": "long", "entry_date": "2024-02-25",
                "entry_price": 140, "exit_date": "2024-03-15", "exit_price": 155,
                "quantity": 75, "setup": "trend_follow",
                "entry_reason": "Following uptrend, higher lows",
                "exit_reason": "Trailing stop hit",
                "emotions_entry": "calm, disciplined",
                "emotions_exit": "satisfied",
                "what_went_well": "Followed the plan exactly",
                "lessons": "Trend following works",
                "followed_plan": True, "trade_rating": 4,
                "tags": ["tech", "trend", "winner"]
            },
        ]
        
        demo_journal = TradeJournal(storage_path="/tmp/demo_journal.json")
        
        for entry_data in sample_entries:
            demo_journal.add_entry(**entry_data)
        
        demo_journal.print_journal()
        demo_journal.print_insights()
        
        # Clean up
        import os
        os.remove("/tmp/demo_journal.json")
        
    elif args.list:
        journal.print_journal()
    
    elif args.insights:
        journal.print_insights()
    
    elif args.stats:
        journal.print_statistics()
    
    elif args.view:
        journal.print_entry(args.view)
    
    elif args.export:
        journal.export_to_csv()
    
    elif args.interactive:
        print(f"\n{'='*60}")
        print("📔 TRADE JOURNAL - Interactive Mode")
        print(f"{'='*60}")
        print("\nCommands:")
        print("  add                    - Add new entry")
        print("  list / l               - List entries")
        print("  view ID                - View entry details")
        print("  insights / i           - Show insights")
        print("  stats / s              - Show statistics")
        print("  search SYMBOL          - Search by symbol")
        print("  winners                - Show winning trades")
        print("  losers                 - Show losing trades")
        print("  export                 - Export to CSV")
        print("  quit / q               - Exit")
        print()
        
        while True:
            try:
                cmd = input("📔 > ").strip().split()
                
                if not cmd:
                    continue
                
                if cmd[0] in ["quit", "q", "exit"]:
                    break
                
                elif cmd[0] == "add":
                    symbol = input("  Symbol: ").strip().upper()
                    side = input("  Side (long/short): ").strip() or "long"
                    entry_date = input("  Entry date (YYYY-MM-DD): ").strip()
                    entry_price = float(input("  Entry price: ").strip())
                    
                    is_closed = input("  Is trade closed? (y/n): ").strip().lower() == 'y'
                    
                    exit_date = ""
                    exit_price = 0
                    
                    if is_closed:
                        exit_date = input("  Exit date (YYYY-MM-DD): ").strip()
                        exit_price = float(input("  Exit price: ").strip())
                    
                    quantity = float(input("  Quantity: ").strip() or "0")
                    setup = input("  Setup (breakout/pullback/etc): ").strip()
                    entry_reason = input("  Entry reason: ").strip()
                    
                    emotions = input("  Emotions at entry: ").strip()
                    lessons = input("  Lessons learned: ").strip()
                    
                    journal.add_entry(
                        symbol=symbol, side=side, entry_date=entry_date,
                        entry_price=entry_price, exit_date=exit_date,
                        exit_price=exit_price, quantity=quantity,
                        setup=setup, entry_reason=entry_reason,
                        emotions_entry=emotions, lessons=lessons
                    )
                
                elif cmd[0] in ["list", "l"]:
                    journal.print_journal()
                
                elif cmd[0] == "view" and len(cmd) >= 2:
                    journal.print_entry(cmd[1])
                
                elif cmd[0] in ["insights", "i"]:
                    journal.print_insights()
                
                elif cmd[0] in ["stats", "s"]:
                    journal.print_statistics()
                
                elif cmd[0] == "search" and len(cmd) >= 2:
                    results = journal.search(symbol=cmd[1])
                    for e in results[:10]:
                        print(f"  {e.id}: {e.symbol} {e.entry_date} P&L: ${e.pnl:+,.2f}")
                
                elif cmd[0] == "winners":
                    winners = journal.get_winners()
                    for e in winners[:10]:
                        print(f"  {e.symbol} {e.entry_date}: ${e.pnl:+,.2f}")
                
                elif cmd[0] == "losers":
                    losers = journal.get_losers()
                    for e in losers[:10]:
                        print(f"  {e.symbol} {e.entry_date}: ${e.pnl:+,.2f}")
                
                elif cmd[0] == "export":
                    journal.export_to_csv()
                
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
        print("\nUsage: python -m trading.trade_journal --help")


if __name__ == "__main__":
    main()
