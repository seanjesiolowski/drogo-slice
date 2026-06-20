import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.dependencies import get_db
from app.main import app


@pytest.mark.asyncio
async def test_health_check_db_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


@pytest.mark.asyncio
async def test_health_check_db_down(client: AsyncClient):
    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def broken_get_db():
        yield _BrokenSession()

    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = broken_get_db
    try:
        response = await client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy", "database": "error"}
    finally:
        app.dependency_overrides[get_db] = original
