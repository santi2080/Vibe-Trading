"""
MyTrendMagic 趋势指标

改进点：
- 当 magic_change == 0 时，保持前一个趋势方向不变
- 只有当斜率发生变化时才切换趋势方向
- 输出三种状态：上涨(1)、下跌(-1)、震荡(0)

原理：
- 原版 TrendMagic 的 magic_line 变化时立即切换方向，容易受噪音干扰
- 新版在 magic_line 停止变化时保持原方向，只有明确的斜率变化才切换
"""

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import numpy as np


TrendDirection = Literal[1, -1, 0]  # 1=上涨, -1=下跌, 0=震荡


@dataclass
class MyTrendMagicSignal:
    """趋势信号"""
    direction: TrendDirection  # +1=上涨, -1=下跌, 0=震荡
    confidence: float  # 置信度 0-1

    # 详细指标
    cci: float = 0.0
    atr: float = 0.0
    magic_line: float = 0.0
    slope_state: str = ""  # UP/DOWN/FLAT
    trend_duration: int = 0  # 同方向持续K线数


class MyTrendMagic:
    """MyTrendMagic 趋势指标

    核心改进：
    1. CCI >= 0 → 上涨，CCI < 0 → 下跌
    2. 当 magic_line 变化时，记录斜率方向（UP/DOWN）
    3. 当 magic_line 不变时（FLAT），保持前一个趋势方向
    4. 趋势方向只有在新斜率与当前方向相反时才切换
    5. 震荡状态：当趋势持续时间过短时判定为震荡
    """

    def __init__(
        self,
        cci_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 1.0,
        # 新增参数
        min_duration: int = 5,  # 最小持续K线数，低于此值判定为震荡
        cooldown: int = 3,  # 切换后冷却期，期间不接受反向信号
    ):
        self.cci_period = cci_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.min_duration = min_duration
        self.cooldown = cooldown

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 MyTrendMagic

        Args:
            df: 必须包含 high, low, close 列

        Returns:
            DataFrame with trend signals
        """
        result = df.copy()
        n = len(df)

        if n < max(self.cci_period, self.atr_period, 10):
            result["direction"] = 0
            result["cci"] = 0.0
            result["atr"] = 0.0
            result["magic_line"] = 0.0
            result["slope_state"] = "FLAT"
            result["trend_duration"] = 0
            return result

        # ===== 1. 计算 ATR =====
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift()).abs()
        tr3 = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        result["atr"] = atr

        # ===== 2. 计算 CCI =====
        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(window=self.cci_period).mean()
        mad = tp.rolling(window=self.cci_period).apply(
            lambda x: np.abs(x - x.mean()).mean(), raw=True
        )
        cci = (tp - sma_tp) / (0.015 * mad + 1e-10)
        result["cci"] = cci

        # ===== 3. 计算追踪线 =====
        upT = df["low"] - atr * self.atr_multiplier
        downT = df["high"] + atr * self.atr_multiplier

        # ===== 4. Magic Line 状态机 =====
        magic = pd.Series(np.nan, index=df.index)
        magic.iloc[0] = upT.iloc[0] if cci.iloc[0] >= 0 else downT.iloc[0]

        for i in range(1, n):
            if cci.iloc[i] >= 0:
                # 上涨趋势：只跟涨不跟跌
                if upT.iloc[i] > magic.iloc[i - 1]:
                    magic.iloc[i] = upT.iloc[i]
                else:
                    magic.iloc[i] = magic.iloc[i - 1]
            else:
                # 下跌趋势：只跟跌不跟涨
                if downT.iloc[i] < magic.iloc[i - 1]:
                    magic.iloc[i] = downT.iloc[i]
                else:
                    magic.iloc[i] = magic.iloc[i - 1]

        result["magic_line"] = magic

        # ===== 5. 计算斜率变化 =====
        magic_change = magic.diff()
        slope_state = pd.Series("FLAT", index=df.index)
        slope_state[magic_change > 0] = "UP"
        slope_state[magic_change < 0] = "DOWN"
        result["slope_state"] = slope_state

        # ===== 6. 趋势方向（关键改进）=====
        direction = self._compute_direction(slope_state, cci)
        result["direction"] = direction

        # ===== 7. 持续时间 =====
        trend_duration = self._compute_duration(direction)
        result["trend_duration"] = trend_duration

        return result

    def _compute_direction(self, slope_state: pd.Series, cci: pd.Series) -> pd.Series:
        """计算趋势方向

        核心逻辑：
        - 斜率 UP → 趋势向上
        - 斜率 DOWN → 趋势向下
        - 斜率 FLAT（无变化）→ 保持前一个趋势方向
        - 只有斜率发生变化时，趋势方向才改变
        """
        n = len(slope_state)
        direction = np.zeros(n)

        # 初始方向基于 CCI
        current_dir = 1 if cci.iloc[self.cci_period] >= 0 else -1
        direction[self.cci_period] = current_dir

        for i in range(self.cci_period + 1, n):
            curr_slope = slope_state.iloc[i]
            prev_slope = slope_state.iloc[i - 1]

            # 只有斜率发生变化时，才改变方向
            if curr_slope != prev_slope:
                if curr_slope == "UP":
                    current_dir = 1
                elif curr_slope == "DOWN":
                    current_dir = -1
                # FLAT 的情况理论上不会发生（因为它需要与前一个不同）

            direction[i] = current_dir

        return pd.Series(direction, index=slope_state.index)

    def _compute_duration(self, direction: pd.Series) -> pd.Series:
        """计算同方向持续K线数"""
        n = len(direction)
        duration = np.zeros(n)
        current_count = 0
        prev_dir = 0

        for i in range(n):
            curr_dir = direction.iloc[i]
            if curr_dir == prev_dir:
                current_count += 1
            else:
                current_count = 1
                prev_dir = curr_dir
            duration[i] = current_count

        return pd.Series(duration, index=direction.index)

    def get_signal(self, df: pd.DataFrame) -> MyTrendMagicSignal:
        """获取当前趋势信号"""
        result = self.calculate(df)
        last = result.iloc[-1]

        # 震荡判定：持续时间过短
        if last["trend_duration"] < self.min_duration:
            direction = 0
        else:
            direction = int(last["direction"])

        # 置信度：基于持续时间
        confidence = min(1.0, last["trend_duration"] / 20)

        return MyTrendMagicSignal(
            direction=direction,
            confidence=confidence,
            cci=float(last["cci"]) if pd.notna(last["cci"]) else 0.0,
            atr=float(last["atr"]) if pd.notna(last["atr"]) else 0.0,
            magic_line=float(last["magic_line"]) if pd.notna(last["magic_line"]) else 0.0,
            slope_state=str(last["slope_state"]),
            trend_duration=int(last["trend_duration"]),
        )
