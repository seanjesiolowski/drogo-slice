import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def unauthenticated_client():
    """Client without authentication credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def invalid_auth_client():
    """Client with invalid authentication credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=("wrong_user", "wrong_password"),
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint_bypasses_auth(unauthenticated_client: AsyncClient):
    """Health endpoint should not require authentication."""
    response = await unauthenticated_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_missing_authorization_header_returns_401(
    unauthenticated_client: AsyncClient,
):
    """API endpoint without Authorization header should return 401."""
    response = await unauthenticated_client.get("/api/categories/")
    assert response.status_code == 401
    assert "Unauthorized" in response.text


@pytest.mark.asyncio
async def test_invalid_credentials_returns_401(invalid_auth_client: AsyncClient):
    """API endpoint with invalid credentials should return 401."""
    response = await invalid_auth_client.get("/api/categories/")
    assert response.status_code == 401
    assert "Unauthorized" in response.text


@pytest.mark.asyncio
async def test_malformed_basic_auth_returns_401(unauthenticated_client: AsyncClient):
    """Malformed Basic auth header should return 401."""
    response = await unauthenticated_client.get(
        "/api/categories/",
        headers={"Authorization": "Basic invalid_base64_that_wont_decode!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_username_colon_in_basic_auth_returns_401(
    unauthenticated_client: AsyncClient,
):
    """Basic auth without colon separator should return 401."""
    import base64

    invalid_auth = base64.b64encode(b"no_colon_here").decode()
    response = await unauthenticated_client.get(
        "/api/categories/",
        headers={"Authorization": f"Basic {invalid_auth}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_creates_items_requires_auth(
    unauthenticated_client: AsyncClient,
):
    """Creating items without authentication should return 401."""
    response = await unauthenticated_client.post(
        "/api/items/",
        json={
            "name": "Test Item",
            "unit": "units",
            "current_quantity": 1.0,
            "par_level": 5.0,
            "category_id": 1,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deletes_require_auth(
    unauthenticated_client: AsyncClient,
):
    """Delete operations without authentication should return 401."""
    response = await unauthenticated_client.delete("/api/items/1")
    assert response.status_code == 401

    response = await unauthenticated_client.delete("/api/categories/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reset_endpoint_requires_auth(
    unauthenticated_client: AsyncClient,
):
    """Database reset endpoint without authentication should return 401."""
    response = await unauthenticated_client.post("/api/reset")
    assert response.status_code == 401
