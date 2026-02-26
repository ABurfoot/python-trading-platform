#!/usr/bin/env python3
"""
Tax Lot Tracking Module
========================
Track cost basis and tax lots for capital gains calculations.

Features:
- Multiple accounting methods (FIFO, LIFO, Specific ID, Average Cost)
- CGT discount tracking (Australian 50% discount for >12 months)
- Wash sale detection
- Cost basis adjustments (splits, dividends, return of capital)
- Tax report generation

Usage:
    from trading.tax_lots import TaxLotTracker, AccountingMethod
    
    tracker = TaxLotTracker(method=AccountingMethod.FIFO)
    
    # Record a purchase (creates tax lot)
    tracker.buy("AAPL", shares=100, price=150.00, date="2024-01-15")
    
    # Record a sale (matches against lots)
    result = tracker.sell("AAPL", shares=50, price=175.00, date="2024-08-01")
    print(f"Capital gain: ${result.total_gain}")
    
    # Get unrealized gains
    unrealized = tracker.get_unrealized_gains("AAPL", current_price=180.00)
    
    # Generate tax report
    report = tracker.tax_report(2024)
"""

import os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import copy


class AccountingMethod(Enum):
    """Cost basis accounting methods."""
    FIFO = "fifo"           # First In, First Out (Australian default)
    LIFO = "lifo"           # Last In, First Out
    HIFO = "hifo"           # Highest In, First Out (tax optimization)
    SPECIFIC_ID = "specific" # Specific lot identification
    AVERAGE_COST = "average" # Average cost (US mutual funds)


class CGTDiscount(Enum):
    """Capital Gains Tax discount eligibility."""
    NONE = "none"               # No discount (held < 12 months)
    AUSTRALIAN_50 = "au_50"     # Australian 50% discount (held > 12 months)
    US_LONG_TERM = "us_long"    # US long-term rate (held > 12 months)


@dataclass
class TaxLot:
    """
    A tax lot represents shares purchased at a specific time and price.
    """
    id: str                     # Unique lot identifier
    symbol: str                 # Stock symbol
    purchase_date: str          # Date acquired (YYYY-MM-DD)
    shares: float               # Number of shares (remaining)
    original_shares: float      # Original number purchased
    cost_per_share: float       # Cost basis per share
    total_cost: float           # Total cost basis
    currency: str               # Currency of purchase
    
    # Adjustments
    adjusted_cost: float = 0    # Adjusted cost basis (after splits, etc.)
    adjustment_reason: str = "" # Reason for adjustment
    
    # Metadata
    broker: str = ""            # Broker/account
    notes: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = f"{self.symbol}_{self.purchase_date}_{datetime.now().timestamp()}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.adjusted_cost == 0:
            self.adjusted_cost = self.total_cost
        if self.original_shares == 0:
            self.original_shares = self.shares
    
    @property
    def current_cost_per_share(self) -> float:
        """Current cost basis per share (after adjustments)."""
        return self.adjusted_cost / self.shares if self.shares > 0 else 0
    
    @property
    def holding_days(self) -> int:
        """Days held since purchase."""
        purchase = datetime.strptime(self.purchase_date, "%Y-%m-%d")
        return (datetime.now() - purchase).days
    
    @property
    def is_long_term(self) -> bool:
        """Whether held for more than 12 months (CGT discount eligible)."""
        return self.holding_days > 365
    
    @property
    def cgt_discount(self) -> CGTDiscount:
        """Get applicable CGT discount."""
        if self.is_long_term:
            return CGTDiscount.AUSTRALIAN_50
        return CGTDiscount.NONE
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "purchase_date": self.purchase_date,
            "shares": self.shares,
            "original_shares": self.original_shares,
            "cost_per_share": round(self.cost_per_share, 4),
            "total_cost": round(self.total_cost, 2),
            "adjusted_cost": round(self.adjusted_cost, 2),
            "current_cost_per_share": round(self.current_cost_per_share, 4),
            "currency": self.currency,
            "holding_days": self.holding_days,
            "is_long_term": self.is_long_term,
            "cgt_discount": self.cgt_discount.value,
            "broker": self.broker,
            "notes": self.notes,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaxLot':
        # Remove computed properties
        data = {k: v for k, v in data.items() 
                if k not in ['current_cost_per_share', 'holding_days', 'is_long_term', 'cgt_discount']}
        return cls(**data)


