#!/usr/bin/env python3
"""
趋势指标回测工具

测试不同趋势判断指标在各市场的表现

用法:
    python scripts/backtest_trend_indicators.py --symbol GC=F --compare
    python scripts/backtest_trend_indicators.py --all --output reports/
    python scripts/backtest_trend_indicators.py --market贵金属
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import warnings

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.data.watchlist import WatchlistReader
from src.data.watchlist_data_health import check_watchlist_data

# 测试品种配置
SYMBOLS_CONFIG = {
    # ===== 美国期货 =====
    '贵金属': [
        ('GC=F', '黄金', 'us_futures'),
        ('SI=F', '白银', 'us_futures'),
    ],
    '能源': [
        ('CL=F', 'WTI原油', 'us_futures'),
    ],
    '股指(美)': [
        ('ES=F', '标普500', 'us_futures'),
        ('NQ=F', '纳斯达克', 'us_futures'),
    ],
    '农产品': [
        ('ZC=F', '玉米', 'us_futures'),
    ],
    # ===== 美国ETF =====
    '债券ETF': [
        ('TLT', '长期国债', 'etf'),
        ('IAU', '黄金ETF', 'etf'),
    ],
    # ===== 美国行业ETF =====
    '科技': [
        ('XLK', '科技', 'us_stock'),
    ],
    '金融': [
        ('XLF', '金融', 'us_stock'),
    ],
    '医疗': [
        ('XLV', '医疗', 'us_stock'),
    ],
    '可选消费': [
        ('XLY', '可选消费', 'us_stock'),
    ],
    '必需消费': [
        ('XLP', '必需消费', 'us_stock'),
    ],
    '能源ETF': [
        ('XLE', '能源', 'us_stock'),
    ],
    '工业': [
        ('XLI', '工业', 'us_stock'),
    ],
    '材料': [
        ('XLB', '材料', 'us_stock'),
    ],
    '房地产': [
        ('XLRE', '房地产', 'us_stock'),
    ],
    '公用事业': [
        ('XLU', '公用事业', 'us_stock'),
    ],
    '通信': [
        ('XLC', '通信', 'us_stock'),
    ],
    '半导体': [
        ('SOXX', '半导体', 'us_stock'),
    ],
    # ===== A股ETF =====
    'A股股指': [
        ('510300.SS', '沪深300', 'cn_etf'),
        ('510500.SS', '中证500', 'cn_etf'),
    ],
    'A股行业': [
        ('512760.SS', '芯片ETF', 'cn_etf'),
        ('515790.SS', '光伏ETF', 'cn_etf'),
        ('512170.SS', '医疗ETF', 'cn_etf'),
    ],
}

ALL_SYMBOLS = [s for markets in SYMBOLS_CONFIG.values() for s in markets]

# 市场到目录映射
MARKET_DIR = {
    'us_futures': 'us_futures',
    'etf': 'etf',
    'us_stock': 'us_stocks',
    'cn_futures': 'cn_futures',
    'cn_etf': 'cn_etf',
}

# ============================================================
# 数据类
# ============================================================

@dataclass
class IndicatorResult:
    """单个指标结果"""
    name: str
    direction_score: float = 0.0      # 方向准确性 (0-100)
    lead_score: float = 0.0          # 信号领先性 (0-100)
    noise_score: float = 0.0          # 噪音过滤 (0-100)
    overall_score: float = 0.0        # 综合得分
    bullish_rate: float = 0.0         # 多头信号占比
    signal_count: int = 0             # 信号总数
    trend_changes: int = 0            # 趋势切换次数


@dataclass
class SymbolResult:
    """单个品种结果"""
    symbol: str
    name: str
    market: str
    timeframe: str
    data_points: int = 0
    period: str = ""
    indicators: Dict[str, IndicatorResult] = field(default_factory=dict)
    best_indicator: str = ""
    best_score: float = 0.0


# ============================================================
# 指标实现
# ============================================================

class TrendIndicatorBase:
    """趋势指标基类"""

    name: str = "Base"

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算指标"""
        raise NotImplementedError

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        """获取信号: 1=多头, -1=空头, 0=震荡"""
        raise NotImplementedError

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        """获取趋势评分: -100 到 +100"""
        raise NotImplementedError


