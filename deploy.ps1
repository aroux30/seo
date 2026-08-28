# =====================================================================
# AI SEO OS — Automated Single VPS Deployment Script (PowerShell / Windows)
# =====================================================================

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "   🚀 AI SEO OS — Single VPS Production Deployment" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# Check if .env.production exists
if (-not (Test-Path ".env.production")) {
    Write-Host "⚠️  [.env.production] file not found! Copying from .env.production.example..." -ForegroundColor Yellow
    Copy-Item ".env.production.example" ".env.production"
    Write-Host "❗  Please edit .env.production with your real API keys and password!" -ForegroundColor Yellow
}

Write-Host "📦 1/4: Building Docker Images and Services..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml build --pull

Write-Host "🔄 2/4: Starting AI SEO OS Stack in background..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml up -d

Write-Host "⏳ 3/4: Waiting for PostgreSQL and Backend migrations to complete (10s)..." -ForegroundColor Green
Start-Sleep -Seconds 10

Write-Host "📊 4/4: Checking running container statuses..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml ps

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "✅ AI SEO OS has been deployed successfully!" -ForegroundColor Green
Write-Host "   - Frontend Dashboard (Next.js RTL):   http://localhost/" -ForegroundColor White
Write-Host "   - Backend API Docs (FastAPI Swagger): http://localhost/docs" -ForegroundColor White
Write-Host "   - Database: PostgreSQL 16 (Volume: pgdata_prod)" -ForegroundColor White
Write-Host "   - Async Engine: Celery + Redis 7 + Celery Beat" -ForegroundColor White
Write-Host "===========================================================" -ForegroundColor Cyan
