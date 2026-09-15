import pytest
from starlette.datastructures import State

from app.accounts import PRIMARY
from app.database import async_session
from app.dependencies import get_db


class _FakeRequest:
    def __init__(self, account=None):
        self.state = State()
        if account is not None:
            self.state.account = account


@pytest.mark.asyncio
async def test_raises_when_no_account_on_request():
    """get_db must never guess a database."""
    generator = get_db(_FakeRequest())
    with pytest.raises(RuntimeError, match="account"):
        await generator.__anext__()


@pytest.mark.asyncio
async def test_yields_session_from_the_named_account(monkeypatch):
    used = {}

    def fake_lookup(name):
        used["name"] = name
        return async_session

    monkeypatch.setattr("app.dependencies.sessionmaker_for_name", fake_lookup)

    generator = get_db(_FakeRequest(account=PRIMARY))
    session = await generator.__anext__()
    try:
        assert used["name"] == PRIMARY
        assert session is not None
    finally:
        await generator.aclose()