class SuperTrendIndicator(TrendIndicatorBase):
    """SuperTrend 指标"""
    name = "SuperTrend"

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        high = df['high']
        low = df['low']
        close = df['close']

        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.period).mean()

        # HL/2
        hl2 = (high + low) / 2

        # Upper/Lower Band
        upperband = hl2 + (self.multiplier * atr)
        lowerband = hl2 - (self.multiplier * atr)

        # SuperTrend
        st = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(1, index=df.index)

        for i in range(self.period, len(df)):
            if i == self.period:
                st.iloc[i] = lowerband.iloc[i]
                direction.iloc[i] = 1
            else:
                prev_st = st.iloc[i-1]
                prev_dir = direction.iloc[i-1]

                if close.iloc[i] > prev_st:
                    st.iloc[i] = lowerband.iloc[i]
                    direction.iloc[i] = 1
                else:
                    st.iloc[i] = upperband.iloc[i]
                    direction.iloc[i] = -1

        df['supertrend'] = st
        df['st_direction'] = direction
        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'st_direction' not in df.columns:
            df = self.calculate(df)
        return df['st_direction']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'st_direction' not in df.columns:
            df = self.calculate(df)
        return df['st_direction'] * 100


class TrendFusionIndicator(TrendIndicatorBase):
    """TrendFusion 加权指标"""
    name = "TrendFusion"

    def __init__(self):
        self.st = SuperTrendIndicator(period=10, multiplier=3.0)
        self.ema_fast = 12
        self.ema_slow = 26

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()

        # EMA 方向
        df['ema_direction'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)

        # 价格方向
        df['price_direction'] = np.where(df['close'] > df['close'].shift(20), 1, -1)

        # SuperTrend
        df = self.st.calculate(df)

        # 加权评分
        df['trendfusion_score'] = (
            df['st_direction'] * 40 +  # SuperTrend 权重 40%
            df['ema_direction'] * 30 +  # EMA 交叉权重 30%
            df['price_direction'] * 30   # 价格动量权重 30%
        )

        df['trendfusion_signal'] = np.where(df['trendfusion_score'] > 0, 1,
                                            np.where(df['trendfusion_score'] < 0, -1, 0))
        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'trendfusion_signal' not in df.columns:
            df = self.calculate(df)
        return df['trendfusion_signal']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'trendfusion_score' not in df.columns:
            df = self.calculate(df)
        return df['trendfusion_score']


class EMACrossIndicator(TrendIndicatorBase):
    """EMA 交叉指标"""
    name = "EMACross"

    def __init__(self, fast: int = 12, slow: int = 26):
        self.fast = fast
        self.slow = slow

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ema_fast'] = df['close'].ewm(span=self.fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow, adjust=False).mean()
        df['ema_cross_signal'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)
        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'ema_cross_signal' not in df.columns:
            df = self.calculate(df)
        return df['ema_cross_signal']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'ema_cross_signal' not in df.columns:
            df = self.calculate(df)
        return df['ema_cross_signal'] * 100


class SMASlopeIndicator(TrendIndicatorBase):
    """SMA 斜率指标"""
    name = "SMASlope"

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['sma'] = df['close'].rolling(self.period).mean()
        df['sma_slope'] = df['sma'].diff(5) / df['sma'].shift(5) * 100  # 5日斜率百分比
        df['sma_signal'] = np.where(df['sma_slope'] > 0.5, 1,
                                   np.where(df['sma_slope'] < -0.5, -1, 0))
        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'sma_signal' not in df.columns:
            df = self.calculate(df)
        return df['sma_signal']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'sma_slope' not in df.columns:
            df = self.calculate(df)
        # 归一化到 -100 到 +100
        score = df['sma_slope'].clip(-100, 100)
        return score


