#!/usr/bin/env python3
"""
MTES vs 经典趋势策略对比回测脚本

对比 5 个趋势策略在同一品种、同一时间段的历史绩效：
  A  MTES            - 六维度加权评分 (BULL_CONFIRMED/STRONG -> LONG)
  B  EMA(50/200)    - 经典均线黄金交叉
  C  ADX(14)>25     - ADX 趋势强度过滤
  D  MACD(12/26/9)  - MACD 零轴穿越
  E  Donchian(55)   - 结构突破

指标: 年化收益率, 夏普比率, 卡玛比率, 最大回撤, 交易次数, 胜率, 平均盈亏比

用法:
    python scripts/compare_mtes_strategies.py
    python scripts/compare_mtes_strategies.py --symbol GC=F --start 2023-01-01 --end 2025-06-01
    python scripts/compare_mtes_strategies.py --symbols GC=F ES=F BTC-USD --asset-class futures
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

# ── 项目路径 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from backtest.models import TradeRecord
from backtest.metrics import win_rate_and_stats, calc_bars_per_year
from backtest.strategies import BaseStrategy, StrategySignal, StrategyType
from backtest.strategies.major_trend import MajorTrendEvaluationStrategy
from src.analysis.major_trend_evaluator import MajorTrendEvaluator, calculate_adx


# ──────────────────────────────────────────────────────────────────
# 1. 策略实现
# ──────────────────────────────────────────────────────────────────

class EMAGoldenCrossStrategy(BaseStrategy):
    """EMA(50/200) 黄金交叉 — 多头: fast_ema > slow_ema."""

    def __init__(self, fast: int = 50, slow: int = 200):
        super().__init__(
            name="ema_golden_cross",
            strategy_type=StrategyType.TREND,
            parameters={"fast": fast, "slow": slow},
        )
        self.fast = fast
        self.slow = slow

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = 0
        fast = df["ema_fast"].values
        slow = df["ema_slow"].values
        # 交叉信号
        diff = fast - slow
        prev = np.roll(diff, 1)
        prev[0] = diff[0]
        # 从空头转多头
        long_mask = (prev <= 0) & (diff > 0)
        # 从多头转空头
        short_mask = (prev >= 0) & (diff < 0)
        df.loc[long_mask, "signal"] = 1
        df.loc[short_mask, "signal"] = -1
        return df


class ADXTrendStrategy(BaseStrategy):
    """ADX(14) 趋势策略 — ADX > threshold 且 DI+/DI- 方向确认."""

    def __init__(self, period: int = 14, threshold: float = 25.0):
        super().__init__(
            name="adx_trend",
            strategy_type=StrategyType.TREND,
            parameters={"period": period, "threshold": threshold},
        )
        self.period = period
        self.threshold = threshold

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        adx_vals, plus_di_vals, minus_di_vals = calculate_adx(df, self.period)
        df["adx"] = adx_vals.values
        df["plus_di"] = plus_di_vals.values
        df["minus_di"] = minus_di_vals.values
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = 0
        adx_vals = df["adx"].values
        plus_di = df["plus_di"].values
        minus_di = df["minus_di"].values
        # ADX > threshold 且 +DI > -DI -> 多头
        long_mask = (adx_vals > self.threshold) & (plus_di > minus_di)
        # ADX > threshold 且 -DI > +DI -> 空头
        short_mask = (adx_vals > self.threshold) & (minus_di > plus_di)
        df.loc[long_mask, "signal"] = 1
        df.loc[short_mask, "signal"] = -1
        return df


class MACDZeroCrossStrategy(BaseStrategy):
    """MACD(12/26/9) 零轴穿越."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(
            name="macd_zero_cross",
            strategy_type=StrategyType.TREND,
            parameters={"fast": fast, "slow": slow, "signal": signal},
        )
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        df["macd"] = macd_line
        df["macd_signal"] = signal_line
        df["macd_hist"] = macd_line - signal_line
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = 0
        macd = df["macd"].values
        macd_prev = np.roll(macd, 1)
        macd_prev[0] = macd[0]
        # MACD 从负转正 -> 多头
        long_mask = (macd_prev <= 0) & (macd > 0)
        # MACD 从正转负 -> 空头
        short_mask = (macd_prev >= 0) & (macd < 0)
        df.loc[long_mask, "signal"] = 1
        df.loc[short_mask, "signal"] = -1
        return df


