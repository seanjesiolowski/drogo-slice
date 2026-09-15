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

A sandbox is a second, separate deployment of this same app with its own database
and its own login. Because the data lives in a different database entirely, there is
no way for experiments in the sandbox to reach the production inventory at Saint
Drogo's.

For day-to-day development, the local `docker compose up` stack above already gives
you this — it runs against its own Postgres volume. Set up a deployed sandbox only
when you need one reachable from outside your machine, such as on a phone.

### Setting one up on Railway

1. Create a new Railway service pointed at this repo. It builds from the same
   `Dockerfile`, so no code or config changes are needed.
2. Add a Postgres database to that service and let Railway inject its `DATABASE_URL`.
   This must be the sandbox's own database — never the production one.
3. Set the environment variables below on the sandbox service.
4. Deploy. `start.sh` runs the full migration history against the empty database on
   first boot, so there is nothing to initialise by hand.

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | the sandbox Postgres | Injected by Railway. The whole isolation guarantee rests on this pointing somewhere other than production. |
| `ADMIN_USERNAME` | your choice | A separate login, so sandbox credentials are not production credentials. |
| `ADMIN_PASSWORD` | your choice | Same. |
| `BREVO_API_KEY` | leave blank | Blank disables digest sending. Without this, test data could email real recipients. |
| `SENTRY_ENVIRONMENT` | `sandbox` | Keeps experimental errors from being mistaken for production incidents. |
| `SENTRY_DSN` | leave blank | Optional. Blank turns off error tracking for the sandbox entirely. |

The sandbox comes up with an empty inventory, ready to experiment in.

### Working in the sandbox

Add a few categories and items by hand through the UI to get started. There is no
import endpoint — `/api/backup` exports production data but nothing consumes that
file, so sandbox data is entered manually.

`POST /api/reset?confirm=RESET` wipes all items and categories and restarts IDs at 1.
That is safe and useful in the sandbox, and being able to run it freely is much of the
point of having one.