class ADXIndicator(TrendIndicatorBase):
    """ADX 趋势强度指标"""
    name = "ADX"

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        high = df['high']
        low = df['low']
        close = df['close']

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.period).mean()

        # +DM, -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        plus_dm[((plus_dm > minus_dm) & (minus_dm < 0))] = 0
        minus_dm[((minus_dm > plus_dm) & (plus_dm < 0))] = 0

        # Smooth
        plus_dm_smooth = plus_dm.rolling(self.period).sum()
        minus_dm_smooth = minus_dm.rolling(self.period).sum()

        # DI
        plus_di = 100 * (plus_dm_smooth / atr)
        minus_di = 100 * (minus_dm_smooth / atr)

        # DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX
        adx = dx.rolling(self.period).mean()

        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        df['adx_signal'] = np.where(plus_di > minus_di, 1, -1)
        df['adx_signal'] = np.where(adx < 20, 0, df['adx_signal'])  # ADX < 20 为震荡

        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'adx_signal' not in df.columns:
            df = self.calculate(df)
        return df['adx_signal']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'adx' not in df.columns:
            df = self.calculate(df)
        # ADX 强度 * 方向
        score = df['adx'] * np.where(df['plus_di'] > df['minus_di'], 1, -1)
        return score.clip(-100, 100)


class RangeFilterIndicator(TrendIndicatorBase):
    """Range Filter 趋势指标"""
    name = "RangeFilter"

    def __init__(self, period: int = 20, mult: float = 2.0):
        self.period = period
        self.mult = mult

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df['close']

        # 范围
        ran = close.rolling(self.period).std() * self.mult

        # 上轨下轨
        df['rf_up'] = df['close'].rolling(self.period).mean() + ran
        df['rf_down'] = df['close'].rolling(self.period).mean() - ran

        # 信号
        df['rf_direction'] = 1  # 默认多头
        for i in range(self.period, len(df)):
            if close.iloc[i] < df['rf_down'].iloc[i-1]:
                df['rf_direction'].iloc[i] = -1
            elif close.iloc[i] > df['rf_up'].iloc[i-1]:
                df['rf_direction'].iloc[i] = 1
            else:
                df['rf_direction'].iloc[i] = df['rf_direction'].iloc[i-1]

        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'rf_direction' not in df.columns:
            df = self.calculate(df)
        return df['rf_direction']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'rf_direction' not in df.columns:
            df = self.calculate(df)
        return df['rf_direction'] * 100


class MTESIndicator(TrendIndicatorBase):
    """MTES 多周期趋势集成指标

    Multi-Timeframe Ensemble System：
    - 日线/当前周期: SuperTrend + EMA + ADX + RangeFilter + SMA slope
    - 周线: 同样组件计算后前向对齐到当前周期
    - 权重: 当前周期 70%，周线 30%（无周线时仅用当前周期）
    """
    name = "MTES"

    def __init__(self, weekly_df: Optional[pd.DataFrame] = None):
        self.weekly_df = weekly_df
        self.st = SuperTrendIndicator(period=10, multiplier=3.0)
        self.ema = EMACrossIndicator(fast=12, slow=26)
        self.adx = ADXIndicator(period=14)
        self.rf = RangeFilterIndicator(period=20, mult=2.0)
        self.sma = SMASlopeIndicator(period=20)

    def _component_score(self, df: pd.DataFrame) -> pd.Series:
        """计算单周期集成分数 (-100 到 +100)"""
        st_df = self.st.calculate(df.copy())
        ema_df = self.ema.calculate(df.copy())
        adx_df = self.adx.calculate(df.copy())
        rf_df = self.rf.calculate(df.copy())
        sma_df = self.sma.calculate(df.copy())

        st_score = self.st.get_score(st_df).fillna(0)
        ema_score = self.ema.get_score(ema_df).fillna(0)
        adx_score = self.adx.get_score(adx_df).fillna(0)
        rf_score = self.rf.get_score(rf_df).fillna(0)
        sma_score = self.sma.get_score(sma_df).fillna(0)

        score = (
            st_score * 0.30
            + ema_score * 0.20
            + adx_score * 0.20
            + rf_score * 0.15
            + sma_score * 0.15
        )
        return score.clip(-100, 100)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        daily_score = self._component_score(df)
        df['mtes_daily_score'] = daily_score

        if self.weekly_df is not None and len(self.weekly_df) >= 30:
            weekly_score = self._component_score(self.weekly_df.copy())
            aligned_weekly = weekly_score.reindex(df.index, method='ffill').fillna(0)
            df['mtes_weekly_score'] = aligned_weekly
            df['mtes_score'] = (daily_score * 0.70 + aligned_weekly * 0.30).clip(-100, 100)
        else:
            df['mtes_weekly_score'] = 0.0
            df['mtes_score'] = daily_score

        df['mtes_signal'] = np.where(
            df['mtes_score'] > 20,
            1,
            np.where(df['mtes_score'] < -20, -1, 0),
        )
        return df

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        if 'mtes_signal' not in df.columns:
            df = self.calculate(df)
        return df['mtes_signal']

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        if 'mtes_score' not in df.columns:
            df = self.calculate(df)
        return df['mtes_score']


