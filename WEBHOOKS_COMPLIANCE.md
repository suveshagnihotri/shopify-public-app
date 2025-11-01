# Mandatory Compliance Webhooks Setup Guide

Shopify requires all apps to implement mandatory compliance webhooks for customer privacy (GDPR/CCPA compliance). This guide shows how to set up and register these webhooks.

**Reference Documentation:**
- [Shopify Privacy Law Compliance](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance)
- [Shopify HTTPS Webhooks Best Practices](https://shopify.dev/docs/apps/build/webhooks/subscribe/https)

## Required Webhooks

Shopify requires three mandatory webhooks:

1. **`customers/data_request`** - When a customer requests their data
2. **`customers/redact`** - When a customer requests data deletion
3. **`shop/redact`** - When a shop uninstalls your app (data deletion)

## Implementation Status

✅ All three mandatory webhooks have been implemented in `app.py`:
- `/webhooks/customers/data_request`
- `/webhooks/customers/redact`
- `/webhooks/shop/redact`

## Registering Webhooks with Shopify

### Option 1: Register via Partner Dashboard (Recommended)

1. Go to your Shopify Partner Dashboard
2. Navigate to your app
3. Go to **App setup** → **Webhooks**
4. Add these webhook subscriptions:

**Webhook 1: Customer Data Request**
- Event: `customers/data_request`
- Format: JSON
- Callback URL: `https://peeq.co.in/webhooks/customers/data_request`

**Webhook 2: Customer Redact**
- Event: `customers/redact`
- Format: JSON
- Callback URL: `https://peeq.co.in/webhooks/customers/redact`

**Webhook 3: Shop Redact**
- Event: `shop/redact`
- Format: JSON
- Callback URL: `https://peeq.co.in/webhooks/shop/redact`

5. Save all webhooks

### Option 2: Register Programmatically via API

You can register webhooks programmatically when a shop installs your app. Add this to your OAuth callback handler:

```python
def register_compliance_webhooks(shop_domain, access_token):
    """Register mandatory compliance webhooks with Shopify"""
    
    base_url = f"https://{shop_domain}/admin/api/2023-10/webhooks.json"
    webhook_secret = os.getenv('WEBHOOK_SECRET')
    app_url = os.getenv('SHOPIFY_REDIRECT_URI', '').replace('/auth/callback', '')
    
    webhooks = [
        {
            'topic': 'customers/data_request',
            'address': f'{app_url}/webhooks/customers/data_request',
            'format': 'json'
        },
        {
            'topic': 'customers/redact',
            'address': f'{app_url}/webhooks/customers/redact',
            'format': 'json'
        },
        {
            'topic': 'shop/redact',
            'address': f'{app_url}/webhooks/shop/redact',
            'format': 'json'
        }
    ]
    
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    for webhook in webhooks:
        try:
            response = requests.post(
                base_url,
                json={'webhook': webhook},
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Registered webhook: {webhook['topic']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register webhook {webhook['topic']}: {e}")
```

Then call this function in your `/auth/callback` route after successfully installing the app.

### Option 3: Manual Registration via cURL

Register webhooks manually using cURL:

```bash
# Replace with your shop domain and access token
SHOP_DOMAIN="your-shop.myshopify.com"
ACCESS_TOKEN="your_access_token"
APP_URL="https://peeq.co.in"

# Register customers/data_request webhook
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

# Register customers/redact webhook
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

# Register shop/redact webhook
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

## Verify Webhooks Are Registered

Check if webhooks are registered:

```bash
# List all webhooks for a shop
curl -X GET \
  "https://${SHOP_DOMAIN}/admin/api/2023-10/webhooks.json" \
  -H "X-Shopify-Access-Token: ${ACCESS_TOKEN}"
```

You should see all three mandatory webhooks in the response.

## Testing Webhooks

### Test via Shopify Admin

1. Go to Shopify Admin → Settings → Customer privacy
2. Click "Request customer data" (for data request test)
3. Click "Delete customer data" (for redact test)

### Test via cURL (Simulate Webhook)

```bash
# Test customers/data_request webhook
curl -X POST https://peeq.co.in/webhooks/customers/data_request \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Shop-Domain: your-shop.myshopify.com" \
  -d '{
    "shop_domain": "your-shop.myshopify.com",
    "customer": {"id": 12345},
    "orders_requested": [1, 2, 3]
  }'

