# Two logins, two databases — design

**Date:** 2026-09-15
**Status:** Approved, not yet implemented

## Goal

Add a second login to Drogo Slice whose data is completely separate from the
production inventory at Saint Drogo's. The second login is a sandbox: somewhere to
experiment without risk to real data.

Both logins are served by one deployed app. Isolation is physical — each account
gets its own Postgres database in the same Railway project — so no query needs an
owner filter and no existing row changes.

## Non-goals

- Roles or permissions. Both accounts are full admins of their own database.
- More than two accounts. The design does not preclude it, but nothing here is
  built for a third.
- Row-level multi-tenancy. Explicitly rejected: it would require an owner column on
  every table, a backfill migration against live production data, and a filter on
  all ~15 queries, where one missed `WHERE` leaks between accounts.
- Moving or copying data between the two databases. There is no import endpoint;
  the sandbox is populated by hand.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Second database unreachable at startup | App starts anyway; second login disabled | A misconfigured sandbox must never take down the shop's tool |
| Migrating the second database | `start.sh` migrates every configured database | Schemas cannot silently drift after a deploy |
| Digest under the second login | Preview allowed, send blocked | Brevo credentials are shared; test data must not email real recipients |
| Request routing | Account resolved in middleware, database chosen in `get_db` | All 16 handlers already depend on `get_db`; no router or query changes |
| `/health` | Primary only; secondary reported but never affects status | `/health` is Railway's deploy healthcheck — see Failure modes |
| Setting names | `SECONDARY_*` | Neutral if the second database stops being a sandbox |

## Design

### 1. Configuration

`app/config.py` gains three settings, all defaulting to empty:

- `SECONDARY_DATABASE_URL`
- `SECONDARY_ADMIN_USERNAME`
- `SECONDARY_ADMIN_PASSWORD`

The second account is active only when **all three** are non-empty. Partial
configuration means the account does not exist, and its credentials receive a 401.
This also preserves the existing guard: empty-string credentials must never
authenticate.

The `fix_async_scheme` validator must apply to `SECONDARY_DATABASE_URL` as well as
`DATABASE_URL`. Railway injects `postgresql://`; asyncpg requires
`postgresql+asyncpg://`.

Accounts are assembled into an ordered list of records, each holding a name, a
username, a password, and a database URL.

### 2. Engine registry

`app/database.py` keeps `engine` and `async_session` bound to the primary database,
unchanged, so `app/digest/runner.py` continues to work as written.

It adds a mapping of account name to `async_sessionmaker`, built at startup, with an
entry per configured database. Creating an engine opens no connection, so an
unreachable secondary costs nothing at boot — this is what makes "start anyway" fall
out of the design rather than requiring special handling.

### 3. Authentication and routing

`BasicAuthMiddleware` compares the supplied credentials against each configured
account using `secrets.compare_digest` on both username and password, and records
the matching account name on `request.state`. Unmatched credentials return 401 with
the existing `WWW-Authenticate` header, exactly as today.

`get_db` reads the account from the request and yields a session from that account's
sessionmaker.

**`get_db` must fail closed.** If no account is present on the request, it raises
`RuntimeError` rather than falling back to the primary database, surfacing as a 500.
A silent default is the single bug that would write sandbox data into the production
inventory, and it must be impossible by construction rather than by care. The 500 is
deliberate: an unroutable request is a programming error, not a user error.

Of the 16 handlers that currently depend on `get_db`, 15 keep it unchanged. Only
`/health` moves off it, for the reason in section 4.

A configured-but-unreachable secondary database must surface as **503**, not a 500
traceback. SQLAlchemy raises `OperationalError` when the connection cannot be
established, so this requires an explicit exception handler mapping connection
failures to 503 with a message naming the account. Without that handler the
behaviour is an unhandled 500, which is a worse experience and hides the cause.

### 4. `/health`

`railway.json` sets `healthcheckPath` to `/health`. If `/health` reported unhealthy
because the secondary database was broken, Railway would fail the production deploy
— reintroducing, by the back door, the exact failure this design rules out.

Therefore `/health` checks the primary database only, and is pinned to it directly
rather than using routed `get_db` (it bypasses auth, so no account is present and
`get_db` would correctly refuse).

It additionally reports the secondary as `"ok"`, `"error"`, or `"not_configured"`.
This field is informational and **must never** influence the HTTP status code.

### 5. Migrations

`start.sh` iterates over each configured database and runs the existing
bootstrap-and-upgrade logic against each, passing `DATABASE_URL` per alembic
invocation. `alembic/env.py` reads the URL from settings, so this requires no
alembic configuration changes.

- Primary database failure: fatal, as today.
- Secondary database failure: logged and skipped. The app still boots.

A fresh secondary database is empty, so it takes the `migrate` path and the full
`001`–`006` history runs against it. This depends on the fresh-database fix in
commit `cf98a13`; before that fix an empty database crash-looped.

### 6. Digest, backup and reset

- `/admin/digest/preview` follows the login and renders the current account's data.
- `/admin/digest/send` returns 403 under the second account.
- The scheduled CLI runner (`app/digest/runner.py`) stays bound to the primary and
  is unchanged.
- `/api/backup` and `/api/reset` need no special handling. They already depend on
  `get_db`, so each login backs up and resets only its own database. The existing
  `?confirm=RESET` guard is unaffected.

### 7. Testing

The 71 existing tests pass untouched: `tests/conftest.py` overrides `get_db`
wholesale, bypassing routing.

New tests override the sessionmaker registry rather than `get_db`, so routing is
genuinely exercised:

1. Data written under account A is invisible under account B — the core isolation
   property.
2. `get_db` fails closed when no account is present on the request.
3. Secondary credentials are rejected when the secondary is not configured.
4. Secondary credentials are rejected when only some of the three settings are set.
5. `/health` returns 200 when the secondary database is unreachable.
6. `/admin/digest/send` is blocked under the second login; preview is allowed.
7. The primary login continues to reach the primary database — no regression.

### 8. Deployment

Add a second Postgres to the existing Railway project and set the three
`SECONDARY_*` variables on the same app service. `SECONDARY_DATABASE_URL` is a
reference to the new Postgres service, which Railway writes in its
`${{ServiceName.DATABASE_URL}}` reference form using that service's actual name.

One app service, two databases.

The README's sandbox section currently describes a separate second app service and
must be rewritten for this shape.

## Failure modes

| Condition | Result |
|---|---|
| Secondary settings blank | Second login 401s. App normal. |
| Secondary partially configured | Second login 401s. App normal. |
| Secondary URL set, database unreachable | Second login 503s. Primary login and `/health` unaffected. |
| Secondary migration fails at boot | Logged, skipped, app boots. |
| Primary database unreachable | `/health` 503, as today. |
| No account on a request reaching `get_db` | Raises. Never falls back to primary. |

## Risks

- **Routing bug sends writes to the wrong database.** The severest failure.
  Mitigated by fail-closed `get_db` and by isolation test 1, which must exist before
  the routing code is considered done.
- **`/health` coupling.** Covered by test 5; without it a later change could
  reintroduce the deploy-failure path described in section 4.
- **Two connection pools.** Doubles idle connections. Immaterial at this scale, but
  worth knowing if a third database is ever added.
