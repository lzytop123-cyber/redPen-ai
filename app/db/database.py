from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

if settings.database_url.startswith("sqlite"):
    Path("data").mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"timeout": 15} if settings.database_url.startswith("sqlite") else {},
)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 平滑迁移：为老数据库补齐 Web 账号登录字段
        def _ensure_user_columns(sync_conn):
            insp = inspect(sync_conn)
            if "users" not in insp.get_table_names():
                return
            existing = {col["name"] for col in insp.get_columns("users")}
            if "username" not in existing:
                sync_conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(64)"))
                sync_conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
            if "password_hash" not in existing:
                sync_conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))

        await conn.run_sync(_ensure_user_columns)
