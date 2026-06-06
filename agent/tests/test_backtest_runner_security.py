"""Security regression tests for backtest signal_engine loading."""

from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from backtest.runner import (
    _load_module_from_file,
    _sha256_file,
    _verify_trusted_signal_engine,
)


def _module_name() -> str:
    """Return a unique module name for import tests."""
    return f"signal_engine_test_{uuid.uuid4().hex}"


def test_signal_engine_rejects_top_level_execution(tmp_path) -> None:
    artifact = tmp_path / "top_level_rce"
    # ``Path.as_posix()`` so the embedded path uses forward slashes; the raw
    # Windows form ``C:\Users\...`` looks like ``\U`` (a unicode escape) when
    # interpolated into Python source and breaks ``ast.parse`` before the
    # security scrubber under test ever runs.
    artifact_str = artifact.as_posix()
    signal_file = tmp_path / "signal_engine.py"
    signal_file.write_text(
        "\n".join(
            [
                "import os",
                f"os.system('touch {artifact_str}')",
                "class SignalEngine:",
                "    def generate(self, *args, **kwargs):",
                "        return []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Executable top-level statement"):
        _load_module_from_file(signal_file, _module_name())

    assert not artifact.exists()


def test_signal_engine_rejects_class_level_execution(tmp_path) -> None:
    artifact = tmp_path / "class_level_rce"
    artifact_str = artifact.as_posix()  # see top_level test for rationale
    signal_file = tmp_path / "signal_engine.py"
    signal_file.write_text(
        "\n".join(
            [
                "import os",
                "class SignalEngine:",
                f"    os.system('touch {artifact_str}')",
                "    def generate(self, *args, **kwargs):",
                "        return []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Executable class-level statement"):
        _load_module_from_file(signal_file, _module_name())

    assert not artifact.exists()




def test_packaged_signal_engine_template_is_trusted() -> None:
    template = Path(__file__).resolve().parents[1] / "backtest" / "configs" / "signal_engine.py"

    _verify_trusted_signal_engine(template)


def test_untrusted_ast_safe_signal_engine_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("VIBE_TRADING_TRUSTED_SIGNAL_ENGINE_SHA256", raising=False)
    signal_file = tmp_path / "signal_engine.py"
    signal_file.write_text(
        "\n".join(
            [
                '"""Generated signal engine."""',
                "class SignalEngine:",
                "    def generate(self, *args, **kwargs):",
                "        return {}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Untrusted signal_engine.py"):
        _verify_trusted_signal_engine(signal_file)


def test_extra_trusted_signal_engine_hash_is_accepted(tmp_path, monkeypatch) -> None:
    signal_file = tmp_path / "signal_engine.py"
    signal_file.write_text(
        "class SignalEngine:\n    def generate(self, *args, **kwargs):\n        return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBE_TRADING_TRUSTED_SIGNAL_ENGINE_SHA256", _sha256_file(signal_file))

    _verify_trusted_signal_engine(signal_file)
