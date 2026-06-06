"""Security tests for composite backtest comparison orchestration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backtest import composite_backtest_compare as compare


def _config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "codes:",
                "  - GC=F",
                "start_date: '2024-01-01'",
                "end_date: '2024-02-01'",
                "source: yfinance",
                "interval: 1D",
                "engine: daily",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_run_comparison_rejects_unconfigured_run_root(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", raising=False)

    with pytest.raises(ValueError, match="outside allowed run roots"):
        compare.run_comparison(_config_file(tmp_path), tmp_path / "compare")


def test_prepare_run_dir_accepts_configured_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))
    run_root = tmp_path / "compare"

    run_dir = compare._prepare_run_dir(run_root, "MTES+SuperTrend", {"codes": ["GC=F"]})

    assert run_dir == (run_root / "mtes_supertrend").resolve()
    assert (run_dir / "config.json").exists()
    assert (run_dir / "code" / "signal_engine.py").exists()


def test_run_variant_passes_timeout_to_subprocess(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(compare.subprocess, "run", fake_run)

    run_dir = compare._run_variant(
        "MTESv3-only",
        "mtes_only",
        {"codes": ["GC=F"]},
        tmp_path / "compare",
        timeout_seconds=12,
    )

    assert captured["timeout"] == 12
    assert run_dir.name == "mtesv3_only"


def test_run_variant_redacts_and_truncates_failed_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))
    monkeypatch.setenv("VIBE_TRADING_COMPARE_OUTPUT_LIMIT", "40")
    secret_tail = "x" * 80 + " API_KEY=super-secret TOKEN=hidden"

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=2, stdout=secret_tail, stderr="Bearer abc.def.ghi")

    monkeypatch.setattr(compare.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        compare._run_variant(
            "Bad",
            "composite",
            {"codes": ["GC=F"]},
            tmp_path / "compare",
            timeout_seconds=12,
        )

    message = str(exc_info.value)
    assert "exit code 2" in message
    assert "super-secret" not in message
    assert "Bearer abc.def.ghi" not in message
    assert "[REDACTED]" in message
    assert "[truncated" in message


def test_run_variant_timeout_is_bounded_and_redacted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args", "cmd"),
            timeout=kwargs["timeout"],
            output="PASSWORD=super-secret",
            stderr="timeout details",
        )

    monkeypatch.setattr(compare.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        compare._run_variant(
            "Slow",
            "composite",
            {"codes": ["GC=F"]},
            tmp_path / "compare",
            timeout_seconds=3,
        )

    message = str(exc_info.value)
    assert "timed out after 3s" in message
    assert "super-secret" not in message
    assert "[REDACTED]" in message
