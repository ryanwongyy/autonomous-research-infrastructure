"""Test that ``alembic upgrade head`` actually works on a fresh DB.

CI's existing pytest suite uses ``Base.metadata.create_all`` to build the
schema and never invokes alembic. That meant a regression where the
initial migration tried to create indexes for tables it didn't create
shipped silently for months — it was only visible to anyone who ran
``alembic upgrade head`` against a brand-new DB.

This test runs the migration against a temp SQLite file, asserts every
ORM-declared table actually exists, then round-trips through downgrade.
If the migration is incomplete (missing CREATE TABLE for any model), this
test fails and CI catches it.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401  — ensure all models register with Base.metadata
from app.database import Base


def _alembic_config(db_url: str, monkeypatch) -> Config:
    """Build an Alembic Config pointing at a temp DB.

    `alembic/env.py` overrides the URL with `settings.database_url`, so we
    monkeypatch the live settings object too — otherwise migrations would
    target the developer's working DB and clobber it.
    """
    monkeypatch.setattr("app.config.settings.database_url", db_url)
    cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(cfg_path))
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_head_runs_clean(monkeypatch):
    """`alembic upgrade head` succeeds against a fresh DB."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "alembic_test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = _alembic_config(db_url, monkeypatch)

        # Should not raise.
        command.upgrade(cfg, "head")

        # Sanity: at least one table was created.
        # `create_engine` is sync — strip the aiosqlite driver suffix
        engine = create_engine(db_url.replace("+aiosqlite", ""))
        tables = inspect(engine).get_table_names()
        assert len(tables) > 5, f"Migration produced too few tables: {tables}"
        engine.dispose()


def test_migration_creates_every_orm_table(monkeypatch):
    """Every table declared on `Base.metadata` must exist after upgrade.

    Catches the original bug class: indexes referencing non-existent tables.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "alembic_test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = _alembic_config(db_url, monkeypatch)
        command.upgrade(cfg, "head")

        # `create_engine` is sync — strip the aiosqlite driver suffix
        engine = create_engine(db_url.replace("+aiosqlite", ""))
        live_tables = set(inspect(engine).get_table_names())
        engine.dispose()

        expected = {t.name for t in Base.metadata.sorted_tables}
        # Alembic adds its own bookkeeping table; ignore it.
        live_tables.discard("alembic_version")

        missing = expected - live_tables
        assert not missing, (
            f"Migration is missing CREATE TABLE for: {sorted(missing)}. "
            f"Either add the table to the migration or drop the model."
        )


def test_alembic_round_trip_clean(monkeypatch):
    """upgrade head → downgrade base → upgrade head leaves no residue."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "alembic_test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = _alembic_config(db_url, monkeypatch)

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        # After downgrade, only alembic_version (and nothing else) should remain.
        # `create_engine` is sync — strip the aiosqlite driver suffix
        engine = create_engine(db_url.replace("+aiosqlite", ""))
        tables_after_downgrade = set(inspect(engine).get_table_names())
        engine.dispose()
        residue = tables_after_downgrade - {"alembic_version"}
        assert not residue, f"Downgrade left residue tables: {sorted(residue)}"

        # Re-upgrade must work on the now-empty schema.
        command.upgrade(cfg, "head")


# Allow asyncio default loop scope to remain — these tests use sync sqlalchemy.
asyncio  # noqa: B018 — referenced for import-time side effects in some envs
