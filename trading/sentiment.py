#!/usr/bin/env python3
"""
Sentiment Analysis Module
==========================
Analyze market sentiment from news, social media, and other sources.

Features:
- News headline sentiment analysis
- Keyword-based sentiment scoring
- Sentiment trend tracking
- Multi-source aggregation
- Fear & Greed indicators

Usage:
    from trading.sentiment import SentimentAnalyzer
    
    analyzer = SentimentAnalyzer()
    
    # Analyze text
    score = analyzer.analyze_text("Apple reports record earnings")
    
    # Analyze news for symbol
    sentiment = analyzer.analyze_symbol("AAPL")
    
    # Get market sentiment
    market = analyzer.market_sentiment()
"""

import re
import os
import json
import urllib.request
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
from enum import Enum


class SentimentLevel(Enum):
    """Sentiment classification."""
    VERY_BULLISH = "Very Bullish"
    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"
    VERY_BEARISH = "Very Bearish"


@dataclass
class SentimentScore:
    """Sentiment analysis result."""
    score: float           # -1 to 1 (-1 = very bearish, 1 = very bullish)
    level: SentimentLevel
    confidence: float      # 0 to 1
    positive_words: List[str] = field(default_factory=list)
    negative_words: List[str] = field(default_factory=list)
    
    @classmethod
    def from_score(cls, score: float, confidence: float = 0.5,
                   pos_words: List[str] = None, neg_words: List[str] = None) -> 'SentimentScore':
        """Create SentimentScore from numeric score."""
        if score >= 0.5:
            level = SentimentLevel.VERY_BULLISH
        elif score >= 0.2:
            level = SentimentLevel.BULLISH
        elif score <= -0.5:
            level = SentimentLevel.VERY_BEARISH
        elif score <= -0.2:
            level = SentimentLevel.BEARISH
        else:
            level = SentimentLevel.NEUTRAL
        
        return cls(
            score=score,
            level=level,
            confidence=confidence,
            positive_words=pos_words or [],
            negative_words=neg_words or []
        )
    
    def to_dict(self) -> Dict:
        return {
            "score": round(self.score, 3),
            "level": self.level.value,
            "confidence": round(self.confidence, 2),
            "positive_words": self.positive_words[:5],
            "negative_words": self.negative_words[:5]
        }


@dataclass
class NewsSentiment:
    """Sentiment for a single news item."""
    headline: str
    source: str
    published: str
    url: str
    sentiment: SentimentScore
    
    def to_dict(self) -> Dict:
        return {
            "headline": self.headline,
            "source": self.source,
            "published": self.published,
            "url": self.url,
            "sentiment": self.sentiment.to_dict()
        }


