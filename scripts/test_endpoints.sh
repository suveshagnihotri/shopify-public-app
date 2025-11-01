#!/usr/bin/env bash
set -euo pipefail

# Configuration
BASE_URL="${BASE_URL:-http://localhost}"
PORT="${PORT:-5000}"
FULL_URL="${BASE_URL}:${PORT}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "API Endpoint Tests"
echo "=========================================="
echo "Testing against: ${FULL_URL}"
echo ""

# Test 1: Home page
echo -e "${YELLOW}[1] Testing Home Page (GET /)${NC}"
echo "Command: curl -I ${FULL_URL}/"
echo "----------------------------------------"
curl -s -w "\nHTTP Status: %{http_code}\n" -o /dev/null "${FULL_URL}/" && echo -e "${GREEN}✅ Home page is accessible${NC}" || echo -e "${RED}❌ Home page failed${NC}"
echo ""

# Test 2: OAuth initiation (redirects, so use -L)
echo -e "${YELLOW}[2] Testing OAuth Initiation (GET /auth?shop=test-shop.myshopify.com)${NC}"
echo "Command: curl -L -I ${FULL_URL}/auth?shop=test-shop.myshopify.com"
echo "----------------------------------------"
HTTP_CODE=$(curl -s -w "%{http_code}" -o /dev/null "${FULL_URL}/auth?shop=test-shop.myshopify.com")
if [[ "$HTTP_CODE" == "302" ]] || [[ "$HTTP_CODE" == "301" ]] || [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ OAuth endpoint responds (HTTP ${HTTP_CODE})${NC}"
else
  echo -e "${RED}❌ OAuth endpoint failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 3: Products API (requires shop parameter and authentication)
echo -e "${YELLOW}[3] Testing Products API (GET /api/products?shop=test-shop.myshopify.com)${NC}"
echo "Command: curl ${FULL_URL}/api/products?shop=test-shop.myshopify.com"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${FULL_URL}/api/products?shop=test-shop.myshopify.com")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Products API working${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
  echo -e "${YELLOW}⚠️  Products API: Shop not found (expected if shop not authenticated)${NC}"
elif [[ "$HTTP_CODE" == "400" ]]; then
  echo -e "${YELLOW}⚠️  Products API: Bad request (shop parameter required)${NC}"
else
  echo -e "${RED}❌ Products API failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 4: Orders API
echo -e "${YELLOW}[4] Testing Orders API (GET /api/orders?shop=test-shop.myshopify.com)${NC}"
echo "Command: curl ${FULL_URL}/api/orders?shop=test-shop.myshopify.com"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${FULL_URL}/api/orders?shop=test-shop.myshopify.com")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Orders API working${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
  echo -e "${YELLOW}⚠️  Orders API: Shop not found (expected if shop not authenticated)${NC}"
else
  echo -e "${RED}❌ Orders API failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 5: Inventory API
echo -e "${YELLOW}[5] Testing Inventory API (GET /api/inventory?shop=test-shop.myshopify.com)${NC}"
echo "Command: curl ${FULL_URL}/api/inventory?shop=test-shop.myshopify.com"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${FULL_URL}/api/inventory?shop=test-shop.myshopify.com")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Inventory API working${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
  echo -e "${YELLOW}⚠️  Inventory API: Shop not found (expected if shop not authenticated)${NC}"
else
  echo -e "${RED}❌ Inventory API failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 6: Sync Products API (POST)
echo -e "${YELLOW}[6] Testing Sync Products API (POST /api/sync/products)${NC}"
echo "Command: curl -X POST -H 'Content-Type: application/json' -d '{\"shop\":\"test-shop.myshopify.com\"}' ${FULL_URL}/api/sync/products"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST -H "Content-Type: application/json" -d '{"shop":"test-shop.myshopify.com"}' "${FULL_URL}/api/sync/products")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Sync Products API working${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
  echo -e "${YELLOW}⚠️  Sync Products API: Shop not found (expected if shop not authenticated)${NC}"
else
  echo -e "${RED}❌ Sync Products API failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 7: Sync Orders API (POST)
echo -e "${YELLOW}[7] Testing Sync Orders API (POST /api/sync/orders)${NC}"
echo "Command: curl -X POST -H 'Content-Type: application/json' -d '{\"shop\":\"test-shop.myshopify.com\"}' ${FULL_URL}/api/sync/orders"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST -H "Content-Type: application/json" -d '{"shop":"test-shop.myshopify.com"}' "${FULL_URL}/api/sync/orders")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Sync Orders API working${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
  echo -e "${YELLOW}⚠️  Sync Orders API: Shop not found (expected if shop not authenticated)${NC}"
else
  echo -e "${RED}❌ Sync Orders API failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 8: Webhook Products Create (POST)
echo -e "${YELLOW}[8] Testing Webhook Products Create (POST /webhooks/products/create)${NC}"
echo "Command: curl -X POST -H 'Content-Type: application/json' -d '{\"id\":123,\"title\":\"Test Product\"}' ${FULL_URL}/webhooks/products/create"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST -H "Content-Type: application/json" -d '{"id":123,"title":"Test Product"}' "${FULL_URL}/webhooks/products/create")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Webhook Products Create API working${NC}"
elif [[ "$HTTP_CODE" == "401" ]]; then
  echo -e "${YELLOW}⚠️  Webhook Products Create: Invalid signature (expected without proper webhook secret)${NC}"
else
  echo -e "${RED}❌ Webhook Products Create failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

# Test 9: Webhook Orders Create (POST)
echo -e "${YELLOW}[9] Testing Webhook Orders Create (POST /webhooks/orders/create)${NC}"
echo "Command: curl -X POST -H 'Content-Type: application/json' -d '{\"id\":456,\"order_number\":\"1234\"}' ${FULL_URL}/webhooks/orders/create"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST -H "Content-Type: application/json" -d '{"id":456,"order_number":"1234"}' "${FULL_URL}/webhooks/orders/create")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}✅ Webhook Orders Create API working${NC}"
elif [[ "$HTTP_CODE" == "401" ]]; then
  echo -e "${YELLOW}⚠️  Webhook Orders Create: Invalid signature (expected without proper webhook secret)${NC}"
else
  echo -e "${RED}❌ Webhook Orders Create failed (HTTP ${HTTP_CODE})${NC}"
fi
echo ""

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "💡 Usage Examples:"
echo ""
echo "# Test with custom URL and port:"
echo "BASE_URL=https://your-domain.com PORT=443 ./scripts/test_endpoints.sh"
echo ""
echo "# Test local development:"
echo "BASE_URL=http://localhost PORT=5000 ./scripts/test_endpoints.sh"
echo ""
echo "# Direct curl commands:"
echo ""
echo "curl ${FULL_URL}/"
echo "curl ${FULL_URL}/auth?shop=your-shop.myshopify.com"
echo "curl ${FULL_URL}/api/products?shop=your-shop.myshopify.com"
echo "curl ${FULL_URL}/api/orders?shop=your-shop.myshopify.com"
echo "curl ${FULL_URL}/api/inventory?shop=your-shop.myshopify.com"
echo "curl -X POST -H 'Content-Type: application/json' -d '{\"shop\":\"your-shop.myshopify.com\"}' ${FULL_URL}/api/sync/products"
echo "curl -X POST -H 'Content-Type: application/json' -d '{\"shop\":\"your-shop.myshopify.com\"}' ${FULL_URL}/api/sync/orders"

