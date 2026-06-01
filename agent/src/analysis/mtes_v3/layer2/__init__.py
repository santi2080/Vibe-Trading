"""
Layer 2: Trend Strength Confirmation

包含:
- ADXStrengthFilter: ADX 趋势强度过滤器
- MomentumDivergenceDetector: 动量背离检测器
"""
from .strength_filter import ADXStrengthFilter
from .divergence import MomentumDivergenceDetector, DivergenceResult

__all__ = ['ADXStrengthFilter', 'MomentumDivergenceDetector', 'DivergenceResult']
