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

