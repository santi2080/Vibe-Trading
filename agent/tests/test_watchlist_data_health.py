from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.watchlist_data_health import check_watchlist_data

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_watchlist_data.py"


def write_watchlist(path: Path, timeframes: str = "1D-4H") -> None:
    path.write_text(
        "symbol,name,market,exchange,sector,timeframes,contract_type,multiplier,max_lots,ATR\n"
        f"GC=F,黄金,US_FUTURES,COMEX,贵金属,{timeframes},standard,1,1,10\n",
        encoding="utf-8",
    )


def write_ohlcv(path: Path, end: datetime, periods: int = 5, freq: str = "h", drop_column: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    index = pd.date_range(end=end, periods=periods, freq=freq, name="timestamp")
    df = pd.DataFrame(
        {
            "open": [100 + index for index in range(periods)],
            "high": [101 + index for index in range(periods)],
            "low": [99 + index for index in range(periods)],
            "close": [100.5 + index for index in range(periods)],
            "volume": [1000 + index for index in range(periods)],
        },
        index=index,
    )
    if drop_column:
        df = df.drop(columns=[drop_column])
    df.to_parquet(path)


def test_empty_watchlist_blocks_backtest(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    watchlist.write_text("symbol,name,market,exchange,sector,timeframes\n", encoding="utf-8")

    report = check_watchlist_data(watchlist, data_dir=tmp_path / "data", now=datetime(2026, 5, 27, 12, 0, 0))

    assert report.can_backtest is False
    assert report.gate_status == "FAIL"
    assert report.to_dict()["gate"]["empty_watchlist"] is True


def test_valid_1d_and_1h_allows_backtest(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)

    assert report.can_backtest is True
    assert report.gate_status == "PASS"
    assert report.blocking_failures == 0
    assert report.warnings == 0
    assert report.to_dict()["calendar_adjusted"] is False


def test_missing_1h_blocks_backtest(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)

    failed = [item for item in report.items if item.timeframe == "1h"][0]
    assert report.can_backtest is False
    assert failed.status == "FAIL"
    assert failed.reason == "missing required file"


def test_missing_auxiliary_4h_warns_only(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-4H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)

    warning = [item for item in report.items if item.timeframe == "4h"][0]
    assert report.can_backtest is True
    assert report.gate_status == "WARN"
    assert warning.status == "WARN"
    assert warning.reason == "missing auxiliary file"


def test_stale_1d_blocks_backtest(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", datetime(2026, 5, 24, 12, 0, 0), freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)

    failed = [item for item in report.items if item.timeframe == "1d"][0]
    assert failed.status == "FAIL"
    assert failed.reason == "recent data missing"
    assert failed.missing_recent is True


def test_us_futures_1h_uses_twenty_four_hour_threshold(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 28, 11, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", datetime(2026, 5, 27, 0, 0, 0), freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", datetime(2026, 5, 27, 22, 0, 0), freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)
    one_hour = [item for item in report.items if item.timeframe == "1h"][0]

    assert one_hour.status == "PASS"
    assert one_hour.reason == "ok"
    assert report.can_backtest is True


def test_cn_futures_1h_keeps_strict_six_hour_threshold(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 28, 11, 0, 0)
    watchlist.write_text(
        "symbol,name,market,exchange,sector,timeframes,contract_type,multiplier,max_lots,ATR\n"
        "al0,铝主连,CN_FUTURES,SHFE,有色金属,1D-1H,standard,5,2,100\n",
        encoding="utf-8",
    )
    write_ohlcv(data_dir / "cn_futures" / "al0" / "1d.parquet", datetime(2026, 5, 27, 0, 0, 0), freq="D")
    write_ohlcv(data_dir / "cn_futures" / "al0" / "1h.parquet", datetime(2026, 5, 27, 22, 0, 0), freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)
    one_hour = [item for item in report.items if item.timeframe == "1h"][0]

    assert one_hour.status == "FAIL"
    assert one_hour.reason == "recent data missing"

def test_missing_required_column_fails_blocking_timeframe(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D", drop_column="volume")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    report = check_watchlist_data(watchlist, data_dir=data_dir, now=now)

    failed = [item for item in report.items if item.timeframe == "1d"][0]
    assert failed.status == "FAIL"
    assert failed.reason == "missing required columns"
    assert "missing_required_columns" in failed.issues


def test_json_report_contains_gate_and_calendar_metadata(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    payload = check_watchlist_data(watchlist, data_dir=data_dir, now=now).to_dict()

    assert payload["calendar_adjusted"] is False
    assert payload["gate"]["can_backtest"] is True
    assert payload["rules"]["blocking_timeframes"] == ["1d", "1h"]
    assert payload["rules"]["market_overrides"] == {"us_futures:1h": "24h"}
    assert len(payload["items"]) == 2


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_returns_zero_and_prints_json_for_passing_report(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = "2026-05-27T12:00:00"
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", datetime.fromisoformat(now), freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", datetime.fromisoformat(now), freq="h")

    result = run_cli("--watchlist", str(watchlist), "--data-dir", str(data_dir), "--format", "json", "--now", now)

    assert result.returncode == 0
    assert json.loads(result.stdout)["gate"]["status"] == "PASS"


def test_cli_returns_one_for_blocking_failure(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = "2026-05-27T12:00:00"
    write_watchlist(watchlist, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", datetime.fromisoformat(now), freq="D")

    result = run_cli("--watchlist", str(watchlist), "--data-dir", str(data_dir), "--format", "json", "--now", now)

    assert result.returncode == 1
    assert json.loads(result.stdout)["gate"]["status"] == "FAIL"


def test_cli_returns_two_for_missing_watchlist(tmp_path: Path) -> None:
    result = run_cli("--watchlist", str(tmp_path / "missing.csv"))

    assert result.returncode == 2
    assert "File not found" in result.stderr
