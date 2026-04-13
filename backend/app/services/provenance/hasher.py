"""Content-addressable hashing utilities for provenance tracking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def hash_content(content: bytes) -> str:
    """SHA-256 hash of raw content."""
    return hashlib.sha256(content).hexdigest()


def hash_file(file_path: Path) -> str:
    """SHA-256 hash of a file, reading in chunks for large files."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_dict(data: dict) -> str:
    """Deterministic SHA-256 hash of a dict (JSON-serialized with sorted keys)."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def verify_hash(content: bytes, expected_hash: str) -> bool:
    """Verify content matches expected SHA-256 hash."""
    return hash_content(content) == expected_hash


def compute_merkle_root(hashes: list[str]) -> str:
    """Compute Merkle-tree root hash from a list of SHA-256 hex strings.

    Used for paper package manifest verification.
    """
    if not hashes:
        return hash_content(b"")
    if len(hashes) == 1:
        return hashes[0]
    # Pair and hash upward
    while len(hashes) > 1:
        next_level: list[str] = []
        for i in range(0, len(hashes), 2):
            if i + 1 < len(hashes):
                combined = (hashes[i] + hashes[i + 1]).encode("utf-8")
            else:
                combined = (hashes[i] + hashes[i]).encode("utf-8")  # duplicate odd element
            next_level.append(hashlib.sha256(combined).hexdigest())
        hashes = next_level
    return hashes[0]
