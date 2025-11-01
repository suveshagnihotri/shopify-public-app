#!/bin/bash

# Test Compliance Webhooks Script
# Tests if compliance webhooks are accessible and responding correctly

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_URL="${APP_URL:-https://peeq.co.in}"

echo -e "${BLUE}=== Testing Compliance Webhooks ===${NC}\n"

# Test customers/data_request
echo -e "${YELLOW}Testing customers/data_request...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "${APP_URL}/webhooks/customers/data_request" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: test_signature" \
  -d '{
    "shop_id": 12345,
    "shop_domain": "test-shop.myshopify.com",
    "customer": {"id": 123},
    "orders_requested": [],
    "data_request": {"id": 999}
  }')

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Webhook is accessible and returns 401 for invalid signature (correct behavior)${NC}"
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${YELLOW}⚠ Webhook returns 200 (may not verify signature - check WEBHOOK_SECRET)${NC}"
else
    echo -e "${RED}✗ Webhook returned HTTP ${HTTP_CODE}${NC}"
fi

echo ""

# Test customers/redact
echo -e "${YELLOW}Testing customers/redact...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "${APP_URL}/webhooks/customers/redact" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: test_signature" \
  -d '{
    "shop_id": 12345,
    "shop_domain": "test-shop.myshopify.com",
    "customer": {"id": 123},
    "orders_to_redact": []
  }')

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Webhook is accessible and returns 401 for invalid signature (correct behavior)${NC}"
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${YELLOW}⚠ Webhook returns 200 (may not verify signature - check WEBHOOK_SECRET)${NC}"
else
    echo -e "${RED}✗ Webhook returned HTTP ${HTTP_CODE}${NC}"
fi

echo ""

# Test shop/redact
echo -e "${YELLOW}Testing shop/redact...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "${APP_URL}/webhooks/shop/redact" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: test_signature" \
  -d '{
    "shop_id": 12345,
    "shop_domain": "test-shop.myshopify.com"
  }')

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Webhook is accessible and returns 401 for invalid signature (correct behavior)${NC}"
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${YELLOW}⚠ Webhook returns 200 (may not verify signature - check WEBHOOK_SECRET)${NC}"
else
    echo -e "${RED}✗ Webhook returned HTTP ${HTTP_CODE}${NC}"
fi

echo ""
echo -e "${BLUE}=== Test Complete ===${NC}\n"
echo "Note: These tests use invalid signatures."
echo "In production, Shopify will send valid signatures with proper HMAC."
echo ""
echo "To verify webhooks are registered, check Partner Dashboard → App → Webhooks"

