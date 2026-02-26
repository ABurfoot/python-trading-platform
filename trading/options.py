#!/usr/bin/env python3
"""
Options Analysis Module
========================
Options pricing, Greeks calculation, and strategy analysis.

Features:
- Black-Scholes option pricing
- Greeks: Delta, Gamma, Theta, Vega, Rho
- Implied volatility calculation
- Options chain analysis
- Strategy payoff diagrams
- Put-Call parity

Usage:
    from trading.options import OptionsAnalyzer, BlackScholes
    
    # Price an option
    bs = BlackScholes(S=150, K=155, T=30/365, r=0.05, sigma=0.25)
    call_price = bs.call_price()
    greeks = bs.greeks()
    
    # Analyze options chain
    analyzer = OptionsAnalyzer(symbol="AAPL")
    chain = analyzer.get_chain()
    analysis = analyzer.analyze()
"""

import math
import numpy as np
from scipy import stats
from scipy.optimize import brentq
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import os
import json
import urllib.request


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class Greeks:
    """Option Greeks."""
    delta: float      # Price sensitivity to underlying
    gamma: float      # Delta sensitivity to underlying
    theta: float      # Time decay (per day)
    vega: float       # Volatility sensitivity (per 1% change)
    rho: float        # Interest rate sensitivity (per 1% change)
    
    def to_dict(self) -> Dict:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 4),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4)
        }


@dataclass
class OptionContract:
    """Single option contract."""
    symbol: str
    underlying: str
    strike: float
    expiration: str
    option_type: OptionType
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    greeks: Greeks = None
    
    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def spread_pct(self) -> float:
        return (self.spread / self.mid_price * 100) if self.mid_price > 0 else 0
    
    @property
    def days_to_expiry(self) -> int:
        exp_date = datetime.strptime(self.expiration, "%Y-%m-%d")
        return (exp_date - datetime.now()).days
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "underlying": self.underlying,
            "strike": self.strike,
            "expiration": self.expiration,
            "type": self.option_type.value,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "mid": self.mid_price,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "implied_volatility": round(self.implied_volatility * 100, 2),
            "days_to_expiry": self.days_to_expiry,
            "greeks": self.greeks.to_dict() if self.greeks else None
        }


