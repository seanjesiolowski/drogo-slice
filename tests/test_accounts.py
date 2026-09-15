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
