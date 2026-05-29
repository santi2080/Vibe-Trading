"""Backtest package compatibility bridge."""

from __future__ import annotations

import sys

sys.modules["agent.backtest"] = sys.modules[__name__]
sys.modules["backtest"] = sys.modules[__name__]
