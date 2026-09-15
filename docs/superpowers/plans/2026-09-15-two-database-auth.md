# Two Logins, Two Databases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second login to Drogo Slice that reads and writes its own Postgres database, served by the same app.

**Architecture:** Each account is a name, a credential pair, and a database URL. `BasicAuthMiddleware` decides which account a request belongs to and records it on `request.state`; `get_db` uses that to pick a sessionmaker. Isolation is physical — separate databases — so no query gains an owner filter and no router changes.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, asyncpg, Alembic, pytest + pytest-asyncio, Postgres 16 in production, SQLite for tests.

**Spec:** `docs/superpowers/specs/2026-09-15-two-database-auth-design.md`

## Global Constraints

- The second account is active only when **all three** of `SECONDARY_DATABASE_URL`, `SECONDARY_ADMIN_USERNAME`, `SECONDARY_ADMIN_PASSWORD` are non-empty. Partial configuration means the account does not exist.
- Empty-string credentials must never authenticate.
- `get_db` never falls back to the primary database. No account on the request means it raises.
- `/health` status code reflects the primary database only. The `secondary` field is informational and must never change the status code.
- A failure of the secondary database must never prevent the app from starting or fail a production deploy.
- Never log a database URL. Log host, port, and database name only — URLs carry the password.
- Account name constants are `PRIMARY = "primary"` and `SECONDARY = "secondary"`, defined once in `app/accounts.py`.

---

### Task 1: Account configuration

**Files:**
- Create: `app/accounts.py`
- Modify: `app/config.py:6-28`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Consumes: `settings` from `app/config.py`.
- Produces: `PRIMARY: str`, `SECONDARY: str`, `Account` (frozen dataclass with fields `name: str`, `username: str`, `password: str`, `database_url: str`), and `configured_accounts() -> list[Account]` returning primary first.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_accounts.py
import pytest

from app import accounts as accounts_module
from app.accounts import PRIMARY, SECONDARY, configured_accounts


@pytest.fixture
def settings(monkeypatch):
    """Patch the settings object that app.accounts reads."""
    s = accounts_module.settings
    monkeypatch.setattr(s, "admin_username", "admin", raising=False)
    monkeypatch.setattr(s, "admin_password", "primary-pass", raising=False)
    monkeypatch.setattr(s, "database_url", "sqlite+aiosqlite:///primary.db", raising=False)
    monkeypatch.setattr(s, "secondary_admin_username", "", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "", raising=False)
    monkeypatch.setattr(s, "secondary_database_url", "", raising=False)
    return s


def test_primary_only_when_secondary_unset(settings):
    result = configured_accounts()
    assert [a.name for a in result] == [PRIMARY]
    assert result[0].username == "admin"
    assert result[0].database_url == "sqlite+aiosqlite:///primary.db"


def test_both_accounts_when_secondary_fully_configured(settings, monkeypatch):
    monkeypatch.setattr(settings, "secondary_admin_username", "sandbox")
    monkeypatch.setattr(settings, "secondary_admin_password", "sandbox-pass")
    monkeypatch.setattr(settings, "secondary_database_url", "sqlite+aiosqlite:///second.db")

    result = configured_accounts()

    assert [a.name for a in result] == [PRIMARY, SECONDARY]
    assert result[1].username == "sandbox"
    assert result[1].database_url == "sqlite+aiosqlite:///second.db"


@pytest.mark.parametrize(
    "username,password,url",
    [
        ("sandbox", "sandbox-pass", ""),
        ("sandbox", "", "sqlite+aiosqlite:///second.db"),
        ("", "sandbox-pass", "sqlite+aiosqlite:///second.db"),
        ("sandbox", "", ""),
    ],
)
def test_partial_secondary_config_is_ignored(settings, monkeypatch, username, password, url):
    monkeypatch.setattr(settings, "secondary_admin_username", username)
    monkeypatch.setattr(settings, "secondary_admin_password", password)
    monkeypatch.setattr(settings, "secondary_database_url", url)

    assert [a.name for a in configured_accounts()] == [PRIMARY]


