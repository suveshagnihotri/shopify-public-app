#!/bin/bash

# SSL Certificate Installation Script
# This script installs SSL certificates using Let's Encrypt/Certbot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="peeq.co.in"
WWW_DOMAIN="www.peeq.co.in"
EMAIL="suveshagnihotri145@gmail.com"
COMPOSE_FILE="${COMPOSE_CMD}.prod.yml"

echo -e "${GREEN}=== SSL Certificate Installation Script ===${NC}\n"

# Change to script directory (parent directory where ${COMPOSE_CMD}.yml is)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.." || exit 1

# Step 1: Check prerequisites
echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check if ${COMPOSE_CMD} or docker compose is available
if command -v ${COMPOSE_CMD} &> /dev/null; then
    COMPOSE_CMD="${COMPOSE_CMD}"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: ${COMPOSE_CMD} not found${NC}"
    exit 1
fi

# Check if services are running
echo "Checking Docker services..."
if ! ${COMPOSE_CMD} -f ${COMPOSE_FILE} ps | grep -q "nginx.*Up"; then
    echo -e "${RED}Error: Nginx service is not running${NC}"
    echo "Start services with: ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d"
    exit 1
fi

if ! ${COMPOSE_CMD} -f ${COMPOSE_FILE} ps | grep -q "app.*Up"; then
    echo -e "${YELLOW}Warning: App service is not running${NC}"
    echo "Starting services..."
    ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}\n"

# Step 2: Test ACME challenge path
echo -e "${YELLOW}Step 2: Testing ACME challenge path...${NC}"

# Create test file
${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T nginx sh -c 'mkdir -p /var/www/certbot/.well-known/acme-challenge/ && echo "test-ssl-verification" > /var/www/certbot/.well-known/acme-challenge/test-file' || {
    echo -e "${RED}Error: Failed to create test file in nginx container${NC}"
    exit 1
}

# Test if accessible
echo "Testing ACME challenge accessibility..."
HTTP_CODE_1=$(curl -s -o /dev/null -w "%{http_code}" http://${DOMAIN}/.well-known/acme-challenge/test-file)
HTTP_CODE_2=$(curl -s -o /dev/null -w "%{http_code}" http://${WWW_DOMAIN}/.well-known/acme-challenge/test-file)

# Clean up test file
${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T nginx rm -f /var/www/certbot/.well-known/acme-challenge/test-file > /dev/null 2>&1

if [ "$HTTP_CODE_1" != "200" ] || [ "$HTTP_CODE_2" != "200" ]; then
    echo -e "${RED}Error: ACME challenge path is not accessible${NC}"
    echo "HTTP codes: ${DOMAIN} -> ${HTTP_CODE_1}, ${WWW_DOMAIN} -> ${HTTP_CODE_2}"
    echo "Expected: Both should return 200"
    echo ""
    echo "Please verify:"
    echo "1. Nginx configuration has ACME challenge location block"
    echo "2. Domain DNS points to this server"
    echo "3. Port 80 is open in firewall/security group"
    exit 1
fi

echo -e "${GREEN}✓ ACME challenge path is accessible${NC}\n"

# Step 3: Install SSL certificate
echo -e "${YELLOW}Step 3: Installing SSL certificate...${NC}"
echo "This may take a minute..."

${COMPOSE_CMD} -f ${COMPOSE_FILE} run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email ${EMAIL} \
  --agree-tos \
  --no-eff-email \
  -d ${DOMAIN} \
  -d ${WWW_DOMAIN}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SSL certificate installed successfully${NC}\n"
else
    echo -e "${RED}Error: SSL certificate installation failed${NC}"
    echo "Check the error messages above for details"
    exit 1
fi

# Step 4: Update nginx config for HTTPS
echo -e "${YELLOW}Step 4: Updating Nginx configuration for HTTPS...${NC}"

# Check if HTTPS config exists
if [ -f "nginx/peeq.conf.https" ]; then
    echo "Found HTTPS configuration template, updating..."
    cp nginx/peeq.conf.https nginx/peeq.conf
    echo -e "${GREEN}✓ Nginx configuration updated${NC}\n"
else
    echo -e "${YELLOW}Warning: HTTPS config template not found${NC}"
    echo "You'll need to manually update nginx/peeq.conf to include HTTPS server block"
    echo "See nginx/peeq.conf.https for reference"
    echo ""
    read -p "Press Enter to continue after updating nginx config manually..."
fi

# Step 5: Test nginx configuration
echo -e "${YELLOW}Step 5: Testing Nginx configuration...${NC}"

${COMPOSE_CMD} -f ${COMPOSE_FILE} exec -T nginx nginx -t || {
    echo -e "${RED}Error: Nginx configuration test failed${NC}"
    echo "Please fix the configuration errors before continuing"
    exit 1
}

echo -e "${GREEN}✓ Nginx configuration is valid${NC}\n"

# Step 6: Restart nginx
echo -e "${YELLOW}Step 6: Restarting Nginx...${NC}"
${COMPOSE_CMD} -f ${COMPOSE_FILE} restart nginx

# Wait a moment for nginx to restart
sleep 2

echo -e "${GREEN}✓ Nginx restarted${NC}\n"

# Step 7: Verify HTTPS
echo -e "${YELLOW}Step 7: Verifying HTTPS...${NC}"

sleep 3  # Give nginx time to fully start

HTTPS_CODE_1=$(curl -s -o /dev/null -w "%{http_code}" -k https://${DOMAIN}/ 2>/dev/null || echo "000")
HTTPS_CODE_2=$(curl -s -o /dev/null -w "%{http_code}" -k https://${WWW_DOMAIN}/ 2>/dev/null || echo "000")

if [ "$HTTPS_CODE_1" = "200" ] || [ "$HTTPS_CODE_1" = "301" ] || [ "$HTTPS_CODE_1" = "302" ]; then
    echo -e "${GREEN}✓ HTTPS is working for ${DOMAIN} (HTTP ${HTTPS_CODE_1})${NC}"
else
    echo -e "${YELLOW}Warning: HTTPS check for ${DOMAIN} returned ${HTTPS_CODE_1}${NC}"
fi

if [ "$HTTPS_CODE_2" = "200" ] || [ "$HTTPS_CODE_2" = "301" ] || [ "$HTTPS_CODE_2" = "302" ]; then
    echo -e "${GREEN}✓ HTTPS is working for ${WWW_DOMAIN} (HTTP ${HTTPS_CODE_2})${NC}"
else
    echo -e "${YELLOW}Warning: HTTPS check for ${WWW_DOMAIN} returned ${HTTPS_CODE_2}${NC}"
fi

echo ""
echo -e "${GREEN}=== SSL Installation Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Update your .env file: SHOPIFY_REDIRECT_URI=https://${DOMAIN}/auth/callback"
echo "2. Test your application: curl https://${DOMAIN}/"
echo "3. Set up certificate auto-renewal (see PRODUCTION.md)"
echo ""