# Note: You'll need to generate a proper HMAC signature for production
```

## What Each Webhook Does

### 1. customers/data_request

**When triggered**: When a customer requests their personal data (GDPR right to access)

**Payload structure** (from [Shopify documentation](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance)):
```json
{
    "shop_id": 954889,
    "shop_domain": "{shop}.myshopify.com",
    "orders_requested": [299938, 280263, 220458],
    "customer": {
        "id": 191167,
        "email": "john@example.com",
        "phone": "555-625-1199"
    },
    "data_request": {
        "id": 9999
    }
}
```

**What you must do**:
- Collect all customer data from your database
- Compile it in a format the customer/store owner can access
- Make it available (via email or your app)
- Complete within 30 days of receiving the request

**Current implementation**: Logs the request for compliance tracking. **TODO**: Implement actual data collection and delivery.

### 2. customers/redact

**When triggered**: When a customer requests data deletion (GDPR right to be forgotten)

**Timing**:
- If customer hasn't placed an order in past 6 months: webhook sent 10 days after request
- Otherwise: webhook sent 6 months after request

**Payload structure** (from [Shopify documentation](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance)):
```json
{
    "shop_id": 954889,
    "shop_domain": "{shop}.myshopify.com",
    "customer": {
        "id": 191167,
        "email": "john@example.com",
        "phone": "555-625-1199"
    },
    "orders_to_redact": [299938, 280263, 220458]
}
```

**What you must do**:
- Delete or anonymize all customer personal data
- Delete or anonymize all orders in `orders_to_redact` list
- Delete any other customer-related records
- Complete within 30 days (unless legally required to retain data)

**Current implementation**: Logs the request. **TODO**: Implement actual data deletion/anonymization.

### 3. shop/redact

**When triggered**: 48 hours after a store owner uninstalls your app

**Payload structure** (from [Shopify documentation](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance)):
```json
{
    "shop_id": 954889,
    "shop_domain": "{shop}.myshopify.com"
}
```

**What you must do**:
- Delete all shop-related data from your database
- Delete orders, products, inventory, webhook logs, etc. for that shop
- Delete the shop record itself

**Current implementation**: ✅ Fully implemented - deletes all shop-related data (orders, products, inventory, order line items, webhook logs, shop record)

## Important Notes

According to [Shopify's privacy law compliance requirements](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance):

1. **All webhooks must return HTTP 200 series status code** - If they don't, Shopify will retry
2. **Webhooks must be publicly accessible** - Use HTTPS (`https://peeq.co.in`)
3. **Webhook signature verification** - Must return `401 Unauthorized` if HMAC header is invalid
4. **Response time** - Webhooks should respond within 5 seconds (Shopify timeout)
5. **Completion deadline** - Must complete the action within 30 days of receiving the request
6. **Handle POST requests** - Must handle POST requests with JSON body and `Content-Type: application/json`
7. **Logging** - All webhooks log requests for compliance/audit purposes

## Environment Variables

Ensure these are set in your `.env`:

```bash
WEBHOOK_SECRET=your_webhook_secret_from_shopify
SHOPIFY_REDIRECT_URI=https://peeq.co.in/auth/callback
```

## Troubleshooting

### Webhook not being received

1. Check webhook is registered: List webhooks via API
2. Check URL is correct: Must be `https://peeq.co.in/webhooks/...`
3. Check webhook is publicly accessible
4. Check nginx/proxy allows POST requests
5. Check app logs: `docker-compose -f docker-compose.prod.yml logs app | grep webhook`

### Webhook signature verification failing

1. Check `WEBHOOK_SECRET` is set correctly in `.env`
2. Verify webhook secret matches Shopify Partner Dashboard
3. Check signature calculation in `verify_webhook()` function

### Webhook returns 500 error

1. Check app logs for errors
2. Check database connection is working
3. Verify all models are imported correctly
4. Check Celery worker is running (if using async processing)

## Compliance Checklist

- [x] Implemented `customers/data_request` webhook
- [x] Implemented `customers/redact` webhook
- [x] Implemented `shop/redact` webhook
- [ ] Registered webhooks in Partner Dashboard
- [ ] Tested webhooks (Shopify Admin → Customer privacy)
- [ ] Verified webhook logs are being stored
- [ ] Extended `customers/redact` to actually delete customer data (if you store customer data)
- [ ] Documented data retention policy

## Next Steps

1. **Register webhooks** via Partner Dashboard or programmatically
2. **Test webhooks** using Shopify Admin customer privacy settings
3. **Monitor webhook logs** to ensure they're being received
4. **Extend functionality** if you store additional customer data beyond what's currently handled

For more information, see:
- [Shopify Webhooks Documentation](https://shopify.dev/docs/api/admin-graphql/latest/resources/webhook)
- [GDPR Compliance Guide](https://help.shopify.com/en/manual/your-account/privacy/GDPR)
- [Mandatory Webhooks Guide](https://shopify.dev/docs/apps/webhooks/configuration/mandatory-webhooks)

