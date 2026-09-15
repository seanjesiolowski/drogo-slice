#!/bin/sh
set -e

# See app/bootstrap.py for the migration and failure-handling rules.
python -m app.bootstrap

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
