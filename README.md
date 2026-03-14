# Drogo Slice

Shop inventory tracker built with FastAPI and PostgreSQL.

## Running locally (Docker installed and running)

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

## Security

All endpoints (except `/health`) require HTTP Basic Auth. Credentials are set via `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables.

## Testing

```bash
docker compose exec api pytest
```