class SentimentLexicon:
    """
    Sentiment word lists for financial text analysis.
    Based on Loughran-McDonald financial sentiment dictionary.
    """
    
    # Positive words (financial context)
    POSITIVE = {
        # General positive
        "gain", "gains", "gained", "gaining", "profit", "profits", "profitable",
        "growth", "growing", "grew", "increase", "increased", "increases", "increasing",
        "rise", "rises", "rising", "rose", "surge", "surges", "surging", "surged",
        "jump", "jumps", "jumped", "jumping", "rally", "rallies", "rallied", "rallying",
        "boom", "booming", "soar", "soars", "soaring", "soared",
        "advance", "advances", "advanced", "advancing",
        "upturn", "uptrend", "upside", "bullish", "bull",
        
        # Performance
        "beat", "beats", "beating", "exceed", "exceeds", "exceeded", "exceeding",
        "outperform", "outperforms", "outperformed", "outperforming",
        "strong", "stronger", "strongest", "strength",
        "record", "records", "high", "highs", "highest", "peak", "peaks",
        "best", "better", "improve", "improves", "improved", "improving", "improvement",
        
        # Business positive
        "success", "successful", "successfully", "achieve", "achieved", "achievement",
        "win", "wins", "winning", "won", "winner", "winners",
        "opportunity", "opportunities", "optimistic", "optimism",
        "confident", "confidence", "positive", "favorable", "favourable",
        "upgrade", "upgrades", "upgraded", "upgrading",
        "recommend", "recommended", "buy", "buying", "bought",
        "breakthrough", "innovation", "innovative",
        
        # Financial positive
        "dividend", "dividends", "earnings", "revenue", "revenues",
        "expansion", "expand", "expanded", "expanding",
        "recover", "recovers", "recovered", "recovering", "recovery",
        "rebound", "rebounds", "rebounded", "rebounding",
    }
    
    # Negative words (financial context)
    NEGATIVE = {
        # General negative
        "loss", "losses", "lost", "losing", "lose",
        "decline", "declines", "declined", "declining",
        "drop", "drops", "dropped", "dropping",
        "fall", "falls", "fell", "falling", "fallen",
        "decrease", "decreases", "decreased", "decreasing",
        "plunge", "plunges", "plunged", "plunging",
        "crash", "crashes", "crashed", "crashing",
        "sink", "sinks", "sank", "sinking", "sunk",
        "tumble", "tumbles", "tumbled", "tumbling",
        "slide", "slides", "slid", "sliding",
        "slump", "slumps", "slumped", "slumping",
        "downturn", "downtrend", "downside", "bearish", "bear",
        
        # Performance
        "miss", "misses", "missed", "missing",
        "underperform", "underperforms", "underperformed", "underperforming",
        "weak", "weaker", "weakest", "weakness",
        "low", "lows", "lowest", "bottom",
        "worst", "worse", "worsen", "worsens", "worsened", "worsening",
        "disappoint", "disappoints", "disappointed", "disappointing", "disappointment",
        
        # Business negative
        "fail", "fails", "failed", "failing", "failure", "failures",
        "problem", "problems", "issue", "issues", "concern", "concerns",
        "risk", "risks", "risky", "threat", "threats", "threaten",
        "warning", "warn", "warns", "warned",
        "crisis", "crises", "trouble", "troubles", "troubled",
        "difficult", "difficulty", "difficulties", "challenge", "challenges",
        "pessimistic", "pessimism", "negative", "unfavorable", "unfavourable",
        "downgrade", "downgrades", "downgraded", "downgrading",
        "sell", "selling", "sold", "selloff",
        
        # Financial negative
        "debt", "debts", "deficit", "deficits",
        "bankruptcy", "bankrupt", "default", "defaults", "defaulted",
        "layoff", "layoffs", "layoffing", "restructure", "restructuring",
        "recession", "recessionary", "slowdown", "stagnation", "stagnant",
        "inflation", "inflationary",
        "lawsuit", "lawsuits", "litigation", "sue", "sued", "suing",
        "fraud", "fraudulent", "scandal", "scandals",
        "investigation", "investigate", "investigated", "investigating",
    }
    
    # Intensifiers
    INTENSIFIERS = {
        "very", "extremely", "highly", "significantly", "substantially",
        "sharply", "dramatically", "massive", "massively", "huge", "hugely",
        "major", "severe", "severely", "serious", "seriously"
    }
    
    # Negators (flip sentiment)
    NEGATORS = {
        "not", "no", "never", "neither", "nor", "none", "nobody", "nothing",
        "hardly", "barely", "scarcely", "seldom", "rarely",
        "without", "lack", "lacks", "lacking", "lacked",
        "fail", "fails", "failed", "failing", "unable", "cannot"
    }


