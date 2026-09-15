import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import accounts as accounts_module
from app.dependencies import get_db
from app.main import app


def _unreachable_client_factory(monkeypatch, database_url: str):
    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(s, "secondary_database_url", database_url, raising=False)


@pytest_asyncio.fixture
async def unreachable_host_client(monkeypatch):
    """Secondary database points at a hostname that cannot be resolved.

    This raises socket.gaierror, not sqlalchemy.exc.OperationalError.
    """
    _unreachable_client_factory(
        monkeypatch,
        "postgresql+asyncpg://user:pw@nonexistent-host-xyz:5432/db",
    )

    original = app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            auth=("sandbox", "sandbox-pass"),
        ) as ac:
            yield ac
    finally:
        if original is not None:
            app.dependency_overrides[get_db] = original


@pytest_asyncio.fixture
async def refused_connection_client(monkeypatch):
    """Secondary database points at a port with nothing listening.

    This raises ConnectionRefusedError, not sqlalchemy.exc.OperationalError.
    """
    _unreachable_client_factory(
        monkeypatch,
        "postgresql+asyncpg://user:pw@127.0.0.1:59998/db",
    )

    original = app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            auth=("sandbox", "sandbox-pass"),
        ) as ac:
            yield ac
    finally:
        if original is not None:
            app.dependency_overrides[get_db] = original


@pytest.mark.asyncio
async def test_unresolvable_host_returns_503_not_500(
    unreachable_host_client: AsyncClient,
):
    response = await unreachable_host_client.get("/api/categories/")
    assert response.status_code == 503
    assert "secondary" in response.text
    assert "nonexistent-host-xyz" not in response.text


@pytest.mark.asyncio
async def test_refused_connection_returns_503_not_500(
    refused_connection_client: AsyncClient,
):
    response = await refused_connection_client.get("/api/categories/")
    assert response.status_code == 503
    assert "secondary" in response.text
    assert "127.0.0.1" not in response.text
