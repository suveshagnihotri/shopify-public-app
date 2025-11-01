#!/bin/bash

# Fix Port Conflict Script
# Diagnoses and fixes port 80/443 conflicts

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Port Conflict Diagnostic Tool ===${NC}\n"

# Check what's using port 80
echo -e "${YELLOW}Checking what's using port 80...${NC}"
echo "----------------------------------------"

if command -v lsof >/dev/null 2>&1; then
    # macOS/Linux
    echo "Port 80 usage:"
    sudo lsof -i :80 || echo "No process found using port 80"
elif command -v netstat >/dev/null 2>&1; then
    # Linux
    echo "Port 80 usage:"
    sudo netstat -tuln | grep ":80 " || echo "No process found using port 80"
elif command -v ss >/dev/null 2>&1; then
    # Linux (modern)
    echo "Port 80 usage:"
    sudo ss -tuln | grep ":80 " || echo "No process found using port 80"
else
    echo -e "${RED}No tools available to check port usage${NC}"
fi

echo ""

# Check what's using port 443
echo -e "${YELLOW}Checking what's using port 443...${NC}"
echo "----------------------------------------"

if command -v lsof >/dev/null 2>&1; then
    sudo lsof -i :443 || echo "No process found using port 443"
elif command -v netstat >/dev/null 2>&1; then
    sudo netstat -tuln | grep ":443 " || echo "No process found using port 443"
elif command -v ss >/dev/null 2>&1; then
    sudo ss -tuln | grep ":443 " || echo "No process found using port 443"
fi

echo ""

# Check for Docker containers
echo -e "${YELLOW}Checking for Docker containers using ports 80/443...${NC}"
echo "----------------------------------------"

if command -v docker >/dev/null 2>&1; then
    # Check for containers using ports 80 or 443
    echo "Containers using port 80:"
    docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" | grep ":80" || echo "No containers found"
    
    echo ""
    echo "Containers using port 443:"
    docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" | grep ":443" || echo "No containers found"
else
    echo -e "${RED}Docker not found${NC}"
fi

echo ""

# Check for nginx on host
echo -e "${YELLOW}Checking for nginx running on host...${NC}"
echo "----------------------------------------"

if systemctl is-active --quiet nginx 2>/dev/null; then
    echo -e "${RED}✗ Nginx is running on host (systemd)${NC}"
    echo "   This may be conflicting with Docker nginx"
elif service nginx status >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Nginx service may be running${NC}"
elif pgrep -x nginx >/dev/null 2>&1; then
    echo -e "${RED}✗ Nginx process is running on host${NC}"
else
    echo -e "${GREEN}✓ No nginx running on host${NC}"
fi

echo ""

# Check for macOS AirPlay Receiver (if on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}Checking for macOS AirPlay Receiver...${NC}"
    echo "----------------------------------------"
    
    AIRPLAY=$(defaults read com.apple.NetworkBrowser DisableAirPlayReceiver 2>/dev/null || echo "0")
    if [ "$AIRPLAY" = "0" ]; then
        echo -e "${YELLOW}⚠ AirPlay Receiver may be enabled (can use port 80)${NC}"
        echo "   To disable: sudo defaults write com.apple.NetworkBrowser DisableAirPlayReceiver -bool YES"
    else
        echo -e "${GREEN}✓ AirPlay Receiver is disabled${NC}"
    fi
    echo ""
fi

# Recommendations
echo -e "${BLUE}=== Recommendations ===${NC}\n"

echo "If port 80 is in use, try these solutions:"
echo ""
echo "1. Stop conflicting Docker containers:"
echo "   docker ps | grep nginx"
echo "   docker stop <container_id>"
echo ""
echo "2. Stop nginx on host (if running):"
echo "   sudo systemctl stop nginx    # systemd"
echo "   # OR"
echo "   sudo service nginx stop      # init.d"
echo ""
echo "3. Kill process using port 80:"
echo "   # Find process: sudo lsof -i :80"
echo "   # Kill process: sudo kill -9 <PID>"
echo ""
echo "4. Remove old/stuck Docker containers:"
echo "   docker-compose -f docker-compose.prod.yml down"
echo "   docker system prune -f"
echo ""
echo "5. After fixing, restart nginx:"
echo "   docker-compose -f docker-compose.prod.yml up -d nginx"
echo ""