def test_secondary_url_gets_asyncpg_scheme():
    from app.config import Settings

    s = Settings(secondary_database_url="postgresql://user:pw@host:5432/db")
    assert s.secondary_database_url == "postgresql+asyncpg://user:pw@host:5432/db"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accounts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.accounts'`

- [ ] **Step 3: Write minimal implementation**

Add the three settings to `app/config.py`, inside the `Settings` class next to `admin_password`:

```python
    secondary_database_url: str = ""
    secondary_admin_username: str = ""
    secondary_admin_password: str = ""
```

Then widen the existing validator so it covers both URLs. Replace the
`@field_validator("database_url", mode="before")` decorator line with:

```python
    @field_validator("database_url", "secondary_database_url", mode="before")
```

Create `app/accounts.py`:

```python
"""Which logins exist, and which database each one uses."""

from dataclasses import dataclass

from app.config import settings

PRIMARY = "primary"
SECONDARY = "secondary"


@dataclass(frozen=True)
class Account:
    name: str
    username: str
    password: str
    database_url: str


def configured_accounts() -> list[Account]:
    """Every fully configured account, primary first.

    The secondary account exists only when its username, password and
    database URL are all set. Partial configuration is treated as absent so
    that blank credentials can never authenticate.
    """
    accounts = [
        Account(
            name=PRIMARY,
            username=settings.admin_username,
            password=settings.admin_password,
            database_url=settings.database_url,
        )
    ]

    if (
        settings.secondary_admin_username
        and settings.secondary_admin_password
        and settings.secondary_database_url
    ):
        accounts.append(
            Account(
                name=SECONDARY,
                username=settings.secondary_admin_username,
                password=settings.secondary_admin_password,
                database_url=settings.secondary_database_url,
            )
        )

    return accounts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accounts.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 78 passed (71 existing + 7 new)

- [ ] **Step 6: Commit**

```bash
git add app/accounts.py app/config.py tests/test_accounts.py
git commit -m "Add account configuration for a second login"
```

---

### Task 2: Sessionmaker registry

**Files:**
- Modify: `app/database.py:1-15`
- Test: `tests/test_database_registry.py`

**Interfaces:**
- Consumes: `Account`, `PRIMARY`, `configured_accounts` from Task 1.
- Produces: `sessionmaker_for_name(name: str) -> async_sessionmaker[AsyncSession]`, raising `KeyError` for an unconfigured name. Existing module attributes `engine`, `async_session` and `Base` keep their current meaning and stay bound to the primary database.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_database_registry.py
import pytest

from app import accounts as accounts_module
from app.accounts import PRIMARY, SECONDARY
from app.database import async_session, sessionmaker_for_name


@pytest.fixture
def secondary_configured(monkeypatch):
    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", "sqlite+aiosqlite:///./secondary_test.db", raising=False
    )


def test_primary_resolves_to_the_existing_sessionmaker():
    assert sessionmaker_for_name(PRIMARY) is async_session


def test_secondary_gets_its_own_sessionmaker(secondary_configured):
    from app.database import _sessionmakers

    maker = sessionmaker_for_name(SECONDARY)
    assert maker is not async_session
    assert _sessionmakers[SECONDARY] is maker
    assert _sessionmakers[PRIMARY] is async_session


def test_secondary_sessionmaker_is_cached(secondary_configured):
    assert sessionmaker_for_name(SECONDARY) is sessionmaker_for_name(SECONDARY)


def test_unconfigured_name_raises(monkeypatch):
    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "", raising=False)
    monkeypatch.setattr(s, "secondary_database_url", "", raising=False)

    with pytest.raises(KeyError):
        sessionmaker_for_name(SECONDARY)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'sessionmaker_for_name'`

- [ ] **Step 3: Write minimal implementation**

Append to `app/database.py`, after the existing `async_session` assignment and
leaving `engine`, `async_session` and `Base` exactly as they are:

```python
from app.accounts import PRIMARY, Account, configured_accounts

_sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {PRIMARY: async_session}


def _sessionmaker_for(account: Account) -> async_sessionmaker[AsyncSession]:
    """One engine per account, created on first use and cached.

    Creating an engine opens no connection, so an unreachable secondary
    database costs nothing here — it surfaces when a query runs.
    """
    if account.name not in _sessionmakers:
        account_engine = create_async_engine(
            account.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _sessionmakers[account.name] = async_sessionmaker(
            account_engine, expire_on_commit=False
        )
    return _sessionmakers[account.name]


def sessionmaker_for_name(name: str) -> async_sessionmaker[AsyncSession]:
    """Look up an account's sessionmaker by account name."""
    for account in configured_accounts():
        if account.name == name:
            return _sessionmaker_for(account)
    raise KeyError(f"No configured account named {name!r}")
```

Add `AsyncSession` to the existing import from `sqlalchemy.ext.asyncio` at the top
of the file, so the line reads:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database_registry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 82 passed

- [ ] **Step 6: Commit**

```bash
git add app/database.py tests/test_database_registry.py
git commit -m "Add per-account sessionmaker registry"
```

---

### Task 3: Route get_db by account, failing closed

**Files:**
- Modify: `app/dependencies.py:1-11`
- Test: `tests/test_get_db_routing.py`

**Interfaces:**
- Consumes: `sessionmaker_for_name` from Task 2.
- Produces: `get_db(request: Request) -> AsyncGenerator[AsyncSession]`. Reads `request.state.account`; raises `RuntimeError` when absent. The FastAPI dependency signature gains a `Request` parameter, which existing `dependency_overrides` in the test suite continue to bypass.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_get_db_routing.py
import pytest
from starlette.datastructures import State

from app.accounts import PRIMARY
from app.database import async_session
from app.dependencies import get_db


class _FakeRequest:
    def __init__(self, account=None):
        self.state = State()
        if account is not None:
            self.state.account = account


@pytest.mark.asyncio
async def test_raises_when_no_account_on_request():
    """get_db must never guess a database."""
    generator = get_db(_FakeRequest())
    with pytest.raises(RuntimeError, match="account"):
        await generator.__anext__()