class BlackScholes:
    """
    Black-Scholes option pricing model.
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annual)
        q: Dividend yield (annual, default 0)
    """
    
    def __init__(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0):
        self.S = S          # Stock price
        self.K = K          # Strike price
        self.T = max(T, 1e-10)  # Time to expiry (avoid division by zero)
        self.r = r          # Risk-free rate
        self.sigma = sigma  # Volatility
        self.q = q          # Dividend yield
        
        # Pre-calculate d1 and d2
        self._calculate_d1_d2()
    
    def _calculate_d1_d2(self):
        """Calculate d1 and d2 for Black-Scholes formula."""
        sqrt_T = math.sqrt(self.T)
        self.d1 = (math.log(self.S / self.K) + (self.r - self.q + 0.5 * self.sigma**2) * self.T) / (self.sigma * sqrt_T)
        self.d2 = self.d1 - self.sigma * sqrt_T
    
    def call_price(self) -> float:
        """Calculate call option price."""
        N_d1 = stats.norm.cdf(self.d1)
        N_d2 = stats.norm.cdf(self.d2)
        
        call = (self.S * math.exp(-self.q * self.T) * N_d1 - 
                self.K * math.exp(-self.r * self.T) * N_d2)
        return max(call, 0)
    
    def put_price(self) -> float:
        """Calculate put option price."""
        N_neg_d1 = stats.norm.cdf(-self.d1)
        N_neg_d2 = stats.norm.cdf(-self.d2)
        
        put = (self.K * math.exp(-self.r * self.T) * N_neg_d2 - 
               self.S * math.exp(-self.q * self.T) * N_neg_d1)
        return max(put, 0)
    
    def delta(self, option_type: OptionType = OptionType.CALL) -> float:
        """
        Delta: Rate of change of option price with respect to underlying price.
        Call delta: 0 to 1
        Put delta: -1 to 0
        """
        if option_type == OptionType.CALL:
            return math.exp(-self.q * self.T) * stats.norm.cdf(self.d1)
        else:
            return math.exp(-self.q * self.T) * (stats.norm.cdf(self.d1) - 1)
    
    def gamma(self) -> float:
        """
        Gamma: Rate of change of delta with respect to underlying price.
        Same for calls and puts.
        """
        return (math.exp(-self.q * self.T) * stats.norm.pdf(self.d1) / 
                (self.S * self.sigma * math.sqrt(self.T)))
    
    def theta(self, option_type: OptionType = OptionType.CALL) -> float:
        """
        Theta: Rate of time decay (per day).
        Usually negative (options lose value over time).
        """
        sqrt_T = math.sqrt(self.T)
        
        term1 = -(self.S * math.exp(-self.q * self.T) * stats.norm.pdf(self.d1) * self.sigma) / (2 * sqrt_T)
        
        if option_type == OptionType.CALL:
            term2 = self.q * self.S * math.exp(-self.q * self.T) * stats.norm.cdf(self.d1)
            term3 = -self.r * self.K * math.exp(-self.r * self.T) * stats.norm.cdf(self.d2)
        else:
            term2 = -self.q * self.S * math.exp(-self.q * self.T) * stats.norm.cdf(-self.d1)
            term3 = self.r * self.K * math.exp(-self.r * self.T) * stats.norm.cdf(-self.d2)
        
        # Convert to daily theta
        return (term1 + term2 + term3) / 365
    
    def vega(self) -> float:
        """
        Vega: Sensitivity to volatility changes.
        Same for calls and puts. Per 1% change in volatility.
        """
        return (self.S * math.exp(-self.q * self.T) * stats.norm.pdf(self.d1) * 
                math.sqrt(self.T)) / 100
    
    def rho(self, option_type: OptionType = OptionType.CALL) -> float:
        """
        Rho: Sensitivity to interest rate changes.
        Per 1% change in interest rate.
        """
        if option_type == OptionType.CALL:
            return (self.K * self.T * math.exp(-self.r * self.T) * 
                   stats.norm.cdf(self.d2)) / 100
        else:
            return (-self.K * self.T * math.exp(-self.r * self.T) * 
                   stats.norm.cdf(-self.d2)) / 100
    
    def greeks(self, option_type: OptionType = OptionType.CALL) -> Greeks:
        """Calculate all Greeks for an option."""
        return Greeks(
            delta=self.delta(option_type),
            gamma=self.gamma(),
            theta=self.theta(option_type),
            vega=self.vega(),
            rho=self.rho(option_type)
        )
    
    @staticmethod
    def implied_volatility(price: float, S: float, K: float, T: float, 
                          r: float, option_type: OptionType, q: float = 0) -> float:
        """
        Calculate implied volatility from option price using bisection.
        
        Args:
            price: Market price of the option
            S, K, T, r, q: Black-Scholes parameters
            option_type: CALL or PUT
        
        Returns:
            Implied volatility
        """
        def objective(sigma):
            bs = BlackScholes(S, K, T, r, sigma, q)
            if option_type == OptionType.CALL:
                return bs.call_price() - price
            else:
                return bs.put_price() - price
        
        try:
            # Search between 1% and 500% volatility
            iv = brentq(objective, 0.01, 5.0, xtol=1e-6)
            return iv
        except Exception:
            return 0.30  # Default to 30% if calculation fails