# ============================================================
# 评估函数
# ============================================================

def evaluate_direction_accuracy(signal: pd.Series, future_returns: pd.Series, lookback: int = 5) -> float:
    """评估方向准确性

    计算信号方向与未来 N 日收益的一致率
    """
    # 对齐
    valid_idx = signal.index.intersection(future_returns.index)
    if len(valid_idx) == 0:
        return 50.0

    signal = signal.loc[valid_idx]
    future_returns = future_returns.loc[valid_idx]

    # 移除 NaN
    valid = ~(signal.isna() | future_returns.isna())
    signal = signal[valid]
    future_returns = future_returns[valid]

    if len(signal) == 0:
        return 50.0

    # 方向一致性
    correct = (signal * future_returns) > 0
    accuracy = correct.sum() / len(correct) * 100

    return accuracy


def evaluate_signal_lead(signal: pd.Series, returns: pd.Series, lookback: int = 10) -> float:
    """评估信号领先性

    计算信号与收益率的相关性
    """
    # 对齐
    valid_idx = signal.index.intersection(returns.index)
    if len(valid_idx) == 0:
        return 50.0

    signal = signal.loc[valid_idx]
    returns = returns.loc[valid_idx]

    # 移除 NaN
    valid = ~(signal.isna() | returns.isna())
    signal = signal[valid]
    returns = returns[valid]

    if len(signal) < 10:
        return 50.0

    # 领先性: 信号与未来收益的相关性
    lead_returns = returns.shift(-lookback)
    correlation = signal.corr(lead_returns)

    if pd.isna(correlation):
        return 50.0

    # 归一化到 0-100
    score = (correlation + 1) / 2 * 100
    return score


def evaluate_noise_filter(signal: pd.Series, close: pd.Series, window: int = 10) -> float:
    """评估噪音过滤能力

    计算趋势内反向波动占比
    """
    # 对齐
    valid_idx = signal.index.intersection(close.index)
    if len(valid_idx) == 0:
        return 50.0

    signal = signal.loc[valid_idx]
    close = close.loc[valid_idx]

    if len(signal) < window:
        return 50.0

    # 计算趋势持续性
    trend_changes = (signal.diff() != 0).sum()
    total_bars = len(signal)

    # 趋势切换越少越好
    stability = (total_bars - trend_changes) / total_bars * 100

    return stability


# ============================================================
# 主函数
# ============================================================

def get_indicators(weekly_df: Optional[pd.DataFrame] = None) -> List[TrendIndicatorBase]:
    """获取所有指标实例"""
    return [
        SuperTrendIndicator(period=10, multiplier=3.0),
        TrendFusionIndicator(),
        EMACrossIndicator(fast=12, slow=26),
        SMASlopeIndicator(period=20),
        ADXIndicator(period=14),
        RangeFilterIndicator(period=20, mult=2.0),
        MTESIndicator(weekly_df=weekly_df),
    ]


