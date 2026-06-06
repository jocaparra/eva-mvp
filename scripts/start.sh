#!/usr/bin/env bash
# Railway / produção: migrations + uvicorn
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "WARN: DATABASE_URL não definida — usando SQLite local (não recomendado em prod)."
else
  echo "==> Alembic upgrade head"
  python3 -m alembic upgrade head
fi

echo "==> Uvicorn na porta ${PORT:-8000}"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
