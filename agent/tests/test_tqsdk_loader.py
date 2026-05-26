"""Tests for TqSdkLoader without opening real TqSdk connections."""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from agent.backtest.loaders import registry
from agent.backtest.loaders.tqsdk_loader import TqSdkConnectionPool, TqSdkLoader, _to_tqsdk_symbol


class _FakePool:
    def __init__(self, api):
        self.api = api

    @contextmanager
    def get_connection(self):
        yield self.api


def _make_kline_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "datetime": ["2024-01-02 09:00:00", "2024-01-02 10:00:00"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1200],
        }
    )


def test_tqsdk_loader_registers_with_registry():
    registry.LOADER_REGISTRY.pop("tqsdk", None)
    importlib.reload(sys.modules["agent.backtest.loaders.tqsdk_loader"])
    assert registry.LOADER_REGISTRY["tqsdk"].name == "tqsdk"


def test_ensure_loaders_imports_tqsdk_loader():
    import agent.backtest.loaders as loaders

    assert ("tqsdk_loader", "agent.backtest.loaders.tqsdk_loader") in loaders._LOADER_MODULES


def test_tqsdk_loader_declares_china_futures_markets_only():
    assert TqSdkLoader.markets == {"futures", "cn_futures"}


def test_registry_aliases_share_loader_state():
    from backtest.loaders.registry import LOADER_REGISTRY as plain_registry

    assert plain_registry is registry.LOADER_REGISTRY


def test_symbol_translation_uses_tqsdk_main_contract_format():
    assert _to_tqsdk_symbol("rb0") == "KQ.m@SHFE.rb"


def test_symbol_translation_uses_correct_dce_exchange():
    assert _to_tqsdk_symbol("i0") == "KQ.m@DCE.i"


def test_symbol_translation_uses_correct_cffex_case():
    assert _to_tqsdk_symbol("if0") == "KQ.m@CFFEX.IF"


def test_symbol_translation_normalizes_specific_contract_case():
    assert _to_tqsdk_symbol("RB2405") == "SHFE.rb2405"
    assert _to_tqsdk_symbol("if2406") == "CFFEX.IF2406"


def test_connection_uses_namespaced_tqsdk_credentials(monkeypatch):
    api_cls = MagicMock()
    auth_cls = MagicMock()
    monkeypatch.setitem(sys.modules, "tqsdk", SimpleNamespace(TqApi=api_cls, TqAuth=auth_cls))
    monkeypatch.setenv("TQSDK_ACCOUNT", "new-account")
    monkeypatch.setenv("TQSDK_PASSWORD", "new-password")
    monkeypatch.setenv("TQ_ACCOUNT", "legacy-account")
    monkeypatch.setenv("TQ_PASSWORD", "legacy-password")

    TqSdkConnectionPool._instance = None
    pool = TqSdkConnectionPool()
    pool._create_connection()

    auth_cls.assert_called_once_with("new-account", "new-password")
    api_cls.assert_called_once_with(auth=auth_cls.return_value)


def test_connection_falls_back_to_legacy_tq_credentials(monkeypatch):
    api_cls = MagicMock()
    auth_cls = MagicMock()
    monkeypatch.setitem(sys.modules, "tqsdk", SimpleNamespace(TqApi=api_cls, TqAuth=auth_cls))
    monkeypatch.delenv("TQSDK_ACCOUNT", raising=False)
    monkeypatch.delenv("TQSDK_PASSWORD", raising=False)
    monkeypatch.setenv("TQ_ACCOUNT", "legacy-account")
    monkeypatch.setenv("TQ_PASSWORD", "legacy-password")

    TqSdkConnectionPool._instance = None
    pool = TqSdkConnectionPool()
    pool._create_connection()

    auth_cls.assert_called_once_with("legacy-account", "legacy-password")
    api_cls.assert_called_once_with(auth=auth_cls.return_value)


def test_fetch_uses_duration_seconds_and_normalizes_frame():
    api = MagicMock()
    api.get_kline_serial.return_value = _make_kline_df()
    loader = TqSdkLoader()
    loader._pool = _FakePool(api)

    result = loader.fetch(["rb0"], "2024-01-01", "2024-01-03", interval="1H")

    args, kwargs = api.get_kline_serial.call_args
    assert args[0] == "KQ.m@SHFE.rb"
    assert kwargs["duration_seconds"] == 3600
    assert "duration_n" not in kwargs
    assert list(result["rb0"].columns) == ["open", "high", "low", "close", "volume"]
    assert result["rb0"].index.name == "datetime"
