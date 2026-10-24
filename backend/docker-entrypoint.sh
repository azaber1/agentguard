#!/bin/sh
set -e
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m app.seed || echo "Demo seed skipped."
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-1}"