class SuperTrendStrategy(BaseStrategy):
    """SuperTrend(10,3) 策略 — ATR 追踪止损."""

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        super().__init__(
            name="supertrend",
            strategy_type=StrategyType.TREND,
            parameters={"period": period, "multiplier": multiplier},
        )
        self.period = period
        self.multiplier = multiplier

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # ATR
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()

        # 基础带
        hl_avg = (high + low) / 2
        basic_ub = hl_avg + self.multiplier * atr
        basic_lb = hl_avg - self.multiplier * atr

        # 最终带（向量化）
        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()
        supertrend = close.copy() * 0
        direction = pd.Series(1, index=df.index)

        for i in range(self.period, len(df)):
            if basic_ub.iloc[i] < final_ub.iloc[i - 1] or close.iloc[i - 1] > final_ub.iloc[i - 1]:
                final_ub.iloc[i] = basic_ub.iloc[i]
            else:
                final_ub.iloc[i] = final_ub.iloc[i - 1]

            if basic_lb.iloc[i] > final_lb.iloc[i - 1] or close.iloc[i - 1] < final_lb.iloc[i - 1]:
                final_lb.iloc[i] = basic_lb.iloc[i]
            else:
                final_lb.iloc[i] = final_lb.iloc[i - 1]

            if supertrend.iloc[i - 1] == final_ub.iloc[i - 1] and close.iloc[i] <= final_ub.iloc[i]:
                supertrend.iloc[i] = final_ub.iloc[i]
                direction.iloc[i] = -1
            elif supertrend.iloc[i - 1] == final_ub.iloc[i - 1] and close.iloc[i] > final_ub.iloc[i]:
                supertrend.iloc[i] = final_lb.iloc[i]
                direction.iloc[i] = 1
            elif supertrend.iloc[i - 1] == final_lb.iloc[i - 1] and close.iloc[i] >= final_lb.iloc[i]:
                supertrend.iloc[i] = final_lb.iloc[i]
                direction.iloc[i] = 1
            elif supertrend.iloc[i - 1] == final_lb.iloc[i - 1] and close.iloc[i] < final_lb.iloc[i]:
                supertrend.iloc[i] = final_ub.iloc[i]
                direction.iloc[i] = -1

        df["atr"] = atr
        df["supertrend"] = supertrend
        df["st_direction"] = direction
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = df["st_direction"].values
        return df


class DonchianBreakoutStrategy(BaseStrategy):
    """Donchian(55) 突破策略."""

    def __init__(self, period: int = 55):
        super().__init__(
            name="donchian_breakout",
            strategy_type=StrategyType.TREND,
            parameters={"period": period},
        )
        self.period = period

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["donch_high"] = df["high"].rolling(self.period).max()
        df["donch_low"] = df["low"].rolling(self.period).min()
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = 0
        close = df["close"].values
        donch_high = df["donch_high"].values
        donch_low = df["donch_low"].values
        # 突破上轨 -> 多头
        long_mask = close > donch_high
        # 跌破下轨 -> 空头
        short_mask = close < donch_low
        df.loc[long_mask, "signal"] = 1
        df.loc[short_mask, "signal"] = -1
        return df


# ──────────────────────────────────────────────────────────────────
# 2. MTES 策略 (复用 MajorTrendEvaluator)
# ──────────────────────────────────────────────────────────────────

