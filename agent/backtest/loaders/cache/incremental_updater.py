"""Incremental data update mechanism for efficient data synchronization.

This module provides incremental update functionality that only fetches new data
since the last update, avoiding redundant API calls.

Usage:
    from backtest.loaders.cache.incremental_updater import IncrementalUpdater

    updater = IncrementalUpdater()
    updated_df = updater.update(cached_df, loader, symbol, timeframe)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class UpdateMetadata:
    """Metadata for tracking incremental updates.

    Attributes:
        symbol: Security symbol
        timeframe: Data timeframe (1D, 1H, etc.)
        last_update: Last successful update timestamp
        start_date: Data start date in cache
        end_date: Data end date in cache
        row_count: Number of rows cached
        version: Metadata schema version
    """

    symbol: str
    timeframe: str
    last_update: datetime
    start_date: str
    end_date: str
    row_count: int
    version: str = "1.0"
    source: str = "unknown"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_update": self.last_update.isoformat(),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "row_count": self.row_count,
            "version": self.version,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UpdateMetadata":
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            last_update=datetime.fromisoformat(data["last_update"]),
            start_date=data["start_date"],
            end_date=data["end_date"],
            row_count=data["row_count"],
            version=data.get("version", "1.0"),
            source=data.get("source", "unknown"),
        )


class IncrementalUpdater:
    """Handles incremental data updates to minimize API calls.

    This class tracks the last update time and only fetches new data
    since then, avoiding redundant downloads.

    Example:
        >>> updater = IncrementalUpdater(cache_dir=".cache")
        >>> loader = TushareLoader()
        >>>
        >>> # First update (full fetch)
        >>> df = updater.update(None, loader, "000001.SZ", "1D")
        >>>
        >>> # Second update (incremental)
        >>> cached_df = pd.read_parquet("000001.SZ_1D.parquet")
        >>> df = updater.update(cached_df, loader, "000001.SZ", "1D")
    """

    def __init__(
        self,
        metadata_dir: Optional[str] = None,
        max_gap_days: int = 30,
        check_frequency_hours: int = 24,
    ):
        """Initialize incremental updater.

        Args:
            metadata_dir: Directory to store update metadata.
                        Defaults to ~/.cache/vibe-trading/metadata
            max_gap_days: Maximum gap in days before forcing full refresh.
                         If gap > this, do a full update instead of incremental.
            check_frequency_hours: Minimum hours between update checks.
                                 Prevents excessive API calls.
        """
        if metadata_dir is None:
            metadata_dir = str(Path.home() / ".cache" / "vibe-trading" / "metadata")

        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.max_gap_days = max_gap_days
        self.check_frequency_hours = check_frequency_hours

        self._metadata_cache: Dict[Tuple[str, str], UpdateMetadata] = {}

    def _get_metadata_path(self, symbol: str, timeframe: str) -> Path:
        """Get path for metadata file."""
        safe_symbol = symbol.replace("/", "_").replace(".", "_")
        return self.metadata_dir / f"{safe_symbol}_{timeframe}.json"

    def get_metadata(self, symbol: str, timeframe: str) -> Optional[UpdateMetadata]:
        """Get update metadata for symbol/timeframe.

        Args:
            symbol: Security symbol
            timeframe: Data timeframe

        Returns:
            UpdateMetadata if exists, None otherwise
        """
        cache_key = (symbol, timeframe)
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]

        path = self._get_metadata_path(symbol, timeframe)
        if path.exists():
            try:
                import json
                data = json.loads(path.read_text())
                metadata = UpdateMetadata.from_dict(data)
                self._metadata_cache[cache_key] = metadata
                return metadata
            except Exception as e:
                logger.warning(f"Failed to load metadata from {path}: {e}")

        return None

    def save_metadata(self, metadata: UpdateMetadata) -> None:
        """Save update metadata.

        Args:
            metadata: UpdateMetadata to save
        """
        cache_key = (metadata.symbol, metadata.timeframe)
        self._metadata_cache[cache_key] = metadata

        path = self._get_metadata_path(metadata.symbol, metadata.timeframe)
        try:
            import json
            path.write_text(json.dumps(metadata.to_dict(), indent=2))
            logger.debug(f"Saved metadata to {path}")
        except Exception as e:
            logger.error(f"Failed to save metadata to {path}: {e}")

    def needs_update(
        self,
        symbol: str,
        timeframe: str,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Check if data needs updating.

        Args:
            symbol: Security symbol
            timeframe: Data timeframe
            force: Force update regardless of check

        Returns:
            Tuple of (needs_update, reason)
            reason is None if needs_update is False
        """
        if force:
            return True, "forced"

        metadata = self.get_metadata(symbol, timeframe)
        if metadata is None:
            return True, "no_metadata"

        now = datetime.now()
        hours_since_update = (now - metadata.last_update).total_seconds() / 3600

        # Check frequency
        if hours_since_update < self.check_frequency_hours:
            return False, f"recent_update ({hours_since_update:.1f}h ago)"

        return True, "stale"

    def update(
        self,
        cached_df: Optional[pd.DataFrame],
        loader,
        symbol: str,
        timeframe: str,
        force: bool = False,
    ) -> Tuple[pd.DataFrame, bool]:
        """Update data incrementally.

        Args:
            cached_df: Existing cached data (can be None for first fetch)
            loader: Data loader instance with fetch method
            symbol: Security symbol
            timeframe: Data timeframe
            force: Force full refresh

        Returns:
            Tuple of (updated_dataframe, is_incremental)
            is_incremental is True if only new data was fetched
        """
        needs_update, reason = self.needs_update(symbol, timeframe, force)

        if not needs_update:
            if cached_df is not None:
                return cached_df, False
            needs_update = True
            reason = "no_cached_data"

        # Get metadata for current state
        metadata = self.get_metadata(symbol, timeframe)

        # Determine fetch strategy
        if metadata is not None and not force:
            # Incremental update: fetch only new data
            end_date = datetime.now().strftime("%Y-%m-%d")

            # Check for large gap
            if metadata.end_date:
                last_date = pd.Timestamp(metadata.end_date)
                gap_days = (datetime.now() - last_date).days

                if gap_days > self.max_gap_days:
                    logger.info(f"Large gap ({gap_days} days) for {symbol}, doing full update")
                    start_date = metadata.start_date
                else:
                    # Incremental: start from day after last cached date
                    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")

                if pd.Timestamp(start_date) >= pd.Timestamp(end_date):
                    logger.info(f"No new data for {symbol} ({start_date} to {end_date})")
                    return cached_df if cached_df is not None else pd.DataFrame(), False
        else:
            # Full fetch
            start_date = None
            end_date = None

        logger.info(f"Fetching {symbol} {timeframe}: {reason}, start={start_date}, end={end_date}")

        # Fetch data
        try:
            if start_date and end_date:
                result = loader.fetch([symbol], start_date, end_date, interval=timeframe)
            else:
                result = loader.fetch([symbol], interval=timeframe)

            if symbol not in result:
                logger.warning(f"No data returned for {symbol}")
                return cached_df if cached_df is not None else pd.DataFrame(), False

            new_df = result[symbol]
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return cached_df if cached_df is not None else pd.DataFrame(), False

        # Merge with cached data
        if cached_df is not None and not cached_df.empty:
            # Merge: existing + new (deduplicated)
            combined = pd.concat([cached_df, new_df], ignore_index=False)

            # Remove duplicates, keeping the most recent
            combined = combined[~combined.index.duplicated(keep="last")]

            # Sort by index
            combined = combined.sort_index()

            # Update metadata
            metadata = UpdateMetadata(
                symbol=symbol,
                timeframe=timeframe,
                last_update=datetime.now(),
                start_date=combined.index[0].strftime("%Y-%m-%d") if len(combined) > 0 else metadata.start_date if metadata else "unknown",
                end_date=combined.index[-1].strftime("%Y-%m-%d") if len(combined) > 0 else metadata.end_date if metadata else "unknown",
                row_count=len(combined),
                source=loader.name if hasattr(loader, 'name') else "unknown",
            )
            self.save_metadata(metadata)

            return combined, True
        else:
            # First fetch
            if new_df.empty:
                return pd.DataFrame(), False

            metadata = UpdateMetadata(
                symbol=symbol,
                timeframe=timeframe,
                last_update=datetime.now(),
                start_date=new_df.index[0].strftime("%Y-%m-%d") if len(new_df) > 0 else "unknown",
                end_date=new_df.index[-1].strftime("%Y-%m-%d") if len(new_df) > 0 else "unknown",
                row_count=len(new_df),
                source=loader.name if hasattr(loader, 'name') else "unknown",
            )
            self.save_metadata(metadata)

            return new_df, False

    def clear_metadata(self, symbol: str, timeframe: str) -> None:
        """Clear metadata for symbol/timeframe.

        Args:
            symbol: Security symbol
            timeframe: Data timeframe
        """
        path = self._get_metadata_path(symbol, timeframe)
        if path.exists():
            path.unlink()
            logger.info(f"Cleared metadata for {symbol} {timeframe}")

        cache_key = (symbol, timeframe)
        self._metadata_cache.pop(cache_key, None)

    def get_stats(self) -> Dict:
        """Get updater statistics.

        Returns:
            Dictionary with updater stats
        """
        metadata_files = list(self.metadata_dir.glob("*.json"))
        return {
            "metadata_count": len(metadata_files),
            "metadata_dir": str(self.metadata_dir),
            "max_gap_days": self.max_gap_days,
            "check_frequency_hours": self.check_frequency_hours,
        }