@dataclass
class SaleResult:
    """Result of a sale transaction showing lots matched and gains."""
    symbol: str
    sale_date: str
    shares_sold: float
    sale_price: float
    total_proceeds: float
    lots_matched: List[Dict]    # List of {lot_id, shares, cost_basis, gain, discount}
    total_cost_basis: float
    total_gain: float
    short_term_gain: float      # Gain from lots held < 12 months
    long_term_gain: float       # Gain from lots held > 12 months
    discounted_gain: float      # Gain after CGT discount applied
    wash_sale_disallowed: float # Gain disallowed due to wash sale
    currency: str
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "sale_date": self.sale_date,
            "shares_sold": self.shares_sold,
            "sale_price": round(self.sale_price, 4),
            "total_proceeds": round(self.total_proceeds, 2),
            "total_cost_basis": round(self.total_cost_basis, 2),
            "total_gain": round(self.total_gain, 2),
            "short_term_gain": round(self.short_term_gain, 2),
            "long_term_gain": round(self.long_term_gain, 2),
            "discounted_gain": round(self.discounted_gain, 2),
            "wash_sale_disallowed": round(self.wash_sale_disallowed, 2),
            "lots_matched": self.lots_matched,
            "currency": self.currency
        }


@dataclass
class WashSale:
    """Wash sale record."""
    original_sale_date: str
    symbol: str
    disallowed_loss: float
    repurchase_date: str
    repurchase_lot_id: str
    
    def to_dict(self) -> Dict:
        return {
            "original_sale_date": self.original_sale_date,
            "symbol": self.symbol,
            "disallowed_loss": round(self.disallowed_loss, 2),
            "repurchase_date": self.repurchase_date,
            "repurchase_lot_id": self.repurchase_lot_id
        }


