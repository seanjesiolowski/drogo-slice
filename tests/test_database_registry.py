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
