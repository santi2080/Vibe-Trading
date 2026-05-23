"""Disk cache (L2) with Parquet storage

Persistent disk cache with:
- Parquet format with Snappy compression
- Metadata tracking (creation time, hit count, size, expression)
- Automatic directory management
- Cache statistics and health monitoring
- Top accessed entries tracking
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

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
            Dictionary with comprehensive cache stats:
            - entries: Number of cached entries
            - total_size_mb: Total disk usage in MB
            - total_hits: Total cache hits
            - cache_dir: Cache directory path
            - avg_hits_per_entry: Average hits per entry
            - top_accessed: Top 5 most accessed entries
            - oldest_entry: Age of oldest entry
            - newest_entry: Age of newest entry
        """
        total_size = sum(
            info.get("size_bytes", 0) for info in self._metadata.values()
        )
        total_hits = sum(
            info.get("hit_count", 0) for info in self._metadata.values()
        )

        # Calculate average hits
        avg_hits = total_hits / len(self._metadata) if self._metadata else 0

        # Get top accessed entries
        top_accessed = self._get_top_accessed(5)

        # Calculate entry ages
        oldest_age, newest_age = self._get_entry_ages()

        return {
            "entries": len(self._metadata),
            "total_size_mb": total_size / (1024 * 1024),
            "total_hits": total_hits,
            "avg_hits_per_entry": avg_hits,
            "cache_dir": str(self.cache_dir),
            "top_accessed": top_accessed,
            "oldest_entry_days": oldest_age,
            "newest_entry_days": newest_age,
        }

    def _get_top_accessed(self, n: int = 5) -> List[dict]:
        """Get top N most accessed cache entries

        Args:
            n: Number of top entries to return

        Returns:
            List of dicts with hash, hit_count, size_kb, and created_at
        """
        if not self._metadata:
            return []

        # Sort by hit count (descending)
        sorted_entries = sorted(
            self._metadata.items(),
            key=lambda x: x[1].get("hit_count", 0),
            reverse=True
        )

        # Return top N
        top = []
        for cache_hash, info in sorted_entries[:n]:
            key_info = info.get("key_info") or {}
            top.append({
                "hash": cache_hash[:8],  # Short hash for display
                "hit_count": info.get("hit_count", 0),
                "size_kb": info.get("size_bytes", 0) / 1024,
                "created_at": info.get("created_at", ""),
                "expression": key_info.get("expression"),  # Include expression if present
            })

        return top

    def _get_entry_ages(self) -> Tuple[Optional[float], Optional[float]]:
        """Get ages of oldest and newest entries

        Returns:
            Tuple of (oldest_age_days, newest_age_days) or (None, None) if empty
        """
        if not self._metadata:
            return None, None

        now = datetime.now()
        oldest_age = None
        newest_age = None

        for info in self._metadata.values():
            try:
                created = datetime.fromisoformat(info.get("created_at", ""))
                age_days = (now - created).total_seconds() / 86400

                if oldest_age is None or age_days > oldest_age:
                    oldest_age = age_days
                if newest_age is None or age_days < newest_age:
                    newest_age = age_days
            except Exception:
                continue

        return oldest_age, newest_age

    def get_least_accessed(self, n: int = 10) -> List[dict]:
        """Get least accessed entries (candidates for cleanup)

        Args:
            n: Number of entries to return

        Returns:
            List of dicts with hash, hit_count, size_kb, and created_at
        """
        if not self._metadata:
            return []

        # Sort by hit count (ascending)
        sorted_entries = sorted(
            self._metadata.items(),
            key=lambda x: x[1].get("hit_count", 0)
        )

        # Return bottom N
        bottom = []
        for cache_hash, info in sorted_entries[:n]:
            bottom.append({
                "hash": cache_hash[:8],
                "hit_count": info.get("hit_count", 0),
                "size_kb": info.get("size_bytes", 0) / 1024,
                "created_at": info.get("created_at", ""),
            })

        return bottom

    def get_entries_by_expression(self, expression: str) -> List[dict]:
        """Get all cache entries for a specific expression

        Args:
            expression: Expression to search for

        Returns:
            List of matching entries
        """
        matches = []
        for cache_hash, info in self._metadata.items():
            key_info = info.get("key_info") or {}
            if key_info.get("expression") == expression:
                matches.append({
                    "hash": cache_hash[:8],
                    "hit_count": info.get("hit_count", 0),
                    "size_kb": info.get("size_bytes", 0) / 1024,
                    "created_at": info.get("created_at", ""),
                })

        return matches

    def get_top_accessed(self, n: int = 5) -> List[dict]:
        """Get top N most accessed entries

        Args:
            n: Number of entries to return

        Returns:
            List of top accessed entries
        """
        return self._get_top_accessed(n)

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
