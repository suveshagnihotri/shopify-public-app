# Quick Fix for Failing Compliance Checks

Your automated checks show:
- ❌ "Provides mandatory compliance webhooks"
- ❌ "Verifies webhooks with HMAC signatures"

## Immediate Actions Required

### Step 1: Register Webhooks in Partner Dashboard (CRITICAL)

Shopify's automated checks need webhooks to be registered. Do this first:

1. **Go to Shopify Partner Dashboard**
2. Navigate to **Your App** → **App setup** → **Webhooks**
3. **Add these three webhooks:**

   **Webhook 1:**
   - **Topic**: `customers/data_request`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/customers/data_request`
   - **Save**

   **Webhook 2:**
   - **Topic**: `customers/redact`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/customers/redact`
   - **Save**

   **Webhook 3:**
   - **Topic**: `shop/redact`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/shop/redact`
   - **Save**

### Step 2: Set SHOPIFY_API_SECRET (CRITICAL for HMAC)

**Important**: Shopify uses your **API Secret (Client Secret)** for webhook HMAC verification, not a separate webhook secret.

1. **Verify SHOPIFY_API_SECRET is set:**
   - Go to **Partner Dashboard** → **Your App** → **App setup** → **API credentials**
   - Your **Client secret** is what you need for HMAC verification
   - This should already be set in your `.env` as `SHOPIFY_API_SECRET`

2. **Check `.env` on EC2:**
   ```bash
   # Edit .env file on your EC2 server
   nano .env
   
   # Ensure this is set:
   SHOPIFY_API_SECRET=your_client_secret_from_partner_dashboard
   
   # Optional: Also set WEBHOOK_SECRET (if you use Partner Dashboard webhooks)
   # For Admin API registered webhooks, SHOPIFY_API_SECRET is used automatically
   ```

3. **Restart app service:**
   ```bash
   docker-compose -f docker-compose.prod.yml restart app
   ```

### Step 3: Verify Webhooks Are Accessible

Test if webhooks are reachable:

```bash
# Test each webhook endpoint
curl -I https://peeq.co.in/webhooks/customers/data_request
curl -I https://peeq.co.in/webhooks/customers/redact
curl -I https://peeq.co.in/webhooks/shop/redact
```

All should return HTTP responses (not connection refused).

### Step 4: Test HMAC Verification

Test if webhooks return 401 for invalid signatures:

```bash
# Test with invalid signature (should return 401)
curl -X POST https://peeq.co.in/webhooks/customers/data_request \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: invalid_signature" \
  -d '{"shop_domain": "test.myshopify.com"}'

# Expected: HTTP 401 with {"error": "Invalid signature"}
```

If it returns 200 instead of 401:
- Check `WEBHOOK_SECRET` is set correctly
- Verify app was restarted after setting the secret
- Check app logs for errors

### Step 5: Rebuild App (After Code Changes)

If you just updated the code:

```bash
# On your EC2 server
cd /path/to/shopify_public_app

# Rebuild app image
docker-compose -f docker-compose.prod.yml build app

# Restart app service
docker-compose -f docker-compose.prod.yml restart app

# Check logs
docker-compose -f docker-compose.prod.yml logs app | tail -50
```

### Step 6: Re-run Automated Checks

After completing steps 1-5:

1. Go back to **Partner Dashboard** → **Your App**
2. Scroll to **Automated checks**
3. Click **Run** button
4. Wait for checks to complete (may take a few minutes)

## What Was Fixed

✅ **HMAC Verification** - Fixed to properly compare base64-encoded signatures
✅ **Automatic Registration** - Webhooks now register automatically when shops install
✅ **Webhook Endpoints** - All three compliance webhooks implemented

## Still Failing?

### Check 1: Webhooks Registered?

```bash
# List webhooks for a test shop (requires access token)
curl -X GET \
  "https://your-shop.myshopify.com/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: your_access_token" | jq '.webhooks[] | select(.topic | startswith("customers/") or . == "shop/redact")'
```

You should see all three compliance webhooks.

### Check 2: WEBHOOK_SECRET Set?

```bash
# On EC2, check if WEBHOOK_SECRET is set
docker-compose -f docker-compose.prod.yml exec app env | grep WEBHOOK_SECRET
```

Should show `WEBHOOK_SECRET=your_secret_value`

### Check 3: Webhooks Returning 401 for Invalid Signatures?

Use the test script:

```bash
./scripts/test_compliance_webhooks.sh
```

All webhooks should return 401 for invalid signatures.

### Check 4: App Logs

```bash
# Check for webhook-related errors
docker-compose -f docker-compose.prod.yml logs app | grep -i webhook | tail -50
```

Look for:
- "Invalid webhook signature" messages (when testing)
- "Registered webhook" messages (during OAuth)
- Any errors related to webhooks

## Summary

**The two most critical steps are:**
1. **Register webhooks manually in Partner Dashboard** (Shopify's checks can't find them otherwise)
2. **Set WEBHOOK_SECRET in `.env`** (required for HMAC verification to work)

After these two steps, the automated checks should pass.

