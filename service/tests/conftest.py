import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.main import app


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with async_session_factory() as db_session:
        yield db_session


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
