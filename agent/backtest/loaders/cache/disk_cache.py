"""Disk cache (L2) with Parquet storage

Persistent disk cache with:
- Parquet format with Snappy compression
- Metadata tracking (creation time, hit count, size)
- Automatic directory management
- Cache statistics
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DiskCache:
    """L2 disk cache with Parquet storage

    Stores cached data persistently on disk using Parquet format.
    Maintains metadata for each cache entry.

    Attributes:
        cache_dir: Directory for cache files
    """

    def __init__(self, cache_dir: str = "./data/cache/vibe"):
        """Initialize disk cache

        Args:
            cache_dir: Directory path for cache storage
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_file = self.cache_dir / "metadata.json"
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        """Load cache metadata from disk

        Returns:
            Dictionary of cache metadata
        """
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
        return {}

    def _save_metadata(self) -> None:
        """Save cache metadata to disk"""
        try:
            with open(self._metadata_file, "w") as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")

    def get(self, cache_hash: str) -> Optional[pd.DataFrame]:
        """Get cached data from disk

        Args:
            cache_hash: Cache key hash

        Returns:
            Cached DataFrame if exists, None otherwise
        """
        cache_file = self.cache_dir / f"{cache_hash}.parquet"

        if not cache_file.exists():
            return None

        try:
            df = pd.read_parquet(cache_file)

            # Update metadata
            if cache_hash in self._metadata:
                self._metadata[cache_hash]["hit_count"] += 1
                self._metadata[cache_hash]["last_access"] = datetime.now().isoformat()
                self._save_metadata()

            logger.debug(f"Disk cache hit: {cache_hash}")
            return df

        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_hash}: {e}")
            return None

    def set(
        self,
        cache_hash: str,
        data: pd.DataFrame,
        key_info: Optional[dict] = None,
    ) -> None:
        """Save data to disk cache

        Args:
            cache_hash: Cache key hash
            data: DataFrame to cache
            key_info: Optional cache key information for metadata
        """
        cache_file = self.cache_dir / f"{cache_hash}.parquet"

        try:
            # Save data as Parquet with Snappy compression
            data.to_parquet(cache_file, compression="snappy")

            # Update metadata
            self._metadata[cache_hash] = {
                "created_at": datetime.now().isoformat(),
                "last_access": datetime.now().isoformat(),
                "hit_count": 0,
                "size_bytes": cache_file.stat().st_size,
                "key_info": key_info,
            }
            self._save_metadata()

            logger.debug(f"Disk cache set: {cache_hash}")

        except Exception as e:
            logger.warning(f"Failed to write cache file {cache_hash}: {e}")

    def delete(self, cache_hash: str) -> bool:
        """Delete cache entry

        Args:
            cache_hash: Cache key hash

        Returns:
            True if deleted successfully, False if not found
        """
        cache_file = self.cache_dir / f"{cache_hash}.parquet"

        # Check if file or metadata exists
        if not cache_file.exists() and cache_hash not in self._metadata:
            return False

        try:
            # Delete file
            if cache_file.exists():
                cache_file.unlink()

            # Delete metadata
            if cache_hash in self._metadata:
                del self._metadata[cache_hash]
                self._save_metadata()

            logger.debug(f"Disk cache deleted: {cache_hash}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete cache file {cache_hash}: {e}")
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        # Delete all parquet files
        for cache_file in self.cache_dir.glob("*.parquet"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")

        # Clear metadata
        self._metadata.clear()
        self._save_metadata()
        logger.info("Disk cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics

        Returns:
            Dictionary with cache stats:
            - entries: Number of cached entries
            - total_size_mb: Total disk usage in MB
            - total_hits: Total cache hits
            - cache_dir: Cache directory path
        """
        total_size = sum(
            info.get("size_bytes", 0) for info in self._metadata.values()
        )
        total_hits = sum(
            info.get("hit_count", 0) for info in self._metadata.values()
        )

        return {
            "entries": len(self._metadata),
            "total_size_mb": total_size / (1024 * 1024),
            "total_hits": total_hits,
            "cache_dir": str(self.cache_dir),
        }

    def cleanup_old_entries(self, days: int = 30) -> int:
        """Clean up cache entries older than specified days

        Args:
            days: Delete entries older than this many days

        Returns:
            Number of entries deleted
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        for cache_hash, info in list(self._metadata.items()):
            try:
                created_at = datetime.fromisoformat(info["created_at"])
                if created_at < cutoff:
                    if self.delete(cache_hash):
                        deleted += 1
            except Exception as e:
                logger.warning(f"Failed to check age of {cache_hash}: {e}")

        logger.info(f"Cleaned up {deleted} old cache entries")
        return deleted

    def __len__(self) -> int:
        """Return number of cached entries"""
        return len(self._metadata)

    def __contains__(self, cache_hash: str) -> bool:
        """Check if cache hash exists"""
        cache_file = self.cache_dir / f"{cache_hash}.parquet"
        return cache_file.exists()
