#!/bin/bash

# SSL Certificate Renewal Script
# Run this daily via cron to automatically renew certificates before expiration

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

COMPOSE_FILE="${COMPOSE_CMD}.prod.yml"

echo -e "${GREEN}=== SSL Certificate Renewal Check ===${NC}\n"

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.." || exit 1

# Determine ${COMPOSE_CMD} command
if command -v ${COMPOSE_CMD} &> /dev/null; then
    COMPOSE_CMD="${COMPOSE_CMD}"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: ${COMPOSE_CMD} not found${NC}"
    exit 1
fi

# Check if certificates are close to expiration (within 30 days)
echo "Checking certificate expiration..."

# Renew certificates (certbot will only renew if within 30 days of expiration)
${COMPOSE_CMD} -f ${COMPOSE_FILE} run --rm certbot renew

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Certificate renewal check completed${NC}"
    
    # Check if any certificates were renewed
    if ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs certbot | grep -q "Congratulations"; then
        echo -e "${YELLOW}Certificate(s) were renewed - restarting nginx...${NC}"
        ${COMPOSE_CMD} -f ${COMPOSE_FILE} restart nginx
        echo -e "${GREEN}✓ Nginx restarted with new certificates${NC}"
    else
        echo "Certificates are still valid (not yet due for renewal)"
    fi
else
    echo -e "${RED}Error: Certificate renewal failed${NC}"
    exit 1
fi

echo -e "${GREEN}=== Renewal Check Complete ===${NC}\n"

