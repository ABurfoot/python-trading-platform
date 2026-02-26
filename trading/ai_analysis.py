#!/usr/bin/env python3
"""
AI Analysis Module
===================
AI-powered stock analysis using Claude API.

Features:
- Natural language stock analysis
- News sentiment summarization
- Trade idea generation
- Technical pattern recognition
- Earnings analysis
- Risk assessment

Usage:
    from trading.ai_analysis import AIAnalyzer
    
    ai = AIAnalyzer()
    
    # Analyze a stock
    analysis = ai.analyze_stock("AAPL")
    print(analysis)
    
    # Get trade ideas
    ideas = ai.generate_trade_ideas(["AAPL", "MSFT", "GOOGL"])
    
    # Summarize news
    summary = ai.summarize_news("AAPL")
"""

import os
import json
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AnalysisType(Enum):
    """Types of AI analysis."""
    FULL = "full"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    EARNINGS = "earnings"
    RISK = "risk"
    TRADE_IDEA = "trade_idea"


@dataclass
class AIAnalysisResult:
    """Result from AI analysis."""
    symbol: str
    analysis_type: AnalysisType
    summary: str
    key_points: List[str]
    sentiment: str  # bullish, bearish, neutral
    confidence: float  # 0-1
    recommendation: str
    risks: List[str]
    catalysts: List[str]
    timestamp: datetime
    model: str
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "analysis_type": self.analysis_type.value,
            "summary": self.summary,
            "key_points": self.key_points,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "risks": self.risks,
            "catalysts": self.catalysts,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model
        }


