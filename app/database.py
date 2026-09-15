from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.accounts import PRIMARY, Account, configured_accounts

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

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


class Base(DeclarativeBase):
    pass
