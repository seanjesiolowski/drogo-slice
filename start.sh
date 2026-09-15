#!/bin/sh
set -e

# Migrate every configured database. Primary failure is fatal; a failing
# secondary is logged and skipped so it can never take production down.
python -m app.bootstrap

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
