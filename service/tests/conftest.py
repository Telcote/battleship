import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import get_session
from app.main import app


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    # Отдельный engine на тест, а не общий app.db.engine: pytest-asyncio даёт каждому
    # тесту свой event loop, а asyncpg-соединение, открытое в одном loop, нельзя
    # переиспользовать из другого — общий пул на процесс из-за этого падает или виснет
    # уже на втором тесте. Здесь engine целиком живёт и умирает в границах одного теста.
    test_engine = create_async_engine(settings.database_url)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_session_factory() as db_session:
        yield db_session
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    # Роуты получают AsyncSession через ту же зависимость get_session, что и в проде —
    # подменяем её на фикстуру session, иначе FastAPI брал бы соединение из общего
    # app.db.engine и упирался в ту же проблему с чужим event loop, что и выше.
    async def _get_test_session() -> AsyncSession:
        return session

    app.dependency_overrides[get_session] = _get_test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)
