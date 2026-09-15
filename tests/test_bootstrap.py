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
