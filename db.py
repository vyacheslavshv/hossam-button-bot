import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)

SessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False,
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Create tables on startup. The bot has a single small table, so we skip
    migrations entirely — this is idempotent and runs every boot."""
    import models  # noqa: F401  (register models on Base.metadata)

    # make sure the sqlite directory (e.g. data/) exists on a fresh server
    url = make_url(DATABASE_URL)
    if url.database and url.get_backend_name().startswith("sqlite"):
        db_dir = os.path.dirname(url.database)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
