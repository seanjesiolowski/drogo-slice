import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_init_sentry_skips_without_dsn():
    from app.observability import init_sentry

    settings = SimpleNamespace(
        sentry_dsn="",
        sentry_environment="production",
        sentry_traces_sample_rate=0.0,
    )
    assert init_sentry(settings) is False


def test_init_sentry_initializes_with_dsn(monkeypatch):
    fake_sentry = types.ModuleType("sentry_sdk")
    fake_sentry.init = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

    from app.observability import init_sentry

    settings = SimpleNamespace(
        sentry_dsn="https://abc123@o0.ingest.sentry.io/1",
        sentry_environment="production",
        sentry_traces_sample_rate=0.1,
    )
    assert init_sentry(settings) is True

    fake_sentry.init.assert_called_once()
    kwargs = fake_sentry.init.call_args.kwargs
    assert kwargs["dsn"] == "https://abc123@o0.ingest.sentry.io/1"
    assert kwargs["environment"] == "production"
    assert kwargs["traces_sample_rate"] == 0.1
    assert kwargs["send_default_pii"] is False