class MTESBacktestWrapper(BaseStrategy):
    """MTES 策略包装 — 在历史 OHLCV DataFrame 上逐 bar 评分."""

    def __init__(self, asset_class: str = "stock", min_state: str = "BULL_CONFIRMED",
                 warmup: int = 252):
        """
        Args:
            asset_class: stock/etf/futures/crypto/fx
            min_state: 触发多头的最小状态阈值.
                       BULL_STRONG (最严格) / BULL_CONFIRMED / BULL_EARLY
        """
        super().__init__(
            name="mtes",
            strategy_type=StrategyType.TREND,
            parameters={"asset_class": asset_class, "min_state": min_state},
        )
        self.asset_class = asset_class
        self.min_state = min_state
        self.warmup = warmup  # 可配置 warmup，默认 252
        self.evaluator = MajorTrendEvaluator()

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["mtes_signal"] = 0
        df["mtes_score"] = np.nan
        df["mtes_state"] = ""

        # BULL 状态优先级: STRONG > CONFIRMED > EARLY
        bull_states = ["BULL_STRONG", "BULL_CONFIRMED", "BULL_EARLY"]
        bear_states = ["BEAR_STRONG", "BEAR_CONFIRMED", "BEAR_EARLY"]

        min_idx = self.warmup

        for i in range(min_idx, len(df)):
            window = df.iloc[: i + 1].copy()
            try:
                result = self.evaluator.evaluate(
                    window,
                    asset_class=self.asset_class,
                    higher_timeframe=None,
                    base_timeframe="1d",
                    higher_timeframe_name="1w",
                )
                score = result.trend_score
                state = result.trend_state.value if hasattr(result.trend_state, "value") else result.trend_state
                direction = result.direction

                df.iloc[i, df.columns.get_loc("mtes_score")] = score
                df.iloc[i, df.columns.get_loc("mtes_state")] = state

                if direction == "BULL" and state in bull_states:
                    # 按严格程度映射信号
                    if self.min_state == "BULL_STRONG" and state == "BULL_STRONG":
                        df.iloc[i, df.columns.get_loc("mtes_signal")] = 1
                    elif self.min_state in ("BULL_CONFIRMED", "BULL_STRONG") and state in ("BULL_STRONG", "BULL_CONFIRMED"):
                        df.iloc[i, df.columns.get_loc("mtes_signal")] = 1
                    elif state == "BULL_EARLY":
                        df.iloc[i, df.columns.get_loc("mtes_signal")] = 1
                elif direction == "BEAR" and state in bear_states:
                    df.iloc[i, df.columns.get_loc("mtes_signal")] = -1
            except Exception:
                pass
        return df


# ──────────────────────────────────────────────────────────────────
# 3. 简单回测引擎
# ──────────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    start_date: str
    end_date: str
    total_return: float  # 累计收益率 (小数)
    annual_return: float  # 年化收益率 (小数)
    sharpe: float
    calmar: float
    max_drawdown: float  # 小数
    max_drawdown_pct: float  # 百分比
    n_trades: int
    win_rate: float
    profit_loss_ratio: float
    profit_factor: float
    avg_holding_days: float
    trades: list = field(default_factory=list)

    def to_row(self) -> dict:
        return {
            "品种": self.symbol,
            "策略": self.strategy,
            "年化%": f"{self.annual_return * 100:.1f}",
            "夏普": f"{self.sharpe:.2f}",
            "卡玛": f"{self.calmar:.2f}",
            "最大回撤%": f"{self.max_drawdown_pct:.1f}",
            "交易次数": self.n_trades,
            "胜率%": f"{self.win_rate * 100:.0f}",
            "盈亏比": f"{self.profit_loss_ratio:.2f}",
        }


