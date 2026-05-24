"""数据获取器基类

从 trading-assistant 移植
定义数据获取器的标准接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd

from .market import Market, Timeframe
from .security import Security


class BaseFetcher(ABC):
    """数据获取器基类"""

    source_name: str = "base"

    @property
    @abstractmethod
    def supported_markets(self) -> List[Market]:
        """支持的市场列表"""
        ...

    @abstractmethod
    def fetch(
        self,
        security: Security,
        timeframe: Timeframe,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """获取 K 线数据

        Args:
            security: 证券标的
            timeframe: 时间周期
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            limit: K 线数量限制

        Returns:
            K 线数据 DataFrame
        """
        ...

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return True

    def get_name(self) -> str:
        """获取数据源名称"""
        return self.source_name


class FetchResult:
    """获取结果"""

    def __init__(
        self,
        data: Optional[pd.DataFrame] = None,
        source: Optional[str] = None,
        success: bool = False,
        error: Optional[str] = None,
        quality_score: float = 1.0,
    ):
        self.data = data
        self.source = source
        self.success = success
        self.error = error
        self.quality_score = quality_score

    @property
    def is_fresh(self) -> bool:
        """数据是否新鲜"""
        if self.data is None or self.data.empty:
            return False
        return self.quality_score >= 0.8
