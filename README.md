# C++ High-Performance Trading Platform

A comprehensive, production-grade trading platform built in modern C++20, featuring low-latency order management, execution algorithms, risk management, backtesting, and market simulation capabilities.

![C++](https://img.shields.io/badge/C%2B%2B-20-blue.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)
![Tests](https://img.shields.io/badge/tests-339%20passing-brightgreen.svg)
![Lines of Code](https://img.shields.io/badge/lines%20of%20code-49%2C000-informational.svg)

## Overview

This trading platform provides a complete infrastructure for algorithmic trading, from market data handling through order execution and post-trade analytics. The system is designed with performance, modularity, and extensibility as core principles.

### Key Features

- **Low-Latency Architecture**: Lock-free data structures, cache-optimized order books, nanosecond-precision timing
- **Complete Order Lifecycle**: Order management, smart routing, execution algorithms (TWAP, VWAP, POV, Iceberg)
- **Risk Management**: Real-time position limits, P&L tracking, VaR calculations, circuit breakers
- **Strategy Framework**: Backtesting engine, signal generation, portfolio optimization
- **Production Systems**: Configuration management, observability, shadow trading for validation

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Trading Platform                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Market    │  │    Order    │  │  Execution  │  │    Risk     │    │
│  │    Data     │  │  Management │  │   Algos     │  │  Management │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         ▼                ▼                ▼                ▼            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Core Infrastructure                          │   │
│  │  • Lock-free Queues  • Order Books  • Type System  • Gateway    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                │                │                │            │
│         ▼                ▼                ▼                ▼            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Strategy   │  │  Backtest   │  │  Analytics  │  │   Shadow    │    │
│  │  Framework  │  │   Engine    │  │    Suite    │  │   Trading   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### Phase 1: Core Infrastructure
| Component | Description |
|-----------|-------------|
| **Type System** | Price, Quantity, OrderId, InstrumentId with compile-time safety |
| **Order Book** | Cache-optimized L2/L3 book with O(1) top-of-book access |
| **Lock-free Structures** | SPSC/MPMC queues, seqlock, object pool for zero-allocation paths |
| **Order Manager** | Complete order lifecycle with state machine validation |
| **Market Data** | Handlers for quotes, trades, and book updates |
| **Gateway** | Exchange connectivity abstraction layer |

### Phase 2: Trading Logic
| Component | Description |
|-----------|-------------|
| **Pricing Engine** | Black-Scholes, binomial trees, Monte Carlo, Greeks calculation |
| **Quoting Engine** | Market making with spread management and inventory control |
| **Hedging System** | Delta/gamma hedging, exposure aggregation |
| **Smart Order Router** | Multi-venue routing with latency-aware selection |
| **Execution Algorithms** | TWAP, VWAP, POV, Iceberg, Implementation Shortfall |
| **Historical Data** | Time series storage, corporate actions, replay capability |

### Phase 3: Strategy & Analytics
| Component | Description |
|-----------|-------------|
| **Strategy Framework** | Base classes, signal combination, position sizing (Kelly) |
| **Backtesting Engine** | Event-driven simulation with realistic fill modeling |
| **Analytics Suite** | Returns analysis, drawdown, rolling statistics |
| **Market Simulation** | Order book simulation, market impact models |
| **Performance Attribution** | P&L decomposition, factor analysis, TCA |
| **Risk Management** | VaR, portfolio risk, correlation analysis |

### Phase 4: Production Systems
| Component | Description |
|-----------|-------------|
| **Demo Mode** | Sandbox environment for testing |
| **Reference Data** | Instrument definitions, symbology, calendars |
| **Signal Generation** | Technical indicators, signal normalization, decay |
| **Configuration** | Hot-reload config, feature flags, versioning |
| **Observability** | Metrics, alerting, health monitoring |
| **Shadow Trading** | Paper trading, model validation, live comparison |

## Building

### Prerequisites

- C++20 compatible compiler (GCC 10+, Clang 12+, Apple Clang 14+)
- CMake 3.16+
- pthreads

### Build Instructions

```bash
# Clone the repository
git clone https://github.com/yourusername/trading_platform.git
cd trading_platform

# Create build directory
mkdir build && cd build

# Configure and build
cmake .. -DCMAKE_BUILD_TYPE=Release

# Linux
make -j$(nproc)

# macOS
make -j$(sysctl -n hw.ncpu)

# Run tests
ctest --output-on-failure
```

### Build Options

| Option | Default | Description |
|--------|---------|-------------|
| `CMAKE_BUILD_TYPE` | Release | Build type (Debug/Release/RelWithDebInfo) |
| `BUILD_TESTS` | ON | Build unit tests |
| `BUILD_BENCHMARKS` | OFF | Build performance benchmarks |

## Usage

### Running the Example

```bash
./bin/trading_example
```

### Running Tests

```bash
# Run all tests
ctest --output-on-failure

# Run specific test
./bin/test_execution
./bin/test_shadow
./bin/test_pricing
```

### Code Example

```cpp
#include <trading/platform.hpp>
#include <trading/shadow/shadow_controller.hpp>

int main() {
    using namespace trading;
    
    // Create shadow trading controller for paper trading
    shadow::ShadowController controller("my_strategy");
    
    // Configure circuit breakers
    shadow::CircuitBreakerConfig config;
    config.max_daily_loss = 10000.0;
    config.max_drawdown_pct = 5.0;
    controller.set_circuit_breaker_config(config);
    
    // Start in shadow mode
    controller.start();
    
    // Update market data
    shadow::MarketQuote quote;
    quote.instrument_id = "AAPL";
    quote.bid = 149.90;
    quote.ask = 150.10;
    controller.update_market_data(quote);
    
    // Process trading signals
    controller.process_signal("AAPL", 0.8, 0.75);  // bullish signal
    
    // Generate report
    auto report = controller.generate_report();
    
    return 0;
}
```

## Project Structure

```
trading_platform/
├── CMakeLists.txt
├── README.md
├── include/
│   └── trading/
│       ├── types.hpp              # Core type definitions
│       ├── order_book.hpp         # Order book implementation
│       ├── order_manager.hpp      # Order lifecycle management
│       ├── market_data.hpp        # Market data handling
│       ├── lockfree.hpp           # Lock-free data structures
│       ├── gateway.hpp            # Exchange connectivity
│       ├── platform.hpp           # Main include header
│       ├── pricing/               # Pricing models
│       ├── execution/             # Execution algorithms
│       ├── strategy/              # Strategy framework
│       ├── backtest/              # Backtesting engine
│       ├── analytics/             # Performance analytics
│       ├── risk/                  # Risk management
│       ├── portfolio/             # Portfolio optimization
│       ├── shadow/                # Shadow trading system
│       ├── observability/         # Monitoring & alerting
│       └── ...
├── tests/
│   ├── test_types.cpp
│   ├── test_order_book.cpp
│   ├── test_execution.cpp
│   └── ...
└── examples/
    └── main.cpp
```

## Performance Characteristics

- **Order Book Updates**: < 100ns per update
- **Lock-free Queue**: ~20ns enqueue/dequeue
- **Order Submission**: < 1μs internal latency
- **Memory**: Zero-allocation on critical paths using object pools

## Testing

The platform includes comprehensive test coverage:

- Unit tests for all components
- Integration tests for order flow
- Edge case handling
- Thread safety validation

```bash
# Run with verbose output
ctest -V

# Run specific test suite
./bin/test_shadow
./bin/test_execution
./bin/test_risk
```

## Extending the Platform

### Adding a New Execution Algorithm

```cpp
// In include/trading/execution/my_algo.hpp
class MyAlgorithm : public ExecutionAlgorithm {
public:
    SliceResult calculate_slice(const AlgoOrder& order, 
                                const MarketState& market) override {
        // Your algorithm logic here
    }
};
```

### Adding a New Signal Generator

```cpp
// In include/trading/signals/my_signal.hpp
class MySignal : public SignalGenerator {
public:
    double generate(InstrumentId id, const MarketData& data) override {
        // Your signal logic here
    }
};
```

## Future Enhancements

Potential areas for extension:

- [ ] FIX protocol connectivity
- [ ] Interactive Brokers / Alpaca integration
- [ ] Web-based dashboard (React)
- [ ] Machine learning model integration
- [ ] Cryptocurrency exchange support
- [ ] Options market making strategies

## License

This project is available for educational and portfolio purposes.

## Author

Built as a comprehensive demonstration of quantitative finance and systems programming skills, showcasing:

- Modern C++20 features (concepts, ranges, coroutines-ready)
- Low-latency design patterns
- Financial domain knowledge
- Production-quality software engineering
