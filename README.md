# Drogo Slice

Coffee shop inventory tracker built with FastAPI and PostgreSQL

***Currently in production ( internal tooling ) at [Saint Drogo's](https://saintdrogoscoffee.com) in Lowville, NY***

![alt text](image.png)


## Running locally (Docker installed and running)

```bash
docker compose up --build
```

App runs at `http://localhost:8000`. API docs at `/docs`.

## Development workflow

The Docker setup supports **hot-reloading** — edit code in VS Code and changes appear automatically without rebuilding.

1. Start the stack once: `docker compose up --build`
2. Edit code in VS Code — files sync into the container via a volume mount
3. Uvicorn detects changes and auto-restarts the API
4. Only rebuild (`docker compose up --build`) when you change `requirements.txt`

For subsequent sessions, just run `docker compose up` (no `--build` needed).

## Testing

```bash
docker compose exec api pytest
```

## Sandbox environment

The sandbox is a second login on this same app, backed by its own Postgres database.
There is one app service, not two — the second login just points at a different
database, so nothing done under it can reach the production inventory at Saint
Drogo's. Isolation is physical (separate databases), not a permissions check.

The second login only exists when all three of `SECONDARY_DATABASE_URL`,
`SECONDARY_ADMIN_USERNAME` and `SECONDARY_ADMIN_PASSWORD` are set. If any one of
them is blank, the account doesn't exist and its credentials get a 401 like any
other wrong login.

For day-to-day development, the local `docker compose up` stack above already gives
you an isolated database to experiment in. Set up the sandbox login on Railway only
when you need one reachable from outside your machine, such as on a phone.

### Setting it up on Railway

1. In the same Railway project as the app, add a second Postgres database (in the
   Railway dashboard, roughly "New" → "Database" → "Add PostgreSQL" — the exact
   wording may differ depending on Railway's current UI). This creates it as its
   own service, separate from the app service and from the production Postgres.
2. Railway does **not** wire a new database into your app automatically — adding a
   Postgres only creates the service, and you still need to reference it. On the app
   service, add an environment variable `SECONDARY_DATABASE_URL` and set its value to
   a reference of the new Postgres's `DATABASE_URL`, e.g.
   `${{Postgres-2.DATABASE_URL}}`, substituting whatever Railway actually named that
   service (check the reference variable it offers you when adding it — the exact
   name matters).
3. Set `SECONDARY_ADMIN_USERNAME` and `SECONDARY_ADMIN_PASSWORD` on the app service
   to your choice of sandbox credentials. All three variables must be present for the
   second login to exist.
4. Deploy. `start.sh` migrates every configured database at boot, including the
   secondary one, so there is nothing to initialise by hand. If the secondary
   migration fails, it's logged and skipped — the app still starts and serves the
   primary login normally; only the primary database failing is fatal.

| Variable | Value | Why |
|---|---|---|
| `SECONDARY_DATABASE_URL` | reference to the second Postgres | Must point at the sandbox database, never the production one. All three `SECONDARY_*` variables must be set or the login doesn't exist. |
| `SECONDARY_ADMIN_USERNAME` | your choice | A separate login, so sandbox credentials are not production credentials. |
| `SECONDARY_ADMIN_PASSWORD` | your choice | Same. |

Brevo and Sentry settings are shared with the primary login — there's no separate
configuration for them. That's also why `/admin/digest/send` is blocked entirely
under the sandbox login (see below).

The sandbox database comes up empty, ready to experiment in.

### Working in the sandbox

Add a few categories and items by hand through the UI to get started. There is no
import endpoint — `/api/backup` under the sandbox login exports only the sandbox
database (empty at first), so sandbox data is entered manually.

`POST /api/reset?confirm=RESET` under the sandbox login wipes only the sandbox
database's items and categories and restarts IDs at 1. It never touches production
data, because it operates on whichever database the logged-in account owns.

`/admin/digest/preview` works under the sandbox login — it just renders HTML from
whatever's in the sandbox database. `/admin/digest/send` returns 403 under the
sandbox login: the Brevo credentials are shared with production, so sending is
restricted to the primary login to keep test digests from reaching the shop's real
recipients.

`/health` reports the sandbox database's status separately, as
`"secondary": "ok" | "error" | "not_configured"`. This never changes `/health`'s
status code — that code reflects the primary database only, so a broken sandbox
can never fail a Railway deploy healthcheck.

If a request under the sandbox login returns `503`, that means its database
(`SECONDARY_DATABASE_URL`) is configured but currently unreachable — the response
names the account. That's distinct from `/health` showing `"not_configured"`, which
means the three `SECONDARY_*` variables aren't all set.

### Troubleshooting: `socket.gaierror: Name or service not known`

If a deploy crash-loops with this error at boot, `DATABASE_URL` is missing or its
Railway reference is broken. When `DATABASE_URL` isn't set, the app falls back to
the docker-compose default host `db:5432`, which resolves nowhere outside
`docker compose` — the DNS lookup for host `db` fails on Railway. The migration
step that `start.sh` runs (`python -m app.bootstrap`) prints an explicit warning at
boot when it detects this fallback host, so check the deploy logs first. The error
is not the database being down; it's the environment variable being absent or its
reference pointing at the wrong service name.

`SECONDARY_DATABASE_URL` has no such default — it's blank unless set, and a blank
value is exactly what disables the second login (see the all-three-or-nothing rule
above). So this specific error can only happen on the secondary side if
`SECONDARY_DATABASE_URL` is *set* to something that resolves to host `db` — for
example an accidentally copied primary URL, or a Railway reference left in place
as a literal string that never resolved. It never happens just from leaving it
blank.

If the second login returns 401 and there's nothing about it in the deploy logs,
that's the blank case: one of the three `SECONDARY_*` variables is missing, so the
account doesn't exist rather than failing loudly. Check all three are set before
looking for a crash that won't be there.
