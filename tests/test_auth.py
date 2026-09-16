import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db
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


@pytest_asyncio.fixture
async def secondary_client(monkeypatch):
    """Client authenticated as a configured secondary account."""
    from app import accounts as accounts_module

    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", "sqlite+aiosqlite:///./secondary_auth.db", raising=False
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=("sandbox", "sandbox-pass"),
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_secondary_credentials_authenticate(secondary_client: AsyncClient):
    response = await secondary_client.get("/api/categories/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_primary_credentials_still_work_alongside_secondary(
    secondary_client: AsyncClient, client: AsyncClient
):
    response = await client.get("/api/categories/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_secondary_credentials_rejected_when_not_configured():
    """With no secondary configured, its credentials are just wrong credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=("sandbox", "sandbox-pass"),
    ) as ac:
        response = await ac.get("/api/categories/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mixed_credentials_rejected(monkeypatch):
    """Primary username with secondary password must not authenticate."""
    from app import accounts as accounts_module

    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", "sqlite+aiosqlite:///./secondary_auth.db", raising=False
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=(s.admin_username, "sandbox-pass"),
    ) as ac:
        response = await ac.get("/api/categories/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_ascii_username_returns_401_not_500(unauthenticated_client: AsyncClient):
    """secrets.compare_digest raises TypeError on non-ASCII str, not bytes.

    A non-ASCII character typed into the browser's login prompt must be
    rejected as bad credentials, not crash the request handler.
    """
    import base64

    non_ascii_auth = base64.b64encode("jöe:whatever".encode("utf-8")).decode()
    response = await unauthenticated_client.get(
        "/api/categories/",
        headers={"Authorization": f"Basic {non_ascii_auth}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_credentials_rejected(unauthenticated_client: AsyncClient):
    """Blank username and password must never authenticate."""
    import base64

    blank = base64.b64encode(b":").decode()
    response = await unauthenticated_client.get(
        "/api/categories/", headers={"Authorization": f"Basic {blank}"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_sets_account_for_real_get_db():
    """/health must set request.state.account so the real get_db doesn't raise.

    tests/conftest.py overrides get_db globally for every other test, which
    hides a regression where the /health branch calls through without ever
    setting request.state.account: the real get_db then raises RuntimeError,
    which FastAPI turns into an unhandled 500. This test removes the override
    for the duration of the request so it exercises the real get_db, and
    restores the override afterwards so other tests are unaffected.
    """
    original = app.dependency_overrides.pop(get_db, None)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
    finally:
        if original is not None:
            app.dependency_overrides[get_db] = original
