#!/usr/bin/env python3
"""
Integrated Portfolio Manager
=============================
Full-featured portfolio management with tax lot tracking, dividend tracking,
and multi-currency support.

Features:
- Multiple portfolios with paper trading
- Tax lot accounting (FIFO/LIFO/HIFO) with CGT discount
- Dividend tracking with franking credits
- Multi-currency support (AUD, USD, GBP, etc.)
- Realized and unrealized P&L
- Performance metrics and benchmarking
- Tax-ready reports (Australian CGT)

Usage:
    from trading.portfolio import IntegratedPortfolioManager
    
    pm = IntegratedPortfolioManager(base_currency="AUD")
    
    # Buy shares (automatically creates tax lot)
    pm.buy("default", "AAPL", 100, 150.00, currency="USD")
    
    # Record dividend (with franking)
    pm.record_dividend("default", "VAS.AX", 250.00, franking_pct=100)
    
    # Sell shares (uses tax lot accounting)
    result = pm.sell("default", "AAPL", 50, 180.00)
    print(f"Capital gain: ${result['gain']:.2f}")
    
    # Get comprehensive summary
    summary = pm.get_summary("default", include_tax=True)
    
    # Generate tax report
    pm.generate_tax_report("default", year=2024)
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum

# Import the existing modules - handle gracefully if not available
TaxLotTracker = None
TaxLot = None
SaleResult = None
AccountingMethod = None
DividendTracker = None
Dividend = None
CurrencyManager = None

try:
    from trading.tax_lots import TaxLotTracker, TaxLot, SaleResult, AccountingMethod
except ImportError as e:
    print(f"Warning: tax_lots module not available: {e}")

try:
    from trading.dividends import DividendTracker, DividendPayment as Dividend
except ImportError as e:
    print(f"Warning: dividends module not available: {e}")

try:
    from trading.currency import CurrencyManager
except ImportError as e:
    print(f"Warning: currency module not available: {e}")


class TransactionType(Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    FX_CONVERSION = "fx_conversion"
    SPLIT = "split"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


@dataclass
class Transaction:
    """A portfolio transaction."""
    id: str
    timestamp: str
    type: str
    symbol: str
    quantity: float
    price: float
    total: float
    currency: str = "USD"
    exchange_rate: float = 1.0
    base_total: float = 0  # Total in base currency
    notes: str = ""
    tax_lot_id: str = ""  # Link to tax lot
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        return cls(**data)


@dataclass
class Position:
    """A portfolio position with full details."""
    symbol: str
    quantity: float
    avg_cost: float
    total_cost: float
    currency: str = "USD"
    exchange: str = ""
    current_price: float = 0
    current_value: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    # Tax lot info
    num_lots: int = 0
    oldest_lot_date: str = ""
    # Base currency values
    base_cost: float = 0
    base_value: float = 0
    base_pnl: float = 0
    # Dividend info
    total_dividends: float = 0
    dividend_yield: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortfolioData:
    """Portfolio data structure."""
    name: str
    cash: Dict[str, float]  # currency -> amount
    positions: Dict[str, Dict]  # symbol -> position data
    transactions: List[Dict]
    created: str
    initial_value: float
    base_currency: str
    realized_pnl: float = 0
    total_dividends: float = 0
    total_franking_credits: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PortfolioData':
        return cls(**data)


class IntegratedPortfolioManager:
    """
    Full-featured portfolio manager with integrated tax, dividend, and currency tracking.
    """
    
    def __init__(self, base_currency: str = "AUD", storage_path: str = None, 
                 accounting_method: str = "FIFO"):
        """
        Initialize the integrated portfolio manager.
        
        Args:
            base_currency: Base currency for reporting (AUD, USD, etc.)
            storage_path: Custom storage path
            accounting_method: Tax lot method (FIFO, LIFO, HIFO, AVERAGE)
        """
        self.base_currency = base_currency.upper()
        
        # Storage
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".trading_platform" / "portfolios_integrated.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize sub-managers
        if TaxLotTracker:
            from trading.tax_lots import AccountingMethod
            try:
                method_enum = AccountingMethod[accounting_method.upper()]
            except (KeyError, AttributeError):
                method_enum = AccountingMethod.FIFO
            
            self.tax_tracker = TaxLotTracker(
                method=method_enum,
                country="AU" if base_currency == "AUD" else "US"
            )
        else:
            self.tax_tracker = None
        
        self.dividend_tracker = DividendTracker() if DividendTracker else None
        
        self.currency_manager = CurrencyManager(
            base_currency=base_currency
        ) if CurrencyManager else None
        
        # Load portfolios
        self.portfolios: Dict[str, PortfolioData] = self._load()
        self._next_tx_id = self._get_max_tx_id() + 1
    
    def _load(self) -> Dict[str, PortfolioData]:
        """Load portfolios from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    return {k: PortfolioData.from_dict(v) for k, v in data.items()}
            except Exception as e:
                print(f"Warning: Could not load portfolios: {e}")
        
        # Create default portfolio
        return {
            "default": PortfolioData(
                name="Default Portfolio",
                cash={self.base_currency: 100000.0},
                positions={},
                transactions=[],
                created=datetime.now().isoformat(),
                initial_value=100000.0,
                base_currency=self.base_currency,
                realized_pnl=0,
                total_dividends=0,
                total_franking_credits=0
            )
        }
    
    def _save(self):
        """Save portfolios to disk."""
        with open(self.storage_path, 'w') as f:
            json.dump({k: v.to_dict() for k, v in self.portfolios.items()}, f, indent=2)
    
    def _get_max_tx_id(self) -> int:
        """Get maximum transaction ID."""
        max_id = 0
        for p in self.portfolios.values():
            for tx in p.transactions:
                try:
                    tx_num = int(tx["id"].split("_")[1])
                    max_id = max(max_id, tx_num)
                except Exception:
                    pass
        return max_id
    
    def _generate_tx_id(self) -> str:
        """Generate unique transaction ID."""
        tx_id = f"tx_{self._next_tx_id}"
        self._next_tx_id += 1
        return tx_id
    
    def _get_exchange_rate(self, from_currency: str, to_currency: str = None) -> float:
        """Get exchange rate."""
        to_currency = to_currency or self.base_currency
        if from_currency == to_currency:
            return 1.0
        
        if self.currency_manager:
            try:
                return self.currency_manager.get_rate(from_currency, to_currency)
            except Exception:
                pass
        
        # Fallback rates
        fallback_rates = {
            ("USD", "AUD"): 1.55,
            ("AUD", "USD"): 0.65,
            ("GBP", "AUD"): 1.95,
            ("EUR", "AUD"): 1.65,
        }
        return fallback_rates.get((from_currency, to_currency), 1.0)
    
    def _detect_exchange(self, symbol: str) -> Tuple[str, str]:
        """Detect exchange and currency from symbol."""
        if "." in symbol:
            suffix = symbol.split(".")[-1].upper()
            exchange_map = {
                "AX": ("ASX", "AUD"),
                "L": ("LSE", "GBP"),
                "TO": ("TSX", "CAD"),
                "HK": ("HKEX", "HKD"),
                "T": ("TSE", "JPY"),
                "PA": ("EPA", "EUR"),
                "DE": ("FRA", "EUR"),
            }
            return exchange_map.get(suffix, ("", "USD"))
        return ("NYSE/NASDAQ", "USD")
    
    # =========================================================================
    # PORTFOLIO MANAGEMENT
    # =========================================================================
    
    def create(self, name: str, initial_cash: float = 100000.0, 
               currency: str = None) -> bool:
        """Create a new portfolio."""
        key = name.lower().replace(" ", "_")
        if key in self.portfolios:
            return False
        
        currency = currency or self.base_currency
        
        self.portfolios[key] = PortfolioData(
            name=name,
            cash={currency: initial_cash},
            positions={},
            transactions=[],
            created=datetime.now().isoformat(),
            initial_value=initial_cash,
            base_currency=self.base_currency,
            realized_pnl=0,
            total_dividends=0,
            total_franking_credits=0
        )
        self._save()
        return True
    
    def delete(self, name: str) -> bool:
        """Delete a portfolio."""
        key = name.lower().replace(" ", "_")
        if key in self.portfolios and key != "default":
            del self.portfolios[key]
            self._save()
            return True
        return False
    
    def reset(self, name: str, initial_cash: float = 100000.0) -> bool:
        """Reset a portfolio to initial state (clear positions, transactions, reset cash)."""
        key = name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return False
        
        portfolio = self.portfolios[key]
        
        # Reset all fields - use USD for simplicity (most common trading currency)
        portfolio.positions = {}
        portfolio.transactions = []
        portfolio.cash = {'USD': initial_cash}  # All USD for simplicity
        portfolio.realized_pnl = 0
        portfolio.total_dividends = 0
        portfolio.total_franking_credits = 0
        portfolio.initial_value = initial_cash
        
        self._save()
        return True
    
    def list_portfolios(self) -> List[Dict]:
        """List all portfolios."""
        results = []
        for k, v in self.portfolios.items():
            total_cash = sum(v.cash.values())
            results.append({
                "key": k,
                "name": v.name,
                "cash": total_cash,
                "cash_breakdown": v.cash,
                "positions": len(v.positions),
                "base_currency": v.base_currency,
                "created": v.created
            })
        return results
    
    # =========================================================================
    # BUY / SELL WITH TAX LOT INTEGRATION
    # =========================================================================
    
    def buy(self, portfolio_name: str, symbol: str, quantity: float, price: float,
            currency: str = None, date: str = None, notes: str = "",
            commission: float = 0) -> Optional[Transaction]:
        """
        Buy shares with automatic tax lot creation.
        
        Args:
            portfolio_name: Portfolio to use
            symbol: Stock symbol
            quantity: Number of shares
            price: Price per share
            currency: Transaction currency (auto-detected if not provided)
            date: Purchase date (defaults to now)
            notes: Optional notes
            commission: Trading commission
        
        Returns:
            Transaction object or None if failed
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        symbol = symbol.upper().strip()
        
        # Detect currency and exchange
        exchange, default_currency = self._detect_exchange(symbol)
        currency = currency or default_currency
        
        # Calculate totals
        total = quantity * price + commission
        exchange_rate = self._get_exchange_rate(currency, self.base_currency)
        base_total = total * exchange_rate
        
        # Check cash - try multiple sources
        if currency not in portfolio.cash:
            portfolio.cash[currency] = 0
        
        cash_deducted = False
        
        # First try: use the transaction currency directly
        if portfolio.cash[currency] >= total:
            portfolio.cash[currency] -= total
            cash_deducted = True
        
        # Second try: use base currency with conversion
        if not cash_deducted:
            base_cash = portfolio.cash.get(self.base_currency, 0)
            if base_cash >= base_total:
                portfolio.cash[self.base_currency] -= base_total
                cash_deducted = True
        
        # Third try: use any available currency with conversion
        if not cash_deducted:
            for avail_currency, avail_amount in list(portfolio.cash.items()):
                if avail_amount <= 0:
                    continue
                # Convert required amount to this currency
                rate_to_avail = self._get_exchange_rate(currency, avail_currency)
                required_in_avail = total * rate_to_avail
                if avail_amount >= required_in_avail:
                    portfolio.cash[avail_currency] -= required_in_avail
                    cash_deducted = True
                    break
        
        if not cash_deducted:
            return None  # Insufficient funds
        
        # Create transaction
        date = date or datetime.now().isoformat()
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=date,
            type=TransactionType.BUY.value,
            symbol=symbol,
            quantity=quantity,
            price=price,
            total=total,
            currency=currency,
            exchange_rate=exchange_rate,
            base_total=base_total,
            notes=notes
        )
        
        # Create tax lot
        if self.tax_tracker:
            lot = self.tax_tracker.buy(
                symbol=symbol,
                shares=quantity,
                price=price,
                date=date[:10] if len(date) > 10 else date,
                commission=commission
            )
            tx.tax_lot_id = lot.id
        
        # Update position
        if symbol in portfolio.positions:
            pos = portfolio.positions[symbol]
            new_qty = pos["quantity"] + quantity
            new_cost = pos["total_cost"] + total
            pos["quantity"] = new_qty
            pos["total_cost"] = new_cost
            pos["avg_cost"] = new_cost / new_qty
            pos["base_cost"] = pos.get("base_cost", 0) + base_total
            pos["num_lots"] = pos.get("num_lots", 0) + 1
        else:
            portfolio.positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "avg_cost": price,
                "total_cost": total,
                "currency": currency,
                "exchange": exchange,
                "base_cost": base_total,
                "num_lots": 1,
                "first_purchase": date,
                "total_dividends": 0,
            }
        
        # Record transaction
        portfolio.transactions.append(tx.to_dict())
        self._save()
        
        return tx
    
    def sell(self, portfolio_name: str, symbol: str, quantity: float, price: float,
             currency: str = None, date: str = None, notes: str = "",
             commission: float = 0, method: str = None) -> Optional[Dict]:
        """
        Sell shares with tax lot accounting.
        
        Args:
            portfolio_name: Portfolio to use
            symbol: Stock symbol
            quantity: Number of shares to sell
            price: Sale price per share
            currency: Transaction currency
            date: Sale date
            notes: Optional notes
            commission: Trading commission
            method: Override accounting method (FIFO, LIFO, HIFO)
        
        Returns:
            Dict with sale details and tax info, or None if failed
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        symbol = symbol.upper().strip()
        
        if symbol not in portfolio.positions:
            return None
        
        pos = portfolio.positions[symbol]
        if pos["quantity"] < quantity:
            return None  # Insufficient shares
        
        # Get currency
        exchange, default_currency = self._detect_exchange(symbol)
        currency = currency or pos.get("currency", default_currency)
        
        # Calculate totals
        gross_total = quantity * price
        total = gross_total - commission
        exchange_rate = self._get_exchange_rate(currency, self.base_currency)
        base_total = total * exchange_rate
        
        date = date or datetime.now().isoformat()
        
        # Calculate gain using tax lots
        sale_result = None
        gain = 0
        discounted_gain = 0
        
        if self.tax_tracker:
            sale_result = self.tax_tracker.sell(
                symbol=symbol,
                shares=quantity,
                price=price,
                date=date[:10] if len(date) > 10 else date,
                method=method,
                commission=commission
            )
            if sale_result:
                gain = sale_result.total_gain
                discounted_gain = sale_result.discounted_gain
        else:
            # Simple calculation if no tax tracker
            cost_basis = pos["avg_cost"] * quantity
            gain = total - cost_basis
            discounted_gain = gain  # No discount calculation
        
        # Create transaction
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=date,
            type=TransactionType.SELL.value,
            symbol=symbol,
            quantity=quantity,
            price=price,
            total=total,
            currency=currency,
            exchange_rate=exchange_rate,
            base_total=base_total,
            notes=notes
        )
        
        # Update cash
        if currency not in portfolio.cash:
            portfolio.cash[currency] = 0
        portfolio.cash[currency] += total
        
        # Update position
        new_qty = pos["quantity"] - quantity
        if new_qty <= 0.0001:  # Close position
            del portfolio.positions[symbol]
        else:
            cost_sold = pos["avg_cost"] * quantity
            pos["quantity"] = new_qty
            pos["total_cost"] -= cost_sold
            pos["base_cost"] = pos.get("base_cost", 0) - (cost_sold * exchange_rate)
        
        # Update realized P&L
        portfolio.realized_pnl += discounted_gain
        
        # Record transaction
        portfolio.transactions.append(tx.to_dict())
        self._save()
        
        return {
            "transaction": tx,
            "gross_proceeds": gross_total,
            "net_proceeds": total,
            "commission": commission,
            "gain": gain,
            "discounted_gain": discounted_gain,
            "is_long_term": sale_result.long_term_gain > 0 if sale_result else False,
            "sale_result": sale_result,
        }
    
    # =========================================================================
    # DIVIDEND TRACKING
    # =========================================================================
    
    def record_dividend(self, portfolio_name: str, symbol: str, amount: float,
                       shares: float = None, date: str = None,
                       franking_pct: float = 0, withholding_pct: float = 0,
                       currency: str = None, reinvest: bool = False) -> Optional[Dict]:
        """
        Record a dividend payment.
        
        Args:
            portfolio_name: Portfolio
            symbol: Stock symbol
            amount: Gross dividend amount
            shares: Number of shares (for yield calculation)
            date: Payment date
            franking_pct: Australian franking percentage (0-100)
            withholding_pct: Foreign withholding tax percentage
            currency: Dividend currency
            reinvest: Whether to reinvest (DRIP)
        
        Returns:
            Dict with dividend details
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        symbol = symbol.upper().strip()
        
        # Get shares from position if not provided
        if shares is None and symbol in portfolio.positions:
            shares = portfolio.positions[symbol]["quantity"]
        shares = shares or 0
        
        # Get currency
        exchange, default_currency = self._detect_exchange(symbol)
        currency = currency or default_currency
        
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Record in dividend tracker
        dividend = None
        franking_credit = 0
        net_amount = amount
        
        if self.dividend_tracker:
            dividend = self.dividend_tracker.add_dividend(
                symbol=symbol,
                amount=amount,
                shares=shares,
                ex_date=date,
                pay_date=date,
                franking_pct=franking_pct,
                withholding_tax_pct=withholding_pct
            )
            if dividend:
                franking_credit = dividend.franking_credit
                net_amount = dividend.net_amount
        else:
            # Simple calculation
            if franking_pct > 0:
                franking_credit = amount * (franking_pct / 100) * (30 / 70)
            if withholding_pct > 0:
                net_amount = amount * (1 - withholding_pct / 100)
        
        # Convert to base currency
        exchange_rate = self._get_exchange_rate(currency, self.base_currency)
        base_amount = net_amount * exchange_rate
        base_franking = franking_credit * exchange_rate
        
        # Create transaction
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=date,
            type=TransactionType.DIVIDEND.value,
            symbol=symbol,
            quantity=shares,
            price=amount / shares if shares > 0 else amount,
            total=net_amount,
            currency=currency,
            exchange_rate=exchange_rate,
            base_total=base_amount,
            notes=f"Franking: {franking_pct}%, WHT: {withholding_pct}%"
        )
        
        # Update cash or reinvest
        if reinvest and symbol in portfolio.positions:
            # Get current price (simplified - would normally fetch real price)
            pos = portfolio.positions[symbol]
            price = pos.get("current_price", pos["avg_cost"])
            if price > 0:
                new_shares = net_amount / price
                self.buy(portfolio_name, symbol, new_shares, price, currency, date,
                        notes="DRIP reinvestment")
        else:
            if currency not in portfolio.cash:
                portfolio.cash[currency] = 0
            portfolio.cash[currency] += net_amount
        
        # Update portfolio totals
        portfolio.total_dividends += base_amount
        portfolio.total_franking_credits += base_franking
        
        # Update position dividend total
        if symbol in portfolio.positions:
            portfolio.positions[symbol]["total_dividends"] = \
                portfolio.positions[symbol].get("total_dividends", 0) + net_amount
        
        # Record transaction
        portfolio.transactions.append(tx.to_dict())
        self._save()
        
        return {
            "transaction": tx,
            "gross_amount": amount,
            "net_amount": net_amount,
            "franking_credit": franking_credit,
            "withholding_tax": amount * withholding_pct / 100 if withholding_pct else 0,
            "base_amount": base_amount,
            "reinvested": reinvest,
            "dividend": dividend,
        }
    
    # =========================================================================
    # CASH MANAGEMENT
    # =========================================================================
    
    def deposit(self, portfolio_name: str, amount: float, currency: str = None,
                notes: str = "") -> Optional[Transaction]:
        """Deposit cash into portfolio."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        currency = currency or self.base_currency
        
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=datetime.now().isoformat(),
            type=TransactionType.DEPOSIT.value,
            symbol="CASH",
            quantity=1,
            price=amount,
            total=amount,
            currency=currency,
            exchange_rate=self._get_exchange_rate(currency, self.base_currency),
            base_total=amount * self._get_exchange_rate(currency, self.base_currency),
            notes=notes
        )
        
        if currency not in portfolio.cash:
            portfolio.cash[currency] = 0
        portfolio.cash[currency] += amount
        
        portfolio.transactions.append(tx.to_dict())
        self._save()
        return tx
    
    def withdraw(self, portfolio_name: str, amount: float, currency: str = None,
                 notes: str = "") -> Optional[Transaction]:
        """Withdraw cash from portfolio."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        
        # If currency specified, try that first
        if currency and portfolio.cash.get(currency, 0) >= amount:
            withdraw_currency = currency
            withdraw_amount = amount
        else:
            # Find a currency with enough balance
            withdraw_currency = None
            withdraw_amount = amount
            
            # First try the specified currency or base currency
            for try_currency in [currency, self.base_currency, 'USD', 'AUD']:
                if try_currency and portfolio.cash.get(try_currency, 0) >= amount:
                    withdraw_currency = try_currency
                    break
            
            # If still not found, try any currency with enough balance
            if not withdraw_currency:
                for curr, bal in portfolio.cash.items():
                    if bal >= amount:
                        withdraw_currency = curr
                        break
            
            # If still not found, try converting from any currency
            if not withdraw_currency:
                target_currency = currency or self.base_currency
                for curr, bal in portfolio.cash.items():
                    if bal <= 0:
                        continue
                    rate = self._get_exchange_rate(target_currency, curr)
                    needed_in_curr = amount * rate
                    if bal >= needed_in_curr:
                        withdraw_currency = curr
                        withdraw_amount = needed_in_curr
                        break
        
        if not withdraw_currency:
            return None  # Insufficient funds in any currency
        
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=datetime.now().isoformat(),
            type=TransactionType.WITHDRAW.value,
            symbol="CASH",
            quantity=1,
            price=withdraw_amount,
            total=withdraw_amount,
            currency=withdraw_currency,
            exchange_rate=self._get_exchange_rate(withdraw_currency, self.base_currency),
            base_total=withdraw_amount * self._get_exchange_rate(withdraw_currency, self.base_currency),
            notes=notes
        )
        
        portfolio.cash[withdraw_currency] -= withdraw_amount
        portfolio.transactions.append(tx.to_dict())
        self._save()
        return tx
    
    def convert_currency(self, portfolio_name: str, from_currency: str, 
                        to_currency: str, amount: float) -> Optional[Dict]:
        """Convert cash between currencies."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return None
        
        portfolio = self.portfolios[key]
        
        if portfolio.cash.get(from_currency, 0) < amount:
            return None
        
        rate = self._get_exchange_rate(from_currency, to_currency)
        converted = amount * rate
        
        portfolio.cash[from_currency] -= amount
        if to_currency not in portfolio.cash:
            portfolio.cash[to_currency] = 0
        portfolio.cash[to_currency] += converted
        
        # Record FX transaction
        tx = Transaction(
            id=self._generate_tx_id(),
            timestamp=datetime.now().isoformat(),
            type=TransactionType.FX_CONVERSION.value,
            symbol=f"{from_currency}/{to_currency}",
            quantity=amount,
            price=rate,
            total=converted,
            currency=to_currency,
            exchange_rate=rate,
            base_total=converted * self._get_exchange_rate(to_currency, self.base_currency),
            notes=f"Converted {amount} {from_currency} to {converted:.2f} {to_currency}"
        )
        
        portfolio.transactions.append(tx.to_dict())
        self._save()
        
        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "from_amount": amount,
            "to_amount": converted,
            "rate": rate,
            "transaction": tx
        }
    
    # =========================================================================
    # PRICE UPDATES
    # =========================================================================
    
    def update_prices(self, portfolio_name: str, prices: Dict[str, float]):
        """
        Update current prices for positions.
        
        Args:
            portfolio_name: Portfolio to update
            prices: Dict of symbol -> current price
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return
        
        portfolio = self.portfolios[key]
        
        for symbol, pos in portfolio.positions.items():
            if symbol in prices:
                price = prices[symbol]
                pos["current_price"] = price
                pos["current_value"] = pos["quantity"] * price
                pos["unrealized_pnl"] = pos["current_value"] - pos["total_cost"]
                pos["unrealized_pnl_pct"] = (pos["unrealized_pnl"] / pos["total_cost"] * 100) \
                    if pos["total_cost"] > 0 else 0
                
                # Update base currency values
                exchange_rate = self._get_exchange_rate(
                    pos.get("currency", "USD"), 
                    self.base_currency
                )
                pos["base_value"] = pos["current_value"] * exchange_rate
                pos["base_pnl"] = pos["base_value"] - pos.get("base_cost", pos["total_cost"] * exchange_rate)
        
        self._save()
    
    def fetch_and_update_prices(self, portfolio_name: str) -> Dict[str, float]:
        """Fetch current prices and update portfolio."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return {}
        
        portfolio = self.portfolios[key]
        prices = {}
        
        try:
            from trading.data_sources import DataFetcher
            fetcher = DataFetcher(verbose=False)
            
            for symbol in portfolio.positions.keys():
                quote, source = fetcher.get_quote(symbol)
                if quote and quote.get("price"):
                    prices[symbol] = quote["price"]
        except Exception as e:
            print(f"Warning: Could not fetch prices: {e}")
        
        if prices:
            self.update_prices(portfolio_name, prices)
        
        return prices
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_positions(self, portfolio_name: str) -> List[Position]:
        """Get all positions in a portfolio."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return []
        
        positions = []
        for symbol, data in self.portfolios[key].positions.items():
            # Get tax lot info
            num_lots = 0
            oldest_lot = ""
            if self.tax_tracker:
                lots_dict = self.tax_tracker.get_lots(symbol)
                lots = lots_dict.get(symbol, []) if isinstance(lots_dict, dict) else lots_dict
                if lots:
                    num_lots = len(lots)
                    oldest_lot = min(lot.purchase_date for lot in lots)
            
            positions.append(Position(
                symbol=data["symbol"],
                quantity=data["quantity"],
                avg_cost=data["avg_cost"],
                total_cost=data["total_cost"],
                currency=data.get("currency", "USD"),
                exchange=data.get("exchange", ""),
                current_price=data.get("current_price", 0),
                current_value=data.get("current_value", 0),
                unrealized_pnl=data.get("unrealized_pnl", 0),
                unrealized_pnl_pct=data.get("unrealized_pnl_pct", 0),
                num_lots=num_lots,
                oldest_lot_date=oldest_lot,
                base_cost=data.get("base_cost", 0),
                base_value=data.get("base_value", 0),
                base_pnl=data.get("base_pnl", 0),
                total_dividends=data.get("total_dividends", 0),
            ))
        
        return positions
    
    def get_summary(self, portfolio_name: str, include_tax: bool = True) -> Dict:
        """
        Get comprehensive portfolio summary.
        
        Args:
            portfolio_name: Portfolio name
            include_tax: Include tax-related calculations
        
        Returns:
            Dict with full summary
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return {}
        
        portfolio = self.portfolios[key]
        
        # Calculate position totals (in original currencies)
        total_cost = sum(p["total_cost"] for p in portfolio.positions.values())
        total_value = sum(p.get("current_value", p["total_cost"]) for p in portfolio.positions.values())
        unrealized_pnl = total_value - total_cost
        
        # Cash totals - just sum all cash without conversion for display
        # This avoids fake "gains" from currency fluctuations
        total_cash = sum(portfolio.cash.values())
        
        # For a simple portfolio (USD only), don't do currency conversion
        # This prevents showing fake gains from AUD/USD rate changes
        currencies_used = set(portfolio.cash.keys())
        for p in portfolio.positions.values():
            currencies_used.add(p.get("currency", "USD"))
        
        # If single currency portfolio, keep it simple
        if len(currencies_used) <= 1 or currencies_used == {'USD'}:
            total_portfolio_value = total_cash + total_value
            positions_value_base = total_value
            total_cash_base = total_cash
        else:
            # Multi-currency: convert to base currency
            total_cash_base = 0
            for currency, amount in portfolio.cash.items():
                rate = self._get_exchange_rate(currency, self.base_currency)
                total_cash_base += amount * rate
            
            positions_value_base = sum(
                p.get("base_value", p["total_cost"] * self._get_exchange_rate(p.get("currency", "USD"), self.base_currency))
                for p in portfolio.positions.values()
            )
            total_portfolio_value = total_cash_base + positions_value_base
        
        # Calculate net invested (initial + deposits - withdrawals)
        # Use base_total for transactions to match how they were recorded
        net_deposits = portfolio.initial_value
        for tx in portfolio.transactions:
            tx_type = tx.get('type', '').lower()
            # Use base_total if available, otherwise use total
            amount = abs(float(tx.get('base_total', 0) or tx.get('total', 0) or tx.get('amount', 0) or 0))
            # For single currency, just use the raw total
            if len(currencies_used) <= 1:
                amount = abs(float(tx.get('total', 0) or tx.get('amount', 0) or 0))
            if tx_type == 'deposit':
                net_deposits += amount
            elif tx_type == 'withdraw':
                net_deposits -= amount
        
        # Investment return = current value vs what was put in
        investment_return = total_portfolio_value - net_deposits
        investment_return_pct = (investment_return / net_deposits * 100) if net_deposits > 0 else 0
        
        summary = {
            "name": portfolio.name,
            "base_currency": self.base_currency,
            "display_currency": "USD" if currencies_used == {'USD'} else self.base_currency,
            "cash": portfolio.cash,
            "total_cash_base": total_cash_base,
            "positions_value": total_value,
            "positions_value_base": positions_value_base,
            "total_value": total_portfolio_value,
            "initial_value": portfolio.initial_value,
            "net_deposits": net_deposits,
            "total_cost": total_cost,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": portfolio.realized_pnl,
            "total_pnl": unrealized_pnl + portfolio.realized_pnl,
            "total_return": investment_return,
            "total_return_pct": investment_return_pct,
            "positions_count": len(portfolio.positions),
            "transactions_count": len(portfolio.transactions),
            "total_dividends": portfolio.total_dividends,
            "total_franking_credits": portfolio.total_franking_credits,
            "created": portfolio.created,
        }
        
        # Tax calculations
        if include_tax and self.tax_tracker:
            # Get unrealized gains with CGT discount info
            unrealized_gains = {}
            total_unrealized_discounted = 0
            
            for symbol, pos in portfolio.positions.items():
                current_price = pos.get("current_price", 0)
                if current_price > 0:
                    gains = self.tax_tracker.get_unrealized_gains(symbol, current_price)
                    unrealized_gains[symbol] = gains
                    total_unrealized_discounted += gains.get("discounted_gain", 0)
            
            summary["tax"] = {
                "unrealized_gains_by_symbol": unrealized_gains,
                "total_unrealized_discounted": total_unrealized_discounted,
                "realized_gains_ytd": portfolio.realized_pnl,
                "franking_credits_ytd": portfolio.total_franking_credits,
            }
        
        return summary
    
    def get_transactions(self, portfolio_name: str, limit: int = 50,
                        tx_type: str = None) -> List[Transaction]:
        """Get transactions with optional type filter."""
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return []
        
        txs = self.portfolios[key].transactions
        
        if tx_type:
            txs = [tx for tx in txs if tx["type"] == tx_type]
        
        txs = txs[-limit:]
        return [Transaction.from_dict(tx) for tx in reversed(txs)]
    
    def generate_tax_report(self, portfolio_name: str, year: int = None) -> Dict:
        """
        Generate tax report for Australian CGT.
        
        Args:
            portfolio_name: Portfolio name
            year: Tax year (defaults to current FY)
        
        Returns:
            Dict with comprehensive tax report
        """
        key = portfolio_name.lower().replace(" ", "_")
        if key not in self.portfolios:
            return {}
        
        portfolio = self.portfolios[key]
        
        # Default to current financial year
        if year is None:
            now = datetime.now()
            year = now.year if now.month >= 7 else now.year - 1
        
        fy_start = f"{year}-07-01"
        fy_end = f"{year + 1}-06-30"
        
        report = {
            "financial_year": f"{year}/{year + 1}",
            "portfolio": portfolio.name,
            "base_currency": self.base_currency,
            "generated": datetime.now().isoformat(),
        }
        
        # Capital gains from tax tracker
        if self.tax_tracker:
            tax_report = self.tax_tracker.tax_report(year)
            report["capital_gains"] = tax_report
        
        # Dividend income
        if self.dividend_tracker:
            div_report = self.dividend_tracker.annual_report(year)
            report["dividends"] = div_report
        else:
            # Calculate from transactions
            dividend_txs = [
                tx for tx in portfolio.transactions
                if tx["type"] == "dividend" and fy_start <= tx["timestamp"][:10] <= fy_end
            ]
            report["dividends"] = {
                "total_gross": sum(tx["total"] for tx in dividend_txs),
                "transaction_count": len(dividend_txs),
            }
        
        # Summary
        report["summary"] = {
            "total_capital_gains": report.get("capital_gains", {}).get("total_discounted_gain", 0),
            "total_dividend_income": report.get("dividends", {}).get("total_net", 0),
            "total_franking_credits": report.get("dividends", {}).get("total_franking", 0),
            "total_taxable_income": (
                report.get("capital_gains", {}).get("total_discounted_gain", 0) +
                report.get("dividends", {}).get("total_grossed_up", 0)
            ),
        }
        
        return report
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def print_summary(self, portfolio_name: str = "default"):
        """Print formatted portfolio summary."""
        summary = self.get_summary(portfolio_name)
        
        if not summary:
            print(f"Portfolio not found: {portfolio_name}")
            return
        
        print(f"\n{'='*60}")
        print(f"Portfolio: {summary['name']}")
        print(f"{'='*60}")
        
        print(f"\nCASH HOLDINGS")
        print("-"*40)
        for currency, amount in summary['cash'].items():
            if amount > 0:
                print(f"   {currency}: {amount:>15,.2f}")
        print(f"   {'─'*30}")
        print(f"   Total ({self.base_currency}): {summary['total_cash_base']:>10,.2f}")
        
        print(f"\nPOSITIONS")
        print("-"*40)
        positions = self.get_positions(portfolio_name)
        if positions:
            for p in positions:
                pnl_str = f"{p.unrealized_pnl:+,.2f}" if p.current_price > 0 else "N/A"
                print(f"   {p.symbol:<10} {p.quantity:>8.2f} @ {p.avg_cost:>8.2f}  P&L: {pnl_str}")
        else:
            print("   (no positions)")
        
        print(f"\nSUMMARY")
        print("-"*40)
        print(f"   Positions Value:   {summary['positions_value_base']:>12,.2f} {self.base_currency}")
        print(f"   Cash:              {summary['total_cash_base']:>12,.2f} {self.base_currency}")
        print(f"   {'─'*35}")
        print(f"   Total Value:       {summary['total_value']:>12,.2f} {self.base_currency}")
        print(f"   Initial Value:     {summary['initial_value']:>12,.2f} {self.base_currency}")
        
        print(f"\n💵 PERFORMANCE")
        print("-"*40)
        print(f"   Unrealized P&L:    {summary['unrealized_pnl']:>+12,.2f}")
        print(f"   Realized P&L:      {summary['realized_pnl']:>+12,.2f}")
        print(f"   Dividends:         {summary['total_dividends']:>+12,.2f}")
        print(f"   {'─'*35}")
        print(f"   Total Return:      {summary['total_return']:>+12,.2f} ({summary['total_return_pct']:+.2f}%)")
        
        if summary.get('total_franking_credits', 0) > 0:
            print(f"\n🏛️ TAX")
            print("-"*40)
            print(f"   Franking Credits:  {summary['total_franking_credits']:>12,.2f}")
        
        print(f"\n{'='*60}")
    
    def print_positions(self, portfolio_name: str = "default"):
        """Print detailed positions table."""
        positions = self.get_positions(portfolio_name)
        
        if not positions:
            print(f"No positions in {portfolio_name}")
            return
        
        print(f"\n{'='*90}")
        print(f"POSITIONS - {portfolio_name}")
        print(f"{'='*90}")
        print(f"{'Symbol':<10} {'Qty':>8} {'Avg Cost':>10} {'Price':>10} {'Value':>12} {'P&L':>12} {'P&L%':>8}")
        print("-"*90)
        
        total_cost = 0
        total_value = 0
        total_pnl = 0
        
        for p in positions:
            price_str = f"{p.current_price:,.2f}" if p.current_price > 0 else "N/A"
            value_str = f"{p.current_value:,.2f}" if p.current_value > 0 else "N/A"
            pnl_str = f"{p.unrealized_pnl:+,.2f}" if p.current_price > 0 else "N/A"
            pnl_pct_str = f"{p.unrealized_pnl_pct:+.2f}%" if p.current_price > 0 else "N/A"
            
            print(f"{p.symbol:<10} {p.quantity:>8.2f} {p.avg_cost:>10.2f} {price_str:>10} {value_str:>12} {pnl_str:>12} {pnl_pct_str:>8}")
            
            total_cost += p.total_cost
            total_value += p.current_value
            total_pnl += p.unrealized_pnl
        
        print("-"*90)
        pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        print(f"{'TOTAL':<10} {'':<8} {total_cost:>10.2f} {'':<10} {total_value:>12,.2f} {total_pnl:>+12,.2f} {pnl_pct:>+7.2f}%")
        print(f"{'='*90}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_portfolio_manager(base_currency: str = "AUD") -> IntegratedPortfolioManager:
    """Create a portfolio manager with default settings."""
    return IntegratedPortfolioManager(base_currency=base_currency)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Portfolio Manager")
    parser.add_argument("--currency", "-c", default="AUD", help="Base currency")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # List
    subparsers.add_parser("list", help="List portfolios")
    
    # Show
    show_p = subparsers.add_parser("show", help="Show portfolio summary")
    show_p.add_argument("name", nargs="?", default="default")
    
    # Positions
    pos_p = subparsers.add_parser("positions", help="Show positions")
    pos_p.add_argument("name", nargs="?", default="default")
    
    # Buy
    buy_p = subparsers.add_parser("buy", help="Buy shares")
    buy_p.add_argument("symbol")
    buy_p.add_argument("quantity", type=float)
    buy_p.add_argument("price", type=float)
    buy_p.add_argument("-p", "--portfolio", default="default")
    buy_p.add_argument("--currency", default=None)
    
    # Sell
    sell_p = subparsers.add_parser("sell", help="Sell shares")
    sell_p.add_argument("symbol")
    sell_p.add_argument("quantity", type=float)
    sell_p.add_argument("price", type=float)
    sell_p.add_argument("-p", "--portfolio", default="default")
    
    # Dividend
    div_p = subparsers.add_parser("dividend", help="Record dividend")
    div_p.add_argument("symbol")
    div_p.add_argument("amount", type=float)
    div_p.add_argument("-p", "--portfolio", default="default")
    div_p.add_argument("--franking", type=float, default=0)
    
    # Tax report
    tax_p = subparsers.add_parser("tax", help="Generate tax report")
    tax_p.add_argument("-p", "--portfolio", default="default")
    tax_p.add_argument("--year", type=int, default=None)
    
    # Update prices
    update_p = subparsers.add_parser("update", help="Update prices")
    update_p.add_argument("name", nargs="?", default="default")
    
    args = parser.parse_args()
    pm = IntegratedPortfolioManager(base_currency=args.currency)
    
    if args.command == "list":
        portfolios = pm.list_portfolios()
        print("\nPortfolios:")
        for p in portfolios:
            print(f"   • {p['name']} ({p['key']}): {p['positions']} positions")
    
    elif args.command == "show":
        pm.print_summary(args.name)
    
    elif args.command == "positions":
        pm.print_positions(args.name)
    
    elif args.command == "buy":
        tx = pm.buy(args.portfolio, args.symbol, args.quantity, args.price, args.currency)
        if tx:
            print(f"✓ Bought {tx.quantity} {tx.symbol} @ ${tx.price:.2f}")
        else:
            print("Failed to execute buy")
    
    elif args.command == "sell":
        result = pm.sell(args.portfolio, args.symbol, args.quantity, args.price)
        if result:
            print(f"✓ Sold {args.quantity} {args.symbol} @ ${args.price:.2f}")
            print(f"   Gain: ${result['gain']:+,.2f}")
            print(f"   Discounted Gain: ${result['discounted_gain']:+,.2f}")
        else:
            print("Failed to execute sell")
    
    elif args.command == "dividend":
        result = pm.record_dividend(args.portfolio, args.symbol, args.amount,
                                    franking_pct=args.franking)
        if result:
            print(f"✓ Recorded dividend: ${args.amount:.2f} from {args.symbol}")
            if result['franking_credit'] > 0:
                print(f"   Franking credit: ${result['franking_credit']:.2f}")
        else:
            print("Failed to record dividend")
    
    elif args.command == "tax":
        report = pm.generate_tax_report(args.portfolio, args.year)
        if report:
            print(f"\nTax Report - FY {report['financial_year']}")
            print("="*50)
            summary = report.get('summary', {})
            print(f"   Capital Gains:     ${summary.get('total_capital_gains', 0):>12,.2f}")
            print(f"   Dividend Income:   ${summary.get('total_dividend_income', 0):>12,.2f}")
            print(f"   Franking Credits:  ${summary.get('total_franking_credits', 0):>12,.2f}")
            print(f"   ─────────────────────────────────────")
            print(f"   Total Taxable:     ${summary.get('total_taxable_income', 0):>12,.2f}")
    
    elif args.command == "update":
        prices = pm.fetch_and_update_prices(args.name)
        if prices:
            print(f"✓ Updated {len(prices)} prices")
            for symbol, price in prices.items():
                print(f"   {symbol}: ${price:.2f}")
        else:
            print("No prices updated")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
