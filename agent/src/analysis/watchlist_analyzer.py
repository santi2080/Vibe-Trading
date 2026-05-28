"""Watchlist 分析协调器

整合数据层和策略层，对 watchlist 中的品种进行批量分析。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """单个品种的分析结果"""

    symbol: str
    name: str
    market: str
    trend: str = "-"  # UP / DOWN / SIDEWAYS / -
    pullback: str = "-"  # ✅确认(X.XXATR) / ❌原因 / -
    signal_direction: str = "-"  # LONG / SHORT / NEUTRAL / -
    signal_price: Optional[float] = None
    signal_date: Optional[str] = None
    stop_loss: Optional[float] = None
    atr_1n: Optional[float] = None
    entry_price: Optional[float] = None
    risk_reward: Optional[float] = None
    confidence: float = 0.0
    error: Optional[str] = None
    mtes: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "trend": self.trend,
            "pullback": self.pullback,
            "signal": f"{self.signal_direction}@{self.signal_price}" if self.signal_direction != "-" else "-",
            "signal_date": self.signal_date or "-",
            "stop_loss": f"{self.stop_loss:.2f}" if self.stop_loss else "-",
            "atr_1n": f"{self.atr_1n:.2f}" if self.atr_1n else "-",
            "confidence": f"{self.confidence:.0%}",
            "error": self.error or "-",
        }
        if self.mtes:
            result.update(self.mtes)
        return result


class WatchlistAnalyzer:
    """Watchlist 分析协调器

    协调数据层和策略层，对 watchlist 中的品种进行批量分析。

    数据流:
    1. 从 WatchlistReader 加载品种列表
    2. 从 DataClient 加载数据（中周期 + 小周期）
    3. 调用策略层生成信号
    4. 解析信号结果
    5. 返回 AnalysisResult 列表
    """

    def __init__(
        self,
        data_client=None,
        strategy_registry=None,
        watchlist_path: str = "watchlist/us_futures_watchlist.csv",
    ):
        """初始化

        Args:
            data_client: 数据客户端（DataClient 或 None）
            strategy_registry: 策略注册表（StrategyRegistry 或 None）
            watchlist_path: watchlist 文件路径
        """
        self.watchlist_path = watchlist_path
        self.data_client = data_client
        self.strategy_registry = strategy_registry
        self._trend_strategy = None
        self._pullback_strategy = None
        self._entry_strategy = None

        # 尝试导入数据层
        if self.data_client is None:
            try:
                from backtest.loaders.client import DataClient

                self.data_client = DataClient()
                logger.info("DataClient initialized")
            except Exception as e:
                logger.warning(f"DataClient not available: {e}")

        # 尝试导入策略层
        if self.strategy_registry is None:
            try:
                from backtest.strategies import StrategyRegistry, StrategyType

                self.strategy_registry = StrategyRegistry
                # 加载默认策略
                self._load_default_strategies()
            except Exception as e:
                logger.warning(f"StrategyRegistry not available: {e}")

    def _load_default_strategies(self):
        """加载默认策略"""
        try:
            from backtest.strategies.trend import TrendEmaAdxStrategy
            from backtest.strategies.pullback import PullbackRsiStrategy
            from backtest.strategies.entry import BreakoutEntryStrategy

            self._trend_strategy = TrendEmaAdxStrategy()
            self._pullback_strategy = PullbackRsiStrategy()
            self._entry_strategy = BreakoutEntryStrategy()
            logger.info("Default strategies loaded")
        except ImportError as e:
            logger.warning(f"Could not load default strategies: {e}")

    def _calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 EMA"""
        return df["close"].ewm(span=period, adjust=False).mean()

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ADX"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        plus_di = 100 * (
            plus_dm.rolling(window=period).mean() / tr.rolling(window=period).mean()
        )
        minus_di = 100 * (
            minus_dm.rolling(window=period).mean() / tr.rolling(window=period).mean()
        )

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 RSI"""
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ATR"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.rolling(window=period).mean()

    def analyze_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析趋势

        使用 EMA + ADX 判断趋势方向

        Args:
            df: OHLCV DataFrame

        Returns:
            dict: {
                "direction": "UP" / "DOWN" / "SIDEWAYS",
                "strength": float (0-1),
                "ema_fast": float,
                "ema_slow": float,
                "adx": float
            }
        """
        if len(df) < 50:
            return {"direction": "SIDEWAYS", "strength": 0.0, "adx": 0.0}

        close = df["close"]
        ema_fast = self._calculate_ema(df, 12)
        ema_slow = self._calculate_ema(df, 26)
        adx = self._calculate_adx(df, 14)

        # 最新值
        current = close.iloc[-1]
        fast = ema_fast.iloc[-1]
        slow = ema_slow.iloc[-1]
        adx_val = adx.iloc[-1]

        # 判断方向
        if fast > slow and current > fast:
            direction = "UP"
            strength = min(adx_val / 50, 1.0) if adx_val else 0.5
        elif fast < slow and current < fast:
            direction = "DOWN"
            strength = min(adx_val / 50, 1.0) if adx_val else 0.5
        else:
            direction = "SIDEWAYS"
            strength = 0.3

        return {
            "direction": direction,
            "strength": strength,
            "ema_fast": fast,
            "ema_slow": slow,
            "adx": adx_val,
            "close": current,
        }

    def analyze_pullback(self, df: pd.DataFrame, trend: str) -> Dict[str, Any]:
        """分析回调

        使用 RSI 判断回调是否适合入场

        Args:
            df: OHLCV DataFrame
            trend: 趋势方向

        Returns:
            dict: {
                "status": "CONFIRMED" / "REJECTED",
                "reason": str,
                "atr_multiple": float,
                "rsi": float
            }
        """
        if len(df) < 30:
            return {"status": "REJECTED", "reason": "数据不足", "atr_multiple": 0.0, "rsi": 50.0}

        rsi = self._calculate_rsi(df, 14)
        atr = self._calculate_atr(df, 14)
        close = df["close"]

        rsi_val = rsi.iloc[-1]
        atr_val = atr.iloc[-1]
        current = close.iloc[-1]

        # EMA 作为动态支撑/阻力
        ema_20 = self._calculate_ema(df, 20)
        ema_val = ema_20.iloc[-1]

        if trend == "UP":
            # 上涨趋势：RSI < 40 表示回调，RSI > 70 表示超买
            if rsi_val < 40:
                # 计算回调深度（距离 EMA 的 ATR 倍数）
                if current < ema_val:
                    depth = (ema_val - current) / atr_val if atr_val > 0 else 0
                    if depth <= 2.0:
                        return {
                            "status": "CONFIRMED",
                            "reason": f"✅确认({depth:.1f}ATR)",
                            "atr_multiple": depth,
                            "rsi": rsi_val,
                            "support": ema_val,
                        }
                    else:
                        return {
                            "status": "REJECTED",
                            "reason": f"❌回调过深({depth:.1f}ATR)",
                            "atr_multiple": depth,
                            "rsi": rsi_val,
                        }
                else:
                    return {
                        "status": "CONFIRMED",
                        "reason": "✅确认(趋势中)",
                        "atr_multiple": 0.0,
                        "rsi": rsi_val,
                    }
            else:
                return {
                    "status": "REJECTED",
                    "reason": f"❌未回调(RSI={rsi_val:.0f})",
                    "atr_multiple": 0.0,
                    "rsi": rsi_val,
                }

        elif trend == "DOWN":
            # 下跌趋势：RSI > 60 表示反弹
            if rsi_val > 60:
                if current > ema_val:
                    depth = (current - ema_val) / atr_val if atr_val > 0 else 0
                    if depth <= 2.0:
                        return {
                            "status": "CONFIRMED",
                            "reason": f"✅确认({depth:.1f}ATR)",
                            "atr_multiple": depth,
                            "rsi": rsi_val,
                            "resistance": ema_val,
                        }
                    else:
                        return {
                            "status": "REJECTED",
                            "reason": f"❌反弹过深({depth:.1f}ATR)",
                            "atr_multiple": depth,
                            "rsi": rsi_val,
                        }
                else:
                    return {
                        "status": "CONFIRMED",
                        "reason": "✅确认(趋势中)",
                        "atr_multiple": 0.0,
                        "rsi": rsi_val,
                    }
            else:
                return {
                    "status": "REJECTED",
                    "reason": f"❌未反弹(RSI={rsi_val:.0f})",
                    "atr_multiple": 0.0,
                    "rsi": rsi_val,
                }

        else:
            return {"status": "REJECTED", "reason": "❌震荡市", "atr_multiple": 0.0, "rsi": rsi_val}

    def analyze_single(
        self,
        symbol: str,
        market: str = "us_futures",
        primary_tf: str = "1D",
        secondary_tf: str = "1H",
        atr_override: Optional[float] = None,
    ) -> AnalysisResult:
        """分析单个品种

        Args:
            symbol: 品种代码
            market: 市场类型
            primary_tf: 主周期
            secondary_tf: 次周期
            atr_override: ATR 覆盖值（从 watchlist 读取）

        Returns:
            AnalysisResult
        """
        from src.data.watchlist import WatchlistReader

        # 获取品种名称
        reader = WatchlistReader(self.watchlist_path)
        raw_items = reader.load_raw()
        name = symbol
        for item in raw_items:
            if item["symbol"] == symbol:
                name = item.get("name", symbol)
                break

        try:
            # 加载数据 - 优先从本地文件加载
            df = self._load_data_from_file(symbol, market, primary_tf)

            if df is None or df.empty:
                # 尝试 DataClient（可能网络不可用时会失败）
                df = self._load_data(symbol, market, primary_tf)

            if df is None or df.empty:
                return AnalysisResult(
                    symbol=symbol,
                    name=name,
                    market=market,
                    error="无数据",
                )

            # 分析趋势
            trend_result = self.analyze_trend(df)
            trend = trend_result["direction"]
            close = trend_result["close"]
            atr = atr_override if atr_override else self._calculate_atr(df, 14).iloc[-1]

            # 分析回调
            pullback_result = self.analyze_pullback(df, trend)
            pullback_str = pullback_result["reason"]

            # 生成信号
            signal_direction = "-"
            stop_loss = None
            entry_price = close

            if trend == "UP" and pullback_result["status"] == "CONFIRMED":
                signal_direction = "LONG"
                if "support" in pullback_result:
                    stop_loss = pullback_result["support"] - 1.5 * atr
                else:
                    stop_loss = close - 1.5 * atr
            elif trend == "DOWN" and pullback_result["status"] == "CONFIRMED":
                signal_direction = "SHORT"
                if "resistance" in pullback_result:
                    stop_loss = pullback_result["resistance"] + 1.5 * atr
                else:
                    stop_loss = close + 1.5 * atr
            else:
                signal_direction = "NEUTRAL"

            # 计算风险收益比
            risk_reward = None
            if stop_loss and atr > 0:
                risk = abs(close - stop_loss)
                reward = 2 * atr  # 目标 2ATR
                risk_reward = reward / risk if risk > 0 else None

            # 信号日期
            last_ts = df.index[-1]
            if pd.notna(last_ts):
                signal_date = pd.Timestamp(last_ts).strftime("%Y-%m-%d")
            else:
                signal_date = None

            try:
                from src.analysis.major_trend_evaluator import MajorTrendEvaluator, resolve_asset_class

                asset_class = resolve_asset_class(market)
                mtes_payload = MajorTrendEvaluator().evaluate(df, asset_class=asset_class).to_dict()
            except Exception as exc:
                logger.warning("MTES evaluation failed for %s: %s", symbol, exc)
                mtes_payload = {
                    "asset_class": "unknown",
                    "trend_score": 0.0,
                    "trend_state": "NEUTRAL_CHOPPY",
                    "direction": "NEUTRAL",
                    "confidence": 0.0,
                    "regime": "unavailable",
                    "sub_scores": {},
                    "top_drivers": [],
                    "regime_flags": ["mtes_unavailable"],
                    "explanation": str(exc),
                }

            return AnalysisResult(
                symbol=symbol,
                name=name,
                market=market,
                trend=trend,
                pullback=pullback_str,
                signal_direction=signal_direction,
                signal_price=close,
                signal_date=signal_date,
                stop_loss=stop_loss,
                atr_1n=atr,
                entry_price=entry_price,
                risk_reward=risk_reward,
                confidence=pullback_result["atr_multiple"] / 2.0 if pullback_result["status"] == "CONFIRMED" else 0.0,
                mtes=mtes_payload,
                metadata={
                    "primary_tf": primary_tf,
                    "secondary_tf": secondary_tf,
                    "adx": trend_result.get("adx", 0),
                    "rsi": pullback_result.get("rsi", 50),
                },
            )

        except Exception as e:
            logger.error(f"分析失败 {symbol}: {e}")
            return AnalysisResult(
                symbol=symbol,
                name=name,
                market=market,
                error=str(e),
            )

    def _load_data(
        self, symbol: str, market: str, timeframe: str = "1D"
    ) -> Optional[pd.DataFrame]:
        """从 DataClient 加载数据"""
        if self.data_client is None:
            return None

        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")

            df = self.data_client.load(
                symbol=symbol,
                interval=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            return df

        except Exception as e:
            logger.error(f"DataClient 加载失败 {symbol}: {e}")
            return None

    def _load_data_from_file(
        self, symbol: str, market: str, timeframe: str = "1D"
    ) -> Optional[pd.DataFrame]:
        """从本地文件加载数据"""
        # 映射市场目录
        market_dir_map = {
            "us_futures": "us_futures",
            "US_FUTURES": "us_futures",
            "cn_futures": "cn_futures",
            "CN_FUTURES": "cn_futures",
            "us_stocks": "us_stocks",
            "US_STOCKS": "us_stocks",
            "US_STOCK": "us_stocks",
            "etf": "etf",
            "ETF": "etf",
            "US_ETF": "etf",
            "HK_STOCK": "hk_stocks",
        }

        market_dir = market_dir_map.get(market, "us_futures")
        data_path = Path(f"data/{market_dir}/{symbol}/1d.parquet")

        if not data_path.exists():
            # 尝试 trading-assistant 数据目录
            ta_feature = Path(f"/Users/iagent/projects/trading-assistant/data/features/{market_dir}/{symbol}/1d.parquet")
            ta_cache = Path(f"/Users/iagent/projects/trading-assistant/data/cache/{symbol}_1d.parquet")
            if ta_feature.exists():
                data_path = ta_feature
            elif ta_cache.exists():
                data_path = ta_cache
            else:
                return None

        try:
            df = pd.read_parquet(data_path)
            if df.index.name == "timestamp" or "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"] if "timestamp" in df.columns else df.index)
                df = df.set_index("timestamp")
            return df
        except Exception as e:
            logger.error(f"读取数据文件失败 {data_path}: {e}")
            return None

    def analyze_all(
        self,
        watchlist_path: Optional[str] = None,
        market_filter: Optional[str] = None,
        verbose: bool = True,
    ) -> List[AnalysisResult]:
        """批量分析所有品种

        Args:
            watchlist_path: watchlist 路径（覆盖默认路径）
            market_filter: 市场过滤（如 "US_FUTURES"）

        Returns:
            AnalysisResult 列表
        """
        if watchlist_path:
            self.watchlist_path = watchlist_path

        from src.data.watchlist import WatchlistReader

        reader = WatchlistReader(self.watchlist_path)
        raw_items = reader.load_raw()

        results = []
        for item in raw_items:
            symbol = item["symbol"]
            market = item["market"]
            primary_tf, secondary_tf = reader.get_timeframes(symbol)

            # 市场过滤
            if market_filter and market.upper() != market_filter.upper():
                continue

            # 跳过表头
            if symbol.lower() in ("symbol", "code", "name"):
                continue

            if verbose:
                print(f"分析: {symbol} ({market})...", end=" ")

            atr = item.get("atr", 0.0) if item.get("atr", 0.0) > 0 else None
            result = self.analyze_single(
                symbol=symbol,
                market=market,
                primary_tf=primary_tf,
                secondary_tf=secondary_tf,
                atr_override=atr,
            )

            results.append(result)

            if verbose:
                if result.error:
                    print(f"❌ {result.error}")
                else:
                    print(f"✅ {result.trend} | {result.signal_direction}@{result.signal_price:.2f}")

        logger.info(f"分析完成: {len(results)} 个品种")
        return results