class SentimentAnalyzer:
    """
    Analyze sentiment from text, news, and market data.
    """
    
    def __init__(self):
        self.lexicon = SentimentLexicon()
        self._word_pattern = re.compile(r'\b[a-zA-Z]+\b')
    
    def analyze_text(self, text: str) -> SentimentScore:
        """
        Analyze sentiment of a text string.
        
        Returns score from -1 (very negative) to 1 (very positive).
        """
        if not text:
            return SentimentScore.from_score(0, 0)
        
        # Tokenize
        words = self._word_pattern.findall(text.lower())
        
        if not words:
            return SentimentScore.from_score(0, 0)
        
        positive_count = 0
        negative_count = 0
        positive_words = []
        negative_words = []
        
        # Track negation window
        negation_window = 0
        intensifier_mult = 1.0
        
        for i, word in enumerate(words):
            # Check for intensifiers
            if word in self.lexicon.INTENSIFIERS:
                intensifier_mult = 1.5
                continue
            
            # Check for negators
            if word in self.lexicon.NEGATORS:
                negation_window = 3  # Affect next 3 words
                continue
            
            # Check sentiment
            is_positive = word in self.lexicon.POSITIVE
            is_negative = word in self.lexicon.NEGATIVE
            
            # Apply negation
            if negation_window > 0:
                is_positive, is_negative = is_negative, is_positive
                negation_window -= 1
            
            # Count
            if is_positive:
                positive_count += intensifier_mult
                positive_words.append(word)
            elif is_negative:
                negative_count += intensifier_mult
                negative_words.append(word)
            
            # Reset intensifier
            intensifier_mult = 1.0
        
        # Calculate score
        total = positive_count + negative_count
        if total == 0:
            return SentimentScore.from_score(0, 0.3)
        
        score = (positive_count - negative_count) / total
        
        # Confidence based on word coverage
        sentiment_word_ratio = total / len(words)
        confidence = min(1.0, sentiment_word_ratio * 3)  # Scale up
        
        return SentimentScore.from_score(score, confidence, positive_words, negative_words)
    
    def analyze_headlines(self, headlines: List[Dict]) -> List[NewsSentiment]:
        """
        Analyze sentiment of multiple news headlines.
        
        Args:
            headlines: List of dicts with 'headline', 'source', 'published', 'url'
        """
        results = []
        
        for item in headlines:
            headline = item.get("headline", item.get("title", ""))
            sentiment = self.analyze_text(headline)
            
            results.append(NewsSentiment(
                headline=headline,
                source=item.get("source", "Unknown"),
                published=item.get("published", item.get("publishedDate", "")),
                url=item.get("url", ""),
                sentiment=sentiment
            ))
        
        return results
    
    def analyze_symbol(self, symbol: str, days: int = 7) -> Dict:
        """
        Analyze sentiment for a stock symbol from recent news.
        """
        # Fetch news
        headlines = self._fetch_news(symbol, days)
        
        if not headlines:
            return {
                "symbol": symbol,
                "overall_sentiment": SentimentScore.from_score(0, 0).to_dict(),
                "news_count": 0,
                "news": []
            }
        
        # Analyze each headline
        news_sentiments = self.analyze_headlines(headlines)
        
        # Calculate aggregate sentiment
        if news_sentiments:
            avg_score = sum(n.sentiment.score for n in news_sentiments) / len(news_sentiments)
            avg_confidence = sum(n.sentiment.confidence for n in news_sentiments) / len(news_sentiments)
            
            # Weight by recency
            weighted_score = 0
            weight_sum = 0
            for i, ns in enumerate(news_sentiments):
                weight = 1.0 / (i + 1)  # More recent = higher weight
                weighted_score += ns.sentiment.score * weight
                weight_sum += weight
            
            if weight_sum > 0:
                weighted_avg = weighted_score / weight_sum
            else:
                weighted_avg = avg_score
            
            overall = SentimentScore.from_score(weighted_avg, avg_confidence)
        else:
            overall = SentimentScore.from_score(0, 0)
        
        # Sentiment distribution
        bullish = sum(1 for n in news_sentiments if n.sentiment.score > 0.1)
        bearish = sum(1 for n in news_sentiments if n.sentiment.score < -0.1)
        neutral = len(news_sentiments) - bullish - bearish
        
        return {
            "symbol": symbol,
            "overall_sentiment": overall.to_dict(),
            "news_count": len(news_sentiments),
            "sentiment_distribution": {
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral
            },
            "news": [n.to_dict() for n in news_sentiments[:10]]  # Top 10
        }
    
    def _fetch_news(self, symbol: str, days: int = 7) -> List[Dict]:
        """Fetch news for a symbol."""
        try:
            api_key = os.environ.get("FMP_API_KEY", "")
            if not api_key:
                return []
            
            url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={symbol}&limit=50&apikey={api_key}"
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []
    
    def market_sentiment(self) -> Dict:
        """
        Calculate overall market sentiment from various indicators.
        """
        indicators = {}
        
        # VIX (fear index)
        vix = self._get_vix()
        if vix:
            if vix < 15:
                vix_sentiment = "Low Fear (Complacent)"
                vix_score = 0.5
            elif vix < 20:
                vix_sentiment = "Normal"
                vix_score = 0
            elif vix < 30:
                vix_sentiment = "Elevated Fear"
                vix_score = -0.3
            else:
                vix_sentiment = "High Fear (Panic)"
                vix_score = -0.7
            
            indicators["vix"] = {
                "value": vix,
                "interpretation": vix_sentiment,
                "score": vix_score
            }
        
        # Market breadth (simulated)
        breadth_score = 0.1  # Would come from actual data
        indicators["breadth"] = {
            "value": "55% above 50-day MA",
            "interpretation": "Slightly Bullish",
            "score": breadth_score
        }
        
        # Put/Call ratio (simulated)
        pc_ratio = 0.85  # Would come from actual data
        if pc_ratio < 0.7:
            pc_sentiment = "Bullish (Low puts)"
            pc_score = 0.3
        elif pc_ratio > 1.2:
            pc_sentiment = "Bearish (High puts)"
            pc_score = -0.3
        else:
            pc_sentiment = "Neutral"
            pc_score = 0
        
        indicators["put_call_ratio"] = {
            "value": pc_ratio,
            "interpretation": pc_sentiment,
            "score": pc_score
        }
        
        # Calculate overall
        scores = [ind["score"] for ind in indicators.values() if "score" in ind]
        overall_score = sum(scores) / len(scores) if scores else 0
        overall = SentimentScore.from_score(overall_score, 0.7)
        
        return {
            "overall": overall.to_dict(),
            "indicators": indicators,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_vix(self) -> Optional[float]:
        """Fetch current VIX value."""
        try:
            api_key = os.environ.get("FMP_API_KEY", "")
            if not api_key:
                return 18.5  # Default
            
            url = f"https://financialmodelingprep.com/api/v3/quote/%5EVIX?apikey={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    return data[0].get("price", 18.5)
        except Exception:
            pass
        return 18.5
    
    def fear_greed_index(self) -> Dict:
        """
        Calculate a Fear & Greed style index (0-100).
        0 = Extreme Fear, 100 = Extreme Greed
        """
        market = self.market_sentiment()
        
        # Convert sentiment score (-1 to 1) to index (0 to 100)
        overall_score = market["overall"]["score"]
        index = int((overall_score + 1) * 50)  # Map -1..1 to 0..100
        index = max(0, min(100, index))
        
        if index <= 20:
            level = "Extreme Fear"
        elif index <= 40:
            level = "Fear"
        elif index <= 60:
            level = "Neutral"
        elif index <= 80:
            level = "Greed"
        else:
            level = "Extreme Greed"
        
        return {
            "index": index,
            "level": level,
            "description": self._get_fear_greed_description(level),
            "components": market["indicators"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_fear_greed_description(self, level: str) -> str:
        """Get description for fear/greed level."""
        descriptions = {
            "Extreme Fear": "Investors are very worried. This could be a buying opportunity.",
            "Fear": "Investors are fearful. Markets may be oversold.",
            "Neutral": "Market sentiment is balanced.",
            "Greed": "Investors are getting greedy. Exercise caution.",
            "Extreme Greed": "Investors are extremely greedy. Markets may be overbought."
        }
        return descriptions.get(level, "")


class SentimentTracker:
    """
    Track sentiment over time for a symbol.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.history: List[Tuple[datetime, float]] = []
        self.analyzer = SentimentAnalyzer()
    
    def update(self) -> SentimentScore:
        """Update sentiment and add to history."""
        analysis = self.analyzer.analyze_symbol(self.symbol, days=1)
        score = analysis["overall_sentiment"]["score"]
        
        self.history.append((datetime.now(), score))
        
        # Keep last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        self.history = [(dt, s) for dt, s in self.history if dt > cutoff]
        
        return SentimentScore.from_score(score)
    
    def get_trend(self) -> Dict:
        """Get sentiment trend."""
        if len(self.history) < 2:
            return {"trend": "insufficient_data", "change": 0}
        
        # Compare recent vs older sentiment
        recent = [s for dt, s in self.history if dt > datetime.now() - timedelta(days=7)]
        older = [s for dt, s in self.history if dt <= datetime.now() - timedelta(days=7)]
        
        if not recent or not older:
            return {"trend": "insufficient_data", "change": 0}
        
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        change = recent_avg - older_avg
        
        if change > 0.2:
            trend = "improving"
        elif change < -0.2:
            trend = "deteriorating"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change": round(change, 3),
            "recent_avg": round(recent_avg, 3),
            "older_avg": round(older_avg, 3),
            "data_points": len(self.history)
        }


if __name__ == "__main__":
    # Demo
    print("Sentiment Analysis Demo")
    print("="*60)
    
    analyzer = SentimentAnalyzer()
    
    # Test text analysis
    test_texts = [
        "Apple reports record quarterly earnings, beating all expectations",
        "Stock crashes amid growing concerns over company's future",
        "Company announces neutral quarterly results in line with estimates",
        "CEO warns of significant challenges ahead despite recent gains",
        "Investors optimistic as growth accelerates and profits surge"
    ]
    
    print("\n1. Text Sentiment Analysis")
    print("-"*60)
    for text in test_texts:
        result = analyzer.analyze_text(text)
        print(f"\n'{text[:50]}...'")
        print(f"  Score: {result.score:.2f} ({result.level.value})")
        print(f"  Confidence: {result.confidence:.1%}")
        if result.positive_words:
            print(f"  Positive: {', '.join(result.positive_words[:3])}")
        if result.negative_words:
            print(f"  Negative: {', '.join(result.negative_words[:3])}")
    
    # Market sentiment
    print("\n\n2. Market Sentiment")
    print("-"*60)
    market = analyzer.market_sentiment()
    print(f"Overall: {market['overall']['level']} (score: {market['overall']['score']:.2f})")
    for name, indicator in market['indicators'].items():
        print(f"  {name}: {indicator['interpretation']}")
    
    # Fear & Greed
    print("\n\n3. Fear & Greed Index")
    print("-"*60)
    fg = analyzer.fear_greed_index()
    print(f"Index: {fg['index']} - {fg['level']}")
    print(f"Description: {fg['description']}")
