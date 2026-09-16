"""Which logins exist, and which database each one uses."""

import sys
from dataclasses import dataclass, field

from app.config import settings

PRIMARY = "primary"
SECONDARY = "secondary"


@dataclass(frozen=True)
class Account:
    name: str
    username: str
    password: str = field(repr=False)
    database_url: str = field(repr=False)


def configured_accounts() -> list[Account]:
    """Every fully configured account, primary first.

    The secondary account exists only when its username, password and
    database URL are all set. Partial configuration is treated as absent so
    that blank credentials can never authenticate. The secondary is also
    treated as absent if its database URL is identical to the primary's --
    a copy-paste of that URL would otherwise give the rootlet login full
    read/write access to the live production database.
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
        if settings.secondary_database_url == settings.database_url:
            print(
                "[accounts] WARNING: secondary database URL is identical to the "
                "primary's; refusing to configure the secondary account so a "
                "misconfigured rootlet login cannot reach production data.",
                file=sys.stderr,
            )
        else:
            accounts.append(
                Account(
                    name=SECONDARY,
                    username=settings.secondary_admin_username,
                    password=settings.secondary_admin_password,
                    database_url=settings.secondary_database_url,
                )
            )

    return accounts
