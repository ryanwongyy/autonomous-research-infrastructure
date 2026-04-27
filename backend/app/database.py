import ssl as _ssl_module
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")


def _prepare_pg_url(url: str) -> tuple[str, dict]:
    """Strip sslmode/channel_binding from URL (asyncpg rejects them) and return
    a clean URL plus connect_args with SSL configured."""
    parts = urlsplit(url)
    qs = parse_qs(parts.query)
    needs_ssl = qs.pop("sslmode", [None])[0] in ("require", "verify-ca", "verify-full")
    qs.pop("channel_binding", None)  # asyncpg doesn't support this param
    clean_query = urlencode({k: v[0] for k, v in qs.items()})
    clean_url = urlunsplit(parts._replace(query=clean_query))
    connect_args: dict = {}
    if needs_ssl:
        ssl_ctx = _ssl_module.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl_module.CERT_NONE
        connect_args["ssl"] = ssl_ctx
    return clean_url, connect_args


_engine_kwargs: dict = {
    "echo": settings.debug,
    "pool_pre_ping": True,
}

if not _is_sqlite:
    # PostgreSQL-specific pool settings for production
    _db_url, _connect_args = _prepare_pg_url(settings.database_url)
    _engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,
        }
    )
    if _connect_args:
        _engine_kwargs["connect_args"] = _connect_args
else:
    _db_url = settings.database_url

engine = create_async_engine(_db_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    # Import all models so Base.metadata has them registered
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
