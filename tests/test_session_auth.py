"""Browser login: a signed cookie, and a log-off that actually logs you off."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

COOKIE = "drogo_session"


@pytest_asyncio.fixture
async def browser():
    """A client with no credentials of its own, the way a browser starts out."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_login_with_valid_credentials_sets_a_session_cookie(browser: AsyncClient):
    response = await browser.post(
        "/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert response.status_code == 303
    assert browser.cookies.get(COOKIE)


@pytest.mark.asyncio
async def test_session_cookie_authenticates_a_request(browser: AsyncClient):
    await browser.post(
        "/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    response = await browser.get("/api/categories/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forged_session_cookie_is_rejected(browser: AsyncClient):
    browser.cookies.set(COOKIE, "primary|99999999999.notarealsignature")
    response = await browser.get("/api/categories/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cookie_for_an_unconfigured_account_is_rejected(browser: AsyncClient):
    """A validly signed cookie naming an account that no longer exists.

    Signature alone is not authorisation: if the secondary login is removed
    from the environment, a cookie issued while it existed must stop working
    rather than route someone to a database that is no longer configured.
    """
    from app import session as session_module

    browser.cookies.set(
        COOKIE,
        session_module.issue("secondary", secret=session_module.current_secret()),
    )
    response = await browser.get("/api/categories/")
    assert response.status_code == 401


@pytest.fixture
def secondary_configured(monkeypatch):
    """Configure a secondary login the way test_auth.py does."""
    from app import accounts as accounts_module

    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", "sqlite+aiosqlite:///./secondary_session.db", raising=False
    )


@pytest.mark.asyncio
async def test_whoami_reports_the_logged_in_account(browser: AsyncClient):
    await browser.post(
        "/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    response = await browser.get("/api/whoami")
    assert response.status_code == 200
    assert response.json()["account"] == "primary"


@pytest.mark.asyncio
async def test_logging_in_as_the_secondary_binds_the_session_to_that_account(
    browser: AsyncClient, secondary_configured: None
):
    """The cookie has to carry the account, or the sandbox login would read production."""
    await browser.post("/login", data={"username": "sandbox", "password": "sandbox-pass"})
    response = await browser.get("/api/whoami")
    assert response.json()["account"] == "secondary"


def _basic_header() -> str:
    import base64

    raw = f"{settings.admin_username}:{settings.admin_password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


async def _log_in(browser: AsyncClient) -> None:
    await browser.post(
        "/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )


@pytest.mark.asyncio
async def test_logout_clears_the_session_cookie(browser: AsyncClient):
    await _log_in(browser)
    response = await browser.post("/logout")
    assert response.status_code == 303
    assert not browser.cookies.get(COOKIE)


@pytest.mark.asyncio
async def test_logout_sticks_even_though_the_browser_still_holds_basic_credentials(
    browser: AsyncClient,
):
    """The entire point of the feature.

    A browser that has ever answered the native Basic prompt replays that
    credential on every request, forever. If page loads honoured it, logging
    off would clear the cookie and the very next request would log the
    person straight back in -- the bug this feature exists to fix.
    """
    await _log_in(browser)
    await browser.post("/logout")

    response = await browser.get(
        "/", headers={"Accept": "text/html", "Authorization": _basic_header()}
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


@pytest.mark.asyncio
async def test_page_navigation_without_a_session_redirects_rather_than_prompting(
    browser: AsyncClient,
):
    """No WWW-Authenticate, or the browser's own prompt hijacks the login page."""
    response = await browser.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    assert "WWW-Authenticate" not in response.headers


@pytest.mark.asyncio
async def test_api_request_without_a_session_still_gets_401_for_tools(browser: AsyncClient):
    """curl, /docs and the existing test suite must keep working unchanged."""
    response = await browser.get("/api/categories/")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.asyncio
async def test_login_page_is_reachable_without_credentials(browser: AsyncClient):
    response = await browser.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_failed_login_returns_to_the_form_without_prompting(browser: AsyncClient):
    """A 401 here would make the browser throw its own prompt over the page."""
    response = await browser.post(
        "/login", data={"username": settings.admin_username, "password": "wrong"}
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    assert "WWW-Authenticate" not in response.headers
    assert not browser.cookies.get(COOKIE)


@pytest.mark.asyncio
async def test_login_returns_the_browser_to_the_page_it_wanted(browser: AsyncClient):
    response = await browser.post(
        "/login?next=%2Fmanage",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert response.headers["location"] == "/manage"


@pytest.mark.parametrize(
    "hostile", ["https://evil.example/", "//evil.example/", r"/\evil.example"]
)
@pytest.mark.asyncio
async def test_login_refuses_to_bounce_the_browser_off_site(browser: AsyncClient, hostile: str):
    """An open redirect on a login form is a credential-phishing stepping stone."""
    response = await browser.post(
        f"/login?next={hostile}",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert response.headers["location"] == "/"


@pytest.mark.asyncio
async def test_session_cookie_is_httponly_and_samesite(browser: AsyncClient):
    """HttpOnly keeps the cookie away from any injected script on the page."""
    response = await browser.post(
        "/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


@pytest.mark.parametrize("path", ["/", "/manage", "/qr"])
@pytest.mark.asyncio
async def test_every_page_offers_a_way_to_log_off(client: AsyncClient, path: str):
    response = await client.get(path)
    assert '"/logout"' in response.text


@pytest.mark.parametrize("path", ["/", "/manage", "/qr"])
@pytest.mark.asyncio
async def test_every_page_shows_which_account_is_in_use(client: AsyncClient, path: str):
    """Sandbox and production look identical otherwise -- an easy, costly mixup."""
    response = await client.get(path)
    assert "/api/whoami" in response.text
