"""Abstract and filesystem-based content-addressed artifact storage."""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.services.provenance.hasher import hash_content

logger = logging.getLogger(__name__)


class ArtifactStore(ABC):
    """Abstract interface for content-addressed artifact storage."""

    @abstractmethod
    async def store(self, content: bytes, artifact_type: str = "general") -> str:
        """Store content and return its SHA-256 hash (used as address)."""

    @abstractmethod
    async def retrieve(self, content_hash: str) -> bytes | None:
        """Retrieve content by its SHA-256 hash. Returns None if not found."""

    @abstractmethod
    async def exists(self, content_hash: str) -> bool:
        """Check if content with this hash exists in the store."""

    @abstractmethod
    async def delete(self, content_hash: str) -> bool:
        """Delete content by hash. Returns True if deleted, False if not found."""

    @abstractmethod
    async def get_path(self, content_hash: str) -> Path | None:
        """Get the filesystem path for stored content (if applicable)."""


class FilesystemArtifactStore(ArtifactStore):
    """Content-addressed storage using local filesystem.

    Directory structure: {base_dir}/{hash[:2]}/{hash[2:4]}/{hash}
    This avoids too many files in a single directory.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _hash_path(self, content_hash: str) -> Path:
        """Compute the storage path for a given content hash."""
        return self.base_dir / content_hash[:2] / content_hash[2:4] / content_hash

    async def store(self, content: bytes, artifact_type: str = "general") -> str:
        """Store content and return its SHA-256 hash.

        If the content already exists (same hash), the write is skipped
        (content-addressable deduplication).
        """
        content_hash = hash_content(content)
        dest = self._hash_path(content_hash)

        if dest.exists():
            logger.debug(
                "Content already stored: %s (type=%s)", content_hash[:16], artifact_type
            )
            return content_hash

        # Ensure parent directories exist.
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically via temp file + rename to avoid partial writes.
        # Uses asyncio.to_thread to avoid blocking the event loop on disk I/O.
        tmp_path = dest.with_suffix(".tmp")
        try:
            await asyncio.to_thread(self._write_bytes, tmp_path, content)
            await asyncio.to_thread(os.rename, str(tmp_path), str(dest))
        except Exception:
            # Clean up temp file on failure.
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

        logger.info(
            "Stored artifact: %s (%d bytes, type=%s)",
            content_hash[:16],
            len(content),
            artifact_type,
        )
        return content_hash

    async def retrieve(self, content_hash: str) -> bytes | None:
        """Retrieve content by its SHA-256 hash."""
        path = self._hash_path(content_hash)
        if not path.exists():
            return None

        data: bytes = await asyncio.to_thread(self._read_bytes, path)

        # Integrity check: verify the read content matches the requested hash.
        if hash_content(data) != content_hash:
            logger.error(
                "Integrity failure: stored content at %s does not match hash %s",
                path,
                content_hash[:16],
            )
            return None

        return data

    async def exists(self, content_hash: str) -> bool:
        """Check if content with this hash exists in the store."""
        return self._hash_path(content_hash).exists()

    async def delete(self, content_hash: str) -> bool:
        """Delete content by hash. Returns True if deleted, False if not found."""
        path = self._hash_path(content_hash)
        if not path.exists():
            return False

        path.unlink()
        logger.info("Deleted artifact: %s", content_hash[:16])

        # Clean up empty parent directories.
        self._cleanup_empty_parents(path)
        return True

    async def get_path(self, content_hash: str) -> Path | None:
        """Get the filesystem path for stored content."""
        path = self._hash_path(content_hash)
        return path if path.exists() else None

    def _cleanup_empty_parents(self, path: Path) -> None:
        """Remove empty parent directories up to base_dir."""
        for parent in [path.parent, path.parent.parent]:
            if parent == self.base_dir:
                break
            try:
                parent.rmdir()  # Only succeeds if directory is empty.
            except OSError:
                break

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        """Synchronous helper for writing bytes (runs in thread pool)."""
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        """Synchronous helper for reading bytes (runs in thread pool)."""
        with open(path, "rb") as f:
            return f.read()