def run_backtest(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    initial_capital: float = 100_000.0,
    commission: float = 0.001,
    trailing_stop: float | None = None,
    warmup: int = 0,
) -> BacktestResult:
    """在 OHLCV DataFrame 上运行单策略回测."""
    dates = df.index.tolist()
    prices = df["close"].values
    n = len(df)

    # 生成信号（兼容 MTES 的 mtes_signal 列）
    sig_df = strategy._generate_signals(df)
    signal_col = "mtes_signal" if "mtes_signal" in sig_df.columns else "signal"
    signals = sig_df[signal_col].values

    # 模拟交易
    trades: list[TradeRecord] = []
    position: dict | None = None
    equity_curve: list[float] = []
    peak = initial_capital
    # warmup 期间 equity = initial_capital（不交易）
    equity_curve.extend([initial_capital] * warmup)

    for i in range(n):
        price = prices[i]
        date = dates[i]

        # warmup 期间跳过交易逻辑，只记录 equity 并追踪 peak
        if i < warmup:
            # 基于价格追踪 equity 曲线对应的 equity = initial_capital（无仓位时）
            # 追踪 peak 用于 warmup 后的 drawdown 计算
            peak = initial_capital
            equity_curve.append(initial_capital)
            continue

        if position is None:
            # 无持仓：检查入场信号
            sig = signals[i]
            if sig == 1:
                cost = commission * price
                size = (initial_capital * 0.95) / price
                position = {
                    "entry_price": price,
                    "entry_time": date,
                    "entry_idx": i,
                    "direction": 1,
                    "size": size,
                    "entry_commission": cost,
                }
        else:
            # 有持仓：检查出场信号
            sig = signals[i]
            pnl = (price - position["entry_price"]) * position["size"] * position["direction"]
            total_cost = position["entry_commission"] + commission * price
            net_pnl = pnl - total_cost

            should_exit = False
            exit_reason = "signal"

            # 出场条件: 反向信号
            if sig == -position["direction"]:
                should_exit = True
                exit_reason = "signal"
            # 追踪止损
            if trailing_stop is not None:
                entry = position["entry_price"]
                if position["direction"] == 1:
                    drawdown = (entry - price) / entry
                    if drawdown >= trailing_stop:
                        should_exit = True
                        exit_reason = "trailing_stop"
                else:
                    drawdown = (price - entry) / entry
                    if drawdown >= trailing_stop:
                        should_exit = True
                        exit_reason = "trailing_stop"

            if should_exit:
                trade = TradeRecord(
                    symbol=str(date),
                    direction=position["direction"],
                    entry_price=position["entry_price"],
                    exit_price=price,
                    entry_time=position["entry_time"],
                    exit_time=date,
                    size=position["size"],
                    leverage=1.0,
                    pnl=net_pnl,
                    pnl_pct=net_pnl / initial_capital,
                    exit_reason=exit_reason,
                    holding_bars=i - position["entry_idx"],
                    commission=total_cost,
                )
                trades.append(trade)
                position = None

        # 权益曲线
        equity = initial_capital
        if position:
            unrealized = (price - position["entry_price"]) * position["size"] * position["direction"]
            equity += unrealized
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if i == n - 1 and position:
            # 回测结束时强制平仓
            sig = 0  # 视为信号平仓
            pnl = (price - position["entry_price"]) * position["size"] * position["direction"]
            total_cost = position["entry_commission"] + commission * price
            net_pnl = pnl - total_cost
            trade = TradeRecord(
                symbol=str(date),
                direction=position["direction"],
                entry_price=position["entry_price"],
                exit_price=price,
                entry_time=position["entry_time"],
                exit_time=date,
                size=position["size"],
                leverage=1.0,
                pnl=net_pnl,
                pnl_pct=net_pnl / initial_capital,
                exit_reason="end_of_backtest",
                holding_bars=n - 1 - position["entry_idx"],
                commission=total_cost,
            )
            trades.append(trade)

    # 计算指标
    equity_arr = np.array(equity_curve)
    peak_arr = np.maximum.accumulate(equity_arr)
    dd_arr = (peak_arr - equity_arr) / peak_arr
    max_dd = float(np.max(dd_arr))
    max_dd_pct = max_dd * 100

    total_return = (equity_arr[-1] - initial_capital) / initial_capital

    # 年化
    n_years = len(dates) / 252
    annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0.0

    # 夏普 (日收益率)
    returns = np.diff(equity_arr) / equity_arr[:-1]
    returns = returns[np.isfinite(returns)]
    if len(returns) > 1 and np.std(returns) > 1e-10:
        sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252))
    else:
        sharpe = 0.0

    # 卡玛
    calmar = annual_return / max_dd if max_dd > 1e-6 else 0.0

    # 交易统计
    stats = win_rate_and_stats(trades)
    avg_holding = stats.get("avg_holding_bars", 0.0)

    return BacktestResult(
        symbol="",
        strategy="",
        start_date=str(dates[warmup].date()) if warmup < len(dates) else str(dates[0].date()),
        end_date=str(dates[-1].date()) if dates else "",
        total_return=total_return,
        annual_return=annual_return,
        sharpe=sharpe,
        calmar=calmar,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        n_trades=len(trades),
        win_rate=stats.get("win_rate", 0.0),
        profit_loss_ratio=stats.get("profit_loss_ratio", 0.0),
        profit_factor=stats.get("profit_factor", 0.0),
        avg_holding_days=avg_holding,
        trades=trades,
    )


