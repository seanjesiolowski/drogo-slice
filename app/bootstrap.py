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
