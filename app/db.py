"""
Manages a pool of database connections.

Why a pool and not a fresh connection per request: opening a new PostgreSQL
connection is slow (tens of milliseconds). A pool keeps a handful of
connections open and ready, so each request just borrows one and gives it
back — much faster under real traffic.
"""

import asyncpg
from app.config import settings

_pool: asyncpg.Pool | None = None


async def connect_db() -> None:
    """Called once when the app starts up."""
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)


async def disconnect_db() -> None:
    """Called once when the app shuts down."""
    global _pool
    if _pool:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — did the app start correctly?")
    return _pool
