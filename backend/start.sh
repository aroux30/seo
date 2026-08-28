#!/bin/bash
set -e

echo "Running Alembic Database Migrations..."
alembic -c alembic.ini upgrade head

echo "Starting FastAPI AI SEO OS Production Server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