# ──────────────────────────────────────────────────────────────────
# 4. 数据加载
# ──────────────────────────────────────────────────────────────────

def load_data(symbol: str, start: str | None, end: str) -> pd.DataFrame | None:
    """从本地 Parquet 加载数据，失败返回 None."""
    sym = symbol.upper()

    # 候选路径映射（ETF 没有 =F 后缀）
    candidates = []
    # futures: 目录名可能是 GC=F 或 GC=F
    if "=" in sym:
        base = sym.split("=")[0]
        candidates += [
            PROJECT_ROOT / "data" / "us_futures" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "us_futures" / f"{base}=F" / "1d.parquet",
        ]
    else:
        candidates += [
            PROJECT_ROOT / "data" / "us_futures" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "us_futures" / f"{sym}=F" / "1d.parquet",
            PROJECT_ROOT / "data" / "etf" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "etf" / sym / "1W.parquet",
        ]

    for path in candidates:
        if path.exists():
            df = pd.read_parquet(path)
            if isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            elif "timestamp" in df.columns:
                df = df.set_index("timestamp")
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            start_dt = pd.to_datetime(start) if start else None
            end_dt = pd.to_datetime(end)
            if start_dt:
                mask = (df.index >= start_dt) & (df.index <= end_dt)
            else:
                mask = df.index <= end_dt
            result = df[mask].copy()

            # 确保有 OHLCV 列（处理不同大小写）
            required_lower = {"open", "high", "low", "close", "volume"}
            if required_lower.issubset(set(result.columns)):
                return result
            else:
                # 尝试大写列名
                cols = {c.lower(): c for c in result.columns}
                rename = {}
                for need in required_lower:
                    if need in cols and need != cols[need]:
                        rename[cols[need]] = need
                if rename and all(c in result.columns for c in rename):
                    result = result.rename(columns=rename)
                    mask2 = (result.index >= start_dt) & (result.index <= end_dt) if start_dt else result.index <= end_dt
                    return result[mask2]

    return None


def infer_asset_class(symbol: str) -> str:
    """根据标的名称推断资产类别."""
    crypto_patterns = ["BTC", "ETH", "USDT", "crypto"]
    futures_patterns = ["F", "GC", "ES", "SI", "CL", "NQ", "HG", "ZC", "ZS"]
    etf_patterns = ["SPY", "QQQ", "IWM", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "DBC", "CIBR", "IAU"]

    s = symbol.upper()
    for p in crypto_patterns:
        if p in s:
            return "crypto"
    for p in futures_patterns:
        if p in s:
            return "futures"
    for p in etf_patterns:
        if p in s:
            return "etf"
    return "stock"


# ──────────────────────────────────────────────────────────────────
# 5. 主程序
# ──────────────────────────────────────────────────────────────────

