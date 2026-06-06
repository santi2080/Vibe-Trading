"""Composite strategy backtest comparison orchestrator.

Runs three backtest passes (composite, MTES-only, SuperTrend-only), collects
``run_card.json`` files, and produces a METR-01 strategy comparison report.

Usage:
    python -m backtest.composite_backtest_compare --config backtest/configs/composite_backtest.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from backtest.strategies.comparison import StrategyComparator
from src.tools.path_utils import safe_run_dir

_VARIANTS = {
    "MTES+SuperTrend": "composite",
    "MTESv3-only": "mtes_only",
    "SuperTrend-only": "supertrend_only",
}

_COMPARE_TIMEOUT_ENV = "VIBE_TRADING_COMPARE_TIMEOUT_SECONDS"
_COMPARE_OUTPUT_LIMIT_ENV = "VIBE_TRADING_COMPARE_OUTPUT_LIMIT"
_DEFAULT_COMPARE_TIMEOUT_SECONDS = 300
_DEFAULT_COMPARE_OUTPUT_LIMIT = 2000
_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*([^\s]+)"),
    re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]+)"),
]


def _agent_root() -> Path:
    """Return the agent package root directory."""
    return Path(__file__).resolve().parents[1]


def _project_root() -> Path:
    """Return repository root from the agent package root."""
    return _agent_root().parent


def _load_config(config_path: Path) -> dict[str, Any]:
    """Load YAML or JSON comparison config."""
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        return json.loads(text)
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _env_int(name: str, default: int) -> int:
    """Return a positive integer environment setting or its default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _compare_timeout_seconds(value: int | float | None = None) -> float:
    """Return the subprocess timeout for each comparison variant."""
    if value is not None and value > 0:
        return float(value)
    return float(_env_int(_COMPARE_TIMEOUT_ENV, _DEFAULT_COMPARE_TIMEOUT_SECONDS))


def _output_limit() -> int:
    """Return the maximum characters exposed per subprocess stream."""
    return _env_int(_COMPARE_OUTPUT_LIMIT_ENV, _DEFAULT_COMPARE_OUTPUT_LIMIT)


def _redact_output(text: str | bytes | None) -> str:
    """Redact common secret patterns from subprocess output."""
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    redacted = str(text)
    for pattern in _SECRET_PATTERNS:
        if "Bearer" in pattern.pattern:
            redacted = pattern.sub("Bearer [REDACTED]", redacted)
        else:
            redacted = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", redacted)
    return redacted


def _truncate_output(text: str, limit: int | None = None) -> str:
    """Return bounded diagnostic output, keeping the most recent tail."""
    limit = _output_limit() if limit is None else limit
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"[truncated {omitted} chars]\n{text[-limit:]}"


def _format_subprocess_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    """Return redacted, truncated stdout/stderr for exceptions."""
    safe_stdout = _truncate_output(_redact_output(stdout))
    safe_stderr = _truncate_output(_redact_output(stderr))
    return f"STDOUT:\n{safe_stdout}\nSTDERR:\n{safe_stderr}"



def _base_backtest_config(config: dict[str, Any], variant: str) -> dict[str, Any]:
    """Return runner-compatible config for a strategy variant."""
    run_config = dict(config)
    run_config["strategy_variant"] = variant
    run_config["engine"] = run_config.get("engine", "daily")
    run_config["source"] = run_config.get("source", "yfinance")
    run_config["interval"] = run_config.get("interval", "1D")
    return run_config


def _prepare_run_dir(run_root: Path, label: str, config: dict[str, Any]) -> Path:
    """Create a safe run_dir with config.json and code/signal_engine.py."""
    safe_label = label.lower().replace("+", "_").replace("-", "_").replace(" ", "_")
    run_dir = safe_run_dir(str(run_root / safe_label))
    code_dir = run_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    template = _agent_root() / "backtest" / "configs" / "signal_engine.py"
    shutil.copy2(template, code_dir / "signal_engine.py")
    return run_dir


def _run_variant(
    label: str,
    variant: str,
    config: dict[str, Any],
    run_root: Path,
    timeout_seconds: float | None = None,
) -> Path:
    """Run one strategy variant and return its run directory."""
    run_config = _base_backtest_config(config, variant)
    run_dir = _prepare_run_dir(run_root, label, run_config)

    timeout = _compare_timeout_seconds(timeout_seconds)
    cmd = [sys.executable, "-m", "backtest.runner", str(run_dir)]
    try:
        result = subprocess.run(
            cmd,
            cwd=_agent_root(),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        output = _format_subprocess_output(exc.stdout, exc.stderr)
        raise RuntimeError(
            f"Backtest variant {label!r} timed out after {timeout:g}s\n{output}"
        ) from exc
    if result.returncode != 0:
        output = _format_subprocess_output(result.stdout, result.stderr)
        raise RuntimeError(
            f"Backtest variant {label!r} failed with exit code {result.returncode}\n{output}"
        )
    return run_dir


def run_comparison(
    config_path: Path,
    run_root: Path | None = None,
    timeout_seconds: float | None = None,
) -> str:
    """Run composite vs single-source comparisons and return markdown report.

    Args:
        config_path: YAML/JSON config path.
        run_root: Optional output root. Defaults to ``agent/runs/composite_compare``.
        timeout_seconds: Optional per-variant subprocess timeout.

    Returns:
        Markdown comparison report.
    """
    config_path = Path(config_path)
    config = _load_config(config_path)
    if not config:
        raise ValueError(f"Empty or invalid config: {config_path}")

    default_root = _agent_root() / "runs" / "composite_compare"
    run_root = safe_run_dir(str(run_root if run_root is not None else default_root))
    run_root.mkdir(parents=True, exist_ok=True)

    run_dirs: list[tuple[str, Path]] = []
    for label, variant in _VARIANTS.items():
        run_dirs.append((label, _run_variant(label, variant, config, run_root, timeout_seconds)))

    comparator = StrategyComparator()
    for label, run_dir in run_dirs:
        comparator.add_from_path(label, run_dir)

    comparison = comparator.compare(ranked_by="sharpe_ratio")
    report = comparison.to_markdown()

    best_sharpe = comparator.get_best("sharpe_ratio")
    best_return = comparator.get_best("total_return")
    best_win_rate = comparator.get_best("win_rate")
    report += "\n\n## Best Configuration\n"
    report += f"- Best by Sharpe: {best_sharpe.name if best_sharpe else 'N/A'}\n"
    report += f"- Best by Total Return: {best_return.name if best_return else 'N/A'}\n"
    report += f"- Best by Win Rate: {best_win_rate.name if best_win_rate else 'N/A'}\n"
    report += "\n## Run Directories\n"
    for label, run_dir in run_dirs:
        report += f"- {label}: `{run_dir}`\n"

    (run_root / "comparison_report.md").write_text(report, encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Path to YAML/JSON config")
    parser.add_argument("--run-root", type=Path, default=None, help="Optional output run root")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Per-variant subprocess timeout (default: env or 300 seconds)",
    )
    args = parser.parse_args(argv)

    report = run_comparison(args.config, args.run_root, args.timeout_seconds)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