class OptionsAnalyzer:
    """
    Options chain analysis and strategy evaluation.
    
    Args:
        symbol: Stock symbol
        stock_price: Current stock price (fetched if not provided)
        risk_free_rate: Annual risk-free rate (default 5%)
    """
    
    def __init__(self, symbol: str, stock_price: float = None, risk_free_rate: float = 0.05):
        self.symbol = symbol.upper()
        self.stock_price = stock_price
        self.risk_free_rate = risk_free_rate
        self.chain: List[OptionContract] = []
        
        # Fetch stock price if not provided
        if self.stock_price is None:
            self._fetch_stock_price()
    
    def _fetch_stock_price(self):
        """Fetch current stock price."""
        try:
            api_key = os.environ.get("FMP_API_KEY", "")
            url = f"https://financialmodelingprep.com/api/v3/quote/{self.symbol}?apikey={api_key}"
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    self.stock_price = data[0].get("price", 100)
                else:
                    self.stock_price = 100
        except Exception:
            self.stock_price = 100
    
    def fetch_chain(self, expiration: str = None) -> List[OptionContract]:
        """
        Fetch options chain from API.
        
        Args:
            expiration: Specific expiration date (YYYY-MM-DD) or None for nearest
        """
        # Try to fetch from FMP or other source
        # For now, generate synthetic chain for demonstration
        self.chain = self._generate_synthetic_chain(expiration)
        return self.chain
    
    def _generate_synthetic_chain(self, expiration: str = None) -> List[OptionContract]:
        """Generate synthetic options chain for demonstration."""
        if expiration is None:
            # Next monthly expiration (3rd Friday)
            today = datetime.now()
            days_ahead = 4 - today.weekday()  # Friday
            if days_ahead <= 0:
                days_ahead += 7
            next_friday = today + timedelta(days=days_ahead)
            while next_friday.day < 15:
                next_friday += timedelta(days=7)
            while next_friday.day > 21:
                next_friday -= timedelta(days=7)
            expiration = next_friday.strftime("%Y-%m-%d")
        
        chain = []
        S = self.stock_price
        
        # Generate strikes around current price
        strike_range = np.arange(S * 0.85, S * 1.15, S * 0.025)
        
        exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        T = max((exp_date - datetime.now()).days / 365, 0.01)
        
        for strike in strike_range:
            strike = round(strike, 0)
            
            # Base IV (smile shape)
            moneyness = strike / S
            base_iv = 0.25 + 0.1 * (moneyness - 1) ** 2  # Volatility smile
            
            # Add some randomness
            iv_call = base_iv * (1 + np.random.uniform(-0.05, 0.05))
            iv_put = base_iv * (1 + np.random.uniform(-0.05, 0.05))
            
            # Calculate prices using Black-Scholes
            bs_call = BlackScholes(S, strike, T, self.risk_free_rate, iv_call)
            bs_put = BlackScholes(S, strike, T, self.risk_free_rate, iv_put)
            
            call_price = bs_call.call_price()
            put_price = bs_put.put_price()
            
            # Add bid-ask spread
            spread_pct = 0.02 + 0.02 * abs(moneyness - 1)  # Wider spread for OTM
            
            # Call option
            call = OptionContract(
                symbol=f"{self.symbol}{expiration.replace('-', '')}C{int(strike):05d}",
                underlying=self.symbol,
                strike=strike,
                expiration=expiration,
                option_type=OptionType.CALL,
                bid=round(call_price * (1 - spread_pct/2), 2),
                ask=round(call_price * (1 + spread_pct/2), 2),
                last=round(call_price, 2),
                volume=int(np.random.exponential(500)),
                open_interest=int(np.random.exponential(2000)),
                implied_volatility=iv_call,
                greeks=bs_call.greeks(OptionType.CALL)
            )
            chain.append(call)
            
            # Put option
            put = OptionContract(
                symbol=f"{self.symbol}{expiration.replace('-', '')}P{int(strike):05d}",
                underlying=self.symbol,
                strike=strike,
                expiration=expiration,
                option_type=OptionType.PUT,
                bid=round(put_price * (1 - spread_pct/2), 2),
                ask=round(put_price * (1 + spread_pct/2), 2),
                last=round(put_price, 2),
                volume=int(np.random.exponential(400)),
                open_interest=int(np.random.exponential(1500)),
                implied_volatility=iv_put,
                greeks=bs_put.greeks(OptionType.PUT)
            )
            chain.append(put)
        
        self.chain = chain
        return chain
    
    def get_calls(self) -> List[OptionContract]:
        """Get all call options."""
        return [o for o in self.chain if o.option_type == OptionType.CALL]
    
    def get_puts(self) -> List[OptionContract]:
        """Get all put options."""
        return [o for o in self.chain if o.option_type == OptionType.PUT]
    
    def get_atm_options(self, tolerance: float = 0.02) -> Tuple[OptionContract, OptionContract]:
        """Get at-the-money call and put."""
        calls = self.get_calls()
        puts = self.get_puts()
        
        atm_call = min(calls, key=lambda o: abs(o.strike - self.stock_price))
        atm_put = min(puts, key=lambda o: abs(o.strike - self.stock_price))
        
        return atm_call, atm_put
    
    def calculate_put_call_ratio(self) -> Dict:
        """Calculate put-call ratios (sentiment indicator)."""
        calls = self.get_calls()
        puts = self.get_puts()
        
        call_volume = sum(c.volume for c in calls)
        put_volume = sum(p.volume for p in puts)
        
        call_oi = sum(c.open_interest for c in calls)
        put_oi = sum(p.open_interest for p in puts)
        
        volume_ratio = put_volume / call_volume if call_volume > 0 else 1
        oi_ratio = put_oi / call_oi if call_oi > 0 else 1
        
        # Interpretation
        if volume_ratio > 1.5:
            sentiment = "Bearish (high put volume)"
        elif volume_ratio < 0.7:
            sentiment = "Bullish (high call volume)"
        else:
            sentiment = "Neutral"
        
        return {
            "volume_ratio": round(volume_ratio, 2),
            "open_interest_ratio": round(oi_ratio, 2),
            "total_call_volume": call_volume,
            "total_put_volume": put_volume,
            "total_call_oi": call_oi,
            "total_put_oi": put_oi,
            "sentiment": sentiment
        }
    
    def calculate_max_pain(self) -> Dict:
        """
        Calculate max pain strike (price at which most options expire worthless).
        """
        calls = self.get_calls()
        puts = self.get_puts()
        
        strikes = sorted(set(o.strike for o in self.chain))
        
        pain_by_strike = {}
        for test_strike in strikes:
            total_pain = 0
            
            # Call pain (calls ITM if price > strike)
            for call in calls:
                if test_strike > call.strike:
                    total_pain += (test_strike - call.strike) * call.open_interest * 100
            
            # Put pain (puts ITM if price < strike)
            for put in puts:
                if test_strike < put.strike:
                    total_pain += (put.strike - test_strike) * put.open_interest * 100
            
            pain_by_strike[test_strike] = total_pain
        
        # Find strike with minimum total pain
        max_pain_strike = min(pain_by_strike, key=pain_by_strike.get)
        
        return {
            "max_pain_strike": max_pain_strike,
            "current_price": self.stock_price,
            "distance_pct": round((max_pain_strike - self.stock_price) / self.stock_price * 100, 2),
            "pain_by_strike": {k: round(v/1000000, 2) for k, v in sorted(pain_by_strike.items())}  # In millions
        }
    
    def analyze_volatility_surface(self) -> Dict:
        """Analyze implied volatility across strikes and expirations."""
        calls = self.get_calls()
        
        if not calls:
            return {}
        
        # Group by moneyness
        iv_by_moneyness = {}
        for call in calls:
            moneyness = round(call.strike / self.stock_price, 2)
            iv_by_moneyness[moneyness] = call.implied_volatility
        
        # Find skew
        atm_iv = iv_by_moneyness.get(1.0, list(iv_by_moneyness.values())[len(iv_by_moneyness)//2])
        otm_put_iv = iv_by_moneyness.get(0.95, atm_iv)
        otm_call_iv = iv_by_moneyness.get(1.05, atm_iv)
        
        skew = otm_put_iv - otm_call_iv
        
        return {
            "atm_iv": round(atm_iv * 100, 2),
            "otm_put_iv_95": round(otm_put_iv * 100, 2),
            "otm_call_iv_105": round(otm_call_iv * 100, 2),
            "skew": round(skew * 100, 2),
            "skew_interpretation": "Put skew (fear)" if skew > 0.02 else "Call skew" if skew < -0.02 else "Neutral",
            "iv_by_moneyness": {k: round(v * 100, 2) for k, v in sorted(iv_by_moneyness.items())}
        }
    
    def find_best_strategies(self) -> List[Dict]:
        """Suggest optimal strategies based on current conditions."""
        strategies = []
        
        atm_call, atm_put = self.get_atm_options()
        vol_analysis = self.analyze_volatility_surface()
        pc_ratio = self.calculate_put_call_ratio()
        
        atm_iv = vol_analysis.get("atm_iv", 25) / 100
        
        # High IV strategies (sell premium)
        if atm_iv > 0.35:
            strategies.append({
                "name": "Iron Condor",
                "description": "High IV - sell premium with defined risk",
                "outlook": "Neutral, expecting price to stay range-bound",
                "max_profit": "Net credit received",
                "max_loss": "Width of spread - credit",
                "best_when": "IV is high and expected to decrease"
            })
            strategies.append({
                "name": "Short Strangle",
                "description": "Sell OTM call and put",
                "outlook": "Neutral with high IV",
                "max_profit": "Premium received",
                "max_loss": "Unlimited",
                "best_when": "High IV, expecting consolidation"
            })
        
        # Low IV strategies (buy premium)
        if atm_iv < 0.20:
            strategies.append({
                "name": "Long Straddle",
                "description": "Buy ATM call and put",
                "outlook": "Expecting big move, direction uncertain",
                "max_profit": "Unlimited",
                "max_loss": "Premium paid",
                "best_when": "Low IV before earnings or events"
            })
            strategies.append({
                "name": "Calendar Spread",
                "description": "Sell near-term, buy longer-term",
                "outlook": "Expecting IV increase",
                "max_profit": "Limited",
                "max_loss": "Net debit paid",
                "best_when": "Low IV expected to rise"
            })
        
        # Directional strategies based on sentiment
        if pc_ratio["volume_ratio"] > 1.3:  # Bearish sentiment
            strategies.append({
                "name": "Put Credit Spread",
                "description": "Contrarian - sell put spread against bearish crowd",
                "outlook": "Mildly bullish (contrarian)",
                "max_profit": "Credit received",
                "max_loss": "Width - credit",
                "best_when": "Extreme put buying, expecting reversal"
            })
        elif pc_ratio["volume_ratio"] < 0.7:  # Bullish sentiment
            strategies.append({
                "name": "Call Credit Spread",
                "description": "Contrarian - sell call spread against bullish crowd",
                "outlook": "Mildly bearish (contrarian)",
                "max_profit": "Credit received",
                "max_loss": "Width - credit",
                "best_when": "Extreme call buying, expecting pullback"
            })
        
        return strategies
    
    def analyze(self) -> Dict:
        """Comprehensive options analysis."""
        if not self.chain:
            self.fetch_chain()
        
        return {
            "symbol": self.symbol,
            "stock_price": self.stock_price,
            "chain_summary": {
                "total_contracts": len(self.chain),
                "calls": len(self.get_calls()),
                "puts": len(self.get_puts()),
                "expirations": list(set(o.expiration for o in self.chain))
            },
            "put_call_ratio": self.calculate_put_call_ratio(),
            "max_pain": self.calculate_max_pain(),
            "volatility_surface": self.analyze_volatility_surface(),
            "suggested_strategies": self.find_best_strategies()
        }
    
    def print_chain(self, option_type: OptionType = None):
        """Print formatted options chain."""
        contracts = self.chain
        if option_type:
            contracts = [c for c in contracts if c.option_type == option_type]
        
        print(f"\n{'='*80}")
        print(f"OPTIONS CHAIN: {self.symbol} @ ${self.stock_price:.2f}")
        print(f"{'='*80}")
        print(f"{'Strike':>8} {'Type':>6} {'Bid':>8} {'Ask':>8} {'IV':>7} {'Delta':>7} {'Gamma':>7} {'Theta':>7} {'OI':>8}")
        print("-"*80)
        
        for c in sorted(contracts, key=lambda x: (x.strike, x.option_type.value)):
            greeks = c.greeks if c.greeks else Greeks(0,0,0,0,0)
            print(f"{c.strike:>8.0f} {c.option_type.value:>6} {c.bid:>8.2f} {c.ask:>8.2f} "
                  f"{c.implied_volatility*100:>6.1f}% {greeks.delta:>7.3f} {greeks.gamma:>7.4f} "
                  f"{greeks.theta:>7.3f} {c.open_interest:>8}")


if __name__ == "__main__":
    # Demo
    print("Options Analysis Demo")
    print("="*50)
    
    # Black-Scholes example
    print("\n1. Black-Scholes Pricing")
    print("-"*50)
    
    S = 150      # Stock price
    K = 155      # Strike
    T = 30/365   # 30 days to expiry
    r = 0.05     # 5% risk-free rate
    sigma = 0.25 # 25% volatility
    
    bs = BlackScholes(S, K, T, r, sigma)
    
    print(f"Stock Price: ${S}")
    print(f"Strike: ${K}")
    print(f"Days to Expiry: {int(T*365)}")
    print(f"Volatility: {sigma*100}%")
    print()
    print(f"Call Price: ${bs.call_price():.2f}")
    print(f"Put Price: ${bs.put_price():.2f}")
    print()
    
    greeks = bs.greeks(OptionType.CALL)
    print("Call Greeks:")
    print(f"  Delta: {greeks.delta:.4f}")
    print(f"  Gamma: {greeks.gamma:.4f}")
    print(f"  Theta: ${greeks.theta:.4f}/day")
    print(f"  Vega: ${greeks.vega:.4f}/1% IV")
    print(f"  Rho: ${greeks.rho:.4f}/1% rate")
    
    # Options chain analysis
    print("\n2. Options Chain Analysis")
    print("-"*50)
    
    analyzer = OptionsAnalyzer("AAPL", stock_price=175)
    analyzer.fetch_chain()
    
    analysis = analyzer.analyze()
    
    print(f"\nPut-Call Ratio: {analysis['put_call_ratio']['volume_ratio']:.2f}")
    print(f"Sentiment: {analysis['put_call_ratio']['sentiment']}")
    print(f"\nMax Pain Strike: ${analysis['max_pain']['max_pain_strike']:.0f}")
    print(f"ATM IV: {analysis['volatility_surface']['atm_iv']}%")
    
    print("\nSuggested Strategies:")
    for strat in analysis['suggested_strategies']:
        print(f"  - {strat['name']}: {strat['description']}")
