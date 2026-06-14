"""Deterministic artifact generation and Markdown report rendering for daily scan (ART-01, RPT-01, RPT-02).

Four artifacts are written for every scan run:
    manifest.json  — scan metadata + file inventory (written before gate)
    data_health.json — data health gate results (written by gate)
    scan_results.json — signal scan results (written by signal scan)
    report.md      — human-readable Markdown summary (written after signal scan)

The report is rendered entirely from JSON artifacts, never from ad-hoc state.
It avoids unverified ranking, performance metrics, best-configuration claims,
and trading advice language.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from .scan_plan import ScanPlan
from .scan_signal_buckets import ScanSignalReport

# Forbidden terms — report must not contain these
_FORBIDDEN_TERMS = frozenset({
    "buy", "sell", "hold",           # trading advice
    "best configuration",            # unverified ranking
    "rank", "ranking",              # unverified ranking
    "performance metric",            # unverified claims
    "win rate",                      # unverified claims
    "sharpe", "sharpe ratio",        # unverified claims
})


# --- Manifest ----------------------------------------------------------------


@dataclass
class Manifest:
    """Scan metadata and file inventory.

    Written to manifest.json before the data-health gate runs so that even a
    blocked scan has a record of what was attempted.
    """

    scan_date: str
    watchlist_name: str
    version: str = "1.0.0"
    artifacts: dict[str, str] | None = None
    scan_info: dict[str, Any] | None = None
    total_symbols: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_date": self.scan_date,
            "watchlist_name": self.watchlist_name,
            "version": self.version,
            "artifacts": self.artifacts or {},
            "scan_info": self.scan_info or {},
            "total_symbols": self.total_symbols,
        }

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)


# --- Markdown Report Renderer -----------------------------------------------


class MarkdownReportRenderer:
    """Renders a human-readable Markdown report from scan JSON artifacts.

    The report is fully derived from data_health.json and scan_results.json;
    no ad-hoc state is used.

    Sections (in order):
        1. Header
        2. Data Health  — stops here if status is FAIL
        3. Actionable Candidates
        4. Watch List
        5. Risk / Excluded
        6. Skipped
        7. Failed
        8. Artifacts
    """

    def __init__(
        self,
        scan_plan: ScanPlan,
        output_dir: Path,
        scan_date: str,
        signal_report: ScanSignalReport | None = None,
        health_report_dict: dict[str, Any] | None = None,
    ) -> None:
        self.scan_plan = scan_plan
        self.output_dir = output_dir
        self.scan_date = scan_date
        self.signal_report = signal_report
        self.health_report_dict = health_report_dict

    def load_artifacts(self) -> None:
        """Load scan_results.json and data_health.json from output_dir if not provided."""
        if self.signal_report is None:
            results_path = self.output_dir / "scan_results.json"
            if results_path.exists():
                with open(results_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.signal_report = ScanSignalReport(**data)

        if self.health_report_dict is None:
            health_path = self.output_dir / "data_health.json"
            if health_path.exists():
                with open(health_path, encoding="utf-8") as fh:
                    self.health_report_dict = json.load(fh)

    def _render_header(self) -> str:
        lines = [
            f"# Daily Scan Report — {self.scan_date}",
            "",
            f"**Watchlist:** {self.scan_plan.watchlist_name}",
            f"**Version:** 1.0.0",
            "",
        ]
        return "\n".join(lines)

    def _render_data_health(self) -> str:
        """Render data health section. Returns early-stop string if status is FAIL."""
        if self.health_report_dict is None:
            return "## Data Health\n\n*[data_health.json not found]*\n"

        health = self.health_report_dict
        status = health.get("status", "UNKNOWN")
        total = health.get("total_checks", 0)
        blocking = health.get("blocking_failures", 0)
        warnings = health.get("warnings", 0)

        badge_map = {"PASS": "✅ PASS", "WARNING": "⚠️ WARNING", "FAIL": "❌ FAIL"}
        badge = badge_map.get(status, status)

        lines = [
            "## Data Health",
            "",
            f"| Status | Total Checks | Blocking Failures | Warnings |",
            f"| --- | --- | --- | --- |",
            f"| {badge} | {total} | {blocking} | {warnings} |",
            "",
        ]

        # Fail: stop here
        if status == "FAIL":
            lines.extend([
                "**Scan blocked — fix data issues above.**",
                "",
                "See `data_health.json` for details.",
                "",
            ])
            return "\n".join(lines)

        return "\n".join(lines)

    def _render_bucket_table(
        self,
        bucket_name: str,
        title: str,
        columns: list[str],
        row_fn,
    ) -> str:
        """Render a Markdown table for one bucket."""
        if self.signal_report is None:
            return ""

        items = self.signal_report.buckets.get(bucket_name, [])
        if not items:
            return f"## {title}\n\n*No symbols.*\n"

        col_header = "| " + " | ".join(columns) + " |"
        col_sep = "| " + " | ".join(["---"] * len(columns)) + " |"

        lines = [f"## {title}", ""]
        lines.append(f"*{len(items)} symbol(s).*")
        lines.append("")
        lines.append(col_header)
        lines.append(col_sep)

        for item in items:
            rows = row_fn(item)
            lines.append("| " + " | ".join(str(c) for c in rows) + " |")

        lines.append("")
        return "\n".join(lines)

    def _render_actionable(self) -> str:
        def row(item: dict[str, Any]) -> list[str]:
            ts = item.get("trading_signal") or {}
            return [
                item["symbol"],
                item.get("name", ""),
                item.get("market", ""),
                item.get("action_bias", "—"),
                f"{ts.get('signal_score', 0):.1f}",
                f"{ts.get('confidence', 0):.2f}",
                item.get("bucket_reason", ""),
            ]

        return self._render_bucket_table(
            "actionable",
            "Actionable Candidates",
            ["Symbol", "Name", "Market", "Bias", "Score", "Confidence", "Reason"],
            row,
        )

    def _render_watch(self) -> str:
        def row(item: dict[str, Any]) -> list[str]:
            return [
                item["symbol"],
                item.get("name", ""),
                item.get("market", ""),
                item.get("action_bias", "—"),
                item.get("bucket_reason", ""),
            ]

        return self._render_bucket_table(
            "watch",
            "Watch List",
            ["Symbol", "Name", "Market", "Bias", "Reason"],
            row,
        )

    def _render_risk_excluded(self) -> str:
        def row(item: dict[str, Any]) -> list[str]:
            return [
                item["symbol"],
                item.get("name", ""),
                item.get("market", ""),
                item.get("bucket_reason", ""),
            ]

        return self._render_bucket_table(
            "risk_excluded",
            "Risk / Excluded",
            ["Symbol", "Name", "Market", "Reason"],
            row,
        )

    def _render_skipped(self) -> str:
        def row(item: dict[str, Any]) -> list[str]:
            return [
                item["symbol"],
                item.get("name", ""),
                item.get("bucket_reason", ""),
            ]

        return self._render_bucket_table(
            "skipped",
            "Skipped",
            ["Symbol", "Name", "Reason"],
            row,
        )

    def _render_failed(self) -> str:
        def row(item: dict[str, Any]) -> list[str]:
            return [
                item["symbol"],
                item.get("bucket_reason", ""),
            ]

        return self._render_bucket_table(
            "failed",
            "Failed",
            ["Symbol", "Error"],
            row,
        )

    def _render_caveats(self) -> str:
        return (
            "**Disclaimer:** "
            "Candidates are for research only. Not financial advice. "
            "This report does not constitute investment recommendation. "
            "Past signals do not guarantee future outcomes.\n"
        )

    def _render_artifacts(self) -> str:
        artifacts = [
            ("data_health.json", "Data health gate results"),
            ("scan_results.json", "Signal scan results"),
            ("manifest.json", "Scan metadata and file inventory"),
            ("report.md", "This report"),
        ]
        lines = ["## Artifacts", "",]
        for fname, desc in artifacts:
            lines.append(f"- [`{fname}`]({fname}) — {desc}")
        lines.append("")
        return "\n".join(lines)

    def render(self) -> str:
        """Produce the full Markdown report string."""
        sections = [self._render_header()]

        health_section = self._render_data_health()
        sections.append(health_section)

        # Stop on FAIL — do not render candidate tables
        if self.health_report_dict is not None and self.health_report_dict.get("status") == "FAIL":
            return "\n".join(sections)

        sections.append(self._render_actionable())
        sections.append(self._render_watch())
        sections.append(self._render_risk_excluded())
        sections.append(self._render_skipped())
        sections.append(self._render_failed())
        sections.append(self._render_caveats())
        sections.append(self._render_artifacts())

        return "\n".join(sections)

    def write(self, path: Path) -> None:
        """Write the rendered Markdown report to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")


