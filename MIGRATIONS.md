# Database Migrations

The backend uses **Alembic** for schema migrations. SQLAlchemy 2 async +
asyncpg in production, async SQLite in development and tests.

---

## When to write a migration

Whenever an SQLAlchemy model under `backend/app/models/` changes shape:

- New table → add migration
- New column → add migration
- Column rename / type change → add migration
- New index / unique constraint → add migration
- Default-only change → migration recommended but not strictly required

Tests (`backend/tests/`) call `Base.metadata.create_all` against a fresh
in-memory SQLite, so they never run migrations — but production does. A
schema change with no migration **will deploy and break in production.**

---

## Creating a migration

```bash
cd backend
source .venv/bin/activate

# Auto-generate from model diffs (recommended)
alembic revision --autogenerate -m "add x column to papers"

# Or write by hand
alembic revision -m "backfill x column from y"
```

Auto-generation reads the live database and compares it against
`Base.metadata`. **Always review the generated file before committing** —
it sometimes misses indexes, defaults, or check constraints.

---

## Naming conventions

- Migration message: imperative, lowercase. `"add release_status to papers"`,
  not `"Adds release_status"`.
- File ID: Alembic generates a 12-char hash. Don't rename it.
- Multiple unrelated changes → multiple migrations. One concern per file.

---

## Running migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one
alembic downgrade -1

# Inspect current revision
alembic current

# History
alembic history --verbose
```

In Docker:

```bash
docker compose exec backend alembic upgrade head
```

In production (Render):

```bash
# Pre-deploy hook in render.yaml runs alembic upgrade head
# automatically. To run manually:
render run "alembic upgrade head"
```

---

## Conflict resolution

When two branches both add migrations, Alembic detects the divergence on
`upgrade head` (`Multiple head revisions`).

```bash
# See heads
alembic heads

# Merge them
alembic merge -m "merge heads after rebase" <hash1> <hash2>
```

The merge migration has no `upgrade` / `downgrade` body — it just records
that the two histories now share a parent.

---

## Production checklist before merging a migration PR

- [ ] Auto-generated file matches the intent (no spurious changes).
- [ ] `alembic upgrade head` succeeds against a fresh dev DB.
- [ ] `alembic downgrade -1 && alembic upgrade head` round-trips cleanly.
- [ ] Backfills (if any) are idempotent — re-running them is safe.
- [ ] Long-running migrations (large table backfills, index creation) are
      flagged in the PR description so deploys can be timed accordingly.
- [ ] Destructive changes (drops, NOT NULL on existing columns without a
      default) have an explicit migration plan in the PR.

---

## Backfills

For data migrations that touch many rows, prefer **idempotent backfills
in a separate migration from the schema change**:

1. Migration A: add the new column as nullable.
2. Migration B: backfill values in batches.
3. Migration C (later): set NOT NULL.

This pattern lets the application code roll out independently of the
backfill, and the backfill can be retried without violating constraints.

---

## Common pitfalls

| Symptom                                       | Cause                                                                     |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| `sslmode is not a valid asyncpg parameter`    | Render Postgres URL contains `?sslmode=…`. Already stripped in `db.py`.   |
| `Can't locate revision identified by …`       | Migration deleted or branch checkout missed it. `git pull` and re-check.  |
| Auto-gen produces empty migration             | Models not imported. `app/models/__init__.py` must export every table.    |
| Auto-gen recreates an enum every revision     | Postgres enum type. Use string columns + Pydantic enums in app code.      |
