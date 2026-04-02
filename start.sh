#!/bin/sh
set -e

# If alembic has never run, stamp the DB at 001 since tables already exist
python -c "
import asyncio
from sqlalchemy import text
from app.database import engine

async def check():
    async with engine.connect() as conn:
        try:
            await conn.execute(text('SELECT 1 FROM alembic_version LIMIT 1'))
            return True
        except Exception:
            return False

if not asyncio.run(check()):
    print('No alembic history found — stamping existing DB at 001_initial')
    exit(1)
" || alembic stamp 001_initial

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
