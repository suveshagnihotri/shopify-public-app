# Critical Fixes for Failing Compliance Checks

Your automated checks are still failing:
- ❌ "Provides mandatory compliance webhooks"
- ❌ "Verifies webhooks with HMAC signatures"

## ⚠️ CRITICAL: You Must Do These Steps

### Step 1: Register Webhooks in Partner Dashboard (REQUIRED)

**This is the most likely reason for the failure.** Shopify's automated checks look for registered webhooks in your Partner Dashboard.

1. **Go to Shopify Partner Dashboard**
   - Navigate to: https://partners.shopify.com
   - Go to **Apps** → **Your App**

2. **Navigate to Webhooks Section**
   - Click **App setup** tab
   - Scroll to **Webhooks** section
   - Click **Add webhook** or **Edit webhooks**

3. **Add These Three Webhooks:**

   **Webhook 1: Customer Data Request**
   - **Topic**: `customers/data_request`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/customers/data_request`
   - Click **Save**

   **Webhook 2: Customer Redact**
   - **Topic**: `customers/redact`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/customers/redact`
   - Click **Save**

   **Webhook 3: Shop Redact**
   - **Topic**: `shop/redact`
   - **Format**: JSON
   - **Callback URL**: `https://peeq.co.in/webhooks/shop/redact`
   - Click **Save**

4. **Verify All Three Webhooks Are Listed**
   - Check that all three webhooks appear in the list
   - They should show as "Active" or "Enabled"

### Step 2: Verify SHOPIFY_API_SECRET is Set (REQUIRED)

Shopify uses your **Client Secret (API Secret)** for webhook HMAC verification.

1. **Get Your Client Secret:**
   - Go to **Partner Dashboard** → **Your App** → **App setup** → **API credentials**
   - Copy the **Client secret** value

2. **Set in `.env` on Your EC2 Server:**
   ```bash
   # On your EC2 server
   cd /path/to/shopify_public_app
   nano .env
   
   # Ensure this line is set correctly:
   SHOPIFY_API_SECRET=your_client_secret_from_partner_dashboard
   ```

3. **Verify It's Loaded:**
   ```bash
   # Check if secret is loaded in app container
   docker-compose -f docker-compose.prod.yml exec app env | grep SHOPIFY_API_SECRET
   ```

4. **Restart App:**
   ```bash
   docker-compose -f docker-compose.prod.yml restart app
   ```

### Step 3: Verify Webhooks Are Accessible

Test if Shopify can reach your webhooks:

```bash
# Test each endpoint (from anywhere on internet)
curl -I https://peeq.co.in/webhooks/customers/data_request
curl -I https://peeq.co.in/webhooks/customers/redact
curl -I https://peeq.co.in/webhooks/shop/redact
```

All should return HTTP responses (200 or 405 for GET on POST-only endpoints).

### Step 4: Test HMAC Verification

Test if webhooks correctly reject invalid signatures:

```bash
# Test with invalid signature (should return 401)
curl -v -X POST https://peeq.co.in/webhooks/customers/data_request \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: invalid_signature" \
  -d '{"shop_domain": "test.myshopify.com"}'

# Expected: HTTP 401 with {"error": "Invalid signature"}
```

If it returns 200 instead of 401:
- Check `SHOPIFY_API_SECRET` is set in `.env`
- Restart app service
- Check logs for HMAC errors

### Step 5: Rebuild App After Code Changes

If you just updated the code:

```bash
# On your EC2 server
cd /path/to/shopify_public_app

# Rebuild app image
docker-compose -f docker-compose.prod.yml build app

# Restart services
docker-compose -f docker-compose.prod.yml restart app

# Check logs
docker-compose -f docker-compose.prod.yml logs app | tail -50
```

### Step 6: Re-run Automated Checks

After completing Steps 1-5:

1. **Go to Partner Dashboard** → **Your App**
2. **Scroll to "Automated checks for common errors"**
3. **Click the "Run" button**
4. **Wait 2-5 minutes** for checks to complete
5. **Check the results**

## Common Mistakes

### Mistake 1: Not Registering Webhooks

**Symptom**: "Provides mandatory compliance webhooks" fails

**Cause**: Webhooks aren't registered in Partner Dashboard

**Fix**: Complete Step 1 above - register all three webhooks manually

### Mistake 2: Wrong Secret for HMAC

**Symptom**: "Verifies webhooks with HMAC signatures" fails

**Cause**: Using wrong secret or secret not set

**Fix**: 
- Use `SHOPIFY_API_SECRET` (your Client Secret)
- NOT a separate WEBHOOK_SECRET (unless specified in Partner Dashboard)
- Complete Step 2 above

### Mistake 3: Webhooks Not Accessible

**Symptom**: Both checks fail

**Cause**: Webhooks can't be reached from internet

**Fix**: 
- Verify HTTPS is working: `curl -I https://peeq.co.in`
- Check nginx is running: `docker-compose -f docker-compose.prod.yml ps nginx`
- Check app is running: `docker-compose -f docker-compose.prod.yml ps app`
- Complete Step 3 above

## Verification Checklist

Before re-running automated checks, verify:

- [ ] All three webhooks registered in Partner Dashboard → App setup → Webhooks
- [ ] `SHOPIFY_API_SECRET` is set correctly in `.env`
- [ ] App service is running: `docker-compose -f docker-compose.prod.yml ps app`
- [ ] Nginx service is running: `docker-compose -f docker-compose.prod.yml ps nginx`
- [ ] Webhooks are accessible: `curl -I https://peeq.co.in/webhooks/customers/data_request`
- [ ] HMAC verification works: Invalid signature returns 401
- [ ] App logs show no errors: `docker-compose -f docker-compose.prod.yml logs app | tail -50`

## Still Failing?

If checks still fail after completing all steps:

1. **Check App Logs:**
   ```bash
   docker-compose -f docker-compose.prod.yml logs app | grep -i webhook
   ```

2. **Check Webhook Registration:**
   - Go to Partner Dashboard → Your App → App setup → Webhooks
   - Verify all three compliance webhooks are listed
   - Check their status (should be "Active" or "Enabled")

3. **Test Webhooks Manually:**
   ```bash
   # Test each webhook with a valid signature (requires generating HMAC)
   # Or use the test script:
   ./scripts/test_compliance_webhooks.sh
   ```

4. **Contact Shopify Support:**
   - If all steps are completed but checks still fail
   - Provide details about webhook registration
   - Share app logs if possible

## Important Notes

- **Webhooks must be registered in Partner Dashboard** for automated checks to pass
- **HMAC verification uses SHOPIFY_API_SECRET** (your Client Secret)
- **All webhooks must be publicly accessible** via HTTPS
- **Webhooks must return 401 for invalid signatures** to pass HMAC check
- **Automated checks can take 2-5 minutes** to complete

