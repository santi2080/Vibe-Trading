"""指标层

对外接口：
    from agent.src.indicators import ema, adx, rsi, atr, supertrend

标准输入：OHLCV DataFrame
标准输出：pd.Series 或 Dict[str, pd.Series]
"""

from .standard import (  # noqa: E402
    ema,
    sma,
    adx,
    macd,
    rsi,
    stochastic,
    atr,
    bollinger_bands,
    tr,
    supertrend,
    supertrend_signal,
)

__all__ = [
    "ema",
    "sma",
    "adx",
    "macd",
    "rsi",
    "stochastic",
    "atr",
    "bollinger_bands",
    "tr",
    "supertrend",
    "supertrend_signal",
]
