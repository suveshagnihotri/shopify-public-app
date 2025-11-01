#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "Starting Production Environment"
echo "=========================================="
echo ""

# Check if .env file exists
if [[ ! -f .env ]]; then
  echo "⚠️  Warning: .env file not found"
  echo "Creating .env from env.example..."
  if [[ -f env.example ]]; then
    cp env.example .env
    echo "✅ Created .env file. Please update it with your production values!"
    echo ""
    echo "Required environment variables:"
    echo "  - SHOPIFY_API_KEY"
    echo "  - SHOPIFY_API_SECRET"
    echo "  - SHOPIFY_REDIRECT_URI"
    echo "  - DATABASE_URL"
    echo "  - REDIS_URL"
    echo "  - SECRET_KEY"
    echo "  - WEBHOOK_SECRET"
    echo ""
    read -p "Press enter to continue after updating .env file..."
  else
    echo "❌ Error: env.example not found. Cannot create .env file."
    exit 1
  fi
fi

# Source .env file to check for critical variables
source .env

# Check critical environment variables
echo "🔍 Checking environment variables..."
MISSING_VARS=()
[[ -z "${SHOPIFY_API_KEY:-}" ]] && MISSING_VARS+=("SHOPIFY_API_KEY")
[[ -z "${SHOPIFY_API_SECRET:-}" ]] && MISSING_VARS+=("SHOPIFY_API_SECRET")
[[ -z "${DATABASE_URL:-}" ]] && MISSING_VARS+=("DATABASE_URL")
[[ -z "${REDIS_URL:-}" ]] && MISSING_VARS+=("REDIS_URL")
[[ -z "${SECRET_KEY:-}" ]] && MISSING_VARS+=("SECRET_KEY")

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
  echo "❌ Missing required environment variables:"
  for var in "${MISSING_VARS[@]}"; do
    echo "   - $var"
  done
  echo ""
  echo "Please update your .env file with these values."
  exit 1
fi
echo "✅ All required environment variables are set"
echo ""

# Build images
echo "🔨 Building Docker images..."
echo "----------------------------------------"
DOCKER_BUILDKIT=0 docker-compose -f docker-compose.prod.yml build
echo "✅ Build complete"
echo ""

# Stop any existing containers
echo "🛑 Stopping existing containers..."
echo "----------------------------------------"
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
echo "✅ Containers stopped"
echo ""

# Start services
echo "🚀 Starting production services..."
echo "----------------------------------------"
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
echo "----------------------------------------"
docker-compose -f docker-compose.prod.yml ps
echo ""

# Wait for database to be ready and run migrations
echo "🗄️  Waiting for database to be ready..."
DB_READY=0
for i in {1..30}; do
  if docker-compose -f docker-compose.prod.yml exec -T db pg_isready -U postgres >/dev/null 2>&1; then
    DB_READY=1
    break
  fi
  echo "   Attempt $i/30..."
  sleep 2
done

if [[ $DB_READY -eq 1 ]]; then
  echo "✅ Database is ready"
  echo ""
  echo "📦 Running database migrations..."
  echo "----------------------------------------"
  docker-compose -f docker-compose.prod.yml exec -T app flask db upgrade 2>/dev/null || \
    echo "⚠️  Migration command failed (this may be expected if tables already exist)"
else
  echo "❌ Database did not become ready in time"
fi
echo ""

# Check Redis
echo "📮 Checking Redis..."
if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping >/dev/null 2>&1; then
  echo "✅ Redis is ready"
else
  echo "⚠️  Redis may not be ready yet"
fi
echo ""

# Final status check
echo "=========================================="
echo "Production Environment Started"
echo "=========================================="
echo ""
echo "📋 Service URLs:"
echo "   - App: http://localhost:5000 (internal)"
echo "   - Nginx: http://localhost:80 (http)"
echo "   - Nginx: https://localhost:443 (https)"
echo ""
echo "🔍 Useful Commands:"
echo "   View logs:        docker-compose -f docker-compose.prod.yml logs -f [service]"
echo "   Check status:     docker-compose -f docker-compose.prod.yml ps"
echo "   Stop services:    docker-compose -f docker-compose.prod.yml down"
echo "   Restart service:  docker-compose -f docker-compose.prod.yml restart [service]"
echo ""
echo "🧪 Test endpoints:"
echo "   ./scripts/check_prod.sh"
echo "   ./scripts/test_endpoints.sh"
echo ""

