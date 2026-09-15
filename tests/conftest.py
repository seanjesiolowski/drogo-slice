import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.dependencies import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, expire_on_commit=False)


@event.listens_for(engine_test.sync_engine, "connect")
def _set_sqlite_fk_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def override_get_db():
    async with async_session_test() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _pin_health_check_to_test_db(monkeypatch):
    """/health is pinned directly to app.database's primary async_session,
    bypassing the get_db override above (Task 6: routed get_db must not be
    trusted for a route that runs with no account on the request). Point
    that direct reference at the same in-memory test database as every
    other route, so /health's primary check reflects test reality instead
    of the unreachable production DATABASE_URL default.
    """
    monkeypatch.setattr("app.main.async_session", async_session_test)


@pytest.fixture(autouse=True)
def _clear_secondary_sessionmakers():
    """Stop one test's secondary database config leaking into the next via the cache."""
    from app.accounts import PRIMARY
    from app.database import _sessionmakers

    def _drop_non_primary():
        for name in [n for n in _sessionmakers if n != PRIMARY]:
            del _sessionmakers[name]

    _drop_non_primary()
    yield
    _drop_non_primary()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=(settings.admin_username, settings.admin_password),
    ) as ac:
        yield ac
