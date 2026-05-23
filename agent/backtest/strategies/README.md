"""Strategy System Documentation for Vibe-Trading.

# Strategy System Overview

The strategy system provides a modular, extensible framework for
defining and running trading strategies in backtests.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    StrategyRegistry                         │
│         (Central registration & lookup)                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Trend       │  │  Pullback     │  │    Entry      │
│  Strategies  │  │  Strategies   │  │  Strategies   │
├───────────────┤  ├───────────────┤  ├───────────────┤
│ - EMA+ADX    │  │ - RSI        │  │ - Breakout    │
│ - MACD       │  │ - Bollinger  │  │ - Volume Spike│
│ - Dual EMA   │  │ - Stochastic │  │ - VWAP       │
│              │  │ - Fibonacci  │  │ - Confluence  │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Strategy Types

### 1. Trend Strategies
Identify the primary direction of the market.

- **TrendEmaAdxStrategy**: EMA crossover with ADX confirmation
- **TrendMacdStrategy**: MACD crossover
- **TrendDualEmaStrategy**: Simple dual EMA crossover

### 2. Pullback Strategies
Identify corrections against the primary trend.

- **PullbackRsiStrategy**: RSI oversold/overbought conditions
- **PullbackBollingerBandsStrategy**: Bollinger Band touches
- **PullbackStochasticStrategy**: Stochastic crossovers
- **PullbackFibonacciStrategy**: Fibonacci retracement levels

### 3. Entry Strategies
Generate precise entry signals with confirmation.

- **BreakoutEntryStrategy**: Price breakout with volume confirmation
- **VolumeSpikeEntryStrategy**: Volume spike entries
- **VwapEntryStrategy**: VWAP crossover entries
- **SignalConfluenceStrategy**: Multiple indicator confluence

## Usage

### Basic Usage

```python
from agent.backtest.strategies import StrategyRegistry
from agent.backtest.strategies.trend import TrendEmaAdxStrategy

# Get a registered strategy
strategy = StrategyRegistry.get("trend_ema_adx")

# Generate signals
result = strategy.generate(df)
```

### Custom Strategy

```python
from agent.backtest.strategies import BaseStrategy, StrategyType

class MyStrategy(BaseStrategy):
    def _calculate(self, df):
        # Calculate indicators
        return {"indicator": df["close"].rolling(20).mean()}

    def _generate_signals(self, df, indicators):
        # Generate signals
        return pd.Series(0, index=df.index)

# Register
StrategyRegistry.register(MyStrategy("my_strategy", StrategyType.TREND))
```

### List Available Strategies

```python
from agent.backtest.strategies import StrategyRegistry, StrategyType

# All strategies
all_strategies = StrategyRegistry.list_strategies()

# By type
trend_strategies = StrategyRegistry.list_strategies(StrategyType.TREND)
```

## Trading Sessions

### China Futures

```python
from agent.backtest.strategies.sessions import SessionManager

# Filter to trading hours
df_filtered = SessionManager.filter_by_session(df, "china_futures")

# Check if timestamp is trading time
is_trading = SessionManager.is_trading_time(timestamp, "china_futures")
```

### Session Types

- `china_futures`: Day (9:00-10:15, 10:30-11:30, 13:30-15:00) + Night (21:00-23:00)
- `us_futures`: Regular trading hours
- `crypto`: 24/7

## Performance Considerations

1. **Indicator Caching**: Calculate once, reuse multiple times
2. **Vectorized Operations**: All calculations use pandas/numpy vectorization
3. **Memory Management**: Large datasets processed in chunks

## Testing

```bash
# Run all strategy tests
pytest agent/tests/backtest/strategies/ -v

# Run specific test file
pytest agent/tests/backtest/strategies/test_strategies.py -v
```
"""

# This file contains the strategy system documentation
