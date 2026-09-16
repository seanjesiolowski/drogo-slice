"""Unit tests for the signed session cookie value."""

import pytest

from app import session

SECRET = "test-secret-key"


def test_verify_returns_the_account_that_was_issued():
    token = session.issue("primary", secret=SECRET)
    assert session.verify(token, secret=SECRET) == "primary"


def test_verify_rejects_a_token_that_was_not_signed_with_the_secret():
    """Without this, anyone could hand-write a cookie naming any account."""
    assert session.verify("primary", secret=SECRET) is None


def test_verify_rejects_a_token_whose_account_was_tampered_with():
    token = session.issue("secondary", secret=SECRET)
    forged = token.replace("secondary", "primary", 1)
    assert session.verify(forged, secret=SECRET) is None


def test_verify_rejects_a_token_signed_with_a_different_secret():
    token = session.issue("primary", secret="some-other-secret")
    assert session.verify(token, secret=SECRET) is None


def test_verify_rejects_a_token_past_its_expiry():
    token = session.issue("primary", secret=SECRET, now=1_000_000.0, max_age=60)
    assert session.verify(token, secret=SECRET, now=1_000_061.0) is None


def test_verify_accepts_a_token_before_its_expiry():
    token = session.issue("primary", secret=SECRET, now=1_000_000.0, max_age=60)
    assert session.verify(token, secret=SECRET, now=1_000_059.0) == "primary"


def test_verify_rejects_a_token_whose_expiry_was_extended():
    """The expiry has to be inside the signature, not just alongside it."""
    token = session.issue("primary", secret=SECRET, now=1_000_000.0, max_age=60)
    forged = token.replace("1000060", "9999999999", 1)
    assert session.verify(forged, secret=SECRET, now=1_000_061.0) is None


@pytest.mark.parametrize("garbage", ["", ".", "no-separators", "a.b.c", "primary|notanumber.x"])
def test_verify_returns_none_for_garbage_rather_than_raising(garbage: str):
    """A hand-edited cookie reaches verify() on every request; it must never raise."""
    assert session.verify(garbage, secret=SECRET) is None


def test_current_secret_is_never_empty_when_unconfigured(monkeypatch):
    """An unset SESSION_SECRET must not mean signing with an empty key."""
    monkeypatch.setattr(session.settings, "session_secret", "", raising=False)
    assert len(session.current_secret()) >= 32


def test_current_secret_prefers_the_configured_value(monkeypatch):
    monkeypatch.setattr(session.settings, "session_secret", "from-the-environment", raising=False)
    assert session.current_secret() == "from-the-environment"
