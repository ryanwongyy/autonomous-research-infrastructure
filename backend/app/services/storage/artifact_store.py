"""Content-addressed artifact storage.

Three backends:

  * ``FilesystemArtifactStore`` — local disk. Default in dev. On Render-style
    ephemeral disks the bytes are wiped on every redeploy, so this is
    suitable for development only.

  * ``S3ArtifactStore`` — any S3-compatible object store: AWS S3, Cloudflare
    R2, Backblaze B2, Supabase Storage, MinIO. Bytes survive redeploys, can
    be served via a CDN, and are signable for permalinks. Required for
    public release.

  * ``InMemoryArtifactStore`` — used in tests.

The factory ``get_artifact_store()`` reads ``settings.artifact_store_backend``
and instantiates the right one. Existing code uses
``FilesystemArtifactStore(settings.artifact_store_path)`` directly; new code
should prefer ``get_artifact_store()`` so the cloud backend is picked up
without per-call-site changes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings
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


# ---------------------------------------------------------------------------
# S3-compatible cloud backend
# ---------------------------------------------------------------------------


class S3ArtifactStore(ArtifactStore):
    """Content-addressed storage on any S3-compatible object store.

    Works with AWS S3, Cloudflare R2, Backblaze B2, Supabase Storage, MinIO,
    etc. Uses the same ``{hash[:2]}/{hash[2:4]}/{hash}`` key prefix layout
    as the filesystem backend, so artefacts can be migrated by simple
    ``aws s3 sync``.

    The ``boto3`` dependency is optional (in ``pyproject.toml`` under
    ``[project.optional-dependencies].cloud``). Importing this class without
    boto3 installed will raise ``ImportError`` only when the constructor
    runs — selecting ``artifact_store_backend="filesystem"`` keeps the
    dependency unloaded.

    All boto3 calls are synchronous; we wrap them with ``asyncio.to_thread``
    to avoid blocking the FastAPI event loop. For typical artefact sizes
    (snapshots, manuscripts) this is well below the latency budget.
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str = "",
    ) -> None:
        try:
            import boto3
            from botocore.exceptions import ClientError as _ClientError
        except ImportError as e:  # pragma: no cover — exercised by env without boto3
            raise ImportError(
                "S3ArtifactStore requires the optional 'boto3' dependency. "
                "Install with `pip install -e .[cloud]` or set "
                "ARTIFACT_STORE_BACKEND=filesystem to use local storage."
            ) from e

        self._ClientError = _ClientError
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")  # store as e.g. "artifacts" not "artifacts/"
        # Both AWS-key and IAM/profile creds are supported. When access_key_id
        # is None, boto3 falls through to env / instance profile / etc.
        client_kwargs: dict = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client("s3", **client_kwargs)

    def _key(self, content_hash: str) -> str:
        """Compute the object key for a given content hash."""
        sub = f"{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
        return f"{self.prefix}/{sub}" if self.prefix else sub

    async def store(self, content: bytes, artifact_type: str = "general") -> str:
        """Store content; return its SHA-256 hash. Idempotent on hash collision."""
        content_hash = hash_content(content)
        key = self._key(content_hash)

        # Skip the upload if we already hold this exact content (de-dup).
        if await self.exists(content_hash):
            logger.debug(
                "S3 content already stored: %s (type=%s)",
                content_hash[:16],
                artifact_type,
            )
            return content_hash

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            Metadata={"artifact-type": artifact_type, "sha256": content_hash},
        )
        logger.info(
            "S3 stored artifact: %s (%d bytes, type=%s, key=%s)",
            content_hash[:16],
            len(content),
            artifact_type,
            key,
        )
        return content_hash

    async def retrieve(self, content_hash: str) -> bytes | None:
        """Retrieve content by hash. Returns None if missing or hash mismatches."""
        key = self._key(content_hash)
        try:
            obj = await asyncio.to_thread(
                self._client.get_object, Bucket=self.bucket, Key=key
            )
        except self._ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                return None
            raise

        # boto3 streaming bodies aren't async-friendly; .read() is fine here
        # because we're already inside a thread context for the get_object.
        data = await asyncio.to_thread(obj["Body"].read)

        # Integrity check: the bytes we just read must hash to the requested
        # key. Anything else means upstream corruption or a key collision —
        # either way the retrieve must fail closed.
        if hash_content(data) != content_hash:
            logger.error(
                "S3 integrity failure: object at %s does not match hash %s",
                key,
                content_hash[:16],
            )
            return None
        return data

    async def exists(self, content_hash: str) -> bool:
        """Cheap existence probe via head_object."""
        key = self._key(content_hash)
        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self.bucket, Key=key
            )
            return True
        except self._ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NotFound"}:
                return False
            raise

    async def delete(self, content_hash: str) -> bool:
        """Delete by hash. Returns True if the object was present, False otherwise."""
        if not await self.exists(content_hash):
            return False
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self.bucket,
            Key=self._key(content_hash),
        )
        logger.info("S3 deleted artifact: %s", content_hash[:16])
        return True

    async def get_path(self, content_hash: str) -> Path | None:  # pragma: no cover
        """Object stores don't have filesystem paths — always None."""
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_artifact_store() -> ArtifactStore:
    """Return the configured artefact store, reading ``settings``.

    Backend selection is via ``settings.artifact_store_backend``:
      * ``"filesystem"`` (default) — local disk at ``settings.artifact_store_path``.
      * ``"s3"`` — S3-compatible object store, configured via the ``s3_*``
        settings. Requires the ``boto3`` extra.

    Roles and services that previously instantiated
    ``FilesystemArtifactStore(settings.artifact_store_path)`` directly should
    migrate to this factory so flipping ``ARTIFACT_STORE_BACKEND=s3`` in
    production routes their reads/writes to the cloud without code changes.
    """
    backend = (settings.artifact_store_backend or "filesystem").lower()
    if backend == "s3":
        bucket = settings.s3_bucket
        if not bucket:
            raise ValueError("ARTIFACT_STORE_BACKEND=s3 requires S3_BUCKET to be set.")
        return S3ArtifactStore(
            bucket=bucket,
            endpoint_url=settings.s3_endpoint_url or None,
            region=settings.s3_region or "us-east-1",
            access_key_id=settings.s3_access_key_id or None,
            secret_access_key=settings.s3_secret_access_key or None,
            prefix=settings.s3_artifact_prefix or "",
        )
    if backend == "filesystem":
        return FilesystemArtifactStore(settings.artifact_store_path)
    raise ValueError(
        f"Unknown ARTIFACT_STORE_BACKEND={backend!r}. Expected 'filesystem' or 's3'."
    )
