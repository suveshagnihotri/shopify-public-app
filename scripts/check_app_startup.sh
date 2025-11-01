#!/bin/bash

# App Startup Diagnostic Script
# Checks why app failed to start

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.prod.yml"

echo -e "${BLUE}=== App Startup Diagnostic ===${NC}\n"

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

# Step 1: Check app service status
echo -e "${YELLOW}Step 1: App service status...${NC}"
echo "----------------------------------------"

APP_STATUS=$(${COMPOSE_CMD} -f ${COMPOSE_FILE} ps app 2>/dev/null | grep -E "app|Up|Exit" || echo "")
echo "$APP_STATUS"
echo ""

# Step 2: Get recent app logs (last 50 lines)
echo -e "${YELLOW}Step 2: Recent app logs (last 50 lines)...${NC}"
echo "----------------------------------------"
${COMPOSE_CMD} -f ${COMPOSE_FILE} logs --tail=50 app 2>&1 | tail -50
echo ""

# Step 3: Search for specific errors in logs
echo -e "${YELLOW}Step 3: Common error patterns...${NC}"
echo "----------------------------------------"

# Check for Redis connection errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "redis.*connection\|redis.*refused\|cannot connect to redis"; then
    echo -e "${RED}✗ Redis connection error found${NC}"
    echo "   The app cannot connect to Redis"
    echo "   Fix: Ensure Redis is running and REDIS_URL is correct"
fi

# Check for Database connection errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "database.*connection\|postgres.*refused\|cannot connect to database"; then
    echo -e "${RED}✗ Database connection error found${NC}"
    echo "   The app cannot connect to the database"
    echo "   Fix: Ensure database is running and DATABASE_URL is correct"
fi

# Check for Import errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "import.*error\|module.*not found\|no module named"; then
    echo -e "${RED}✗ Import error found${NC}"
    echo "   A required Python module is missing"
    echo "   Fix: Rebuild Docker image: ${COMPOSE_CMD} -f ${COMPOSE_FILE} build app"
fi

# Check for Flask-Session errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "session.*error\|flask.session\|session.*redis"; then
    echo -e "${RED}✗ Flask-Session error found${NC}"
    echo "   Flask-Session initialization failed"
    echo "   This is often related to Redis connection"
fi

# Check for Gunicorn errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "gunicorn.*error\|failed to find application\|application.*not.*callable"; then
    echo -e "${RED}✗ Gunicorn error found${NC}"
    echo "   Gunicorn cannot start the Flask application"
    echo "   Check for errors in app initialization"
fi

# Check for Port binding errors
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "address.*in use\|port.*already\|bind.*failed"; then
    echo -e "${RED}✗ Port binding error found${NC}"
    echo "   Port 8000 is already in use"
    echo "   Fix: Check what's using port 8000"
fi

# Check if no errors found
if ! ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs app 2>&1 | grep -qi "error\|exception\|traceback\|failed"; then
    echo -e "${GREEN}✓ No obvious errors found in logs${NC}"
    echo "   Check logs manually for other issues"
fi

echo ""

# Step 4: Check dependencies (Redis, Database)
echo -e "${YELLOW}Step 4: Checking dependencies...${NC}"
echo "----------------------------------------"

# Check Redis
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} ps | grep -q "redis.*Up"; then
    if ${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo -e "${GREEN}✓ Redis is running and accessible${NC}"
    else
        echo -e "${YELLOW}⚠ Redis is running but not responding${NC}"
    fi
else
    echo -e "${RED}✗ Redis is NOT running${NC}"
    echo "   Fix: ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d redis"
fi

# Check Database
if ${COMPOSE_CMD} -f ${COMPOSE_FILE} ps | grep -q "db.*Up"; then
    if ${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T db pg_isready -U postgres 2>/dev/null | grep -q "accepting"; then
        echo -e "${GREEN}✓ Database is running and accessible${NC}"
    else
        echo -e "${YELLOW}⚠ Database is running but not accepting connections${NC}"
    fi
else
    echo -e "${RED}✗ Database is NOT running${NC}"
    echo "   Fix: ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d db"
fi

echo ""

# Step 5: Check environment variables
echo -e "${YELLOW}Step 5: Checking environment variables...${NC}"
echo "----------------------------------------"

if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"
    
    # Check critical variables
    MISSING=()
    
    if ! grep -q "^REDIS_URL=" .env 2>/dev/null; then
        MISSING+=("REDIS_URL")
    fi
    
    if ! grep -q "^DATABASE_URL=" .env 2>/dev/null; then
        MISSING+=("DATABASE_URL")
    fi
    
    if ! grep -q "^SHOPIFY_API_KEY=" .env 2>/dev/null; then
        MISSING+=("SHOPIFY_API_KEY")
    fi
    
    if ! grep -q "^SHOPIFY_API_SECRET=" .env 2>/dev/null; then
        MISSING+=("SHOPIFY_API_SECRET")
    fi
    
    if [ ${#MISSING[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ Critical environment variables are set${NC}"
    else
        echo -e "${RED}✗ Missing environment variables:${NC}"
        for var in "${MISSING[@]}"; do
            echo "   - $var"
        done
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo "   Fix: Create .env file from env.example"
fi

echo ""

# Step 6: Recommendations
echo -e "${BLUE}=== Recommendations ===${NC}\n"

echo "Based on the diagnostics above, try these fixes:"
echo ""

echo "1. If Redis connection error:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d redis"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart app"
echo ""

echo "2. If Database connection error:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d db"
echo "   sleep 5  # Wait for DB to be ready"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart app"
echo ""

echo "3. If missing environment variables:"
echo "   Update .env file with required variables"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart app"
echo ""

echo "4. If import/module errors:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} build --no-cache app"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d app"
echo ""

echo "5. Restart all services:"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart"
echo ""

echo "6. Complete restart (if nothing else works):"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} down"
echo "   ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d"
echo ""

