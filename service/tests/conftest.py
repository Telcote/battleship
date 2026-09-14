from collections.abc import AsyncIterator, Awaitable, Callable

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import get_session
from app.main import app

SessionFactory = Callable[[], Awaitable[AsyncSession]]


@pytest_asyncio.fixture
async def make_session() -> AsyncIterator[SessionFactory]:
    opened: list[tuple[AsyncEngine, AsyncSession]] = []

    async def factory() -> AsyncSession:
        test_engine = create_async_engine(settings.database_url)
        test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
        db_session = test_session_factory()
        opened.append((test_engine, db_session))
        return db_session

    yield factory

    for test_engine, db_session in opened:
        await db_session.close()
        await test_engine.dispose()


@pytest_asyncio.fixture
async def session(make_session: SessionFactory) -> AsyncSession:
    return await make_session()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    async def _get_test_session() -> AsyncSession:
        return session

    app.dependency_overrides[get_session] = _get_test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)