def load_data(symbol: str, market: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    """加载数据"""
    data_dir = PROJECT_ROOT / "data" / MARKET_DIR.get(market, market) / symbol
    data_path = data_dir / f"{timeframe}.parquet"

    if not data_path.exists():
        print(f"  ⚠️ 数据文件不存在: {data_path}")
        return None

    df = pd.read_parquet(data_path)

    # 标准化列名 (yfinance 格式 -> 小写)
    col_map = {
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
        'Volume': 'volume', 'Adj Close': 'adj_close'
    }
    df.columns = [col_map.get(c, c.lower()) for c in df.columns]
    df.columns = [c.lower() for c in df.columns]  # 确保全小写

    return df


def backtest_symbol(symbol: str, name: str, market: str, timeframe: str = "1d") -> SymbolResult:
    """回测单个品种"""
    print(f"\n📊 回测 {symbol} ({name}) - {timeframe}")

    # 加载数据
    df = load_data(symbol, market, timeframe)
    if df is None or len(df) < 100:
        print(f"  ❌ 数据不足")
        return None

    result = SymbolResult(
        symbol=symbol,
        name=name,
        market=market,
        timeframe=timeframe,
        data_points=len(df),
        period=f"{str(df.index[0])[:10]} to {str(df.index[-1])[:10]}"
    )

    # 计算收益率
    df['returns'] = df['close'].pct_change()
    df['future_returns'] = df['returns'].shift(-5)  # 5日后收益

    # 获取周线数据供 MTES 使用（日线回测时使用 1W 对齐；周线回测时不用额外周线）
    weekly_df = None
    if timeframe == "1d":
        weekly_df = load_data(symbol, market, "1W")

    # 获取指标
    indicators = get_indicators(weekly_df=weekly_df)

    for indicator in indicators:
        try:
            # 计算指标
            df_ind = indicator.calculate(df.copy())

            # 获取信号
            signal = indicator.get_signal(df_ind)

            # 评估
            direction_acc = evaluate_direction_accuracy(signal, df_ind['future_returns'])
            lead_score = evaluate_signal_lead(signal, df_ind['returns'])
            noise_score = evaluate_noise_filter(signal, df_ind['close'])

            # 综合得分
            overall = (direction_acc * 0.4 + lead_score * 0.3 + noise_score * 0.3)

            # 信号统计
            bullish_rate = (signal == 1).sum() / len(signal) * 100
            trend_changes = (signal.diff() != 0).sum()

            indicator_result = IndicatorResult(
                name=indicator.name,
                direction_score=round(direction_acc, 1),
                lead_score=round(lead_score, 1),
                noise_score=round(noise_score, 1),
                overall_score=round(overall, 1),
                bullish_rate=round(bullish_rate, 1),
                signal_count=len(signal),
                trend_changes=int(trend_changes)
            )

            result.indicators[indicator.name] = indicator_result
            print(f"  ✅ {indicator.name}: 方向={direction_acc:.1f}%, 领先={lead_score:.1f}%, 噪音={noise_score:.1f}%, 综合={overall:.1f}")

        except Exception as e:
            print(f"  ❌ {indicator.name}: {e}")

    # 找出最佳指标
    if result.indicators:
        best = max(result.indicators.values(), key=lambda x: x.overall_score)
        result.best_indicator = best.name
        result.best_score = best.overall_score

    return result


def _serialize_gate_payload(payload: dict[str, Any]) -> str:
    """Serialize gate payloads with consistent JSON formatting."""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_watchlist_gate_payload(watchlist_path: str | Path, now: datetime | None = None) -> dict[str, Any]:
    """Build the watchlist data-health gate payload for backtest entry points."""
    report = check_watchlist_data(
        watchlist_path=watchlist_path,
        data_dir=PROJECT_ROOT / "data",
        now=now,
    )
    report_payload = report.to_dict()
    if report.can_backtest:
        message = "Watchlist data health check passed before backtest execution"
        if report.gate_status == "WARN":
            message = "Watchlist data health check passed with warnings before backtest execution"
        return {
            "status": "ok",
            "message": message,
            **report_payload,
        }
    return {
        "status": "error",
        "error_type": "data_health_gate_blocked",
        "message": "Watchlist data health blocked backtest execution",
        **report_payload,
    }


def _load_watchlist_symbols(
    watchlist_path: str | Path,
    market_filter: str | None = None,
) -> list[tuple[str, str, str]]:
    """Load symbol/name/market tuples from a watchlist CSV."""
    reader = WatchlistReader(str(watchlist_path))
    symbols: list[tuple[str, str, str]] = []
    for item in reader.load_raw():
        symbol = item.get("symbol", "")
        if not symbol or symbol.lower() in ("symbol", "code", "name"):
            continue
        market = item.get("market", "us_futures")
        if market_filter and market.upper() != market_filter.upper():
            continue
        symbols.append((symbol, item.get("name") or symbol, market))
    return symbols


def run_watchlist_backtest(
    watchlist_path: str | Path,
    *,
    timeframe: str = "1d",
    market_filter: str | None = None,
    output_dir: Path | None = None,
    now: datetime | None = None,
    emit_output: bool = True,
) -> tuple[int, dict[str, Any], list[SymbolResult]]:
    """Run the watchlist-aware backtest path with a local data-health gate."""
    gate_payload = build_watchlist_gate_payload(watchlist_path, now=now)
    if emit_output:
        print(_serialize_gate_payload(gate_payload))

    if not gate_payload["gate"]["can_backtest"]:
        if emit_output:
            print("❌ Watchlist data health blocked backtest execution.", file=sys.stderr)
        return 1, gate_payload, []

    symbols = _load_watchlist_symbols(watchlist_path, market_filter=market_filter)
    if emit_output:
        print(f"\n🔍 测试 Watchlist: {watchlist_path} ({len(symbols)} 个品种)")

    results: list[SymbolResult] = []
    for symbol, name, market in symbols:
        result = backtest_symbol(symbol, name, market, timeframe)
        if result:
            results.append(result)

    if results:
        generate_report(results, output_dir or Path("reports"), gate_payload=gate_payload)

    return 0, gate_payload, results


def generate_report(results: List[SymbolResult], output_dir: Path, gate_payload: dict[str, Any] | None = None) -> Path:
    """生成报告"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. CSV 对比表
    csv_path = output_dir / f"trend_indicator_comparison_{timestamp}.csv"
    rows = []
    for result in results:
        for ind_name, ind_result in result.indicators.items():
            rows.append({
                'symbol': result.symbol,
                'name': result.name,
                'timeframe': result.timeframe,
                'indicator': ind_name,
                'direction_score': ind_result.direction_score,
                'lead_score': ind_result.lead_score,
                'noise_score': ind_result.noise_score,
                'overall_score': ind_result.overall_score,
                'bullish_rate': ind_result.bullish_rate,
                'trend_changes': ind_result.trend_changes,
            })

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    print(f"\n✅ CSV 报告: {csv_path}")

    # 2. Markdown 报告
    md_path = output_dir / f"trend_indicator_report_{timestamp}.md"

    # 计算各指标平均得分
    indicator_avg = df.groupby('indicator').agg({
        'direction_score': 'mean',
        'lead_score': 'mean',
        'noise_score': 'mean',
        'overall_score': 'mean',
    }).round(1).sort_values('overall_score', ascending=False)

    gate_summary = ""
    if gate_payload:
        gate = gate_payload.get("gate", {})
        gate_summary = f"""
## Watchlist Data Health Gate

- Gate 状态: {gate.get("status", "N/A")}
- 可回测: {gate.get("can_backtest", False)}
- Blocking failures: {gate.get("blocking_failures", 0)}
- Warnings: {gate.get("warnings", 0)}

"""

    # 生成报告
    report = f"""# 趋势指标回测报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 摘要

- 测试品种: {len(results)} 个
- 测试周期: {results[0].period if results else 'N/A'}
- 时间框架: {results[0].timeframe if results else 'N/A'}
{gate_summary}## 指标平均得分排名

| 排名 | 指标 | 方向准确性 | 信号领先性 | 噪音过滤 | 综合得分 |
|:----:|------|:----------:|:----------:|:--------:|:--------:|
"""
    for i, (ind_name, row) in enumerate(indicator_avg.iterrows(), 1):
        report += f"| {i} | {ind_name} | {row['direction_score']:.1f}% | {row['lead_score']:.1f}% | {row['noise_score']:.1f}% | **{row['overall_score']:.1f}** |\n"

    report += """
## 各品种最佳指标

| 品种 | 符号 | 最佳指标 | 综合得分 |
|------|------|---------|:--------:|
"""
    for result in sorted(results, key=lambda x: x.best_score, reverse=True):
        report += f"| {result.name} | {result.symbol} | {result.best_indicator} | {result.best_score:.1f} |\n"

    report += """
## 详细结果

"""
    for result in results:
        report += f"""### {result.symbol} - {result.name}

**时间范围**: {result.period}
**数据点数**: {result.data_points}

| 指标 | 方向准确性 | 信号领先性 | 噪音过滤 | 综合得分 | 多头占比 | 趋势切换 |
|------|:----------:|:----------:|:--------:|:--------:|:--------:|:--------:|
"""
        for ind_name, ind_result in sorted(result.indicators.items(), key=lambda x: x[1].overall_score, reverse=True):
            report += f"| {ind_name} | {ind_result.direction_score:.1f}% | {ind_result.lead_score:.1f}% | {ind_result.noise_score:.1f}% | **{ind_result.overall_score:.1f}** | {ind_result.bullish_rate:.1f}% | {ind_result.trend_changes} |\n"
        report += "\n"

    report += f"""
## 结论

基于 {len(results)} 个品种的回测结果：

1. **综合最优指标**: {indicator_avg.index[0]} (综合得分: {indicator_avg.iloc[0]['overall_score']:.1f})
2. **最稳定指标**: {indicator_avg['noise_score'].idxmax()} (噪音过滤得分: {indicator_avg['noise_score'].max():.1f})
3. **最佳方向判断**: {indicator_avg['direction_score'].idxmax()} (方向准确性: {indicator_avg['direction_score'].max():.1f}%)

---
*报告由 vibe-trading 趋势指标回测工具生成*
"""

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ Markdown 报告: {md_path}")

    return md_path


def _parse_gate_now(now_value: str) -> datetime | None:
    """Parse optional ISO timestamp used by the watchlist gate."""
    if not now_value:
        return None
    try:
        return datetime.fromisoformat(now_value)
    except ValueError as exc:
        raise ValueError(f"Invalid --now timestamp: {now_value}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description='趋势指标回测工具')
    parser.add_argument('--symbol', type=str, help='单一品种符号')
    parser.add_argument('--name', type=str, default='', help='品种名称')
    parser.add_argument('--market', type=str, default='us_futures', help='市场类型')
    parser.add_argument('--timeframe', type=str, default='1d', choices=['1d', '1W'], help='时间周期')
    parser.add_argument('--compare', action='store_true', help='比较所有指标')
    parser.add_argument('--all', action='store_true', help='测试所有品种')
    parser.add_argument('--watchlist', type=str, help='基于 watchlist 执行受 data health gate 保护的回测')
    parser.add_argument('--now', type=str, default='', help='watchlist gate 使用的 ISO 时间戳（测试用）')
    parser.add_argument('--market-filter', type=str, help='市场过滤 (贵金属/能源/股指/农产品/债券/ETF)')
    parser.add_argument('--output', type=str, default='reports', help='输出目录')

    args = parser.parse_args()

    results = []
    output_dir = Path(args.output)
    try:
        gate_now = _parse_gate_now(args.now)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.watchlist:
        exit_code, _, _ = run_watchlist_backtest(
            args.watchlist,
            timeframe=args.timeframe,
            market_filter=args.market_filter,
            output_dir=output_dir,
            now=gate_now,
            emit_output=True,
        )
        return exit_code

    if args.symbol:
        # 单品种测试
        name = args.name or args.symbol
        result = backtest_symbol(args.symbol, name, args.market, args.timeframe)
        if result:
            results.append(result)

    elif args.market_filter:
        # 按市场过滤
        if args.market_filter in SYMBOLS_CONFIG:
            symbols = SYMBOLS_CONFIG[args.market_filter]
            print(f"\n🔍 测试市场: {args.market_filter} ({len(symbols)} 个品种)")
            for symbol, name, market in symbols:
                result = backtest_symbol(symbol, name, market, args.timeframe)
                if result:
                    results.append(result)
        else:
            print(f"❌ 未知市场: {args.market_filter}")
            print(f"可用市场: {list(SYMBOLS_CONFIG.keys())}")
            return 1

    elif args.all or args.compare:
        # 所有品种
        print(f"\n🔍 测试所有品种 ({len(ALL_SYMBOLS)} 个)")
        for symbol, name, market in ALL_SYMBOLS:
            result = backtest_symbol(symbol, name, market, args.timeframe)
            if result:
                results.append(result)

    else:
        print("❌ 请指定 --symbol, --market-filter, --watchlist, 或 --all")
        print("\n用法示例:")
        print("  python scripts/backtest_trend_indicators.py --symbol GC=F --compare")
        print("  python scripts/backtest_trend_indicators.py --market-filter 贵金属")
        print("  python scripts/backtest_trend_indicators.py --watchlist watchlist/us_futures_watchlist.csv")
        print("  python scripts/backtest_trend_indicators.py --all --output reports/")
        return 1

    # 生成报告
    if results:
        generate_report(results, output_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