@pytest.mark.asyncio
async def test_yields_session_from_the_named_account(monkeypatch):
    used = {}

    def fake_lookup(name):
        used["name"] = name
        return async_session

    monkeypatch.setattr("app.dependencies.sessionmaker_for_name", fake_lookup)

    generator = get_db(_FakeRequest(account=PRIMARY))
    session = await generator.__anext__()
    try:
        assert used["name"] == PRIMARY
        assert session is not None
    finally:
        await generator.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_get_db_routing.py -v`
Expected: FAIL with `TypeError: get_db() takes 0 positional arguments but 1 was given`

- [ ] **Step 3: Write minimal implementation**

Replace the whole of `app/dependencies.py`:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import sessionmaker_for_name


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield a session for the account that authenticated this request.

    Fails closed. A request with no account is a routing bug, and guessing
    the primary database here is how sandbox writes would reach production
    data, so this raises instead.
    """
    account = getattr(request.state, "account", None)
    if account is None:
        raise RuntimeError(
            "No account on request; get_db will not guess which database to use"
        )

    async with sessionmaker_for_name(account)() as session:
        yield session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_get_db_routing.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 84 passed. The existing suite overrides `get_db` wholesale in
`tests/conftest.py:29`, so the new signature does not affect it.

- [ ] **Step 6: Commit**

```bash
git add app/dependencies.py tests/test_get_db_routing.py
git commit -m "Route get_db by authenticated account, failing closed"
```

---

### Task 4: Middleware resolves the account

**Files:**
- Modify: `app/main.py:45-79`
- Test: `tests/test_auth.py` (append)

**Interfaces:**
- Consumes: `configured_accounts`, `Account` from Task 1.
- Produces: `request.state.account` set to the matching account's name for every authenticated request. Unauthenticated and unmatched requests keep today's 401 with `WWW-Authenticate: Basic realm="Drogo Slice"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_auth.py`:

```python
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
async def test_empty_credentials_rejected(unauthenticated_client: AsyncClient):
    """Blank username and password must never authenticate."""
    import base64

    blank = base64.b64encode(b":").decode()
    response = await unauthenticated_client.get(
        "/api/categories/", headers={"Authorization": f"Basic {blank}"}
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL — `test_secondary_credentials_authenticate` returns 401, because the
middleware only knows one credential pair.

- [ ] **Step 3: Write minimal implementation**

In `app/main.py`, add to the imports:

```python
from app.accounts import PRIMARY, SECONDARY, configured_accounts
```

Then replace the `valid = ...` block and its `if not valid:` guard (currently
`app/main.py:70-78`) with:

```python
        matched = None
        for account in configured_accounts():
            if secrets.compare_digest(username, account.username) and secrets.compare_digest(
                password, account.password
            ):
                matched = account
                break

        if matched is None:
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Drogo Slice"'},
            )

        request.state.account = matched.name
        return await call_next(request)
```

Delete the trailing `return await call_next(request)` that previously followed the
`valid` check, so the method ends with the block above.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS (all, including the 9 pre-existing auth tests)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 89 passed

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_auth.py
git commit -m "Resolve the authenticated account in auth middleware"
```

---

### Task 5: Prove the two databases are isolated

This is the task the whole design exists for. It uses two real SQLite files rather
than dependency overrides, so routing is genuinely exercised end to end.

**Files:**
- Test: `tests/test_database_isolation.py`

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: no production code. A regression guard for the isolation property.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database_isolation.py -v`
Expected: FAIL. Before Tasks 1-4 are all in place these error out; if run after
them, they are the first tests to exercise real routing and must pass.

- [ ] **Step 3: No implementation needed**

These tests describe behaviour Tasks 1-4 already deliver. If any fail, the bug is in
Tasks 1-4 — fix it there rather than weakening these assertions. This is the
property the whole feature exists to provide.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database_isolation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 92 passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_database_isolation.py
git commit -m "Add end-to-end test proving the two databases are isolated"
```

---

### Task 6: Pin /health to the primary database

**Files:**
- Modify: `app/main.py:88-99`
- Modify: `tests/test_health.py:1-33`
- Modify: `docs/superpowers/specs/2026-09-15-two-database-auth-design.md:134-135`

**Interfaces:**
- Consumes: `sessionmaker_for_name`, `async_session`, `SECONDARY`, `configured_accounts`.
- Produces: `/health` returning `{"status", "database", "secondary"}` where `secondary` is one of `"ok"`, `"error"`, `"not_configured"`. The status code depends on the primary database alone.

- [ ] **Step 1: Write the failing test**

Replace the contents of `tests/test_health.py`:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app import accounts as accounts_module
from app.main import app


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL — `test_secondary_reported_as_not_configured` raises `KeyError:
'secondary'`, and `test_health_check_db_down` fails because `/health` still routes
through the overridden `get_db`.

- [ ] **Step 3: Write minimal implementation**

In `app/main.py`, add to the imports:

```python
from app.database import Base, async_session, engine, sessionmaker_for_name
```

(replacing the existing `from app.database import Base, engine` line).

Replace the `health_check` handler with:

```python
async def _secondary_status() -> str:
    """Report the secondary database without ever affecting /health's status code."""
    if not any(account.name == SECONDARY for account in configured_accounts()):
        return "not_configured"
    try:
        async with sessionmaker_for_name(SECONDARY)() as db:
            await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


@app.get("/health")
async def health_check():
    # Pinned to the primary database. /health bypasses auth, so no account is
    # on the request and routed get_db would correctly refuse. It is also
    # Railway's deploy healthcheck, so a broken secondary must never fail it.
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "error"},
        )

    return {"status": "healthy", "database": "ok", "secondary": await _secondary_status()}
