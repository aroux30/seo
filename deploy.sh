#!/usr/bin/env bash
# =====================================================================
# AI SEO OS — Automated Single VPS Deployment Script (Docker Compose)
# =====================================================================
set -e

echo "==========================================================="
echo "   🚀 AI SEO OS — Single VPS Production Deployment"
echo "==========================================================="

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo "⚠️  [.env.production] file not found! Copying template from .env.production.example..."
    cp .env.production.example .env.production
    echo "❗  Please edit .env.production with your real API keys and database password before running production!"
fi

# Ensure .env is linked to .env.production so docker-compose variable interpolation works reliably
ln -sf .env.production .env

echo "📦 1/4: Building Docker Images and Services..."
docker-compose -f docker-compose.prod.yml build --pull

echo "🔄 2/4: Starting AI SEO OS Stack in background..."
docker-compose -f docker-compose.prod.yml up -d

echo "⏳ 3/4: Waiting for PostgreSQL and Backend migrations to complete (10s)..."
sleep 10

echo "📊 4/4: Checking running container statuses..."
docker-compose -f docker-compose.prod.yml ps

echo "==========================================================="
echo "✅ AI SEO OS has been deployed successfully on your VPS!"
echo "   - Frontend Dashboard (Next.js RTL):  http://localhost/ (or server IP)"
echo "   - Backend API Docs (FastAPI Swagger): http://localhost/docs"
echo "   - Database: PostgreSQL 16 (Volume: pgdata_prod)"
echo "   - Async Engine: Celery + Redis 7 + Celery Beat"
echo "==========================================================="
