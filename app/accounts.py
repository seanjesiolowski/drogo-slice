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
