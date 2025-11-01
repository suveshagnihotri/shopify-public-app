#!/bin/bash

# 502 Bad Gateway Diagnostic Script
# This script diagnoses why nginx returns 502 Bad Gateway

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.prod.yml"

echo -e "${BLUE}=== 502 Bad Gateway Diagnostic Tool ===${NC}\n"

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.." || exit 1

# Determine docker-compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Step 1: Check if services are running
echo -e "${YELLOW}Step 1: Checking service status...${NC}"
echo "----------------------------------------"

ALL_RUNNING=true
SERVICES=("nginx" "app" "redis" "db")

for service in "${SERVICES[@]}"; do
    if ${COMPOSE_CMD} -f ${COMPOSE_FILE} ps | grep -q "${service}.*Up"; then
        echo -e "${GREEN}✓${NC} ${service} is running"
    else
        echo -e "${RED}✗${NC} ${service} is NOT running"
        ALL_RUNNING=false
    fi
done

if [ "$ALL_RUNNING" = false ]; then
    echo ""
    echo -e "${RED}Some services are not running. Start them with:${NC}"
    echo "  ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d"
    echo ""
fi

echo ""

# Step 2: Check app service logs for errors
echo -e "${YELLOW}Step 2: Checking app service logs (last 20 lines)...${NC}"
echo "----------------------------------------"
${COMPOSE_CMD} -f ${COMPOSE_FILE} logs --tail=20 app | tail -20 || true
echo ""

# Step 3: Check if app is listening on port 8000 inside container
echo -e "${YELLOW}Step 3: Checking if app is listening on port 8000...${NC}"
echo "----------------------------------------"

APP_CONTAINER=$(${COMPOSE_CMD} -f ${COMPOSE_FILE} ps -q app 2>/dev/null || echo "")

if [ -n "$APP_CONTAINER" ]; then
    # Check if port 8000 is listening
    if docker exec "$APP_CONTAINER" netstat -tuln 2>/dev/null | grep -q ":8000" || \
       docker exec "$APP_CONTAINER" ss -tuln 2>/dev/null | grep -q ":8000"; then
        echo -e "${GREEN}✓${NC} App is listening on port 8000"
    else
        echo -e "${RED}✗${NC} App is NOT listening on port 8000"
        echo "   This usually means the app failed to start"
        echo "   Check app logs for errors"
    fi
else
    echo -e "${RED}✗${NC} App container not found"
fi
echo ""

# Step 4: Test connection from nginx to app
echo -e "${YELLOW}Step 4: Testing nginx → app connection...${NC}"
echo "----------------------------------------"

NGINX_CONTAINER=$(${COMPOSE_CMD} -f ${COMPOSE_FILE} ps -q nginx 2>/dev/null || echo "")

if [ -n "$NGINX_CONTAINER" ] && [ -n "$APP_CONTAINER" ]; then
    # Test if nginx can reach app on port 8000
    if docker exec "$NGINX_CONTAINER" wget -q --spider --timeout=2 http://app:8000/ 2>/dev/null || \
       docker exec "$NGINX_CONTAINER" nc -z app 8000 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Nginx can reach app service on port 8000"
    else
        echo -e "${RED}✗${NC} Nginx CANNOT reach app service on port 8000"
        echo "   Common causes:"
        echo "   - App service is not running"
        echo "   - App is not listening on port 8000"
        echo "   - Docker network issue"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Cannot test connection (containers not found)"
fi
echo ""

# Step 5: Check nginx configuration
echo -e "${YELLOW}Step 5: Checking nginx configuration...${NC}"
echo "----------------------------------------"

if [ -n "$NGINX_CONTAINER" ]; then
    # Test nginx config
    if docker exec "$NGINX_CONTAINER" nginx -t 2>&1 | grep -q "successful"; then
        echo -e "${GREEN}✓${NC} Nginx configuration is valid"
        
        # Check if proxy_pass points to correct backend
        if grep -q "proxy_pass.*app:8000" nginx/peeq.conf; then
            echo -e "${GREEN}✓${NC} Nginx proxy_pass points to app:8000"
        else
            echo -e "${RED}✗${NC} Nginx proxy_pass may not point to app:8000"
            echo "   Current config:"
            grep "proxy_pass" nginx/peeq.conf || echo "   Not found in config"
        fi
    else
        echo -e "${RED}✗${NC} Nginx configuration has errors:"
        docker exec "$NGINX_CONTAINER" nginx -t 2>&1 | grep -i error || true
    fi
else
    echo -e "${YELLOW}⚠${NC}  Cannot check nginx config (container not found)"
fi
echo ""

# Step 6: Check nginx error logs
echo -e "${YELLOW}Step 6: Checking nginx error logs...${NC}"
echo "----------------------------------------"
${COMPOSE_CMD} -f ${COMPOSE_FILE} logs --tail=10 nginx 2>&1 | grep -i "error\|502\|bad gateway" || echo "No obvious errors in recent logs"
echo ""

# Step 7: Check Redis connection (app may fail if Redis is down)
echo -e "${YELLOW}Step 7: Checking Redis connection...${NC}"
echo "----------------------------------------"

if ${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✓${NC} Redis is accessible"
else
    echo -e "${RED}✗${NC} Redis is NOT accessible"
    echo "   App may fail to start without Redis"
fi
echo ""

# Step 8: Check Database connection
echo -e "${YELLOW}Step 8: Checking Database connection...${NC}"
echo "----------------------------------------"

if ${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T db pg_isready -U postgres 2>/dev/null | grep -q "accepting"; then
    echo -e "${GREEN}✓${NC} Database is ready"
else
    echo -e "${YELLOW}⚠${NC}  Database may not be ready"
    echo "   App may fail to start if database is not accessible"
fi
echo ""

# Step 9: Check app environment variables
echo -e "${YELLOW}Step 9: Checking critical environment variables...${NC}"
echo "----------------------------------------"

# Check if .env file exists
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check critical variables
    MISSING_VARS=()
    
    if ! grep -q "REDIS_URL" .env 2>/dev/null; then
        MISSING_VARS+=("REDIS_URL")
    fi
    
    if ! grep -q "DATABASE_URL" .env 2>/dev/null; then
        MISSING_VARS+=("DATABASE_URL")
    fi
    
    if ! grep -q "SHOPIFY_API_KEY" .env 2>/dev/null; then
        MISSING_VARS+=("SHOPIFY_API_KEY")
    fi
    
    if [ ${#MISSING_VARS[@]} -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Critical environment variables are set"
    else
        echo -e "${RED}✗${NC} Missing environment variables:"
        for var in "${MISSING_VARS[@]}"; do
            echo "   - $var"
        done
    fi
else
    echo -e "${RED}✗${NC} .env file not found"
fi
echo ""

# Summary and recommendations
echo -e "${BLUE}=== Diagnostic Summary ===${NC}\n"

echo "Most common causes of 502 Bad Gateway:"
echo "1. App service is not running"
echo "2. App service failed to start (check logs)"
echo "3. App is not listening on port 8000"
echo "4. Redis connection error (app can't start)"
echo "5. Database connection error (app can't start)"
echo "6. Docker network issue between nginx and app"
echo ""

echo "Quick fixes to try:"
echo "1. Restart app service:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart app"
echo ""
echo "2. Check app logs for errors:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs -f app"
echo ""
echo "3. Restart all services:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart"
echo ""
echo "4. Recreate app service:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d --force-recreate app"
echo ""

