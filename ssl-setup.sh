#!/usr/bin/env bash
# =====================================================================
# AI SEO OS — Domain + SSL Setup (Let's Encrypt / Certbot)
# Usage: bash /root/SEO/ssl-setup.sh yourdomain.com
# =====================================================================
set -e

DOMAIN=$1
PROJECT_DIR="/root/SEO"

if [ -z "$DOMAIN" ]; then
    echo "❌ Usage: bash ssl-setup.sh yourdomain.com"
    echo "   Example: bash ssl-setup.sh seo.example.com"
    exit 1
fi

echo "==========================================================="
echo "   🔒 SSL Setup for: $DOMAIN"
echo "==========================================================="

# Step 1: Make sure services are running (nginx needs to be up for ACME challenge)
echo "1/4: Ensuring Nginx is running for ACME challenge..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.prod.yml up -d nginx

# Step 2: Obtain SSL certificate
echo "2/4: Requesting SSL certificate from Let's Encrypt..."
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@${DOMAIN} \
    --agree-tos \
    --no-eff-email \
    -d ${DOMAIN}

# Step 3: Generate nginx SSL config
echo "3/4: Generating Nginx SSL configuration..."
cat > "$PROJECT_DIR/nginx/nginx.conf" << 'NGINX_CONF'
user  nginx;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent"';
    access_log  /var/log/nginx/access.log  main;
    sendfile        on;
    keepalive_timeout  65;
    client_max_body_size 50M;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    upstream backend_api { server backend:8000; }
    upstream frontend_app { server frontend:3000; }
    upstream n8n_app { server n8n:5678; }

    # HTTP → HTTPS redirect
    server {
        listen 80;
        server_name DOMAIN_PLACEHOLDER;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS
    server {
        listen 443 ssl;
        http2 on;
        server_name DOMAIN_PLACEHOLDER;

        ssl_certificate     /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;

        # n8n panel
        location /n8n/ {
            proxy_pass http://n8n_app/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            proxy_read_timeout 300s;
        }

        # n8n webhooks
        location /webhook/ {
            proxy_pass http://n8n_app/webhook/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
        }
        location /webhook-test/ {
            proxy_pass http://n8n_app/webhook-test/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Backend API
        location /api/ {
            proxy_pass http://backend_api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            proxy_read_timeout 300s;
        }

        location ~ ^/(docs|redoc|openapi.json) {
            proxy_pass http://backend_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://backend_api;
            proxy_set_header Host $host;
        }

        # Frontend
        location / {
            proxy_pass http://frontend_app;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }
    }
}
NGINX_CONF

# Replace placeholder with actual domain
sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "$PROJECT_DIR/nginx/nginx.conf"

# Update .env.production with domain
sed -i "s/BACKEND_CORS_ORIGINS=.*/BACKEND_CORS_ORIGINS=https:\/\/${DOMAIN}/" "$PROJECT_DIR/.env.production"

# Step 4: Restart nginx with SSL config
echo "4/4: Restarting Nginx with SSL..."
docker compose -f docker-compose.prod.yml restart nginx

echo ""
echo "==========================================================="
echo "✅ SSL Certificate installed successfully!"
echo ""
echo "   🔒 HTTPS Dashboard:  https://${DOMAIN}/"
echo "   📚 API Docs:         https://${DOMAIN}/docs"
echo "   🤖 n8n Panel:        https://${DOMAIN}/n8n/"
echo ""
echo "   Google OAuth Redirect URI (for Search Console):"
echo "   https://${DOMAIN}/api/v1/integrations/gsc/callback"
echo ""
echo "   Certificate auto-renewal is handled by Certbot container."
echo "==========================================================="
