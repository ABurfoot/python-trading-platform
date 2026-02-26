#!/usr/bin/env python3
"""
Economic Calendar Module
=========================
Track economic events, central bank decisions, and market-moving data releases.

Features:
- Global economic events (US, Australia, EU, UK, Japan, China)
- Central bank meetings (Fed, RBA, ECB, BOE, BOJ)
- Economic indicators (GDP, CPI, Employment, PMI)
- Impact ratings (High, Medium, Low)
- Automatic alerts for upcoming events
- Historical data for backtesting

Data Sources:
- Finnhub Economic Calendar API
- FMP Economic Calendar API
- Trading Economics (fallback)
- Built-in major events calendar

Usage:
    from trading.economic_calendar import EconomicCalendar
    
    cal = EconomicCalendar()
    
    # Get this week's events
    events = cal.get_events(days=7)
    
    # Get high-impact events only
    high_impact = cal.get_events(impact="high")
    
    # Get Australian events
    au_events = cal.get_events(country="AU")
    
    # Get upcoming central bank meetings
    meetings = cal.get_central_bank_meetings()
    
    # Print calendar
    cal.print_calendar()
"""

import os
import json
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class Impact(Enum):
    """Event impact level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    HOLIDAY = "holiday"


class EventType(Enum):
    """Type of economic event."""
    INTEREST_RATE = "interest_rate"
    GDP = "gdp"
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    PMI = "pmi"
    RETAIL = "retail"
    HOUSING = "housing"
    TRADE = "trade"
    CONSUMER = "consumer"
    MANUFACTURING = "manufacturing"
    CENTRAL_BANK = "central_bank"
    SPEECH = "speech"
    AUCTION = "auction"
    HOLIDAY = "holiday"
    OTHER = "other"


@dataclass
class EconomicEvent:
    """An economic calendar event."""
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (local time of country)
    country: str  # ISO 2-letter code
    event: str  # Event name
    impact: str  # high, medium, low
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    event_type: str = "other"
    currency: str = ""
    source: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EconomicEvent':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @property
    def datetime_str(self) -> str:
        return f"{self.date} {self.time}"
    
    @property
    def is_upcoming(self) -> bool:
        try:
            event_dt = datetime.strptime(self.date, "%Y-%m-%d")
            return event_dt.date() >= datetime.now().date()
        except Exception:
            return True
    
    @property
    def country_flag(self) -> str:
        """Get emoji flag for country."""
        flags = {
            "US": "🇺🇸", "AU": "🇦🇺", "GB": "🇬🇧", "EU": "🇪🇺",
            "JP": "🇯🇵", "CN": "🇨🇳", "CA": "🇨🇦", "NZ": "🇳🇿",
            "CH": "🇨🇭", "DE": "🇩🇪", "FR": "🇫🇷", "IT": "🇮🇹",
        }
        return flags.get(self.country, "🌍")


# =============================================================================
# BUILT-IN CALENDAR DATA
# =============================================================================

# Major central bank meeting dates (updated periodically)
CENTRAL_BANK_MEETINGS_2024_2026 = {
    "FOMC": {  # US Federal Reserve
        "name": "Federal Reserve FOMC Meeting",
        "country": "US",
        "currency": "USD",
        "dates": [
            "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
            "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
            "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
            "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
            "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10",
            "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
        ]
    },
    "RBA": {  # Reserve Bank of Australia
        "name": "RBA Interest Rate Decision",
        "country": "AU",
        "currency": "AUD",
        "dates": [
            "2024-02-06", "2024-03-19", "2024-05-07", "2024-06-18",
            "2024-08-06", "2024-09-24", "2024-11-05", "2024-12-10",
            "2025-02-18", "2025-04-01", "2025-05-20", "2025-07-08",
            "2025-08-12", "2025-09-30", "2025-11-04", "2025-12-09",
            "2026-02-17", "2026-03-31", "2026-05-05", "2026-06-16",
            "2026-08-04", "2026-09-15", "2026-11-03", "2026-12-08",
        ]
    },
    "ECB": {  # European Central Bank
        "name": "ECB Interest Rate Decision",
        "country": "EU",
        "currency": "EUR",
        "dates": [
            "2024-01-25", "2024-03-07", "2024-04-11", "2024-06-06",
            "2024-07-18", "2024-09-12", "2024-10-17", "2024-12-12",
            "2025-01-30", "2025-03-06", "2025-04-17", "2025-06-05",
            "2025-07-24", "2025-09-11", "2025-10-30", "2025-12-18",
            "2026-01-22", "2026-03-05", "2026-04-16", "2026-06-04",
            "2026-07-16", "2026-09-10", "2026-10-29", "2026-12-10",
        ]
    },
    "BOE": {  # Bank of England
        "name": "BOE Interest Rate Decision",
        "country": "GB",
        "currency": "GBP",
        "dates": [
            "2024-02-01", "2024-03-21", "2024-05-09", "2024-06-20",
            "2024-08-01", "2024-09-19", "2024-11-07", "2024-12-19",
            "2025-02-06", "2025-03-20", "2025-05-08", "2025-06-19",
            "2025-08-07", "2025-09-18", "2025-11-06", "2025-12-18",
            "2026-02-05", "2026-03-19", "2026-05-07", "2026-06-18",
            "2026-08-06", "2026-09-17", "2026-11-05", "2026-12-17",
        ]
    },
    "BOJ": {  # Bank of Japan
        "name": "BOJ Interest Rate Decision",
        "country": "JP",
        "currency": "JPY",
        "dates": [
            "2024-01-23", "2024-03-19", "2024-04-26", "2024-06-14",
            "2024-07-31", "2024-09-20", "2024-10-31", "2024-12-19",
            "2025-01-24", "2025-03-14", "2025-05-01", "2025-06-13",
            "2025-07-31", "2025-09-19", "2025-10-31", "2025-12-19",
            "2026-01-22", "2026-03-13", "2026-04-30", "2026-06-12",
            "2026-07-30", "2026-09-18", "2026-10-30", "2026-12-18",
        ]
    },
}

# Major recurring economic events
MAJOR_ECONOMIC_EVENTS = {
    "US": [
        {"event": "Non-Farm Payrolls", "impact": "high", "type": "employment", "frequency": "monthly", "day": "first_friday"},
        {"event": "CPI (Consumer Price Index)", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "Core CPI", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "PPI (Producer Price Index)", "impact": "medium", "type": "inflation", "frequency": "monthly"},
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "Retail Sales", "impact": "high", "type": "retail", "frequency": "monthly"},
        {"event": "Consumer Confidence", "impact": "medium", "type": "consumer", "frequency": "monthly"},
        {"event": "ISM Manufacturing PMI", "impact": "high", "type": "pmi", "frequency": "monthly"},
        {"event": "ISM Services PMI", "impact": "high", "type": "pmi", "frequency": "monthly"},
        {"event": "Initial Jobless Claims", "impact": "medium", "type": "employment", "frequency": "weekly"},
        {"event": "Existing Home Sales", "impact": "medium", "type": "housing", "frequency": "monthly"},
        {"event": "New Home Sales", "impact": "medium", "type": "housing", "frequency": "monthly"},
        {"event": "Durable Goods Orders", "impact": "medium", "type": "manufacturing", "frequency": "monthly"},
        {"event": "Core PCE Price Index", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "JOLTS Job Openings", "impact": "medium", "type": "employment", "frequency": "monthly"},
        {"event": "ADP Employment Change", "impact": "medium", "type": "employment", "frequency": "monthly"},
    ],
    "AU": [
        {"event": "Employment Change", "impact": "high", "type": "employment", "frequency": "monthly"},
        {"event": "Unemployment Rate", "impact": "high", "type": "employment", "frequency": "monthly"},
        {"event": "CPI (Consumer Price Index)", "impact": "high", "type": "inflation", "frequency": "quarterly"},
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "Retail Sales", "impact": "medium", "type": "retail", "frequency": "monthly"},
        {"event": "Trade Balance", "impact": "medium", "type": "trade", "frequency": "monthly"},
        {"event": "RBA Meeting Minutes", "impact": "high", "type": "central_bank", "frequency": "monthly"},
        {"event": "Building Approvals", "impact": "low", "type": "housing", "frequency": "monthly"},
        {"event": "Consumer Confidence", "impact": "low", "type": "consumer", "frequency": "monthly"},
        {"event": "NAB Business Confidence", "impact": "medium", "type": "consumer", "frequency": "monthly"},
        {"event": "Private Capital Expenditure", "impact": "medium", "type": "manufacturing", "frequency": "quarterly"},
    ],
    "GB": [
        {"event": "CPI", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "Employment Change", "impact": "high", "type": "employment", "frequency": "monthly"},
        {"event": "Retail Sales", "impact": "medium", "type": "retail", "frequency": "monthly"},
        {"event": "Manufacturing PMI", "impact": "medium", "type": "pmi", "frequency": "monthly"},
        {"event": "Services PMI", "impact": "medium", "type": "pmi", "frequency": "monthly"},
    ],
    "EU": [
        {"event": "CPI", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "Unemployment Rate", "impact": "medium", "type": "employment", "frequency": "monthly"},
        {"event": "Manufacturing PMI", "impact": "medium", "type": "pmi", "frequency": "monthly"},
        {"event": "Services PMI", "impact": "medium", "type": "pmi", "frequency": "monthly"},
        {"event": "Consumer Confidence", "impact": "low", "type": "consumer", "frequency": "monthly"},
    ],
    "JP": [
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "CPI", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "Tankan Manufacturing Index", "impact": "high", "type": "pmi", "frequency": "quarterly"},
        {"event": "Trade Balance", "impact": "medium", "type": "trade", "frequency": "monthly"},
    ],
    "CN": [
        {"event": "GDP Growth Rate", "impact": "high", "type": "gdp", "frequency": "quarterly"},
        {"event": "CPI", "impact": "high", "type": "inflation", "frequency": "monthly"},
        {"event": "Manufacturing PMI", "impact": "high", "type": "pmi", "frequency": "monthly"},
        {"event": "Trade Balance", "impact": "medium", "type": "trade", "frequency": "monthly"},
        {"event": "Industrial Production", "impact": "medium", "type": "manufacturing", "frequency": "monthly"},
    ],
}

# Country to timezone offset (simplified)
COUNTRY_TIMEZONES = {
    "US": "EST",
    "AU": "AEDT",
    "GB": "GMT",
    "EU": "CET",
    "JP": "JST",
    "CN": "CST",
    "CA": "EST",
    "NZ": "NZDT",
    "CH": "CET",
}

# Country to currency
COUNTRY_CURRENCIES = {
    "US": "USD",
    "AU": "AUD",
    "GB": "GBP",
    "EU": "EUR",
    "JP": "JPY",
    "CN": "CNY",
    "CA": "CAD",
    "NZ": "NZD",
    "CH": "CHF",
}


class EconomicCalendar:
    """
    Economic calendar with multi-source data fetching.
    """
    
    def __init__(self, cache_hours: int = 1):
        self.cache_hours = cache_hours
        self.cache_dir = Path.home() / ".trading_platform" / "economic_calendar"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, Tuple[List[EconomicEvent], datetime]] = {}
        
        # API keys
        self.finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
        self.fmp_key = os.environ.get("FMP_API_KEY", "")
    
    def _request(self, url: str, timeout: int = 15) -> Optional[Dict]:
        """Make HTTP request."""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None
    
    def _fetch_finnhub_calendar(self, from_date: str, to_date: str) -> List[EconomicEvent]:
        """Fetch from Finnhub Economic Calendar API."""
        if not self.finnhub_key:
            return []
        
        url = f"https://finnhub.io/api/v1/calendar/economic?from={from_date}&to={to_date}&token={self.finnhub_key}"
        data = self._request(url)
        
        if not data or "economicCalendar" not in data:
            return []
        
        events = []
        for item in data.get("economicCalendar", []):
            # Determine impact
            impact_val = item.get("impact", 0)
            if impact_val >= 3:
                impact = "high"
            elif impact_val >= 2:
                impact = "medium"
            else:
                impact = "low"
            
            events.append(EconomicEvent(
                date=item.get("time", "")[:10],
                time=item.get("time", "")[11:16] if len(item.get("time", "")) > 11 else "00:00",
                country=item.get("country", ""),
                event=item.get("event", ""),
                impact=impact,
                actual=str(item.get("actual")) if item.get("actual") is not None else None,
                forecast=str(item.get("estimate")) if item.get("estimate") is not None else None,
                previous=str(item.get("prev")) if item.get("prev") is not None else None,
                currency=COUNTRY_CURRENCIES.get(item.get("country", ""), ""),
                source="finnhub"
            ))
        
        return events
    
    def _fetch_fmp_calendar(self, from_date: str, to_date: str) -> List[EconomicEvent]:
        """Fetch from FMP Economic Calendar API."""
        if not self.fmp_key:
            return []
        
        url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={from_date}&to={to_date}&apikey={self.fmp_key}"
        data = self._request(url)
        
        if not data or not isinstance(data, list):
            return []
        
        events = []
        for item in data:
            # Determine impact from FMP
            impact_str = item.get("impact", "").lower()
            if "high" in impact_str:
                impact = "high"
            elif "medium" in impact_str or "moderate" in impact_str:
                impact = "medium"
            else:
                impact = "low"
            
            events.append(EconomicEvent(
                date=item.get("date", "")[:10],
                time=item.get("date", "")[11:16] if len(item.get("date", "")) > 11 else "00:00",
                country=item.get("country", ""),
                event=item.get("event", ""),
                impact=impact,
                actual=str(item.get("actual")) if item.get("actual") is not None else None,
                forecast=str(item.get("estimate")) if item.get("estimate") is not None else None,
                previous=str(item.get("previous")) if item.get("previous") is not None else None,
                currency=item.get("currency", ""),
                source="fmp"
            ))
        
        return events
    
    def _get_builtin_events(self, from_date: str, to_date: str, 
                            countries: List[str] = None) -> List[EconomicEvent]:
        """Get events from built-in calendar data."""
        events = []
        
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Add central bank meetings
        for bank_code, bank_info in CENTRAL_BANK_MEETINGS_2024_2026.items():
            if countries and bank_info["country"] not in countries:
                continue
            
            for date_str in bank_info["dates"]:
                try:
                    event_dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if from_dt <= event_dt <= to_dt:
                        events.append(EconomicEvent(
                            date=date_str,
                            time="14:00" if bank_info["country"] == "US" else "12:00",
                            country=bank_info["country"],
                            event=bank_info["name"],
                            impact="high",
                            event_type="interest_rate",
                            currency=bank_info["currency"],
                            source="builtin"
                        ))
                except Exception:
                    continue
        
        return events
    
    def get_events(self, days: int = 7, country: str = None, 
                   impact: str = None, event_type: str = None,
                   from_date: str = None, to_date: str = None) -> List[EconomicEvent]:
        """
        Get economic calendar events.
        
        Args:
            days: Number of days to look ahead (default 7)
            country: Filter by country code (US, AU, GB, EU, JP, CN, etc.)
            impact: Filter by impact level (high, medium, low)
            event_type: Filter by event type
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        
        Returns:
            List of EconomicEvent objects
        """
        # Determine date range
        if from_date is None:
            from_date = datetime.now().strftime("%Y-%m-%d")
        if to_date is None:
            to_date = (datetime.strptime(from_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Check cache
        cache_key = f"{from_date}_{to_date}"
        if cache_key in self._cache:
            cached_events, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < timedelta(hours=self.cache_hours):
                events = cached_events
            else:
                events = self._fetch_all_events(from_date, to_date)
        else:
            events = self._fetch_all_events(from_date, to_date)
        
        # Cache results
        self._cache[cache_key] = (events, datetime.now())
        
        # Apply filters
        if country:
            country = country.upper()
            events = [e for e in events if e.country.upper() == country]
        
        if impact:
            impact = impact.lower()
            events = [e for e in events if e.impact.lower() == impact]
        
        if event_type:
            events = [e for e in events if e.event_type.lower() == event_type.lower()]
        
        # Sort by date/time
        events.sort(key=lambda e: (e.date, e.time))
        
        return events
    
    def _fetch_all_events(self, from_date: str, to_date: str) -> List[EconomicEvent]:
        """Fetch events from all available sources."""
        all_events = []
        
        # Try Finnhub first
        finnhub_events = self._fetch_finnhub_calendar(from_date, to_date)
        if finnhub_events:
            all_events.extend(finnhub_events)
        
        # Try FMP if Finnhub didn't return enough
        if len(all_events) < 10:
            fmp_events = self._fetch_fmp_calendar(from_date, to_date)
            # Add non-duplicate events
            existing = {(e.date, e.event, e.country) for e in all_events}
            for e in fmp_events:
                if (e.date, e.event, e.country) not in existing:
                    all_events.append(e)
        
        # Always add built-in events (central bank meetings)
        builtin_events = self._get_builtin_events(from_date, to_date)
        existing = {(e.date, e.country, "interest" in e.event.lower() or "rate" in e.event.lower()) 
                   for e in all_events}
        for e in builtin_events:
            # Only add if we don't have a similar event
            key = (e.date, e.country, True)
            if key not in existing:
                all_events.append(e)
        
        return all_events
    
    def get_central_bank_meetings(self, days: int = 90, 
                                   banks: List[str] = None) -> List[EconomicEvent]:
        """
        Get upcoming central bank meetings.
        
        Args:
            days: Number of days to look ahead
            banks: List of bank codes (FOMC, RBA, ECB, BOE, BOJ)
        
        Returns:
            List of meeting events
        """
        events = []
        now = datetime.now()
        end_date = now + timedelta(days=days)
        
        for bank_code, bank_info in CENTRAL_BANK_MEETINGS_2024_2026.items():
            if banks and bank_code not in banks:
                continue
            
            for date_str in bank_info["dates"]:
                try:
                    event_dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if now.date() <= event_dt.date() <= end_date.date():
                        events.append(EconomicEvent(
                            date=date_str,
                            time="14:00" if bank_info["country"] == "US" else "12:00",
                            country=bank_info["country"],
                            event=bank_info["name"],
                            impact="high",
                            event_type="interest_rate",
                            currency=bank_info["currency"],
                            source="builtin"
                        ))
                except Exception:
                    continue
        
        events.sort(key=lambda e: e.date)
        return events
    
    def get_high_impact_events(self, days: int = 7, 
                               countries: List[str] = None) -> List[EconomicEvent]:
        """Get only high-impact events."""
        events = self.get_events(days=days, impact="high")
        
        if countries:
            countries = [c.upper() for c in countries]
            events = [e for e in events if e.country.upper() in countries]
        
        return events
    
    def get_events_by_type(self, event_type: str, days: int = 30) -> List[EconomicEvent]:
        """
        Get events by type.
        
        Args:
            event_type: employment, inflation, gdp, pmi, retail, housing, etc.
            days: Number of days to look ahead
        """
        events = self.get_events(days=days)
        
        # Filter by type (check both event_type field and event name)
        type_lower = event_type.lower()
        filtered = []
        
        for e in events:
            if e.event_type.lower() == type_lower:
                filtered.append(e)
            elif type_lower in e.event.lower():
                filtered.append(e)
        
        return filtered
    
    def get_today_events(self, country: str = None) -> List[EconomicEvent]:
        """Get today's events."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_events(from_date=today, to_date=today, country=country)
    
    def get_this_week_events(self, country: str = None, 
                             impact: str = None) -> List[EconomicEvent]:
        """Get this week's events."""
        today = datetime.now()
        # Get to end of week (Sunday)
        days_until_sunday = 6 - today.weekday()
        end_of_week = today + timedelta(days=days_until_sunday)
        
        return self.get_events(
            from_date=today.strftime("%Y-%m-%d"),
            to_date=end_of_week.strftime("%Y-%m-%d"),
            country=country,
            impact=impact
        )
    
    def print_calendar(self, days: int = 7, country: str = None, 
                       impact: str = None, show_all: bool = False):
        """
        Print formatted calendar to console.
        
        Args:
            days: Number of days to show
            country: Filter by country
            impact: Filter by impact (high, medium, low)
            show_all: Show all events including low impact
        """
        events = self.get_events(days=days, country=country, impact=impact)
        
        if not show_all and not impact:
            # Default to medium+ impact
            events = [e for e in events if e.impact in ["high", "medium"]]
        
        if not events:
            print("No events found for the specified criteria.")
            return
        
        # Group by date
        events_by_date: Dict[str, List[EconomicEvent]] = {}
        for e in events:
            if e.date not in events_by_date:
                events_by_date[e.date] = []
            events_by_date[e.date].append(e)
        
        print(f"\n{'='*75}")
        print("📅 ECONOMIC CALENDAR")
        if country:
            print(f"   Country: {country}")
        if impact:
            print(f"   Impact: {impact}")
        print(f"{'='*75}")
        
        for date_str in sorted(events_by_date.keys()):
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = date_obj.strftime("%A")
            formatted_date = date_obj.strftime("%b %d, %Y")
            
            # Check if today
            is_today = date_str == datetime.now().strftime("%Y-%m-%d")
            today_marker = " 📍 TODAY" if is_today else ""
            
            print(f"\n┌─ {day_name}, {formatted_date}{today_marker}")
            print(f"│")
            
            day_events = sorted(events_by_date[date_str], key=lambda e: e.time)
            
            for event in day_events:
                # Impact indicator
                if event.impact == "high":
                    impact_icon = "[-]"
                elif event.impact == "medium":
                    impact_icon = "[~]"
                else:
                    impact_icon = "[+]"
                
                # Format values
                forecast_str = f"Exp: {event.forecast}" if event.forecast else ""
                previous_str = f"Prev: {event.previous}" if event.previous else ""
                actual_str = f"Act: {event.actual}" if event.actual else ""
                
                values = " | ".join(filter(None, [forecast_str, previous_str, actual_str]))
                
                print(f"│  {event.time}  {impact_icon} {event.country_flag} {event.event}")
                if values:
                    print(f"│         {values}")
            
            print(f"└{'─'*73}")
        
        print(f"\n{'='*75}")
        
        # Legend
        print("\nLegend: [-] High Impact | [~] Medium Impact | [+] Low Impact")
        print()
    
    def print_upcoming_highlights(self, days: int = 3):
        """Print upcoming high-impact events as highlights."""
        events = self.get_high_impact_events(days=days)
        
        print(f"\n{'='*60}")
        print("[WARN]  HIGH IMPACT EVENTS - Next {} Days".format(days))
        print(f"{'='*60}")
        
        if not events:
            print("\nNo high-impact events in the next {} days.".format(days))
            return
        
        for event in events:
            date_obj = datetime.strptime(event.date, "%Y-%m-%d")
            formatted = date_obj.strftime("%a %b %d")
            
            print(f"\n  {event.country_flag} {formatted} {event.time}")
            print(f"     {event.event}")
            if event.forecast:
                print(f"     Forecast: {event.forecast} | Previous: {event.previous or 'N/A'}")
        
        print(f"\n{'='*60}")
    
    def get_next_event(self, country: str = None, 
                       event_type: str = None) -> Optional[EconomicEvent]:
        """Get the next upcoming event matching criteria."""
        events = self.get_events(days=30, country=country)
        
        now = datetime.now()
        
        for event in events:
            try:
                event_dt = datetime.strptime(f"{event.date} {event.time}", "%Y-%m-%d %H:%M")
                if event_dt > now:
                    if event_type is None or event_type.lower() in event.event.lower():
                        return event
            except Exception:
                continue
        
        return None
    
    def get_market_hours_events(self, market: str = "US") -> List[EconomicEvent]:
        """
        Get events that occur during market hours.
        
        Args:
            market: US, AU, GB, EU
        """
        market_hours = {
            "US": ("09:30", "16:00"),
            "AU": ("10:00", "16:00"),
            "GB": ("08:00", "16:30"),
            "EU": ("09:00", "17:30"),
        }
        
        if market not in market_hours:
            return []
        
        open_time, close_time = market_hours[market]
        events = self.get_events(days=7)
        
        return [
            e for e in events
            if open_time <= e.time <= close_time
        ]
    
    def to_dataframe(self, events: List[EconomicEvent] = None):
        """Convert events to pandas DataFrame if available."""
        try:
            import pandas as pd
            
            if events is None:
                events = self.get_events(days=30)
            
            data = [e.to_dict() for e in events]
            return pd.DataFrame(data)
        except ImportError:
            print("pandas not installed")
            return None


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Economic Calendar")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days to look ahead")
    parser.add_argument("--country", "-c", help="Filter by country (US, AU, GB, EU, JP, CN)")
    parser.add_argument("--impact", "-i", choices=["high", "medium", "low"], help="Filter by impact")
    parser.add_argument("--banks", "-b", action="store_true", help="Show central bank meetings only")
    parser.add_argument("--today", "-t", action="store_true", help="Show today's events only")
    parser.add_argument("--highlights", action="store_true", help="Show high-impact highlights")
    parser.add_argument("--all", "-a", action="store_true", help="Show all events including low impact")
    
    args = parser.parse_args()
    cal = EconomicCalendar()
    
    if args.banks:
        events = cal.get_central_bank_meetings(days=args.days)
        print(f"\n{'='*60}")
        print("🏦 CENTRAL BANK MEETINGS")
        print(f"{'='*60}")
        
        for e in events:
            date_obj = datetime.strptime(e.date, "%Y-%m-%d")
            formatted = date_obj.strftime("%a %b %d, %Y")
            print(f"\n  {e.country_flag} {formatted}")
            print(f"     {e.event}")
        print()
    
    elif args.today:
        cal.print_calendar(days=1, country=args.country, show_all=args.all)
    
    elif args.highlights:
        cal.print_upcoming_highlights(days=args.days)
    
    else:
        cal.print_calendar(
            days=args.days,
            country=args.country,
            impact=args.impact,
            show_all=args.all
        )


if __name__ == "__main__":
    main()
