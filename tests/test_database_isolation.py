# tests/test_database_isolation.py
"""The core property: what one login writes, the other cannot see."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import accounts as accounts_module
from app import database as database_module
from app.accounts import PRIMARY, SECONDARY
from app.config import settings
from app.database import Base
from app.dependencies import get_db
from app.main import app


@pytest_asyncio.fixture
async def two_databases(tmp_path, monkeypatch):
    """Point primary and secondary at two separate SQLite files."""
    primary_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}")
    secondary_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'secondary.db'}")

    for engine in (primary_engine, secondary_engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", f"sqlite+aiosqlite:///{tmp_path / 'secondary.db'}", raising=False
    )

    monkeypatch.setitem(
        database_module._sessionmakers,
        PRIMARY,
        async_sessionmaker(primary_engine, expire_on_commit=False),
    )
    monkeypatch.setitem(
        database_module._sessionmakers,
        SECONDARY,
        async_sessionmaker(secondary_engine, expire_on_commit=False),
    )

    # Use real routing, not the suite-wide override.
    original = app.dependency_overrides.pop(get_db, None)
    try:
        yield
    finally:
        if original is not None:
            app.dependency_overrides[get_db] = original
        await primary_engine.dispose()
        await secondary_engine.dispose()


@pytest_asyncio.fixture
async def primary_client(two_databases):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=(settings.admin_username, settings.admin_password),
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def sandbox_client(two_databases):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=("sandbox", "sandbox-pass"),
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_category_written_by_primary_is_invisible_to_secondary(
    primary_client: AsyncClient, sandbox_client: AsyncClient
):
    created = await primary_client.post("/api/categories/", json={"name": "Espresso"})
    assert created.status_code == 201

    assert [c["name"] for c in (await primary_client.get("/api/categories/")).json()] == [
        "Espresso"
    ]
    assert (await sandbox_client.get("/api/categories/")).json() == []


@pytest.mark.asyncio
async def test_category_written_by_secondary_is_invisible_to_primary(
    primary_client: AsyncClient, sandbox_client: AsyncClient
):
    created = await sandbox_client.post("/api/categories/", json={"name": "Test Beans"})
    assert created.status_code == 201

    assert (await primary_client.get("/api/categories/")).json() == []
    assert [c["name"] for c in (await sandbox_client.get("/api/categories/")).json()] == [
        "Test Beans"
    ]


@pytest.mark.asyncio
async def test_reset_under_secondary_leaves_primary_data_alone(
    primary_client: AsyncClient, sandbox_client: AsyncClient
):
    await primary_client.post("/api/categories/", json={"name": "Keep Me"})
    await sandbox_client.post("/api/categories/", json={"name": "Wipe Me"})

    wiped = await sandbox_client.post("/api/reset?confirm=RESET")
    assert wiped.status_code == 200

    assert (await sandbox_client.get("/api/categories/")).json() == []
    assert [c["name"] for c in (await primary_client.get("/api/categories/")).json()] == [
        "Keep Me"
    ]