```

Remove the now-unused `db: AsyncSession = Depends(get_db)` parameter from
`health_check`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Correct the spec**

The spec says the existing tests pass untouched. Two health tests had to change.
In `docs/superpowers/specs/2026-09-15-two-database-auth-design.md`, replace:

```
The 71 existing tests pass untouched: `tests/conftest.py` overrides `get_db`
wholesale, bypassing routing.
```

with:

```
The 71 existing tests pass untouched except for `tests/test_health.py`, which must
change: one test asserts the exact `/health` body, and the other simulates failure
by overriding `get_db`, which `/health` no longer uses. Everything else is
unaffected because `tests/conftest.py` overrides `get_db` wholesale.
```

- [ ] **Step 6: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 94 passed

- [ ] **Step 7: Commit**

```bash
git add app/main.py tests/test_health.py docs/superpowers/specs/2026-09-15-two-database-auth-design.md
git commit -m "Pin /health to the primary database"
```

---

### Task 7: Return 503 when an account's database is unreachable

**Files:**
- Modify: `app/main.py` (add an exception handler after `app.add_middleware`)
- Test: `tests/test_database_unavailable.py`

**Interfaces:**
- Consumes: `request.state.account` from Task 4.
- Produces: a handler for `sqlalchemy.exc.OperationalError` returning 503 with body `{"detail": "Database for account '<name>' is unavailable"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_database_unavailable.py
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import accounts as accounts_module
from app.dependencies import get_db
from app.main import app


@pytest_asyncio.fixture
async def unreachable_secondary_client(monkeypatch):
    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s,
        "secondary_database_url",
        "postgresql+asyncpg://user:pw@nonexistent-host-xyz:5432/db",
        raising=False,
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
async def test_unreachable_database_returns_503_not_500(
    unreachable_secondary_client: AsyncClient,
):
    response = await unreachable_secondary_client.get("/api/categories/")
    assert response.status_code == 503
    assert "sandbox" in response.text or "secondary" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database_unavailable.py -v`
Expected: FAIL — the connection error propagates as an unhandled 500, or the test
client raises.

- [ ] **Step 3: Write minimal implementation**

In `app/main.py`, add the import:

```python
from sqlalchemy.exc import OperationalError
```

and, immediately after `app.add_middleware(BasicAuthMiddleware)`:

```python
@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    """A database that cannot be reached is a 503, not an opaque 500."""
    account = getattr(request.state, "account", "unknown")
    return JSONResponse(
        status_code=503,
        content={"detail": f"Database for account '{account}' is unavailable"},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database_unavailable.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 95 passed

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_database_unavailable.py
git commit -m "Return 503 when an account's database is unreachable"
```

---

### Task 8: Block digest sending under the second login

**Files:**
- Modify: `app/routers/digest.py:22-25`
- Test: `tests/test_digest.py` (append)

**Interfaces:**
- Consumes: `request.state.account`, `PRIMARY`.
- Produces: `POST /admin/digest/send` returns 403 for any account other than primary. `GET /admin/digest/preview` is unchanged and works for both.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_digest.py`:

```python
@pytest_asyncio.fixture
async def sandbox_digest_client(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app import accounts as accounts_module
    from app.main import app

    s = accounts_module.settings
    monkeypatch.setattr(s, "secondary_admin_username", "sandbox", raising=False)
    monkeypatch.setattr(s, "secondary_admin_password", "sandbox-pass", raising=False)
    monkeypatch.setattr(
        s, "secondary_database_url", "sqlite+aiosqlite:///./secondary_digest.db", raising=False
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        auth=("sandbox", "sandbox-pass"),
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_send_blocked_for_secondary_account(sandbox_digest_client):
    """Brevo credentials are shared; test data must not email real recipients."""
    response = await sandbox_digest_client.post("/admin/digest/send")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_preview_allowed_for_secondary_account(sandbox_digest_client):
    response = await sandbox_digest_client.get("/admin/digest/preview")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL — `test_send_blocked_for_secondary_account` gets 400 (missing Brevo
config), not 403.

- [ ] **Step 3: Write minimal implementation**

In `app/routers/digest.py`, add imports:

```python
from starlette.requests import Request

from app.accounts import PRIMARY
```

Change the `send_digest` signature and add the guard as its first statement:

```python
@router.post("/send")
async def send_digest(request: Request, db: AsyncSession = Depends(get_db)):
    """Render and actually send the digest via Brevo to DIGEST_TO_EMAILS."""
    if getattr(request.state, "account", None) != PRIMARY:
        raise HTTPException(
            status_code=403,
            detail="Digest sending is available only to the primary account",
        )
```

Leave the rest of the handler body unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_digest.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 97 passed

- [ ] **Step 6: Commit**

```bash
git add app/routers/digest.py tests/test_digest.py
git commit -m "Block digest sending under the secondary account"
```

---

### Task 9: Migrate every configured database at boot

Replaces the inline Python in `start.sh` with a testable module. This supersedes the
uncommitted diagnostics currently in the working tree — fold them in here rather
than committing them separately.

**Files:**
- Create: `app/bootstrap.py`
- Modify: `start.sh:1-45` (replace entirely)
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `configured_accounts`, `PRIMARY`, `Account`.
- Produces: `decide(tables: set[str]) -> str` returning `"stamp"` or `"migrate"`; `migrate(account: Account) -> None`; `main() -> int` returning 0 on success and 1 when the **primary** database fails.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bootstrap.py
import pytest

from app.accounts import PRIMARY, SECONDARY, Account
from app.bootstrap import decide, main


def test_fresh_database_migrates_from_scratch():
    """An empty database must run the full history, never be stamped."""
    assert decide(set()) == "migrate"


def test_pre_alembic_database_is_stamped():
    assert decide({"categories", "items"}) == "stamp"


def test_database_with_history_just_migrates():
    assert decide({"alembic_version", "categories", "items"}) == "migrate"


def _account(name):
    return Account(name=name, username="u", password="p", database_url="sqlite+aiosqlite:///x.db")


def test_secondary_failure_is_not_fatal(monkeypatch):
    attempted = []

    def fake_migrate(account):
        attempted.append(account.name)
        if account.name == SECONDARY:
            raise RuntimeError("unreachable")

    monkeypatch.setattr("app.bootstrap.configured_accounts", lambda: [_account(PRIMARY), _account(SECONDARY)])
    monkeypatch.setattr("app.bootstrap.migrate", fake_migrate)

    assert main() == 0
    assert attempted == [PRIMARY, SECONDARY]


def test_primary_failure_is_fatal(monkeypatch):
    def fake_migrate(account):
        raise RuntimeError("unreachable")

    monkeypatch.setattr("app.bootstrap.configured_accounts", lambda: [_account(PRIMARY)])
    monkeypatch.setattr("app.bootstrap.migrate", fake_migrate)

    assert main() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.bootstrap'`

- [ ] **Step 3: Write minimal implementation**

Create `app/bootstrap.py`:

```python
"""Bring every configured database's schema up to date before the app serves.

Run by start.sh. A fresh, empty database must never be stamped: stamping skips
the table creation in 001_initial, and 002_drop_display_order then fails with
'relation "categories" does not exist'.
"""

import asyncio
import os
import subprocess
import sys

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.accounts import PRIMARY, Account, configured_accounts


def decide(tables: set[str]) -> str:
    """Choose between stamping an existing pre-alembic database and migrating."""
    if "alembic_version" in tables:
        return "migrate"
    if "categories" in tables:
        return "stamp"
    return "migrate"


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def _alembic(args: list[str], database_url: str) -> None:
    subprocess.run(
        ["alembic", *args],
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
    )


def migrate(account: Account) -> None:
    """Bring one account's database to head."""
    url = make_url(account.database_url)
    # Never log the URL itself -- it carries the password.
    print(
        f"[bootstrap] {account.name}: host={url.host} port={url.port} name={url.database}",
        file=sys.stderr,
    )
    if url.host == "db":
        print(
            "[bootstrap] WARNING: host 'db' is the docker-compose default and does "
            "not resolve outside docker compose. The database URL is probably unset.",
            file=sys.stderr,
        )

    if decide(asyncio.run(_table_names(account.database_url))) == "stamp":
        print(f"[bootstrap] {account.name}: pre-alembic database, stamping 001_initial", file=sys.stderr)
        _alembic(["stamp", "001_initial"], account.database_url)

    _alembic(["upgrade", "head"], account.database_url)


def main() -> int:
    for account in configured_accounts():
        try:
            migrate(account)
        except Exception as exc:
            if account.name == PRIMARY:
                print(f"[bootstrap] primary database failed: {exc}", file=sys.stderr)
                return 1
            print(f"[bootstrap] {account.name} failed, continuing without it: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Replace `start.sh` entirely:

```sh
#!/bin/sh
set -e

# Migrate every configured database. Primary failure is fatal; a failing
# secondary is logged and skipped so it can never take production down.
python -m app.bootstrap

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Verify against real Postgres**

The unit tests cover the decision logic, not the migrations. Confirm the real
behaviour before trusting it in a deploy:

```bash
docker run -d --name bootstrap-check -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=fresh -p 55440:5432 postgres:16-alpine
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:55440/fresh" python -m app.bootstrap
docker rm -f bootstrap-check
```

Expected: `001_initial` through `006_drop_storage_classes` all run, exit code 0.

- [ ] **Step 6: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 102 passed

- [ ] **Step 7: Commit**

```bash
git add app/bootstrap.py start.sh tests/test_bootstrap.py
git commit -m "Migrate every configured database at boot"
```

---

### Task 10: Document the second login

**Files:**
- Modify: `.env.example:1-4`
- Modify: `README.md` (rewrite the "Sandbox environment" section)

**Interfaces:**
- Consumes: the settings names from Task 1.
- Produces: no code.

- [ ] **Step 1: Add the new settings to `.env.example`**

After the existing `ADMIN_PASSWORD` line:

```
# Optional second login with its own database. All three must be set for it to
# exist; leave blank to disable. Never point this at the production database.
SECONDARY_DATABASE_URL=
SECONDARY_ADMIN_USERNAME=
SECONDARY_ADMIN_PASSWORD=
```

- [ ] **Step 2: Rewrite the README's "Sandbox environment" section**

The current section describes a second Railway *app service*, which this design
replaces. Rewrite it to describe one app service with two databases, covering:

- What the second login is: its own Postgres database in the same project, so
  nothing it does can reach the production inventory.
- Adding a second Postgres to the existing project and referencing it from the app
  service as `SECONDARY_DATABASE_URL`, using Railway's
  `${{ServiceName.DATABASE_URL}}` reference form.
- Setting `SECONDARY_ADMIN_USERNAME` and `SECONDARY_ADMIN_PASSWORD`; all three must
  be set or the second login does not exist.
- That the second database is migrated automatically at boot, and that a failure
  there is logged and skipped rather than taking the app down.
- That `/health` reports `secondary` as `ok`, `error`, or `not_configured`, and that
  this never affects the status code.
- That the digest can be previewed but not sent under the second login.
- That `POST /api/reset?confirm=RESET` under the second login wipes only that
  database.
- That a missing `DATABASE_URL` falls back to the docker-compose default `db:5432`
  and fails with `socket.gaierror: Name or service not known` — keep this
  troubleshooting note from the current section.

- [ ] **Step 3: Verify the docs match the code**

Run: `grep -n "SECONDARY_" .env.example README.md app/config.py`
Expected: the same three names in all three files, spelled identically.

- [ ] **Step 4: Run the full suite one last time**

Run: `python -m pytest -q`
Expected: 102 passed

- [ ] **Step 5: Commit**

```bash
git add .env.example README.md
git commit -m "Document the second login and its database"
```

---

## Done when

- `python -m pytest -q` passes with 102 tests.
- `tests/test_database_isolation.py` passes — the property the feature exists for.
- `/health` returns 200 with `"secondary": "error"` when the secondary is unreachable.
- A fresh Postgres database migrates cleanly via `python -m app.bootstrap`.
- `.env.example`, `README.md` and `app/config.py` agree on the setting names.
