---
name: adx-trend
description: ADX-based trend strength indicator using Wilder's smoothing. Measures trend intensity without direction bias.
category: trend
tags:
  - trend
  - adx
  - medium
timeframes: [1d, 4h, 1h]
markets: [cn_futures, us_futures, a_stock, us_stock]
parameters:
  period: 14
  adx_threshold: 25
---

# ADX Trend Strategy

## Purpose

Measure trend strength using Average Directional Index (ADX). ADX > 25 indicates trending market, ADX < 20 suggests sideways.

## Signal Logic

1. **Calculate True Range (TR)**: Max of (H-L, |H-Cprev|, |L-Cprev|)
2. **Calculate +DI and -DI**: Directional indicators
3. **Calculate DX**: |+DI - -DI| / (+DI + -DI) * 100
4. **Calculate ADX**: Wilder's smoothing of DX
5. **Direction**: Compare +DI vs -DI

## Output Format

```python
{
    "trend": "UP" | "DOWN" | "SIDEWAYS",
    "adx": float,          # 0-100, higher = stronger trend
    "adx_pos": float,       # +DI directional strength
    "adx_neg": float,       # -DI directional strength
    "signal": "LONG" | "SHORT" | "NEUTRAL",
    "strength": "WEAK" | "MODERATE" | "STRONG"
}
```

## Signal Rules

| ADX | +DI > -DI | Signal | Trend |
|-----|-----------|--------|-------|
| > 25 | Yes | LONG | UP |
| > 25 | No | SHORT | DOWN |
| < 20 | - | NEUTRAL | SIDEWAYS |
| 20-25 | - | Based on DI | TRANSITION |

## Implementation

```python
import pandas as pd
import numpy as np

def calculate_true_range(high, low, close):
    """Calculate True Range."""
    hl = high - low
    hc = np.abs(high - np.roll(close, 1))
    lc = np.abs(low - np.roll(close, 1))
    hc[0] = hl.iloc[0] if len(hc) > 0 else 0
    lc[0] = hl.iloc[0] if len(lc) > 0 else 0
    return np.maximum(hl, np.maximum(hc, lc))

def adx_trend(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ADX indicator."""
    df = data.copy()
    n = len(df)
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # True Range
    tr = calculate_true_range(df['high'], df['low'], pd.Series(close))
    
    # Directional Movement
    high_diff = np.diff(high, prepend=high[0])
    low_diff = -np.diff(low, prepend=low[0])
    
    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    
    # Wilder's Smoothing
    alpha = 1.0 / period
    plus_dm_smooth = np.zeros(n)
    minus_dm_smooth = np.zeros(n)
    tr_smooth = np.zeros(n)
    
    plus_dm_smooth[period-1] = np.sum(plus_dm[:period])
    minus_dm_smooth[period-1] = np.sum(minus_dm[:period])
    tr_smooth[period-1] = np.sum(tr[:period])
    
    for i in range(period, n):
        plus_dm_smooth[i] = plus_dm_smooth[i-1] * (1-alpha) + plus_dm[i] * alpha
        minus_dm_smooth[i] = minus_dm_smooth[i-1] * (1-alpha) + minus_dm[i] * alpha
        tr_smooth[i] = tr_smooth[i-1] * (1-alpha) + tr[i] * alpha
    
    # +DI and -DI
    df['adx_pos'] = 100 * plus_dm_smooth / np.maximum(tr_smooth, 1e-10)
    df['adx_neg'] = 100 * minus_dm_smooth / np.maximum(tr_smooth, 1e-10)
    
    # DX
    dx = 100 * np.abs(df['adx_pos'] - df['adx_neg']) / (df['adx_pos'] + df['adx_neg'] + 1e-10)
    
    # ADX (Wilder's smoothing of DX)
    df['adx'] = dx.rolling(period).mean()
    for i in range(period * 2, n):
        if pd.notna(df['adx'].iloc[i-1]):
            df['adx'].iloc[i] = df['adx'].iloc[i-1] * (1-alpha) + dx.iloc[i] * alpha
    
    return df

def get_adx_signal(df: pd.DataFrame, threshold: float = 25.0) -> dict:
    """Get current ADX trend signal."""
    last = df.iloc[-1]
    adx = last['adx'] if pd.notna(last['adx']) else 0
    pos = last['adx_pos'] if pd.notna(last['adx_pos']) else 0
    neg = last['adx_neg'] if pd.notna(last['adx_neg']) else 0
    
    if adx > threshold:
        if pos > neg:
            signal = "LONG"
            trend = "UP"
        else:
            signal = "SHORT"
            trend = "DOWN"
    else:
        signal = "NEUTRAL"
        trend = "SIDEWAYS"
    
    if adx < 20:
        strength = "WEAK"
    elif adx < 40:
        strength = "MODERATE"
    else:
        strength = "STRONG"
    
    return {
        "trend": trend,
        "adx": float(adx),
        "adx_pos": float(pos),
        "adx_neg": float(neg),
        "signal": signal,
        "strength": strength
    }
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| period | 14 | ADX calculation period |
| adx_threshold | 25 | Threshold for trending market |

## Usage

```python
from skills.trend.adx_trend import adx_trend, get_adx_signal

# Calculate
df = adx_trend(data, period=14)

# Get signal
signal = get_adx_signal(df, threshold=25)
print(f"Trend: {signal['trend']}, ADX: {signal['adx']:.1f}, Signal: {signal['signal']}")
```

## ADX Interpretation

| ADX Value | Interpretation |
|-----------|----------------|
| 0-20 | Weak/Non-trending |
| 20-25 | Weak trend |
| 25-50 | Strong trend |
| 50-75 | Very strong trend |
| 75-100 | Extremely strong trend |

## Dependencies

```bash
# None - only pandas/numpy required
```