def build_strategies(asset_class: str, mtes_warmup: int = 252) -> list[tuple[str, BaseStrategy]]:
    """构建所有对比策略."""
    return [
        ("A1. MTES(BULL_CONFIRMED)", MTESBacktestWrapper(asset_class=asset_class, min_state="BULL_CONFIRMED", warmup=mtes_warmup)),
        ("A2. MTES(BULL_EARLY)", MTESBacktestWrapper(asset_class=asset_class, min_state="BULL_EARLY", warmup=mtes_warmup)),
        ("B. SuperTrend(10,3)", SuperTrendStrategy(period=10, multiplier=3.0)),
        ("C. EMA(50/200)", EMAGoldenCrossStrategy(fast=50, slow=200)),
        ("D. ADX(14)>25", ADXTrendStrategy(period=14, threshold=25.0)),
        ("E. MACD(12/26/9)", MACDZeroCrossStrategy(fast=12, slow=26, signal=9)),
        ("F. Donchian(55)", DonchianBreakoutStrategy(period=55)),
    ]


def print_comparison_table(results: list[BacktestResult]):
    """打印对比表格."""
    rows = [r.to_row() for r in results]
    df = pd.DataFrame(rows)

    # 按策略分组，每个品种一行
    print("\n" + "=" * 100)
    print("MTES vs 经典趋势策略对比回测报告".center(90))
    print("=" * 100)

    symbols = df["品种"].unique()
    for sym in symbols:
        sym_df = df[df["品种"] == sym]
        result = sym_df.iloc[0]
        print(f"\n{'─' * 100}")
        print(f"  品种: {sym}  |  时间: {results[0].start_date} ~ {results[0].end_date}  |  资产类别: {infer_asset_class(sym)}")
        print(f"{'─' * 100}")

        # 表头
        header = f"  {'策略':<26} {'年化%':>8} {'夏普':>6} {'卡玛':>6} {'最大回撤%':>9} {'交易次数':>8} {'胜率%':>6} {'盈亏比':>7}"
        print(header)
        print(f"  {'─'*26} {'─'*8} {'─'*6} {'─'*6} {'─'*9} {'─'*8} {'─'*6} {'─'*7}")

        for _, row in sym_df.iterrows():
            # 标记最优指标（有交易的策略中年化最高的）
            tradable = sym_df[pd.to_numeric(sym_df["交易次数"]) > 0]
            if len(tradable) > 0:
                best = tradable.sort_values("年化%", ascending=False).iloc[0]["策略"]
            else:
                best = ""

            line = (f"  {row['策略']:<26} "
                    f"{row['年化%']:>8} "
                    f"{row['夏普']:>6} "
                    f"{row['卡玛']:>6} "
                    f"{row['最大回撤%']:>9} "
                    f"{row['交易次数']:>8} "
                    f"{row['胜率%']:>6} "
                    f"{row['盈亏比']:>7}")
            if row["策略"] == best:
                line = "► " + line[2:]
            print(line)

        # 汇总: 按策略聚合跨品种平均
        print(f"\n  {'跨品种平均':<26}", end="")
        avg_cols = ["年化%", "夏普", "卡玛", "胜率%"]
        for col in avg_cols:
            try:
                vals = pd.to_numeric(sym_df[col], errors="coerce")
                avg = vals.mean()
                if col == "胜率%":
                    print(f" {avg:>6.0f}% ", end="")
                elif col == "最大回撤%":
                    print(f" {avg:>7.1f}% ", end="")
                else:
                    print(f" {avg:>5.1f} ", end="")
            except Exception:
                print(f"  {'N/A':>5} ", end="")
        print()

    print("\n" + "=" * 100)
    print("注: ► 标记该品种中年化收益最高的策略")
    print("    MTES warmup bar 已参数化（默认 --mtes-warmup=60，完整评估用 --mtes-warmup=252）")
    print("    MTES 使用 min_state=BULL_CONFIRMED，即 BULL_CONFIRMED/STRONG 才触发多头")


