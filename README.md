# Python Trading Platform

Stock analysis and portfolio management platform with ML-powered predictions.

## Features

- **Stock Analysis** - Technical indicators (RSI, MACD, Bollinger Bands) and fundamental metrics (P/E, ROE, debt ratios)
- **ML Predictions** - Ensemble models using Random Forest, Gradient Boosting, XGBoost, LightGBM, and LSTM neural networks
- **Portfolio Tracking** - Track holdings, P&L, and performance
- **Watchlists** - Monitor stocks you're interested in
- **Price Alerts** - Get notified when stocks hit target prices
- **Sector Analysis** - Monitor sector ETF performance
- **Multi-Exchange** - Supports US (NYSE, NASDAQ), Australian (ASX), UK (LSE), and more
- **Web Dashboard** - Browser-based interface at localhost:8080

## Tech Stack

- **Python 3.10+**
- **ML Libraries**: scikit-learn, PyTorch, XGBoost, LightGBM
- **Data**: NumPy, Pandas
- **APIs**: Alpaca, FMP, Finnhub, Yahoo Finance

## Installation

```bash
git clone https://github.com/ABurfoot/python-trading-platform.git
cd python-trading-platform

# Required
pip install requests numpy pandas scikit-learn

# Optional - for deep learning
pip install torch xgboost lightgbm
```

## API Keys

Set up API keys as environment variables (all optional - uses available providers):

```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
export FMP_API_KEY="your_key"
export FINNHUB_API_KEY="your_key"
```

## Usage

### Web Dashboard

```bash
python3 -m trading.dashboard
# Open http://localhost:8080
```

### Command Line

```bash
# Analyze a stock
python3 trade.py analyze AAPL

# International stocks
python3 trade.py analyze ASX:BHP
python3 trade.py analyze LSE:VOD

# Watchlist
python3 trade.py watchlist add AAPL MSFT GOOGL
python3 trade.py watchlist list

# Portfolio
python3 trade.py portfolio summary
```

## Project Structure

```
python-trading-platform/
├── trading/
│   ├── analyzer.py          # Stock analysis engine
│   ├── dashboard.py         # Web interface
│   ├── data_sources.py      # Multi-API data fetching
│   ├── ml_predictor_v2.py   # ML prediction models
│   ├── indicators.py        # Technical indicators
│   ├── portfolio.py         # Portfolio management
│   ├── watchlist.py         # Watchlist management
│   ├── alerts.py            # Price alerts
│   ├── sectors.py           # Sector analysis
│   ├── backtest_engine.py   # Strategy backtesting
│   ├── risk_manager.py      # Risk calculations
│   └── ...
├── tests/
├── trade.py                 # CLI entry point
└── test_comprehensive.py    # Test suite (277 tests)
```

## ML Models

The prediction system uses an ensemble of:

| Model | Library | Type |
|-------|---------|------|
| Random Forest | scikit-learn | Traditional ML |
| Gradient Boosting | scikit-learn | Traditional ML |
| Ridge Regression | scikit-learn | Traditional ML |
| XGBoost | xgboost | Boosting |
| LightGBM | lightgbm | Boosting |
| LSTM | PyTorch | Deep Learning |
| GRU | PyTorch | Deep Learning |
| CNN-LSTM | PyTorch | Deep Learning |

## Running Tests

```bash
# All tests
python3 test_comprehensive.py

# Quick (skip API calls)
python3 test_comprehensive.py --quick

# Specific category
python3 test_comprehensive.py --category dashboard
```

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| Analysis | Full technical + fundamental analysis |
| Compare | Side-by-side stock comparison |
| ML Predict | Price predictions with confidence intervals |
| Watchlist | Tracked stocks with live prices |
| Portfolio | Holdings and P&L |
| Alerts | Price alert management |
| News | Stock news feed |
| Sectors | Sector ETF performance |

## Disclaimer

For educational purposes only. Not financial advice. Do your own research before investing.

## License

MIT
