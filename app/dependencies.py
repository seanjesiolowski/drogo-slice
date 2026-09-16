from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import sessionmaker_for_name


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield a session for the account that authenticated this request.

    Fails closed. A request with no account is a routing bug, and guessing
    the primary database here is how rootlet writes would reach production
    data, so this raises instead.
    """
    account = getattr(request.state, "account", None)
    if not account:
        raise RuntimeError(
            "No account on request; get_db will not guess which database to use"
        )

    async with sessionmaker_for_name(account)() as session:
        yield session
