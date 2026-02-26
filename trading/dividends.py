#!/usr/bin/env python3
"""
Dividend Tracking Module
=========================
Track dividend income, yields, and tax implications.

Features:
- Record dividend payments
- Track franking credits (Australian tax)
- Calculate yield on cost vs current yield
- Support DRIP (Dividend Reinvestment)
- Withholding tax tracking
- Generate dividend reports

Usage:
    from trading.dividends import DividendTracker, DividendPayment
    
    tracker = DividendTracker()
    
    # Record dividend
    tracker.add_dividend(
        symbol="VAS.AX",
        amount=150.00,
        shares=100,
        ex_date="2024-03-15",
        pay_date="2024-03-28",
        franking_pct=100
    )
    
    # Get dividend history
    history = tracker.get_history("VAS.AX")
    
    # Calculate yield
    yield_info = tracker.calculate_yield("VAS.AX", cost_basis=5000)
    
    # Generate report
    report = tracker.annual_report(2024)
"""

import os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum


class DividendType(Enum):
    """Type of dividend."""
    ORDINARY = "ordinary"           # Regular dividend
    SPECIAL = "special"             # One-time special dividend
    CAPITAL_RETURN = "capital"      # Return of capital
    INTEREST = "interest"           # Interest distribution (REITs)
    FOREIGN = "foreign"             # Foreign sourced income


class DRIPStatus(Enum):
    """DRIP enrollment status."""
    CASH = "cash"                   # Receive cash
    FULL_DRIP = "full_drip"         # Reinvest all dividends
    PARTIAL_DRIP = "partial_drip"   # Reinvest portion


@dataclass
class DividendPayment:
    """Single dividend payment record."""
    id: str                         # Unique ID
    symbol: str                     # Stock symbol
    ex_date: str                    # Ex-dividend date (YYYY-MM-DD)
    pay_date: str                   # Payment date
    record_date: str                # Record date
    shares: float                   # Shares held at record date
    amount_per_share: float         # Dividend per share
    total_amount: float             # Total payment (shares × amount_per_share)
    currency: str                   # Payment currency
    
    # Tax-related
    franking_pct: float = 0         # Franking percentage (Australian)
    franking_credit: float = 0      # Franking credit amount
    withholding_tax: float = 0      # Foreign withholding tax deducted
    withholding_tax_pct: float = 0  # Withholding tax rate
    
    # Classification
    dividend_type: DividendType = DividendType.ORDINARY
    
    # DRIP
    drip_shares: float = 0          # Shares received if reinvested
    drip_price: float = 0           # Price for DRIP shares
    
    # Metadata
    notes: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = f"{self.symbol}_{self.ex_date}_{datetime.now().timestamp()}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.record_date:
            self.record_date = self.ex_date
    
    @property
    def net_amount(self) -> float:
        """Net amount after withholding tax."""
        return self.total_amount - self.withholding_tax
    
    @property
    def grossed_up_amount(self) -> float:
        """Grossed up amount including franking credits (for tax)."""
        return self.total_amount + self.franking_credit
    
    @property
    def effective_yield_pa(self) -> float:
        """Annualized yield based on this payment."""
        # Assumes quarterly dividends
        return (self.amount_per_share * 4) / self.drip_price * 100 if self.drip_price > 0 else 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "ex_date": self.ex_date,
            "pay_date": self.pay_date,
            "record_date": self.record_date,
            "shares": self.shares,
            "amount_per_share": round(self.amount_per_share, 4),
            "total_amount": round(self.total_amount, 2),
            "currency": self.currency,
            "franking_pct": self.franking_pct,
            "franking_credit": round(self.franking_credit, 2),
            "withholding_tax": round(self.withholding_tax, 2),
            "withholding_tax_pct": self.withholding_tax_pct,
            "dividend_type": self.dividend_type.value,
            "drip_shares": self.drip_shares,
            "drip_price": self.drip_price,
            "net_amount": round(self.net_amount, 2),
            "grossed_up_amount": round(self.grossed_up_amount, 2),
            "notes": self.notes,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DividendPayment':
        data = data.copy()
        if "dividend_type" in data:
            data["dividend_type"] = DividendType(data["dividend_type"])
        # Remove computed properties that shouldn't be passed to __init__
        for key in ["net_amount", "grossed_up_amount", "effective_yield_pa", "days_to_expiry"]:
            data.pop(key, None)
        return cls(**data)


@dataclass
class DividendSummary:
    """Summary of dividends for a symbol or period."""
    total_dividends: float
    total_franking_credits: float
    total_withholding_tax: float
    net_dividends: float
    payment_count: int
    avg_yield: float
    symbols: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "total_dividends": round(self.total_dividends, 2),
            "total_franking_credits": round(self.total_franking_credits, 2),
            "total_withholding_tax": round(self.total_withholding_tax, 2),
            "net_dividends": round(self.net_dividends, 2),
            "grossed_up_total": round(self.total_dividends + self.total_franking_credits, 2),
            "payment_count": self.payment_count,
            "avg_yield": round(self.avg_yield, 2),
            "symbols": self.symbols
        }