class TaxLotTracker:
    """
    Track tax lots and calculate capital gains.
    
    Args:
        method: Default accounting method
        country: Tax jurisdiction (affects discount rules)
    """
    
    # Australian CGT discount (50% for assets held > 12 months)
    AU_CGT_DISCOUNT = 0.50
    
    # Wash sale window (30 days before and after in US)
    WASH_SALE_DAYS = 30
    
    def __init__(self, method: AccountingMethod = AccountingMethod.FIFO,
                 country: str = "AU", data_dir: str = None):
        self.method = method
        self.country = country.upper()
        
        self.data_dir = Path(data_dir or os.path.expanduser("~/.trading_platform"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._lots: Dict[str, List[TaxLot]] = {}  # symbol -> list of lots
        self._sales: List[SaleResult] = []
        self._wash_sales: List[WashSale] = []
        
        self._load_data()
    
    def _load_data(self):
        """Load tax lot data from disk."""
        data_file = self.data_dir / "tax_lots.json"
        if data_file.exists():
            try:
                with open(data_file) as f:
                    data = json.load(f)
                    
                    # Load lots
                    for symbol, lots in data.get("lots", {}).items():
                        self._lots[symbol] = [TaxLot.from_dict(l) for l in lots]
                    
                    # Load sales
                    self._sales = [
                        SaleResult(**s) for s in data.get("sales", [])
                    ]
                    
                    # Load wash sales
                    self._wash_sales = [
                        WashSale(**w) for w in data.get("wash_sales", [])
                    ]
            except Exception as e:
                print(f"Error loading tax lot data: {e}")
    
    def _save_data(self):
        """Save tax lot data to disk."""
        data_file = self.data_dir / "tax_lots.json"
        with open(data_file, 'w') as f:
            json.dump({
                "lots": {sym: [l.to_dict() for l in lots] 
                        for sym, lots in self._lots.items()},
                "sales": [s.to_dict() for s in self._sales],
                "wash_sales": [w.to_dict() for w in self._wash_sales],
                "method": self.method.value,
                "country": self.country,
                "updated": datetime.now().isoformat()
            }, f, indent=2)
    
    def buy(self, symbol: str, shares: float, price: float, date: str = None,
            currency: str = "AUD", commission: float = 0, broker: str = "",
            notes: str = "") -> TaxLot:
        """
        Record a purchase and create a tax lot.
        
        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Price per share
            date: Purchase date (default: today)
            currency: Currency
            commission: Commission paid (added to cost basis)
            broker: Broker/account name
            notes: Optional notes
        
        Returns:
            Created TaxLot
        """
        symbol = symbol.upper()
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Total cost includes commission
        total_cost = (shares * price) + commission
        cost_per_share = total_cost / shares
        
        lot = TaxLot(
            id="",
            symbol=symbol,
            purchase_date=date,
            shares=shares,
            original_shares=shares,
            cost_per_share=cost_per_share,
            total_cost=total_cost,
            currency=currency,
            broker=broker,
            notes=notes
        )
        
        if symbol not in self._lots:
            self._lots[symbol] = []
        self._lots[symbol].append(lot)
        
        # Check for wash sale adjustment (if previous sale within 30 days)
        self._check_wash_sale_repurchase(symbol, date, lot.id)
        
        self._save_data()
        return lot
    
    def sell(self, symbol: str, shares: float, price: float, date: str = None,
             currency: str = "AUD", commission: float = 0,
             method: AccountingMethod = None, lot_ids: List[str] = None) -> SaleResult:
        """
        Record a sale and calculate capital gains.
        
        Args:
            symbol: Stock symbol
            shares: Number of shares to sell
            price: Sale price per share
            date: Sale date (default: today)
            currency: Currency
            commission: Commission paid (reduces proceeds)
            method: Override accounting method for this sale
            lot_ids: Specific lot IDs to sell from (for SPECIFIC_ID method)
        
        Returns:
            SaleResult with gain/loss details
        """
        symbol = symbol.upper()
        date = date or datetime.now().strftime("%Y-%m-%d")
        method = method or self.method
        
        if symbol not in self._lots or not self._lots[symbol]:
            raise ValueError(f"No tax lots found for {symbol}")
        
        # Calculate proceeds
        gross_proceeds = shares * price
        net_proceeds = gross_proceeds - commission
        
        # Get lots to match
        lots = self._get_lots_to_sell(symbol, shares, method, lot_ids)
        
        # Calculate gains
        lots_matched = []
        total_cost_basis = 0
        short_term_gain = 0
        long_term_gain = 0
        shares_remaining = shares
        
        for lot in lots:
            if shares_remaining <= 0:
                break
            
            # Determine shares to take from this lot
            shares_from_lot = min(lot.shares, shares_remaining)
            cost_basis = shares_from_lot * lot.current_cost_per_share
            proceeds = shares_from_lot * price
            gain = proceeds - cost_basis
            
            # Determine if long-term
            lot_date = datetime.strptime(lot.purchase_date, "%Y-%m-%d")
            sale_date = datetime.strptime(date, "%Y-%m-%d")
            holding_days = (sale_date - lot_date).days
            is_long_term = holding_days > 365
            
            # Apply CGT discount for long-term gains (Australian tax)
            discount_applied = 0
            discounted_gain = gain
            if is_long_term and gain > 0 and self.country == "AU":
                discount_applied = gain * self.AU_CGT_DISCOUNT
                discounted_gain = gain - discount_applied
            
            if is_long_term:
                long_term_gain += gain
            else:
                short_term_gain += gain
            
            lots_matched.append({
                "lot_id": lot.id,
                "shares": shares_from_lot,
                "cost_per_share": round(lot.current_cost_per_share, 4),
                "cost_basis": round(cost_basis, 2),
                "proceeds": round(proceeds, 2),
                "gain": round(gain, 2),
                "holding_days": holding_days,
                "is_long_term": is_long_term,
                "discount_applied": round(discount_applied, 2),
                "discounted_gain": round(discounted_gain, 2)
            })
            
            total_cost_basis += cost_basis
            shares_remaining -= shares_from_lot
            
            # Update lot
            lot.shares -= shares_from_lot
            lot.adjusted_cost -= cost_basis
        
        # Remove depleted lots
        self._lots[symbol] = [l for l in self._lots[symbol] if l.shares > 0]
        
        # Calculate totals
        total_gain = net_proceeds - total_cost_basis
        discounted_gain = sum(m["discounted_gain"] for m in lots_matched) - commission
        
        # Check for wash sale (if loss)
        wash_sale_disallowed = 0
        if total_gain < 0:
            wash_sale_disallowed = self._check_wash_sale(symbol, date, abs(total_gain))
        
        result = SaleResult(
            symbol=symbol,
            sale_date=date,
            shares_sold=shares,
            sale_price=price,
            total_proceeds=net_proceeds,
            lots_matched=lots_matched,
            total_cost_basis=total_cost_basis,
            total_gain=total_gain,
            short_term_gain=short_term_gain,
            long_term_gain=long_term_gain,
            discounted_gain=discounted_gain,
            wash_sale_disallowed=wash_sale_disallowed,
            currency=currency
        )
        
        self._sales.append(result)
        self._save_data()
        
        return result
    
    def _get_lots_to_sell(self, symbol: str, shares: float,
                         method: AccountingMethod, lot_ids: List[str] = None) -> List[TaxLot]:
        """Get lots to sell based on accounting method."""
        lots = self._lots.get(symbol, [])
        
        if method == AccountingMethod.SPECIFIC_ID:
            if not lot_ids:
                raise ValueError("lot_ids required for SPECIFIC_ID method")
            selected = [l for l in lots if l.id in lot_ids]
            if sum(l.shares for l in selected) < shares:
                raise ValueError("Not enough shares in specified lots")
            return selected
        
        # Sort based on method
        if method == AccountingMethod.FIFO:
            sorted_lots = sorted(lots, key=lambda l: l.purchase_date)
        elif method == AccountingMethod.LIFO:
            sorted_lots = sorted(lots, key=lambda l: l.purchase_date, reverse=True)
        elif method == AccountingMethod.HIFO:
            sorted_lots = sorted(lots, key=lambda l: l.current_cost_per_share, reverse=True)
        elif method == AccountingMethod.AVERAGE_COST:
            # For average cost, combine all lots into virtual single lot
            total_shares = sum(l.shares for l in lots)
            total_cost = sum(l.adjusted_cost for l in lots)
            avg_cost = total_cost / total_shares if total_shares > 0 else 0
            
            # Create a virtual lot with average cost
            virtual_lot = copy.deepcopy(lots[0])
            virtual_lot.shares = total_shares
            virtual_lot.adjusted_cost = total_cost
            virtual_lot.cost_per_share = avg_cost
            sorted_lots = [virtual_lot]
        else:
            sorted_lots = lots
        
        # Check we have enough shares
        available = sum(l.shares for l in sorted_lots)
        if available < shares:
            raise ValueError(f"Not enough shares. Need {shares}, have {available}")
        
        return sorted_lots
    
    def _check_wash_sale(self, symbol: str, sale_date: str, loss: float) -> float:
        """Check if sale triggers wash sale rule."""
        if self.country != "US":
            return 0  # Wash sale is primarily US rule
        
        sale_dt = datetime.strptime(sale_date, "%Y-%m-%d")
        window_start = (sale_dt - timedelta(days=self.WASH_SALE_DAYS)).strftime("%Y-%m-%d")
        window_end = (sale_dt + timedelta(days=self.WASH_SALE_DAYS)).strftime("%Y-%m-%d")
        
        # Check for purchases within window
        for lot in self._lots.get(symbol, []):
            if window_start <= lot.purchase_date <= window_end and lot.purchase_date != sale_date:
                # Wash sale detected
                self._wash_sales.append(WashSale(
                    original_sale_date=sale_date,
                    symbol=symbol,
                    disallowed_loss=loss,
                    repurchase_date=lot.purchase_date,
                    repurchase_lot_id=lot.id
                ))
                
                # Add disallowed loss to cost basis of replacement shares
                lot.adjusted_cost += loss
                lot.adjustment_reason = f"Wash sale adjustment from {sale_date}"
                
                return loss
        
        return 0
    
    def _check_wash_sale_repurchase(self, symbol: str, purchase_date: str, lot_id: str):
        """Check if purchase triggers wash sale from recent sale."""
        if self.country != "US":
            return
        
        purchase_dt = datetime.strptime(purchase_date, "%Y-%m-%d")
        window_start = (purchase_dt - timedelta(days=self.WASH_SALE_DAYS)).strftime("%Y-%m-%d")
        
        # Check recent sales for losses
        for sale in self._sales:
            if sale.symbol == symbol and sale.total_gain < 0:
                if window_start <= sale.sale_date <= purchase_date:
                    # This purchase triggers wash sale
                    loss = abs(sale.total_gain)
                    
                    self._wash_sales.append(WashSale(
                        original_sale_date=sale.sale_date,
                        symbol=symbol,
                        disallowed_loss=loss,
                        repurchase_date=purchase_date,
                        repurchase_lot_id=lot_id
                    ))
                    
                    # Adjust cost basis of new lot
                    for lot in self._lots.get(symbol, []):
                        if lot.id == lot_id:
                            lot.adjusted_cost += loss
                            lot.adjustment_reason = f"Wash sale adjustment from sale on {sale.sale_date}"
    
    def adjust_for_split(self, symbol: str, split_ratio: float, date: str = None):
        """
        Adjust lots for a stock split.
        
        Args:
            symbol: Stock symbol
            split_ratio: Split ratio (e.g., 4.0 for 4-for-1 split)
            date: Split date
        """
        symbol = symbol.upper()
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        for lot in self._lots.get(symbol, []):
            lot.shares *= split_ratio
            lot.original_shares *= split_ratio
            lot.cost_per_share /= split_ratio
            # Total cost stays the same
            lot.adjustment_reason = f"Split {split_ratio}:1 on {date}"
        
        self._save_data()
    
    def adjust_for_return_of_capital(self, symbol: str, amount_per_share: float, date: str = None):
        """
        Adjust cost basis for return of capital distribution.
        
        Args:
            symbol: Stock symbol
            amount_per_share: Return of capital per share
            date: Distribution date
        """
        symbol = symbol.upper()
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        for lot in self._lots.get(symbol, []):
            reduction = amount_per_share * lot.shares
            lot.adjusted_cost -= reduction
            lot.adjustment_reason = f"Return of capital ${amount_per_share}/share on {date}"
        
        self._save_data()
    
    def get_lots(self, symbol: str = None) -> Dict[str, List[TaxLot]]:
        """Get all lots, optionally filtered by symbol."""
        if symbol:
            return {symbol.upper(): self._lots.get(symbol.upper(), [])}
        return self._lots
    
    def get_cost_basis(self, symbol: str) -> Dict:
        """Get cost basis summary for a symbol."""
        symbol = symbol.upper()
        lots = self._lots.get(symbol, [])
        
        if not lots:
            return {"symbol": symbol, "total_shares": 0, "total_cost": 0, "avg_cost": 0}
        
        total_shares = sum(l.shares for l in lots)
        total_cost = sum(l.adjusted_cost for l in lots)
        
        return {
            "symbol": symbol,
            "total_shares": total_shares,
            "total_cost": round(total_cost, 2),
            "avg_cost": round(total_cost / total_shares, 4) if total_shares > 0 else 0,
            "lots": len(lots),
            "oldest_lot": min(l.purchase_date for l in lots),
            "newest_lot": max(l.purchase_date for l in lots)
        }
    
    def get_unrealized_gains(self, symbol: str, current_price: float) -> Dict:
        """Calculate unrealized gains for a position."""
        symbol = symbol.upper()
        lots = self._lots.get(symbol, [])
        
        if not lots:
            return {"symbol": symbol, "unrealized_gain": 0}
        
        total_shares = sum(l.shares for l in lots)
        total_cost = sum(l.adjusted_cost for l in lots)
        market_value = total_shares * current_price
        unrealized = market_value - total_cost
        
        # Break down by long/short term
        short_term = 0
        long_term = 0
        discounted = 0
        
        for lot in lots:
            lot_value = lot.shares * current_price
            lot_cost = lot.adjusted_cost
            lot_gain = lot_value - lot_cost
            
            if lot.is_long_term:
                long_term += lot_gain
                if lot_gain > 0 and self.country == "AU":
                    discounted += lot_gain * (1 - self.AU_CGT_DISCOUNT)
                else:
                    discounted += lot_gain
            else:
                short_term += lot_gain
                discounted += lot_gain
        
        return {
            "symbol": symbol,
            "total_shares": total_shares,
            "total_cost": round(total_cost, 2),
            "market_value": round(market_value, 2),
            "unrealized_gain": round(unrealized, 2),
            "unrealized_pct": round(unrealized / total_cost * 100, 2) if total_cost > 0 else 0,
            "short_term_gain": round(short_term, 2),
            "long_term_gain": round(long_term, 2),
            "discounted_gain": round(discounted, 2)
        }
    
    def get_sales(self, symbol: str = None, year: int = None) -> List[SaleResult]:
        """Get sale history."""
        sales = self._sales
        
        if symbol:
            symbol = symbol.upper()
            sales = [s for s in sales if s.symbol == symbol]
        
        if year:
            sales = [s for s in sales if s.sale_date.startswith(str(year))]
        
        return sales
    
    def tax_report(self, year: int) -> Dict:
        """
        Generate tax report for a year.
        
        Args:
            year: Tax year
        
        Returns:
            Dict with capital gains summary
        """
        sales = self.get_sales(year=year)
        
        total_proceeds = sum(s.total_proceeds for s in sales)
        total_cost = sum(s.total_cost_basis for s in sales)
        total_gain = sum(s.total_gain for s in sales)
        short_term = sum(s.short_term_gain for s in sales)
        long_term = sum(s.long_term_gain for s in sales)
        discounted = sum(s.discounted_gain for s in sales)
        wash_sales = sum(s.wash_sale_disallowed for s in sales)
        
        # Separate gains and losses
        gains = [s for s in sales if s.total_gain > 0]
        losses = [s for s in sales if s.total_gain < 0]
        
        return {
            "year": year,
            "country": self.country,
            "method": self.method.value,
            "summary": {
                "total_proceeds": round(total_proceeds, 2),
                "total_cost_basis": round(total_cost, 2),
                "total_gain_loss": round(total_gain, 2),
                "short_term_gain": round(short_term, 2),
                "long_term_gain": round(long_term, 2),
                "cgt_discount_applied": round(long_term - discounted + short_term, 2) if long_term > 0 else 0,
                "net_capital_gain": round(discounted, 2),
                "wash_sale_adjustments": round(wash_sales, 2),
                "total_sales": len(sales),
                "profitable_sales": len(gains),
                "loss_sales": len(losses)
            },
            "sales": [s.to_dict() for s in sales],
            "wash_sales": [w.to_dict() for w in self._wash_sales 
                         if w.original_sale_date.startswith(str(year))]
        }
    
    def print_lots(self, symbol: str = None):
        """Print tax lots summary."""
        print(f"\n{'='*80}")
        print("TAX LOTS SUMMARY")
        print(f"{'='*80}")
        
        symbols = [symbol.upper()] if symbol else list(self._lots.keys())
        
        for sym in symbols:
            lots = self._lots.get(sym, [])
            if not lots:
                continue
            
            print(f"\n{sym}:")
            print(f"  {'Date':<12} {'Shares':>10} {'Cost/Share':>12} {'Total Cost':>12} {'Days':>6} {'LT':>4}")
            print(f"  {'-'*66}")
            
            for lot in sorted(lots, key=lambda l: l.purchase_date):
                lt = "Yes" if lot.is_long_term else "No"
                print(f"  {lot.purchase_date:<12} {lot.shares:>10.2f} ${lot.current_cost_per_share:>10.2f} ${lot.adjusted_cost:>10.2f} {lot.holding_days:>6} {lt:>4}")
            
            summary = self.get_cost_basis(sym)
            print(f"  {'-'*66}")
            print(f"  {'Total':<12} {summary['total_shares']:>10.2f} ${summary['avg_cost']:>10.2f} ${summary['total_cost']:>10.2f}")
        
        print(f"\n{'='*80}")
    
    def print_tax_report(self, year: int = None):
        """Print tax report."""
        year = year or datetime.now().year
        report = self.tax_report(year)
        
        print(f"\n{'='*60}")
        print(f"CAPITAL GAINS TAX REPORT - {year}")
        print(f"Country: {self.country} | Method: {self.method.value.upper()}")
        print(f"{'='*60}")
        
        s = report["summary"]
        print(f"\nTotal Proceeds:         ${s['total_proceeds']:>12,.2f}")
        print(f"Total Cost Basis:       ${s['total_cost_basis']:>12,.2f}")
        print(f"Total Gain/Loss:        ${s['total_gain_loss']:>12,.2f}")
        print(f"\nShort-Term Gain:        ${s['short_term_gain']:>12,.2f}")
        print(f"Long-Term Gain:         ${s['long_term_gain']:>12,.2f}")
        
        if self.country == "AU" and s['long_term_gain'] > 0:
            print(f"CGT Discount (50%):     ${s['cgt_discount_applied']:>12,.2f}")
        
        print(f"\nNet Capital Gain:       ${s['net_capital_gain']:>12,.2f}")
        
        if s['wash_sale_adjustments'] > 0:
            print(f"Wash Sale Adjustments:  ${s['wash_sale_adjustments']:>12,.2f}")
        
        print(f"\nTotal Sales: {s['total_sales']} ({s['profitable_sales']} profitable, {s['loss_sales']} losses)")
        print(f"{'='*60}")


if __name__ == "__main__":
    # Demo
    print("Tax Lot Tracking Demo")
    print("="*50)
    
    tracker = TaxLotTracker(method=AccountingMethod.FIFO, country="AU")
    
    # Simulate some trades
    tracker.buy("VAS.AX", shares=100, price=85.00, date="2023-01-15", 
                commission=10, notes="Initial purchase")
    tracker.buy("VAS.AX", shares=50, price=88.00, date="2023-06-20",
                commission=10, notes="Additional purchase")
    tracker.buy("AAPL", shares=20, price=150.00, date="2023-03-01",
                commission=5, currency="USD")
    
    # Print lots
    tracker.print_lots()
    
    # Sell some shares
    print("\nSelling 75 shares of VAS.AX at $92.00...")
    result = tracker.sell("VAS.AX", shares=75, price=92.00, date="2024-08-01", commission=10)
    
    print(f"\nSale Result:")
    print(f"  Proceeds: ${result.total_proceeds:,.2f}")
    print(f"  Cost Basis: ${result.total_cost_basis:,.2f}")
    print(f"  Total Gain: ${result.total_gain:,.2f}")
    print(f"  Long-Term: ${result.long_term_gain:,.2f}")
    print(f"  After CGT Discount: ${result.discounted_gain:,.2f}")
    
    # Show unrealized gains
    print("\nUnrealized Gains (AAPL at $180):")
    unrealized = tracker.get_unrealized_gains("AAPL", current_price=180.00)
    for key, value in unrealized.items():
        print(f"  {key}: {value}")
    
    # Print tax report
    tracker.print_tax_report(2024)
