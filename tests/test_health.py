import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app import accounts as accounts_module


@pytest.mark.asyncio
async def test_health_check_db_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"


@pytest.mark.asyncio
async def test_health_check_db_down(client: AsyncClient, monkeypatch):
    """A failing primary database makes /health unhealthy."""

    class _BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr("app.main.async_session", lambda: _BrokenSession())

    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "error"}


@pytest.mark.asyncio
async def test_secondary_reported_as_not_configured(client: AsyncClient):
    response = await client.get("/health")
    assert response.json()["secondary"] == "not_configured"


@pytest.mark.asyncio
async def test_unreachable_secondary_does_not_make_health_unhealthy(
    client: AsyncClient, monkeypatch
):
    """The guarantee that a broken sandbox cannot fail a production deploy."""
    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s,
        "secondary_database_url",
        "postgresql+asyncpg://user:pw@nonexistent-host-xyz:5432/db",
        raising=False,
    )

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["secondary"] == "error"