class DividendTracker:
    """
    Track and analyze dividend income.
    
    Supports:
    - Multiple currencies
    - Australian franking credits
    - Foreign withholding tax
    - DRIP tracking
    - Yield calculations
    """
    
    # Australian corporate tax rate (for franking credit calculation)
    AU_CORPORATE_TAX_RATE = 0.30
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or os.path.expanduser("~/.trading_platform"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._dividends: List[DividendPayment] = []
        self._drip_settings: Dict[str, DRIPStatus] = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load dividend data from disk."""
        data_file = self.data_dir / "dividends.json"
        if data_file.exists():
            try:
                with open(data_file) as f:
                    data = json.load(f)
                    self._dividends = [
                        DividendPayment.from_dict(d) for d in data.get("dividends", [])
                    ]
                    self._drip_settings = data.get("drip_settings", {})
            except Exception as e:
                print(f"Error loading dividend data: {e}")
    
    def _save_data(self):
        """Save dividend data to disk."""
        data_file = self.data_dir / "dividends.json"
        with open(data_file, 'w') as f:
            json.dump({
                "dividends": [d.to_dict() for d in self._dividends],
                "drip_settings": self._drip_settings,
                "updated": datetime.now().isoformat()
            }, f, indent=2)
    
    def add_dividend(self, symbol: str, amount: float = None, amount_per_share: float = None,
                     shares: float = None, ex_date: str = None, pay_date: str = None,
                     record_date: str = None, currency: str = "AUD",
                     franking_pct: float = 0, withholding_tax_pct: float = 0,
                     dividend_type: str = "ordinary",
                     drip_shares: float = 0, drip_price: float = 0,
                     notes: str = "") -> DividendPayment:
        """
        Add a dividend payment.
        
        Args:
            symbol: Stock symbol
            amount: Total dividend amount (or calculate from amount_per_share × shares)
            amount_per_share: Dividend per share
            shares: Number of shares held
            ex_date: Ex-dividend date
            pay_date: Payment date
            record_date: Record date (default: ex_date)
            currency: Payment currency
            franking_pct: Franking percentage (0-100, Australian stocks)
            withholding_tax_pct: Withholding tax percentage (foreign stocks)
            dividend_type: Type of dividend
            drip_shares: Shares received if DRIP
            drip_price: Price paid for DRIP shares
            notes: Optional notes
        
        Returns:
            DividendPayment object
        """
        symbol = symbol.upper()
        
        # Calculate amounts
        if amount is None and amount_per_share and shares:
            amount = amount_per_share * shares
        elif amount and shares and amount_per_share is None:
            amount_per_share = amount / shares
        
        if not all([amount, shares, ex_date]):
            raise ValueError("Must provide amount, shares, and ex_date")
        
        # Default dates
        if not pay_date:
            pay_date = ex_date
        if not record_date:
            record_date = ex_date
        
        # Calculate franking credit (Australian tax)
        franking_credit = 0
        if franking_pct > 0:
            # Franking credit = Dividend × (Franking % × Corporate Tax Rate / (1 - Corporate Tax Rate))
            franking_credit = amount * (franking_pct / 100) * (self.AU_CORPORATE_TAX_RATE / (1 - self.AU_CORPORATE_TAX_RATE))
        
        # Calculate withholding tax
        withholding_tax = amount * (withholding_tax_pct / 100)
        
        # Parse dividend type
        if isinstance(dividend_type, str):
            dividend_type = DividendType(dividend_type.lower())
        
        # Create payment
        payment = DividendPayment(
            id="",
            symbol=symbol,
            ex_date=ex_date,
            pay_date=pay_date,
            record_date=record_date,
            shares=shares,
            amount_per_share=amount_per_share or (amount / shares),
            total_amount=amount,
            currency=currency,
            franking_pct=franking_pct,
            franking_credit=franking_credit,
            withholding_tax=withholding_tax,
            withholding_tax_pct=withholding_tax_pct,
            dividend_type=dividend_type,
            drip_shares=drip_shares,
            drip_price=drip_price,
            notes=notes
        )
        
        self._dividends.append(payment)
        self._save_data()
        
        return payment
    
    def remove_dividend(self, dividend_id: str) -> bool:
        """Remove a dividend payment by ID."""
        for i, div in enumerate(self._dividends):
            if div.id == dividend_id:
                self._dividends.pop(i)
                self._save_data()
                return True
        return False
    
    def get_dividend(self, dividend_id: str) -> Optional[DividendPayment]:
        """Get a specific dividend by ID."""
        for div in self._dividends:
            if div.id == dividend_id:
                return div
        return None
    
    def get_history(self, symbol: str = None, year: int = None,
                    start_date: str = None, end_date: str = None) -> List[DividendPayment]:
        """
        Get dividend history with optional filters.
        
        Args:
            symbol: Filter by symbol
            year: Filter by year
            start_date: Filter by start date
            end_date: Filter by end date
        
        Returns:
            List of matching dividend payments
        """
        dividends = self._dividends
        
        if symbol:
            symbol = symbol.upper()
            dividends = [d for d in dividends if d.symbol == symbol]
        
        if year:
            dividends = [d for d in dividends if d.pay_date.startswith(str(year))]
        
        if start_date:
            dividends = [d for d in dividends if d.pay_date >= start_date]
        
        if end_date:
            dividends = [d for d in dividends if d.pay_date <= end_date]
        
        return sorted(dividends, key=lambda d: d.pay_date, reverse=True)
    
    def get_summary(self, symbol: str = None, year: int = None,
                    start_date: str = None, end_date: str = None) -> DividendSummary:
        """Get dividend summary for a period."""
        dividends = self.get_history(symbol, year, start_date, end_date)
        
        if not dividends:
            return DividendSummary(
                total_dividends=0,
                total_franking_credits=0,
                total_withholding_tax=0,
                net_dividends=0,
                payment_count=0,
                avg_yield=0,
                symbols=[]
            )
        
        total = sum(d.total_amount for d in dividends)
        franking = sum(d.franking_credit for d in dividends)
        withholding = sum(d.withholding_tax for d in dividends)
        symbols = list(set(d.symbol for d in dividends))
        
        return DividendSummary(
            total_dividends=total,
            total_franking_credits=franking,
            total_withholding_tax=withholding,
            net_dividends=total - withholding,
            payment_count=len(dividends),
            avg_yield=0,  # Would need cost basis to calculate
            symbols=symbols
        )
    
    def calculate_yield(self, symbol: str, cost_basis: float = None,
                        current_price: float = None, shares: float = None) -> Dict:
        """
        Calculate dividend yield for a position.
        
        Args:
            symbol: Stock symbol
            cost_basis: Total cost basis (for yield on cost)
            current_price: Current share price (for current yield)
            shares: Number of shares held
        
        Returns:
            Dict with yield calculations
        """
        symbol = symbol.upper()
        
        # Get last 12 months of dividends
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        dividends = self.get_history(symbol, start_date=one_year_ago)
        
        if not dividends:
            return {
                "symbol": symbol,
                "annual_dividend": 0,
                "yield_on_cost": 0,
                "current_yield": 0,
                "payments_per_year": 0,
                "avg_franking_pct": 0
            }
        
        # Calculate annual dividend (last 12 months)
        annual_dividend = sum(d.total_amount for d in dividends)
        annual_per_share = sum(d.amount_per_share for d in dividends)
        payments_per_year = len(dividends)
        avg_franking = sum(d.franking_pct for d in dividends) / len(dividends)
        
        # Calculate yields
        yield_on_cost = 0
        current_yield = 0
        
        if cost_basis and cost_basis > 0:
            yield_on_cost = (annual_dividend / cost_basis) * 100
        
        if current_price and current_price > 0:
            current_yield = (annual_per_share / current_price) * 100
        
        # Grossed up yield (including franking credits)
        grossed_up_yield = 0
        if yield_on_cost > 0 and avg_franking > 0:
            franking_factor = avg_franking / 100 * self.AU_CORPORATE_TAX_RATE / (1 - self.AU_CORPORATE_TAX_RATE)
            grossed_up_yield = yield_on_cost * (1 + franking_factor)
        elif yield_on_cost > 0:
            grossed_up_yield = yield_on_cost
        
        return {
            "symbol": symbol,
            "annual_dividend": round(annual_dividend, 2),
            "annual_per_share": round(annual_per_share, 4),
            "yield_on_cost": round(yield_on_cost, 2),
            "current_yield": round(current_yield, 2),
            "grossed_up_yield": round(grossed_up_yield, 2),
            "payments_per_year": payments_per_year,
            "avg_franking_pct": round(avg_franking, 1)
        }
    
    def set_drip(self, symbol: str, status: DRIPStatus):
        """Set DRIP status for a symbol."""
        self._drip_settings[symbol.upper()] = status.value
        self._save_data()
    
    def get_drip(self, symbol: str) -> DRIPStatus:
        """Get DRIP status for a symbol."""
        status = self._drip_settings.get(symbol.upper(), "cash")
        return DRIPStatus(status)
    
    def annual_report(self, year: int, base_currency: str = "AUD") -> Dict:
        """
        Generate annual dividend report for tax purposes.
        
        Args:
            year: Tax year
            base_currency: Currency for totals
        
        Returns:
            Dict with annual dividend summary
        """
        dividends = self.get_history(year=year)
        
        # Group by type
        by_type = {}
        for div in dividends:
            dtype = div.dividend_type.value
            if dtype not in by_type:
                by_type[dtype] = []
            by_type[dtype].append(div)
        
        # Group by symbol
        by_symbol = {}
        for div in dividends:
            if div.symbol not in by_symbol:
                by_symbol[div.symbol] = {
                    "total": 0,
                    "franking_credits": 0,
                    "withholding_tax": 0,
                    "payments": 0
                }
            by_symbol[div.symbol]["total"] += div.total_amount
            by_symbol[div.symbol]["franking_credits"] += div.franking_credit
            by_symbol[div.symbol]["withholding_tax"] += div.withholding_tax
            by_symbol[div.symbol]["payments"] += 1
        
        # Calculate totals
        total_dividends = sum(d.total_amount for d in dividends)
        total_franking = sum(d.franking_credit for d in dividends)
        total_withholding = sum(d.withholding_tax for d in dividends)
        
        return {
            "year": year,
            "currency": base_currency,
            "summary": {
                "total_dividends": round(total_dividends, 2),
                "total_franking_credits": round(total_franking, 2),
                "total_withholding_tax": round(total_withholding, 2),
                "net_dividends": round(total_dividends - total_withholding, 2),
                "grossed_up_total": round(total_dividends + total_franking, 2),
                "payment_count": len(dividends)
            },
            "by_symbol": {k: {key: round(v, 2) if isinstance(v, float) else v 
                             for key, v in vals.items()} 
                         for k, vals in by_symbol.items()},
            "by_type": {k: len(v) for k, v in by_type.items()},
            "payments": [d.to_dict() for d in dividends]
        }
    
    def get_upcoming_dividends(self, symbols: List[str] = None) -> List[Dict]:
        """
        Get upcoming ex-dividend dates.
        Note: This would typically fetch from an API. 
        Here we return any future-dated dividends in our records.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        dividends = [d for d in self._dividends if d.ex_date >= today]
        
        if symbols:
            symbols = [s.upper() for s in symbols]
            dividends = [d for d in dividends if d.symbol in symbols]
        
        return [d.to_dict() for d in sorted(dividends, key=lambda d: d.ex_date)]
    
    def get_symbols(self) -> List[str]:
        """Get all symbols with dividend history."""
        return list(set(d.symbol for d in self._dividends))
    
    def print_summary(self, year: int = None):
        """Print dividend summary."""
        if year is None:
            year = datetime.now().year
        
        report = self.annual_report(year)
        
        print(f"\n{'='*60}")
        print(f"DIVIDEND REPORT - {year}")
        print(f"{'='*60}")
        
        summary = report["summary"]
        print(f"\nTotal Dividends:        ${summary['total_dividends']:>12,.2f}")
        print(f"Franking Credits:       ${summary['total_franking_credits']:>12,.2f}")
        print(f"Withholding Tax:        ${summary['total_withholding_tax']:>12,.2f}")
        print(f"Net Dividends:          ${summary['net_dividends']:>12,.2f}")
        print(f"Grossed Up Total:       ${summary['grossed_up_total']:>12,.2f}")
        print(f"Payment Count:          {summary['payment_count']:>12}")
        
        print(f"\n{'-'*60}")
        print("BY SYMBOL:")
        print(f"{'Symbol':<12} {'Total':>12} {'Franking':>12} {'Withholding':>12}")
        print(f"{'-'*60}")
        
        for symbol, data in sorted(report["by_symbol"].items()):
            print(f"{symbol:<12} ${data['total']:>11,.2f} ${data['franking_credits']:>11,.2f} ${data['withholding_tax']:>11,.2f}")
        
        print(f"{'='*60}")


if __name__ == "__main__":
    # Demo
    print("Dividend Tracking Demo")
    print("="*50)
    
    tracker = DividendTracker()
    
    # Add some sample dividends
    tracker.add_dividend(
        symbol="VAS.AX",
        amount=250.00,
        shares=100,
        ex_date="2024-03-15",
        pay_date="2024-03-28",
        currency="AUD",
        franking_pct=100,
        notes="Q1 2024 distribution"
    )
    
    tracker.add_dividend(
        symbol="AAPL",
        amount=24.00,
        shares=100,
        ex_date="2024-02-09",
        pay_date="2024-02-15",
        currency="USD",
        withholding_tax_pct=15,
        notes="US withholding applies"
    )
    
    # Print summary
    tracker.print_summary(2024)
    
    # Calculate yield
    print("\nYield Calculation (VAS.AX):")
    yield_info = tracker.calculate_yield("VAS.AX", cost_basis=8000, current_price=85)
    for key, value in yield_info.items():
        print(f"  {key}: {value}")