class AIAnalyzer:
    """
    AI-powered stock analysis using Claude API.
    
    Requires ANTHROPIC_API_KEY environment variable.
    """
    
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        
        if not self.api_key:
            print("Warning: ANTHROPIC_API_KEY not set. AI analysis will be limited.")
    
    def _call_claude(self, prompt: str, system: str = None, max_tokens: int = 2000) -> Optional[str]:
        """Make API call to Claude."""
        if not self.api_key:
            return self._fallback_analysis(prompt)
        
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            if system:
                data["system"] = system
            
            req = urllib.request.Request(
                self.ANTHROPIC_API_URL,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                return result.get("content", [{}])[0].get("text", "")
        
        except Exception as e:
            print(f"Claude API error: {e}")
            return self._fallback_analysis(prompt)
    
    def _fallback_analysis(self, prompt: str) -> str:
        """Provide basic analysis when API is unavailable."""
        return """AI Analysis (Fallback Mode - API key not configured)

To enable full AI analysis:
1. Get API key from https://console.anthropic.com/
2. Set environment variable: export ANTHROPIC_API_KEY="your-key"

Basic analysis based on available data has been provided where possible."""
    
    def _get_stock_data(self, symbol: str) -> Dict:
        """Fetch stock data for analysis."""
        data = {
            "symbol": symbol,
            "price": None,
            "change_pct": None,
            "volume": None,
            "pe_ratio": None,
            "market_cap": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "news": [],
            "technicals": {}
        }
        
        try:
            # Try to get data from analyzer
            from trading.analyzer import StockAnalyzer
            analyzer = StockAnalyzer()
            result = analyzer.analyze(symbol)
            
            data["price"] = result.current_price
            data["change_pct"] = getattr(result, 'change_pct', None)
            data["pe_ratio"] = getattr(result, 'pe_ratio', None)
            data["market_cap"] = getattr(result, 'market_cap', None)
            data["overall_score"] = result.overall_score
            data["recommendation"] = result.recommendation.value if hasattr(result.recommendation, 'value') else str(result.recommendation)
            data["signals"] = {s.name: {"value": s.value, "signal": s.signal.value if hasattr(s.signal, 'value') else str(s.signal)} 
                             for s in result.signals[:10]}
        except Exception as e:
            print(f"Could not fetch stock data: {e}")
        
        try:
            # Try to get news
            from trading.news import NewsManager
            nm = NewsManager()
            news = nm.get_news(symbol, limit=5)
            data["news"] = [{"title": n.title, "source": n.source} for n in news]
        except Exception:
            pass
        
        return data
    
    def analyze_stock(self, symbol: str, analysis_type: AnalysisType = AnalysisType.FULL) -> AIAnalysisResult:
        """
        Perform comprehensive AI analysis on a stock.
        
        Args:
            symbol: Stock symbol
            analysis_type: Type of analysis to perform
        
        Returns:
            AIAnalysisResult with detailed analysis
        """
        symbol = symbol.upper()
        stock_data = self._get_stock_data(symbol)
        
        system_prompt = """You are an expert financial analyst with deep knowledge of:
- Technical analysis and chart patterns
- Fundamental analysis and valuation
- Market sentiment and news analysis
- Risk assessment and portfolio management

Provide clear, actionable analysis. Be specific with numbers and timeframes.
Format your response as JSON with these fields:
- summary: 2-3 sentence overview
- key_points: array of 3-5 bullet points
- sentiment: "bullish", "bearish", or "neutral"
- confidence: number 0-1
- recommendation: specific action (e.g., "Buy on dips below $150", "Hold", "Take profits above $180")
- risks: array of 2-3 key risks
- catalysts: array of 2-3 potential catalysts"""
        
        if analysis_type == AnalysisType.FULL:
            prompt = f"""Analyze {symbol} comprehensively.

Current Data:
{json.dumps(stock_data, indent=2, default=str)}

Provide a full analysis covering:
1. Technical setup (trend, support/resistance, momentum)
2. Fundamental valuation (if data available)
3. Recent news impact
4. Short-term outlook (1-4 weeks)
5. Key levels to watch

Respond in JSON format."""

        elif analysis_type == AnalysisType.TECHNICAL:
            prompt = f"""Provide technical analysis for {symbol}.

Data: {json.dumps(stock_data, indent=2, default=str)}

Focus on:
1. Trend direction and strength
2. Key support and resistance levels
3. Momentum indicators
4. Chart patterns
5. Entry/exit points

Respond in JSON format."""

        elif analysis_type == AnalysisType.NEWS:
            prompt = f"""Analyze recent news sentiment for {symbol}.

Recent Headlines:
{json.dumps(stock_data.get('news', []), indent=2)}

Assess:
1. Overall news sentiment
2. Key themes in coverage
3. Potential market impact
4. Information not yet priced in

Respond in JSON format."""

        else:
            prompt = f"Analyze {symbol}. Data: {json.dumps(stock_data, indent=2, default=str)}. Respond in JSON format."
        
        response = self._call_claude(prompt, system_prompt)
        
        # Parse response
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
            else:
                json_str = response
            
            parsed = json.loads(json_str)
            
            return AIAnalysisResult(
                symbol=symbol,
                analysis_type=analysis_type,
                summary=parsed.get("summary", response[:500]),
                key_points=parsed.get("key_points", []),
                sentiment=parsed.get("sentiment", "neutral"),
                confidence=float(parsed.get("confidence", 0.5)),
                recommendation=parsed.get("recommendation", "No specific recommendation"),
                risks=parsed.get("risks", []),
                catalysts=parsed.get("catalysts", []),
                timestamp=datetime.now(),
                model=self.model
            )
        except Exception:
            # Return raw response if parsing fails
            return AIAnalysisResult(
                symbol=symbol,
                analysis_type=analysis_type,
                summary=response[:500] if response else "Analysis unavailable",
                key_points=[],
                sentiment="neutral",
                confidence=0.5,
                recommendation="See full analysis",
                risks=[],
                catalysts=[],
                timestamp=datetime.now(),
                model=self.model
            )
    
    def generate_trade_ideas(self, symbols: List[str], strategy: str = "balanced") -> List[Dict]:
        """
        Generate trade ideas for a list of symbols.
        
        Args:
            symbols: List of symbols to analyze
            strategy: Investment strategy (conservative, balanced, aggressive)
        
        Returns:
            List of trade ideas with entry/exit points
        """
        # Gather data for all symbols
        all_data = {}
        for symbol in symbols[:10]:  # Limit to 10
            all_data[symbol] = self._get_stock_data(symbol)
        
        system_prompt = """You are a trading strategist. Generate specific, actionable trade ideas.
Each idea should include:
- Symbol and direction (long/short)
- Entry price or condition
- Stop loss level
- Target price(s)
- Position size suggestion (% of portfolio)
- Timeframe
- Rationale (1-2 sentences)

Format as JSON array of trade ideas."""
        
        prompt = f"""Generate trade ideas for a {strategy} investor.

Available stocks and current data:
{json.dumps(all_data, indent=2, default=str)}

Provide 3-5 specific trade ideas ranked by conviction.
Consider risk/reward, current market conditions, and correlation.

Respond as JSON array."""
        
        response = self._call_claude(prompt, system_prompt)
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "[" in response:
                start = response.index("[")
                end = response.rindex("]") + 1
                json_str = response[start:end]
            else:
                return [{"raw_response": response}]
            
            return json.loads(json_str)
        except Exception:
            return [{"raw_response": response}]
    
    def summarize_news(self, symbol: str, days: int = 7) -> Dict:
        """
        Summarize recent news for a symbol.
        
        Args:
            symbol: Stock symbol
            days: Number of days of news to analyze
        
        Returns:
            Dict with news summary and sentiment
        """
        symbol = symbol.upper()
        
        # Fetch news
        news_items = []
        try:
            from trading.news import NewsManager
            nm = NewsManager()
            news = nm.get_news(symbol, limit=20)
            news_items = [{"title": n.title, "source": n.source, "date": str(n.published_at)} for n in news]
        except Exception as e:
            print(f"Could not fetch news: {e}")
        
        if not news_items:
            return {
                "symbol": symbol,
                "summary": "No recent news available",
                "sentiment": "neutral",
                "key_themes": [],
                "news_count": 0
            }
        
        system_prompt = """Summarize financial news objectively. Identify:
1. Main themes and developments
2. Overall sentiment (bullish/bearish/neutral)
3. Potential market impact
4. Key quotes or data points

Format as JSON with: summary, sentiment, key_themes (array), market_impact, notable_items (array)"""
        
        prompt = f"""Summarize recent news for {symbol}:

{json.dumps(news_items, indent=2)}

Provide a concise summary highlighting what investors need to know."""
        
        response = self._call_claude(prompt, system_prompt, max_tokens=1000)
        
        try:
            if "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                parsed = json.loads(response[start:end])
                parsed["symbol"] = symbol
                parsed["news_count"] = len(news_items)
                return parsed
        except Exception:
            pass
        
        return {
            "symbol": symbol,
            "summary": response,
            "sentiment": "neutral",
            "key_themes": [],
            "news_count": len(news_items)
        }
    
    def analyze_earnings(self, symbol: str) -> Dict:
        """
        Analyze earnings and provide outlook.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dict with earnings analysis
        """
        symbol = symbol.upper()
        
        # Fetch earnings data
        earnings_data = {}
        try:
            from trading.earnings import EarningsCalendar
            ec = EarningsCalendar()
            earnings_data = ec.get_earnings_history(symbol)
        except Exception:
            pass
        
        stock_data = self._get_stock_data(symbol)
        
        system_prompt = """Analyze earnings data and provide forward-looking insights.
Focus on:
1. Recent earnings trends (beats/misses)
2. Revenue and margin trends
3. Management guidance
4. Analyst expectations
5. Historical stock reaction to earnings

Format as JSON with: summary, trend, next_earnings_outlook, key_metrics, trading_strategy"""
        
        prompt = f"""Analyze earnings for {symbol}:

Stock Data: {json.dumps(stock_data, indent=2, default=str)}
Earnings History: {json.dumps(earnings_data, indent=2, default=str)}

Provide earnings analysis and outlook for next report."""
        
        response = self._call_claude(prompt, system_prompt, max_tokens=1500)
        
        try:
            if "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                return json.loads(response[start:end])
        except Exception:
            pass
        
        return {"symbol": symbol, "analysis": response}
    
    def assess_risk(self, symbols: List[str], portfolio_value: float = 100000) -> Dict:
        """
        Assess portfolio risk.
        
        Args:
            symbols: List of portfolio symbols
            portfolio_value: Total portfolio value
        
        Returns:
            Dict with risk assessment
        """
        # Gather data
        portfolio_data = {}
        for symbol in symbols[:20]:
            portfolio_data[symbol] = self._get_stock_data(symbol)
        
        system_prompt = """Assess portfolio risk comprehensively. Analyze:
1. Concentration risk
2. Sector exposure
3. Correlation between holdings
4. Volatility assessment
5. Downside scenarios
6. Hedging recommendations

Format as JSON with: overall_risk_level (low/medium/high), risk_score (1-10), 
key_risks (array), sector_exposure (object), recommendations (array), 
stress_test_scenarios (array)"""
        
        prompt = f"""Assess risk for this ${portfolio_value:,.0f} portfolio:

Holdings:
{json.dumps(portfolio_data, indent=2, default=str)}

Provide comprehensive risk assessment and mitigation strategies."""
        
        response = self._call_claude(prompt, system_prompt, max_tokens=2000)
        
        try:
            if "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                result = json.loads(response[start:end])
                result["portfolio_value"] = portfolio_value
                result["holdings_count"] = len(symbols)
                return result
        except Exception:
            pass
        
        return {
            "portfolio_value": portfolio_value,
            "holdings_count": len(symbols),
            "analysis": response
        }
    
    def explain_indicator(self, indicator_name: str, value: float, symbol: str = None) -> str:
        """
        Get plain-English explanation of a technical indicator.
        
        Args:
            indicator_name: Name of indicator (RSI, MACD, etc.)
            value: Current value
            symbol: Optional symbol for context
        
        Returns:
            Plain-English explanation
        """
        prompt = f"""Explain what {indicator_name} = {value} means for {'the stock ' + symbol if symbol else 'a stock'}.

Keep it simple and actionable:
1. What does this value indicate? (1 sentence)
2. Is it bullish, bearish, or neutral? (1 word)
3. What should a trader watch for? (1 sentence)

Be concise - max 3 sentences total."""
        
        response = self._call_claude(prompt, max_tokens=200)
        return response or f"{indicator_name} is at {value}. Unable to provide AI explanation."
    
    def chat(self, message: str, context: Dict = None) -> str:
        """
        General chat about markets/trading.
        
        Args:
            message: User's question or message
            context: Optional context (portfolio, watchlist, etc.)
        
        Returns:
            AI response
        """
        system_prompt = """You are a knowledgeable financial assistant. 
Provide helpful, accurate information about markets, trading, and investing.
Be concise but thorough. If you're unsure, say so.
Never provide specific financial advice - only education and analysis."""
        
        if context:
            message = f"Context: {json.dumps(context, default=str)}\n\nQuestion: {message}"
        
        response = self._call_claude(message, system_prompt, max_tokens=1500)
        return response or "I'm unable to respond at the moment. Please check your API key configuration."
    
    def print_analysis(self, result: AIAnalysisResult):
        """Print formatted analysis."""
        print(f"\n{'='*60}")
        print(f"AI ANALYSIS: {result.symbol}")
        print(f"{'='*60}")
        print(f"Type: {result.analysis_type.value.title()}")
        print(f"Model: {result.model}")
        print(f"Time: {result.timestamp.strftime('%Y-%m-%d %H:%M')}")
        
        print(f"\n SUMMARY")
        print("-"*60)
        print(result.summary)
        
        if result.key_points:
            print(f"\n KEY POINTS")
            print("-"*60)
            for point in result.key_points:
                print(f"  • {point}")
        
        print(f"\n SENTIMENT: {result.sentiment.upper()} (Confidence: {result.confidence:.0%})")
        print(f"\n💡 RECOMMENDATION: {result.recommendation}")
        
        if result.risks:
            print(f"\n[WARN] RISKS")
            print("-"*60)
            for risk in result.risks:
                print(f"  • {risk}")
        
        if result.catalysts:
            print(f"\n CATALYSTS")
            print("-"*60)
            for catalyst in result.catalysts:
                print(f"  • {catalyst}")
        
        print(f"\n{'='*60}")


# Convenience functions
def analyze(symbol: str) -> AIAnalysisResult:
    """Quick analysis of a symbol."""
    ai = AIAnalyzer()
    return ai.analyze_stock(symbol)


def get_trade_ideas(symbols: List[str]) -> List[Dict]:
    """Get trade ideas for symbols."""
    ai = AIAnalyzer()
    return ai.generate_trade_ideas(symbols)


def chat(message: str) -> str:
    """Chat with AI about markets."""
    ai = AIAnalyzer()
    return ai.chat(message)


if __name__ == "__main__":
    import sys
    
    ai = AIAnalyzer()
    
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        print(f"Analyzing {symbol}...")
        result = ai.analyze_stock(symbol)
        ai.print_analysis(result)
    else:
        print("AI Analysis Module")
        print("="*50)
        print("\nUsage:")
        print("  python ai_analysis.py AAPL    # Analyze a stock")
        print("\nOr in Python:")
        print("  from trading.ai_analysis import AIAnalyzer")
        print("  ai = AIAnalyzer()")
        print("  result = ai.analyze_stock('AAPL')")
        print("\nRequires: ANTHROPIC_API_KEY environment variable")
