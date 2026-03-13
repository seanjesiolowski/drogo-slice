# Drogo Slice

Shop inventory tracker built with FastAPI and PostgreSQL.

## Running locally

```bash
docker compose up --build
```

App runs at `http://localhost:8000`. API docs at `/docs`.

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `ADMIN_USERNAME` | Basic auth username |
| `ADMIN_PASSWORD` | Basic auth password |

See `.env.example` for defaults.
