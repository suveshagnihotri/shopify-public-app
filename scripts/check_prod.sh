#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "Production Status Check"
echo "=========================================="
echo ""

# Check if docker-compose file exists
if [[ ! -f docker-compose.prod.yml ]]; then
  echo "❌ Error: docker-compose.prod.yml not found"
  exit 1
fi

# Check running containers
echo "📦 Running Containers:"
echo "----------------------"
docker-compose -f docker-compose.prod.yml ps
echo ""

# Check container status
echo "🔍 Container Status:"
echo "----------------------"
STATUS=$(docker-compose -f docker-compose.prod.yml ps --services --filter "status=running" 2>/dev/null || echo "")
if [[ -z "$STATUS" ]]; then
  echo "⚠️  No containers are running"
else
  echo "✅ Running services:"
  docker-compose -f docker-compose.prod.yml ps --services --filter "status=running"
fi
echo ""

# Check if app container is responding
echo "🌐 Application Health Check:"
echo "----------------------"
APP_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q app 2>/dev/null || echo "")
if [[ -n "$APP_CONTAINER" ]]; then
  # Check if container is running
  if docker ps --format "{{.ID}}" | grep -q "$APP_CONTAINER"; then
    echo "✅ App container is running"
    # Try to check if the app is responding (adjust port if needed)
    if command -v curl >/dev/null 2>&1; then
      echo "   Testing HTTP connection..."
      if curl -s -f -o /dev/null -w "   HTTP Status: %{http_code}\n" http://localhost:5000/ 2>/dev/null || \
         curl -s -f -o /dev/null -w "   HTTP Status: %{http_code}\n" http://localhost:80/ 2>/dev/null; then
        echo "   ✅ Application is responding"
      else
        echo "   ⚠️  Application may not be responding (this is normal if behind nginx)"
      fi
    fi
  else
    echo "❌ App container exists but is not running"
  fi
else
  echo "❌ App container not found"
fi
echo ""

# Check database
echo "🗄️  Database Status:"
echo "----------------------"
DB_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q db 2>/dev/null || echo "")
if [[ -n "$DB_CONTAINER" ]]; then
  if docker ps --format "{{.ID}}" | grep -q "$DB_CONTAINER"; then
    echo "✅ Database container is running"
    # Try to connect to database
    if docker exec "$DB_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
      echo "   ✅ Database is accepting connections"
    else
      echo "   ⚠️  Database connection check failed"
    fi
  else
    echo "❌ Database container exists but is not running"
  fi
else
  echo "❌ Database container not found"
fi
echo ""

# Check Redis
echo "📮 Redis Status:"
echo "----------------------"
REDIS_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q redis 2>/dev/null || echo "")
if [[ -n "$REDIS_CONTAINER" ]]; then
  if docker ps --format "{{.ID}}" | grep -q "$REDIS_CONTAINER"; then
    echo "✅ Redis container is running"
    # Try to ping Redis
    if docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
      echo "   ✅ Redis is responding"
    else
      echo "   ⚠️  Redis ping failed"
    fi
  else
    echo "❌ Redis container exists but is not running"
  fi
else
  echo "❌ Redis container not found"
fi
echo ""

# Check worker
echo "👷 Worker Status:"
echo "----------------------"
WORKER_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q worker 2>/dev/null || echo "")
if [[ -n "$WORKER_CONTAINER" ]]; then
  if docker ps --format "{{.ID}}" | grep -q "$WORKER_CONTAINER"; then
    echo "✅ Worker container is running"
  else
    echo "❌ Worker container exists but is not running"
  fi
else
  echo "❌ Worker container not found"
fi
echo ""

# Check nginx
echo "🔧 Nginx Status:"
echo "----------------------"
NGINX_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q nginx 2>/dev/null || echo "")
if [[ -n "$NGINX_CONTAINER" ]]; then
  if docker ps --format "{{.ID}}" | grep -q "$NGINX_CONTAINER"; then
    echo "✅ Nginx container is running"
  else
    echo "❌ Nginx container exists but is not running"
  fi
else
  echo "❌ Nginx container not found"
fi
echo ""

# Show recent logs
echo "📋 Recent Logs (last 10 lines from app):"
echo "----------------------"
APP_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q app 2>/dev/null || echo "")
if [[ -n "$APP_CONTAINER" ]] && docker ps --format "{{.ID}}" | grep -q "$APP_CONTAINER"; then
  docker logs --tail 10 "$APP_CONTAINER" 2>/dev/null || echo "   Could not retrieve logs"
else
  echo "   App container not running, cannot show logs"
fi
echo ""

echo "=========================================="
echo "Status check complete!"
echo "=========================================="
echo ""
echo "💡 Useful commands:"
echo "   View logs: docker-compose -f docker-compose.prod.yml logs -f [service]"
echo "   Restart:   docker-compose -f docker-compose.prod.yml restart [service]"
echo "   Stop:      docker-compose -f docker-compose.prod.yml down"
echo "   Start:     docker-compose -f docker-compose.prod.yml up -d"

