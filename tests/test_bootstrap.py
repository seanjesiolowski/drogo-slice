from app.accounts import PRIMARY, SECONDARY, Account
from app.bootstrap import decide, main, migrate


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


def test_primary_failure_is_fatal_even_with_secondary_configured(monkeypatch):
    """The early return on primary failure must skip the secondary entirely."""
    attempted = []

    def fake_migrate(account):
        attempted.append(account.name)
        raise RuntimeError("unreachable")

    monkeypatch.setattr("app.bootstrap.configured_accounts", lambda: [_account(PRIMARY), _account(SECONDARY)])
    monkeypatch.setattr("app.bootstrap.migrate", fake_migrate)

    assert main() == 1
    assert attempted == [PRIMARY]


def test_migrate_never_logs_the_url_or_password(monkeypatch, capsys):
    async def fake_table_names(database_url):
        return {"alembic_version", "categories", "items"}

    monkeypatch.setattr("app.bootstrap._table_names", fake_table_names)
    monkeypatch.setattr("app.bootstrap._alembic", lambda args, database_url: None)

    account = Account(
        name=PRIMARY,
        username="u",
        password="p",
        database_url="postgresql+asyncpg://admin:sw0rdfish123@localhost:5432/shop",
    )

    migrate(account)

    err = capsys.readouterr().err
    assert "host=localhost" in err
    assert "port=5432" in err
    assert "name=shop" in err
    assert "://" not in err
    assert "sw0rdfish123" not in err


def test_migrate_warns_on_docker_compose_default_host(monkeypatch, capsys):
    async def fake_table_names(database_url):
        return {"alembic_version"}

    monkeypatch.setattr("app.bootstrap._table_names", fake_table_names)
    monkeypatch.setattr("app.bootstrap._alembic", lambda args, database_url: None)

    account = Account(
        name=PRIMARY,
        username="u",
        password="p",
        database_url="postgresql+asyncpg://admin:sw0rdfish123@db:5432/shop",
    )

    migrate(account)

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "docker-compose default" in err
    assert "sw0rdfish123" not in err
