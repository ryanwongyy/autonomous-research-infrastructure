import asyncio
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.auth import admin_key_required
from app.config import settings
from app.database import engine, init_db
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("ape_replica")

# Sentry initialization (no-op if DSN not configured)
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment="production"
        if not settings.database_url.startswith("sqlite")
        else "development",
    )


async def _ensure_added_columns() -> None:
    """Add any new columns that ``init_db()`` (Base.metadata.create_all)
    can't add to existing tables.

    ``create_all`` is idempotent for tables: it skips ones that already
    exist. But when we ADD a column to an existing model, ``create_all``
    silently leaves the column missing on the live table. The ORM then
    queries it and we get a 500.

    We were going to use ``alembic upgrade head`` here, but the initial
    migration tries to ``create_index`` on indexes ``create_all`` already
    made — duplicate index errors. Until we untangle the alembic state
    on the live DB, do the safer thing: directly check for and add the
    new columns we need with raw SQL. Idempotent (use IF NOT EXISTS on
    Postgres / equivalent on SQLite).
    """
    from app.database import engine

    if engine.dialect.name == "sqlite":
        # Tests use SQLite in-memory and create everything fresh — no-op.
        return

    # Postgres path. Each ALTER COLUMN is idempotent via IF NOT EXISTS.
    statements = [
        "ALTER TABLE papers ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP",
        "ALTER TABLE papers ADD COLUMN IF NOT EXISTS last_heartbeat_stage VARCHAR(32)",
        # PR #58: durable manuscript content. Render's ephemeral
        # filesystem wipes the .tex files on redeploy; this column
        # holds the actual LaTeX so the export endpoint and L1 review
        # can read it after the disk artifact is gone.
        "ALTER TABLE papers ADD COLUMN IF NOT EXISTS manuscript_latex TEXT",
    ]
    from sqlalchemy import text

    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with asyncio.timeout(30):
            await init_db()
    except TimeoutError:
        logger.critical("Database initialization timed out after 30s")
        raise

    # ``init_db`` (above) calls ``Base.metadata.create_all`` which
    # creates NEW tables but never ALTERs existing ones — so columns
    # added in later migrations (e.g. ``papers.last_heartbeat_at`` from
    # PR #37) never reach the production schema, and ORM queries
    # against them raise 500. Add them directly via raw SQL.
    try:
        async with asyncio.timeout(30):
            await _ensure_added_columns()
            logger.info("Schema columns ensured on existing tables")
    except TimeoutError:
        logger.error("Schema-ensure timed out after 30s — continuing")
    except Exception as e:
        logger.error("Schema-ensure failed (non-fatal): %s", e, exc_info=True)

    # Seed source cards + families on startup. Both seed functions are
    # idempotent (insert-or-update for source cards, skip-if-present for
    # families), so it's safe to run on every boot.
    #
    # Without this, a fresh deployment has zero source cards in the DB,
    # which causes the Data Steward stage to die with an empty fallback
    # whitelist (production run #25131261938 hit this exact symptom).
    # Wrapped in try/except so seed failures don't block the app from
    # serving — the API stays up and reports the issue at request time.
    try:
        async with asyncio.timeout(60):
            from seeds.families import seed_families
            from seeds.source_cards import seed_source_cards

            await seed_families()
            await seed_source_cards()
            logger.info("Seeded families + source cards on startup")
    except TimeoutError:
        logger.error("Seed run timed out after 60s — continuing without seeds")
    except Exception as e:
        logger.error("Seed run failed (non-fatal): %s", e, exc_info=True)

    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


class MutationAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid API key for all non-GET, non-OPTIONS, non-HEAD requests."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if (
            request.method in self.SAFE_METHODS
            or request.url.path in self.OPEN_PATHS
            or not settings.ape_api_key  # auth disabled in dev
        ):
            return await call_next(request)

        key = request.headers.get("X-API-Key") or ""
        auth = request.headers.get("Authorization", "")
        if not key and auth.lower().startswith("bearer "):
            key = auth[7:].strip()

        # Accept either the regular API key or the admin key
        valid = hmac.compare_digest(key, settings.ape_api_key)
        if not valid and settings.ape_admin_key:
            valid = hmac.compare_digest(key, settings.ape_admin_key)

        if not valid:
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )
        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique request ID to each request for trace correlation."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        if path == "/health":
            return response
        request_id = getattr(request.state, "request_id", None)
        log_level = logging.WARNING if duration_ms > 1000 else logging.INFO
        extra = {"request_id": request_id} if request_id else {}
        logger.log(
            log_level,
            "%s %s %d %.0fms",
            request.method,
            path,
            response.status_code,
            duration_ms,
            extra=extra,
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MutationAuthMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return {"status": "ok"}
    except Exception:
        return JSONResponse(
            {"status": "degraded", "db": "unreachable"}, status_code=503
        )


# Register routers
from app.api import (  # noqa: E402
    leaderboard,
    stats,
    papers,
    matches,
    tournament,
    categories,
    config,
    reviews,
)
from app.api import families, sources, provenance  # noqa: E402
from app.api import release, throughput, significance_memos  # noqa: E402
from app.api import reliability  # noqa: E402
from app.api import outcomes, corrections, expert_reviews  # noqa: E402
from app.api import autonomy, failures  # noqa: E402
from app.api import novelty, cohorts  # noqa: E402
from app.api import rsi  # noqa: E402
from app.api import collegial  # noqa: E402
from app.api import batch  # noqa: E402

app.include_router(leaderboard.router, prefix="/api/v1", tags=["leaderboard"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(papers.router, prefix="/api/v1", tags=["papers"])
app.include_router(matches.router, prefix="/api/v1", tags=["matches"])
app.include_router(
    tournament.router,
    prefix="/api/v1",
    tags=["tournament"],
    dependencies=[Depends(admin_key_required)],
)
app.include_router(categories.router, prefix="/api/v1", tags=["categories"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(reviews.router, prefix="/api/v1", tags=["reviews"])
app.include_router(families.router, prefix="/api/v1", tags=["families"])
app.include_router(sources.router, prefix="/api/v1", tags=["sources"])
app.include_router(provenance.router, prefix="/api/v1", tags=["provenance"])
app.include_router(release.router, prefix="/api/v1", tags=["release"])
app.include_router(throughput.router, prefix="/api/v1", tags=["throughput"])
app.include_router(
    significance_memos.router, prefix="/api/v1", tags=["significance-memos"]
)
app.include_router(reliability.router, prefix="/api/v1", tags=["reliability"])
app.include_router(outcomes.router, prefix="/api/v1", tags=["outcomes"])
app.include_router(corrections.router, prefix="/api/v1", tags=["corrections"])
app.include_router(expert_reviews.router, prefix="/api/v1", tags=["expert-reviews"])
app.include_router(autonomy.router, prefix="/api/v1", tags=["autonomy"])
app.include_router(failures.router, prefix="/api/v1", tags=["failures"])
app.include_router(novelty.router, prefix="/api/v1", tags=["novelty"])
app.include_router(cohorts.router, prefix="/api/v1", tags=["cohorts"])
app.include_router(
    rsi.router,
    prefix="/api/v1",
    tags=["rsi"],
    dependencies=[Depends(admin_key_required)],
)
app.include_router(collegial.router, prefix="/api/v1", tags=["collegial"])
app.include_router(
    batch.router,
    prefix="/api/v1",
    tags=["batch"],
    dependencies=[Depends(admin_key_required)],
)
