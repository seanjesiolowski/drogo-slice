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
        # Sentry's default (True) captures repr() of every frame local on an
        # unhandled exception. BasicAuthMiddleware.dispatch binds `account`
        # and raw `username`/`password` locals in the same frame that
        # call_next re-raises through, so leaving this on ships credentials
        # (including the database URL's password) to Sentry on any 500.
        include_local_variables=False,
    )
    return True
