import pytest

from app import accounts as accounts_module
from app.accounts import PRIMARY, SECONDARY, Account, configured_accounts


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


def test_repr_never_contains_password_or_database_url():
    """An unhandled exception can put an Account in a Sentry frame-locals dump.

    Sentry's include_local_variables captures repr() of frame locals, so the
    dataclass repr must never expose the login password or the database URL
    (which itself embeds the database's own password).
    """
    account = Account(
        name=PRIMARY,
        username="admin",
        password="sw0rdfish-login-secret",
        database_url="postgresql+asyncpg://admin:sw0rdfish-db-secret@localhost:5432/shop",
    )

    rendered = repr(account)

    assert "sw0rdfish-login-secret" not in rendered
    assert "sw0rdfish-db-secret" not in rendered
    assert "postgresql" not in rendered


def test_repr_still_shows_non_secret_fields():
    account = Account(
        name=PRIMARY,
        username="admin",
        password="secret",
        database_url="sqlite+aiosqlite:///x.db",
    )

    rendered = repr(account)

    assert "primary" in rendered
    assert "admin" in rendered


def test_configured_accounts_refuses_secondary_matching_primary_url(settings, monkeypatch, capsys):
    """A copy-pasted secondary URL identical to the primary must not grant
    the sandbox login write access to the live production database."""
    shared_url = "postgresql+asyncpg://admin:pw@prod-host:5432/shop"
    monkeypatch.setattr(settings, "database_url", shared_url)
    monkeypatch.setattr(settings, "secondary_admin_username", "sandbox")
    monkeypatch.setattr(settings, "secondary_admin_password", "sandbox-pass")
    monkeypatch.setattr(settings, "secondary_database_url", shared_url)

    result = configured_accounts()

    assert [a.name for a in result] == [PRIMARY]

    err = capsys.readouterr().err
    assert "same" in err.lower() or "match" in err.lower() or "identical" in err.lower()
    assert shared_url not in err
    assert "prod-host" not in err
    assert "pw" not in err
