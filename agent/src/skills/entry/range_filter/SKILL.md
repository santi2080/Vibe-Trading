---
name: range-filter
description: Dynamic range filter for entry signals based on DonovanWall's Range Filter. Filters noise and identifies trend direction.
category: entry
tags:
  - entry
  - range-filter
  - breakout
  - medium
timeframes: [1d, 4h, 1h]
markets: [cn_futures, us_futures, a_stock, us_stock, crypto]
parameters:
  length: 14
  mult: 2.618
  use_wicks: true
---

# Range Filter Entry Strategy

## Purpose

Generate entry signals using dynamic range filtering. Price breaking above range = bullish, below = bearish. Filters minor price fluctuations.

## Signal Logic

1. **Calculate Smoothed Range**: Average true range over period
2. **Calculate Upper/Lower Bands**: SMA ± (Range × Multiplier)
3. **Direction**: Price > Upper = UP, Price < Lower = DOWN, Between = SIDEWAYS
4. **Entry**: Filter line crossover in trend direction

## Output Format

```python
{
    "direction": "UP" | "DOWN" | "SIDEWAYS",
    "filter": float,           # Current filter line
    "upper_band": float,        # Upper boundary
    "lower_band": float,       # Lower boundary
    "buffer": float,           # 0-1, distance from mid
    "signal": "LONG" | "SHORT" | "NEUTRAL",
    "entry_price": float | None
}
```

## Signal Rules

| Price Position | Direction | Signal |
|---------------|-----------|--------|
| > Upper Band | UP | LONG |
| < Lower Band | DOWN | SHORT |
| Between Bands | SIDEWAYS | NEUTRAL |

## Entry Confirmation

```python
# Long Entry Conditions:
# 1. Direction changes from SIDEWAYS to UP
# 2. Close crosses above filter line
# 3. Confirm with trend (if available)

# Short Entry Conditions:
# 1. Direction changes from SIDEWAYS to DOWN
# 2. Close crosses below filter line
```

## Implementation

```python
import pandas as pd
import numpy as np

def range_filter(data: pd.DataFrame, length: int = 14, mult: float = 2.618, use_wicks: bool = True) -> pd.DataFrame:
    """Calculate Range Filter indicator."""
    df = data.copy()
    
    # True Range calculation
    if use_wicks:
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift()).abs()
        tr3 = (df['low'] - df['close'].shift()).abs()
        rf_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    else:
        rf_range = df['close'] - df['open']
    
    # Smoothed range
    rf_smooth_range = rf_range.rolling(length).mean()
    
    # Final range with multiplier
    rf_range_final = rf_smooth_range * mult
    
    # Smoothed source price
    rf_smooth_src = df['close'].rolling(length).mean()
    
    # Upper/Lower bands
    rf_upper = rf_smooth_src + rf_range_final
    rf_lower = rf_smooth_src - rf_range_final
    rf_filter = (rf_upper + rf_lower) / 2  # Center line
    
    # Direction detection
    rf_dir = pd.Series(0, index=df.index)  # 0: SIDEWAYS
    rf_dir[df['close'] > rf_upper] = 1   # 1: UP
    rf_dir[df['close'] < rf_lower] = -1   # -1: DOWN
    
    # Buffer (distance from mid as ratio)
    dist_from_mid = (df['close'] - rf_smooth_src).abs()
    band_half = rf_range_final / 2.0
    band_half = band_half.replace(0, np.nan)
    rf_buffer = (dist_from_mid / band_half).clip(0, 1).fillna(0)
    
    # Direction change detection
    rf_dir_change = rf_dir.diff()
    
    df['rf_upper'] = rf_upper
    df['rf_lower'] = rf_lower
    df['rf_filter'] = rf_filter
    df['rf_dir'] = rf_dir
    df['rf_buffer'] = rf_buffer
    df['rf_dir_change'] = rf_dir_change
    
    return df

def get_rf_signal(df: pd.DataFrame) -> dict:
    """Get current Range Filter signal."""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    
    direction_map = {1: "UP", -1: "DOWN", 0: "SIDEWAYS"}
    
    if last['rf_dir'] == 1:
        signal = "LONG"
    elif last['rf_dir'] == -1:
        signal = "SHORT"
    else:
        signal = "NEUTRAL"
    
    # Entry signal: direction change from sideways
    if prev['rf_dir'] == 0 and last['rf_dir'] != 0:
        entry_price = float(last['close'])
    else:
        entry_price = None
    
    return {
        "direction": direction_map.get(int(last['rf_dir']), "SIDEWAYS"),
        "filter": float(last['rf_filter']),
        "upper_band": float(last['rf_upper']),
        "lower_band": float(last['rf_lower']),
        "buffer": float(last['rf_buffer']),
        "signal": signal,
        "entry_price": entry_price
    }

def detect_entry(df: pd.DataFrame) -> dict:
    """Detect entry signals."""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    
    # Long entry: filter crosses above price
    long_entry = (
        (prev['rf_dir'] <= 0) &  # Was not bullish
        (last['rf_dir'] == 1) &   # Now bullish
        (last['close'] > last['rf_filter'])  # Price above filter
    )
    
    # Short entry: filter crosses below price
    short_entry = (
        (prev['rf_dir'] >= 0) &  # Was not bearish
        (last['rf_dir'] == -1) &  # Now bearish
        (last['close'] < last['rf_filter'])  # Price below filter
    )
    
    return {
        "long_entry": bool(long_entry),
        "short_entry": bool(short_entry),
        "entry_price": float(last['close']),
        "entry_direction": "LONG" if long_entry else ("SHORT" if short_entry else "NEUTRAL")
    }
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| length | 14 | Range smoothing period |
| mult | 2.618 | Range multiplier (Fibonacci) |
| use_wicks | true | Use high/low vs close |

## Usage

```python
from skills.entry.range_filter import range_filter, get_rf_signal, detect_entry

# Calculate
df = range_filter(data, length=14, mult=2.618)

# Get current state
signal = get_rf_signal(df)
print(f"Direction: {signal['direction']}, Signal: {signal['signal']}")

# Detect entry
entry = detect_entry(df)
if entry['long_entry']:
    print(f"LONG ENTRY at {entry['entry_price']}")
```

## Range Multiplier Reference

| Multiplier | Use Case |
|-------------|----------|
| 1.0 | Tight ranges, scalping |
| 1.618 | Standard (Fibonacci golden ratio) |
| 2.0 | Normal volatility |
| 2.618 | Extended ranges (Fibonacci) |
| 3.0 | High volatility |

## Dependencies

```bash
# None - only pandas/numpy required
```
