---
name: ema-trend
description: EMA-based trend detection using dual EMA crossover and price position. Suitable for any OHLCV data on 1D/4H timeframe.
category: trend
tags:
  - trend
  - ema
  - simple
timeframes: [1d, 4h, 1h]
markets: [cn_futures, us_futures, a_stock, us_stock]
parameters:
  fast_period: 20
  slow_period: 50
  confirm_period: 5
---

# EMA Trend Strategy

## Purpose

Determine market direction using dual EMA crossover and price relative position. Primary for medium/long-term trend identification.

## Signal Logic

1. **EMA Calculation**: Calculate fast EMA (default 20) and slow EMA (default 50)
2. **Crossover Detection**: Golden cross (fast > slow) = bullish, death cross = bearish
3. **Price Confirmation**: Price above both EMAs = confirmed uptrend
4. **Trend Strength**: Use ADX or EMA slope angle for strength

## Output Format

```python
{
    "trend": "UP" | "DOWN" | "SIDEWAYS",
    "confidence": 0.0-1.0,
    "ema_fast": float,
    "ema_slow": float,
    "ema_diff": float,
    "signal": "LONG" | "SHORT" | "NEUTRAL"
}
```

## Signal Rules

| Condition | Signal | Trend |
|-----------|--------|-------|
| price > ema_fast > ema_slow | LONG | UP |
| price < ema_fast < ema_slow | SHORT | DOWN |
| ema_fast crossing ema_slow | NEUTRAL | TRANSITION |
| price < ema_fast < ema_slow | SHORT | DOWN |

## Implementation

```python
import pandas as pd
import numpy as np

def ema_trend(data: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    """Calculate EMA trend indicators."""
    df = data.copy()
    
    # Calculate EMAs
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    
    # EMA crossover signal
    df['ema_diff'] = df['ema_fast'] - df['ema_slow']
    df['ema_cross'] = np.where(df['ema_diff'] > 0, 1, -1)
    df['ema_cross_change'] = df['ema_cross'].diff()
    
    # Golden cross / Death cross
    df['golden_cross'] = df['ema_cross_change'] == 2
    df['death_cross'] = df['ema_cross_change'] == -2
    
    # Trend direction
    df['trend_up'] = (df['close'] > df['ema_fast']) & (df['ema_fast'] > df['ema_slow'])
    df['trend_down'] = (df['close'] < df['ema_fast']) & (df['ema_fast'] < df['ema_slow'])
    
    return df

def get_ema_signal(df: pd.DataFrame) -> dict:
    """Get current EMA trend signal."""
    last = df.iloc[-1]
    
    if last['trend_up']:
        direction = "UP"
        signal = "LONG"
        confidence = min(1.0, abs(last['ema_diff']) / last['close'] * 10)
    elif last['trend_down']:
        direction = "DOWN"
        signal = "SHORT"
        confidence = min(1.0, abs(last['ema_diff']) / last['close'] * 10)
    else:
        direction = "SIDEWAYS"
        signal = "NEUTRAL"
        confidence = 0.3
    
    return {
        "trend": direction,
        "confidence": confidence,
        "ema_fast": float(last['ema_fast']),
        "ema_slow": float(last['ema_slow']),
        "ema_diff": float(last['ema_diff']),
        "signal": signal
    }
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| fast_period | 20 | Fast EMA period |
| slow_period | 50 | Slow EMA period |
| confirm_period | 5 | Bars to confirm trend |

## Usage

```python
from skills.trend.ema_trend import ema_trend, get_ema_signal

# Calculate
df = ema_trend(data, fast=20, slow=50)

# Get signal
signal = get_ema_signal(df)
print(f"Trend: {signal['trend']}, Signal: {signal['signal']}")
```

## Dependencies

```bash
# None - only pandas/numpy required
```
