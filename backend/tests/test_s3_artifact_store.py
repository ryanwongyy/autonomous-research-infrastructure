"""Tests for the S3-compatible artefact store backend.

Cloud-durable storage is required for any public release: Render-style hosts
have ephemeral disks, so on every redeploy the local
``FilesystemArtifactStore`` would lose every snapshot. This file covers
``S3ArtifactStore`` (the cloud backend) plus the ``get_artifact_store()``
factory that picks between filesystem and S3 from settings.

Tests use ``moto[s3]`` to mock the S3 API. No network traffic is generated.
"""

from __future__ import annotations

import os
import tempfile

import boto3
import pytest
from moto import mock_aws

from app.services.storage.artifact_store import (
    FilesystemArtifactStore,
    S3ArtifactStore,
    get_artifact_store,
)


# ── moto fixture: standalone S3 mock for these tests ─────────────────────────


@pytest.fixture
def s3_bucket():
    """Spin up a moto S3 mock with a single bucket. Yields the bucket name."""
    # moto uses fake credentials; set them so boto3 doesn't read real ones.
    old = {
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
    }
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="ari-artifact-test")
        yield "ari-artifact-test"
    # Restore env.
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── S3ArtifactStore: store / retrieve / exists / delete ──────────────────────


@pytest.mark.asyncio
async def test_store_returns_sha256(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket, region="us-east-1")
    h = await store.store(b"hello world")
    # SHA-256 of "hello world"
    assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


@pytest.mark.asyncio
async def test_retrieve_round_trips_bytes(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    body = b"some snapshot bytes"
    h = await store.store(body)
    got = await store.retrieve(h)
    assert got == body


@pytest.mark.asyncio
async def test_retrieve_missing_returns_none(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    assert await store.retrieve("0" * 64) is None


@pytest.mark.asyncio
async def test_exists_true_after_store(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    h = await store.store(b"x")
    assert await store.exists(h) is True


@pytest.mark.asyncio
async def test_exists_false_for_unknown_hash(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    assert await store.exists("a" * 64) is False


@pytest.mark.asyncio
async def test_delete_removes_object(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    h = await store.store(b"to delete")
    assert await store.delete(h) is True
    assert await store.exists(h) is False


@pytest.mark.asyncio
async def test_delete_returns_false_for_missing(s3_bucket):
    store = S3ArtifactStore(bucket=s3_bucket)
    assert await store.delete("0" * 64) is False


@pytest.mark.asyncio
async def test_store_is_idempotent_on_hash(s3_bucket):
    """Storing the same bytes twice does not produce a second object."""
    store = S3ArtifactStore(bucket=s3_bucket)
    h1 = await store.store(b"same body")
    h2 = await store.store(b"same body")
    assert h1 == h2

    # boto3 list_objects_v2 — moto exposes the same API.
    raw = boto3.client("s3", region_name="us-east-1").list_objects_v2(Bucket=s3_bucket)
    keys = [obj["Key"] for obj in raw.get("Contents", [])]
    # Exactly one object with the artifact key prefix.
    assert sum(1 for k in keys if h1 in k) == 1


@pytest.mark.asyncio
async def test_key_layout_matches_filesystem(s3_bucket):
    """The S3 key uses the same {hash[:2]}/{hash[2:4]}/{hash} layout as the
    filesystem backend, so artefacts can be migrated by a simple sync."""
    store = S3ArtifactStore(bucket=s3_bucket, prefix="my-prefix")
    h = await store.store(b"layout check")
    expected = f"my-prefix/{h[:2]}/{h[2:4]}/{h}"
    raw = boto3.client("s3", region_name="us-east-1").list_objects_v2(Bucket=s3_bucket)
    keys = [obj["Key"] for obj in raw.get("Contents", [])]
    assert expected in keys


@pytest.mark.asyncio
async def test_retrieve_detects_corruption(s3_bucket):
    """If the bytes at the key don't hash to the requested key, retrieve()
    returns None — defends against a key collision or upstream rewrite."""
    store = S3ArtifactStore(bucket=s3_bucket)
    h = await store.store(b"original")
    # Manually overwrite the object's body with different bytes.
    s3 = boto3.client("s3", region_name="us-east-1")
    key = store._key(h)
    s3.put_object(Bucket=s3_bucket, Key=key, Body=b"tampered")
    # Retrieve must refuse to return mismatched content.
    assert await store.retrieve(h) is None


# ── Factory: get_artifact_store() reads settings ────────────────────────────


def test_factory_returns_filesystem_by_default(monkeypatch):
    monkeypatch.setattr("app.config.settings.artifact_store_backend", "filesystem")
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.artifact_store_backend",
        "filesystem",
    )
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr("app.config.settings.artifact_store_path", tmp)
        monkeypatch.setattr(
            "app.services.storage.artifact_store.settings.artifact_store_path",
            tmp,
        )
        store = get_artifact_store()
        assert isinstance(store, FilesystemArtifactStore)


def test_factory_returns_s3_when_configured(monkeypatch, s3_bucket):
    """`ARTIFACT_STORE_BACKEND=s3` + `S3_BUCKET` set → S3 backend."""
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.artifact_store_backend", "s3"
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_bucket", s3_bucket
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_endpoint_url", ""
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_region", "us-east-1"
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_access_key_id", ""
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_secret_access_key", ""
    )
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.s3_artifact_prefix", ""
    )

    store = get_artifact_store()
    assert isinstance(store, S3ArtifactStore)
    assert store.bucket == s3_bucket


def test_factory_rejects_s3_without_bucket(monkeypatch):
    """`ARTIFACT_STORE_BACKEND=s3` with no bucket → loud error."""
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.artifact_store_backend", "s3"
    )
    monkeypatch.setattr("app.services.storage.artifact_store.settings.s3_bucket", "")
    with pytest.raises(ValueError, match="S3_BUCKET"):
        get_artifact_store()


def test_factory_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr(
        "app.services.storage.artifact_store.settings.artifact_store_backend",
        "redis",
    )
    with pytest.raises(ValueError, match="Unknown ARTIFACT_STORE_BACKEND"):
        get_artifact_store()