def _debug_mtes_states(df: pd.DataFrame, warmup: int, asset_class: str):
    """打印 MTES 在测试窗口的状态分布（调试用）."""
    from collections import Counter
    from src.analysis.major_trend_evaluator import MajorTrendEvaluator

    evaluator = MajorTrendEvaluator()
    states, scores = [], []
    min_idx = min(warmup, len(df) - 5)
    for i in range(min_idx, len(df)):
        window = df.iloc[: i + 1]
        try:
            r = evaluator.evaluate(window, asset_class=asset_class,
                                  base_timeframe="1d", higher_timeframe_name="1w")
            s = r.trend_state.value if hasattr(r.trend_state, "value") else r.trend_state
            states.append(s)
            scores.append(r.trend_score)
        except Exception as e:
            states.append(f"ERR:{e}")

    print(f"\n   [DEBUG] MTES state distribution (bars {min_idx}-{len(df)}):")
    for s, c in Counter(states).most_common():
        print(f"      {s}: {c} ({c/len(states)*100:.0f}%)")
    if scores:
        print(f"      mean_score={sum(scores)/len(scores):.1f}, "
              f"min={min(scores):.0f}, max={max(scores):.0f}")
    print(f"   [DEBUG] trading_window={len(df)-min_idx} bars")


def main():
    parser = argparse.ArgumentParser(description="MTES vs 经典趋势策略对比回测")
    parser.add_argument("--symbols", nargs="+", default=["GC=F", "ES=F", "CL=F"],
                        help="品种列表，默认: GC=F ES=F CL=F")
    parser.add_argument("--start", default="2024-01-01",
                        help="回测开始日期，默认: 2024-01-01")
    parser.add_argument("--end", default="2025-05-27",
                        help="回测结束日期，默认: 2025-05-27")
    parser.add_argument("--asset-class", default=None,
                        help="强制资产类别 (stock/etf/futures/crypto/fx)")
    parser.add_argument("--mtes-warmup", type=int, default=200,
                        help="MTES warmup bar 数（默认 252）")
    parser.add_argument("--debug", action="store_true",
                        help="显示 MTES 状态分布调试信息")
    args = parser.parse_args()

    all_results: list[BacktestResult] = []


    for symbol in args.symbols:
        print(f"\n📊 加载数据: {symbol} ...", end=" ", flush=True)
        df = load_data(symbol, None, args.end)  # 全量数据
        if df is None or len(df) < 30:
            print(f"❌ 数据不足，跳过")
            continue
        print(f"✅ {len(df)} 条 ({df.index[0].date()} ~ {df.index[-1].date()})，MTES warmup={args.mtes_warmup}")

        asset_class = args.asset_class or infer_asset_class(symbol)
        strategies = build_strategies(asset_class, mtes_warmup=args.mtes_warmup)

        for name, strat in strategies:
            is_mtes = "MTES" in name
            # MTES 用全量数据生成信号，warmup=0；其他策略 warmup=0
            warmup = 0
            # MTES debug: 打印信号分布
            if is_mtes and args.debug:
                sig_df = strat._generate_signals(df)
                print(f"\n   [MTES DEBUG] signals[:10]={sig_df['mtes_signal'].values[:10]}")
                print(f"   [MTES DEBUG] unique signals={sig_df['mtes_signal'].unique()}")
                non_zero = (sig_df["mtes_signal"] != 0).sum()
                print(f"   [MTES DEBUG] non-zero signals: {non_zero}/{len(sig_df)}")
            result = run_backtest(df, strat)
            result.symbol = symbol
            result.strategy = name
            all_results.append(result)
            tag = " [MTES]" if "MTES" in name else ""
            print(f"   {name:<26} 年化: {result.annual_return*100:>6.1f}%  "
                  f"夏普: {result.sharpe:>5.2f}  交易: {result.n_trades:>3}  "
                  f"胜率: {result.win_rate*100:>5.0f}%{tag}")

    if all_results:
        print_comparison_table(all_results)
    else:
        print("❌ 没有可用的回测结果，请检查数据文件路径。")


if __name__ == "__main__":
    main()
