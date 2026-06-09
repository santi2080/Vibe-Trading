"""Scan plan dataclass and output formatters (WLS-02)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from .watchlist import WatchlistReader
from .watchlist_data_health import normalize_timeframe, resolve_cache_file


# --- Plan model -----------------------------------------------------------
@dataclass
class SymbolPlan:
    symbol: str
    name: str
    market: str
    exchange: str
    sector: str | None
    timeframes: list[str]           # normalized (e.g., ["1d", "4h"])
    cache_paths: list[Path]         # one per timeframe
    output_path: Path               # single .json output per symbol
    validation_issues: list[str] = field(default_factory=list)  # non-blocking warnings


@dataclass
class ScanPlan:
    watchlist_path: Path
    watchlist_name: str
    data_dir: Path
    output_dir: Path
    scan_date: date_cls
    symbols: list[SymbolPlan] = field(default_factory=list)

    @property
    def total_symbols(self) -> int:
        return len(self.symbols)

    @property
    def by_market(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.symbols:
            counts[s.market] = counts.get(s.market, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "watchlist": str(self.watchlist_path),
            "data_dir": str(self.data_dir),
            "output_dir": str(self.output_dir),
            "scan_date": self.scan_date.isoformat(),
            "summary": {
                "total": self.total_symbols,
                "by_market": self.by_market,
            },
            "symbols": [
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "market": s.market,
                    "exchange": s.exchange,
                    "sector": s.sector,
                    "timeframes": s.timeframes,
                    "cache_paths": [str(p) for p in s.cache_paths],
                    "output_path": str(s.output_path),
                    "warnings": s.validation_issues,
                }
                for s in self.symbols
            ],
        }


# --- Builder -------------------------------------------------------------
def build_scan_plan(
    watchlist_path: str,
    data_dir: str = "data",
    output_dir: str | None = None,
    scan_date: date_cls | None = None,
) -> ScanPlan:
    """Build a ScanPlan from a watchlist CSV.

    Normalizes timeframes and resolves all cache/output paths.
    Raises ValueError on invalid inputs.
    """
    today = scan_date or date_cls.today()

    wl_path = Path(watchlist_path).expanduser()
    data_path = Path(data_dir).expanduser().resolve()
    out_path = Path(output_dir).expanduser().resolve() if output_dir else (
        Path("output") / today.isoformat()
    )

    reader = WatchlistReader(str(wl_path))
    raw_rows = reader.load_raw()

    symbols: list[SymbolPlan] = []
    for row in raw_rows:
        sym = (row.get("symbol") or "").strip()
        market = (row.get("market") or "").strip()
        tf_raw = (row.get("timeframes") or "").strip()

        # Normalize timeframes
        timeframes: list[str] = []
        warnings: list[str] = []
        for tf in tf_raw.split(","):
            tf = tf.strip()
            if tf:
                normalized = normalize_timeframe(tf)
                timeframes.append(normalized)

        # Resolve cache paths (one per timeframe)
        cache_paths: list[Path] = []
        for tf in timeframes:
            cp = resolve_cache_file(data_path, market, sym, tf)
            cache_paths.append(cp)

        # Output path: output_dir / {symbol}.json
        symbol_output = out_path / f"{sym}.json"

        symbols.append(SymbolPlan(
            symbol=sym,
            name=(row.get("name") or row.get("symbol") or sym),
            market=market,
            exchange=(row.get("exchange") or "").strip(),
            sector=(row.get("sector") or "").strip() or None,
            timeframes=timeframes,
            cache_paths=cache_paths,
            output_path=symbol_output,
            validation_issues=warnings,
        ))

    return ScanPlan(
        watchlist_path=wl_path,
        watchlist_name=wl_path.name,
        data_dir=data_path,
        output_dir=out_path,
        scan_date=today,
        symbols=symbols,
    )


# --- Formatters -----------------------------------------------------------
def format_plan_table(plan: ScanPlan) -> str:
    """Format scan plan as a human-readable ASCII table using rich."""
    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Scan Plan — {plan.watchlist_name} ({plan.scan_date})")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Market", style="green")
    table.add_column("Timeframes", style="yellow")
    table.add_column("Cache Status", style="magenta")
    table.add_column("Cache Path", style="dim")

    for s in plan.symbols:
        # Check which cache files exist
        present = [str(tf) for tf, cp in zip(s.timeframes, s.cache_paths) if cp.exists()]
        missing = [str(tf) for tf, cp in zip(s.timeframes, s.cache_paths) if not cp.exists()]
        status = ", ".join(present) if present else "[red]MISSING[/red]"
        if missing:
            status += f" [dim](missing: {', '.join(missing)})[/dim]"
        cache_display = str(s.cache_paths[0]) if s.cache_paths else ""

        table.add_row(
            s.symbol,
            s.market,
            ", ".join(s.timeframes),
            status,
            cache_display,
        )

    # Summary footer
    console = Console()
    with console.capture() as capture:
        console.print(table)
    table_str = capture.get()

    # Add summary
    summary = (
        f"\n[bold]Summary:[/bold] {plan.total_symbols} symbols  |  "
        f"Markets: {', '.join(f'{k}={v}' for k, v in plan.by_market.items())}  |  "
        f"Output: {plan.output_dir}"
    )
    return table_str + summary


def format_plan_json(plan: ScanPlan, indent: int = 2) -> str:
    """Format scan plan as machine-readable JSON."""
    import json
    return json.dumps(plan.to_dict(), indent=indent, ensure_ascii=False)
