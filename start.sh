#!/bin/sh
set -e

# Decide how to bring the schema up to date before serving.
#
#   stamp   - tables exist but predate alembic (the original production DB).
#             Mark 001 as applied without re-running it, then migrate forward.
#   migrate - either alembic history already exists, or the database is empty
#             and the full history should run from 001.
#
# A fresh, empty database MUST NOT be stamped: stamping skips the table
# creation in 001_initial, and 002_drop_display_order then fails with
# 'relation "categories" does not exist'.
MODE=$(python - << 'PYEOF'
import asyncio

from sqlalchemy import inspect

from app.database import engine


async def table_names() -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))


tables = asyncio.run(table_names())

if "alembic_version" in tables:
    print("migrate")
elif "categories" in tables:
    print("stamp")
else:
    print("migrate")
PYEOF
)

if [ "$MODE" = "stamp" ]; then
    echo "Existing pre-alembic database detected — stamping at 001_initial"
    alembic stamp 001_initial
fi

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