# --- Orchestrator -----------------------------------------------------------


def run_reporting(
    scan_plan: ScanPlan,
    output_dir: Path,
    *,
    scan_date: str,
    format: str,
    console: Console | None,
) -> Manifest:
    """Build the scan manifest, write all reporting artifacts.

    Steps:
        1. Build and write manifest.json (metadata + file inventory).
        2. Load data_health.json and scan_results.json from output_dir.
        3. Render report.md via MarkdownReportRenderer.
        4. Write report.md.
        5. Return the Manifest.

    Args:
        scan_plan: The ScanPlan built for this scan.
        output_dir: Directory where all artifacts are written.
        scan_date: ISO date string for the scan.
        format: Output format ("table" or "json").
        console: Optional rich Console for console output.

    Returns:
        The Manifest written to manifest.json.
    """
    # 1. Build and write manifest
    manifest = Manifest(
        scan_date=scan_date,
        watchlist_name=scan_plan.watchlist_name,
        artifacts={
            "data_health": "data_health.json",
            "scan_results": "scan_results.json",
            "report": "report.md",
        },
        scan_info={"watchlist": str(scan_plan.watchlist_path)},
        total_symbols=scan_plan.total_symbols,
    )
    manifest_path = output_dir / "manifest.json"
    manifest.to_json(manifest_path)

    # 2. Load JSON artifacts (written by gate + signal scan phases)
    renderer = MarkdownReportRenderer(
        scan_plan=scan_plan,
        output_dir=output_dir,
        scan_date=scan_date,
        signal_report=None,
        health_report_dict=None,
    )
    renderer.load_artifacts()

    # 3. Render and write report.md
    report_path = output_dir / "report.md"
    renderer.write(report_path)

    # 4. Console output for table format
    if format == "table" and console is not None:
        console.print(f"[dim]Report written to {report_path}[/dim]")

    return manifest
