"""Error tracking wiring. No-op unless SENTRY_DSN is configured."""


def init_sentry(settings) -> bool:
    """Initialize Sentry if a DSN is set. Returns True when enabled.

    Imported lazily so the app runs (and tests pass) without sentry-sdk
    installed when no DSN is configured.
    """
    if not settings.sentry_dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    return True
