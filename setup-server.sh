#!/usr/bin/env bash
# =====================================================================
# AI SEO OS — Ubuntu VPS Full Setup & Deployment Script
# Location: /root/SEO/
# IMPORTANT: This script ONLY touches /root/SEO/ and does NOT modify
#            any other directories or projects on this server.
# =====================================================================
set -e

PROJECT_DIR="/root/SEO"
cd "$PROJECT_DIR"

echo "==========================================================="
echo "   🚀 AI SEO OS — Ubuntu VPS Production Setup"
echo "   📁 Working directory: $PROJECT_DIR"
echo "==========================================================="

# -----------------------------------------------
# 1. Install Docker & Docker Compose (if missing)
# -----------------------------------------------
echo ""
echo "📦 Step 1/6: Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "  → Docker not found. Installing Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "  ✅ Docker installed successfully"
else
    echo "  ✅ Docker is already installed: $(docker --version)"
fi

if ! docker compose version &> /dev/null; then
    echo "  ⚠️  Docker Compose plugin not found. Installing..."
    apt-get install -y -qq docker-compose-plugin
fi
echo "  ✅ Docker Compose: $(docker compose version --short)"

# -----------------------------------------------
# 2. Create .env.production if missing
# -----------------------------------------------
echo ""
echo "🔧 Step 2/6: Setting up environment configuration..."
if [ ! -f "$PROJECT_DIR/.env.production" ]; then
    cp "$PROJECT_DIR/.env.production.example" "$PROJECT_DIR/.env.production"
    echo "  ⚠️  Created .env.production from template."
    echo "  ❗ IMPORTANT: Edit /root/SEO/.env.production with your real API keys!"
    echo "     nano /root/SEO/.env.production"
else
    echo "  ✅ .env.production already exists"
fi

# -----------------------------------------------
# 3. Fix file permissions
# -----------------------------------------------
echo ""
echo "🔑 Step 3/6: Fixing file permissions..."
chmod +x "$PROJECT_DIR/backend/start.sh" 2>/dev/null || true
chmod +x "$PROJECT_DIR/deploy.sh" 2>/dev/null || true
# Ensure LF line endings for shell scripts (in case transferred from Windows)
if command -v sed &> /dev/null; then
    sed -i 's/\r$//' "$PROJECT_DIR/backend/start.sh" 2>/dev/null || true
    sed -i 's/\r$//' "$PROJECT_DIR/deploy.sh" 2>/dev/null || true
fi
echo "  ✅ Permissions fixed"

# -----------------------------------------------
# 4. Build Docker images
# -----------------------------------------------
echo ""
echo "🏗️  Step 4/6: Building Docker images (this may take a few minutes)..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.prod.yml build --pull

# -----------------------------------------------
# 5. Start all services
# -----------------------------------------------
echo ""
echo "🔄 Step 5/6: Starting AI SEO OS stack..."
docker compose -f docker-compose.prod.yml up -d

echo "  ⏳ Waiting for services to initialize (15s)..."
sleep 15

# -----------------------------------------------
# 6. Health check
# -----------------------------------------------
echo ""
echo "📊 Step 6/6: Checking service status..."
docker compose -f docker-compose.prod.yml ps

echo ""
echo "==========================================================="
echo "✅ AI SEO OS has been deployed successfully!"
echo ""
echo "   📊 Dashboard (RTL):    http://$(hostname -I | awk '{print $1}')/"
echo "   📚 API Docs (Swagger): http://$(hostname -I | awk '{print $1}')/docs"
echo "   🤖 n8n Automation:     http://$(hostname -I | awk '{print $1}')/n8n/"
echo "   ❤️  Health Check:       http://$(hostname -I | awk '{print $1}')/health"
echo ""
echo "   Next steps:"
echo "   1. Edit API keys:      nano /root/SEO/.env.production"
echo "   2. Point domain DNS:   A record → $(hostname -I | awk '{print $1}')"
echo "   3. Get SSL cert:       bash /root/SEO/ssl-setup.sh yourdomain.com"
echo "==========================================================="
