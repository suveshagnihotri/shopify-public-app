# Fixing Compliance Webhook Checks

This guide addresses the two failing automated checks:
1. "Provides mandatory compliance webhooks" ❌
2. "Verifies webhooks with HMAC signatures" ❌

## Issue Analysis

Shopify's automated checks test whether:
1. Your app has the mandatory compliance webhooks registered
2. Your app correctly verifies webhook signatures (returns 401 for invalid signatures)

## Solutions

### Solution 1: Ensure Webhooks Are Registered

**The webhooks are now automatically registered** when a shop installs your app (in the OAuth callback).

However, Shopify's automated checks run before any shop installs, so you need to **register them manually** for testing:

#### Option A: Register via Partner Dashboard

1. Go to **Shopify Partner Dashboard** → **Your App** → **App setup**
2. Navigate to **Webhooks** section
3. Add these three webhooks:

   **Webhook 1:**
   - Topic: `customers/data_request`
   - Format: JSON
   - Callback URL: `https://peeq.co.in/webhooks/customers/data_request`

   **Webhook 2:**
   - Topic: `customers/redact`
   - Format: JSON
   - Callback URL: `https://peeq.co.in/webhooks/customers/redact`

   **Webhook 3:**
   - Topic: `shop/redact`
   - Format: JSON
   - Callback URL: `https://peeq.co.in/webhooks/shop/redact`

4. Click **Save** for each webhook

#### Option B: Register via API (for a test shop)

```bash
# Get access token from a test shop first (install app on dev store)
SHOP_DOMAIN="your-dev-shop.myshopify.com"
ACCESS_TOKEN="your_access_token"
APP_URL="https://peeq.co.in"

# Register customers/data_request
curl -X POST \
  "https://${SHOP_DOMAIN}/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "customers/data_request",
      "address": "'"${APP_URL}"'/webhooks/customers/data_request",
      "format": "json"
    }
  }'

# Register customers/redact
curl -X POST \
  "https://${SHOP_DOMAIN}/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "customers/redact",
      "address": "'"${APP_URL}"'/webhooks/customers/redact",
      "format": "json"
    }
  }'

# Register shop/redact
curl -X POST \
  "https://${SHOP_DOMAIN}/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "shop/redact",
      "address": "'"${APP_URL}"'/webhooks/shop/redact",
      "format": "json"
    }
  }'
```

### Solution 2: Verify HMAC Signature Verification Works

Shopify tests if your app returns `401 Unauthorized` when an invalid signature is sent.

**The HMAC verification has been fixed** to correctly:
- Calculate HMAC-SHA256 on raw body
- Encode to base64
- Compare with Shopify's base64-encoded signature
- Return 401 for invalid signatures

**Test the verification:**

```bash
# Test with invalid signature (should return 401)
curl -X POST https://peeq.co.in/webhooks/customers/data_request \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: invalid_signature" \
  -d '{"shop_domain": "test.myshopify.com"}'

# Should return: HTTP 401
```

If it doesn't return 401, check:
1. `WEBHOOK_SECRET` is set in `.env`
2. The app is using the correct secret
3. HMAC verification logic is correct

### Solution 3: Verify Webhooks Are Accessible

Ensure your webhooks are publicly accessible:

```bash
# Test if webhooks are reachable
curl -I https://peeq.co.in/webhooks/customers/data_request
curl -I https://peeq.co.in/webhooks/customers/redact
curl -I https://peeq.co.in/webhooks/shop/redact
```

All should return HTTP responses (not connection refused).

### Solution 4: Check Environment Variables

Ensure these are set correctly in your `.env` file:

```bash
# Required for webhook HMAC verification
WEBHOOK_SECRET=your_webhook_secret_from_shopify

# Required for webhook registration
SHOPIFY_REDIRECT_URI=https://peeq.co.in/auth/callback
APP_URL=https://peeq.co.in
```

**Get WEBHOOK_SECRET:**
1. Go to **Shopify Partner Dashboard** → **Your App**
2. Go to **App setup** → **API credentials**
3. Copy the **Webhook signing secret** (this is your `WEBHOOK_SECRET`)

### Solution 5: Rebuild and Restart Services

After making changes:

```bash
# Rebuild app image with updated code
docker-compose -f docker-compose.prod.yml build app

# Restart app service
docker-compose -f docker-compose.prod.yml restart app

# Check logs for webhook registration
docker-compose -f docker-compose.prod.yml logs app | grep webhook
```

## Verification Steps

### Step 1: Verify Webhooks Are Registered

Check if webhooks are registered for a shop:

```bash
# List webhooks for a shop (requires access token)
curl -X GET \
  "https://${SHOP_DOMAIN}/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: ${ACCESS_TOKEN}"
```

You should see all three compliance webhooks in the response.

### Step 2: Test HMAC Verification

Use the test script:

```bash
./scripts/test_compliance_webhooks.sh
```

This will test if webhooks return 401 for invalid signatures (correct behavior).

### Step 3: Test Webhook Endpoints Directly

Test each webhook endpoint:

```bash
# Test customers/data_request (should return 401 with invalid signature)
curl -X POST https://peeq.co.in/webhooks/customers/data_request \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: test" \
  -d '{"shop_domain": "test.myshopify.com"}'

# Should return: {"error": "Invalid signature"} with HTTP 401
```

### Step 4: Check App Logs

Monitor webhook logs:

```bash
docker-compose -f docker-compose.prod.yml logs -f app | grep -i webhook
```

Look for:
- "Invalid webhook signature" messages (when testing with invalid signatures)
- "Registered webhook" messages (during OAuth install)
- Any errors related to webhooks

## Common Issues

### Issue: "Provides mandatory compliance webhooks" Still Failing

**Possible Causes:**
1. Webhooks not registered in Partner Dashboard
2. Webhook URLs are incorrect
3. Webhooks registered to wrong shop (check Partner Dashboard)
4. Shopify can't reach your webhook URLs (firewall/network issue)

**Solution:**
1. Manually register webhooks in Partner Dashboard (see Solution 1)
2. Verify webhook URLs match exactly: `https://peeq.co.in/webhooks/...`
3. Test webhook accessibility (see Solution 3)

### Issue: "Verifies webhooks with HMAC signatures" Still Failing

**Possible Causes:**
1. `WEBHOOK_SECRET` not set or incorrect
2. HMAC verification logic has bugs
3. Webhook returns 200 instead of 401 for invalid signatures
4. Request body parsing issues

**Solution:**
1. Verify `WEBHOOK_SECRET` is set correctly in `.env`
2. Test HMAC verification (see Solution 2)
3. Check webhook logs for verification errors
4. Ensure webhooks return 401 for invalid signatures

## Next Steps

1. **Register webhooks manually** in Partner Dashboard
2. **Set WEBHOOK_SECRET** in `.env` file (get it from Partner Dashboard)
3. **Rebuild and restart** the app service
4. **Test webhooks** using the test script
5. **Re-run automated checks** in Partner Dashboard
6. **Check logs** if checks still fail

## Additional Notes

- Shopify's automated checks may take a few minutes to complete
- The checks run against your production URL (`https://peeq.co.in`)
- Make sure your app is running and accessible when Shopify tests
- Webhooks will be automatically registered when shops install your app (in OAuth callback)

## Testing Checklist

- [ ] Webhooks registered in Partner Dashboard
- [ ] `WEBHOOK_SECRET` set in `.env`
- [ ] Webhook endpoints accessible via HTTPS
- [ ] Webhooks return 401 for invalid signatures
- [ ] Webhooks return 200 for valid requests
- [ ] App logs show webhook registration during OAuth
- [ ] App logs show webhook verification working

