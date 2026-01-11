#!/bin/bash
set -e

# Allow overriding postgres credentials via env (demo/prod)
PGUSER="${POSTGRES_USER:-arbetsytan}"
PGPASSWORD_ENV="${POSTGRES_PASSWORD:-arbetsytan}"
PGDATABASE="${POSTGRES_DB:-arbetsytan}"

# Wait for postgres to be ready
until PGPASSWORD="${PGPASSWORD_ENV}" psql -h postgres -U "${PGUSER}" -d "${PGDATABASE}" -c '\q' 2>/dev/null; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing init script"

# Ensure full schema exists (SQLAlchemy models) before optional SQL migrations.
# This keeps init_db.sql idempotent even on fresh databases.
python3 -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"

# Optional: run Alembic migrations (off by default to avoid breaking demo)
if [ "${ALEMBIC_UPGRADE:-0}" = "1" ]; then
  echo "Running Alembic migrations..."
  (cd /app && alembic -c alembic.ini upgrade head) || exit 1
fi

# Run init script (optional/legacy migrations)
PGPASSWORD="${PGPASSWORD_ENV}" psql -h postgres -U "${PGUSER}" -d "${PGDATABASE}" -f /app/init_db.sql || true

# Start uvicorn
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

