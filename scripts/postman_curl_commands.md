# Postman Curl Commands for API Testing

Base URL: `http://localhost:5000` (or your production URL)

---

## 1. Home Page (GET)

```bash
curl --location 'http://localhost:5000/'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/`

---

## 2. OAuth Initiation (GET)

```bash
curl --location 'http://localhost:5000/auth?shop=your-shop.myshopify.com'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/auth?shop=your-shop.myshopify.com`

**Note:** This will redirect to Shopify's OAuth page.

---

## 3. OAuth Callback (GET)

```bash
curl --location 'http://localhost:5000/auth/callback?code=AUTH_CODE&shop=your-shop.myshopify.com&state=STATE_PARAMETER'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/auth/callback`
- Query Params:
  - `code`: AUTH_CODE (from Shopify)
  - `shop`: your-shop.myshopify.com
  - `state`: STATE_PARAMETER (must match the state from /auth)

---

## 4. Get Products (GET)

```bash
curl --location 'http://localhost:5000/api/products?shop=your-shop.myshopify.com'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/api/products`
- Query Params:
  - `shop`: your-shop.myshopify.com

---

## 5. Get Orders (GET)

```bash
curl --location 'http://localhost:5000/api/orders?shop=your-shop.myshopify.com'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/api/orders`
- Query Params:
  - `shop`: your-shop.myshopify.com

---

## 6. Get Inventory (GET)

```bash
curl --location 'http://localhost:5000/api/inventory?shop=your-shop.myshopify.com'
```

**Postman Import:**
- Method: GET
- URL: `http://localhost:5000/api/inventory`
- Query Params:
  - `shop`: your-shop.myshopify.com

---

## 7. Sync Products (POST)

```bash
curl --location 'http://localhost:5000/api/sync/products' \
--header 'Content-Type: application/json' \
--data '{
    "shop": "your-shop.myshopify.com"
}'
```

**Postman Import:**
- Method: POST
- URL: `http://localhost:5000/api/sync/products`
- Headers:
  - `Content-Type`: application/json
- Body (raw JSON):
```json
{
    "shop": "your-shop.myshopify.com"
}
```

---

## 8. Sync Orders (POST)

```bash
curl --location 'http://localhost:5000/api/sync/orders' \
--header 'Content-Type: application/json' \
--data '{
    "shop": "your-shop.myshopify.com"
}'
```

**Postman Import:**
- Method: POST
- URL: `http://localhost:5000/api/sync/orders`
- Headers:
  - `Content-Type`: application/json
- Body (raw JSON):
```json
{
    "shop": "your-shop.myshopify.com"
}
```

---

## 9. Webhook - Product Create (POST)

```bash
curl --location 'http://localhost:5000/webhooks/products/create' \
--header 'Content-Type: application/json' \
--header 'X-Shopify-Hmac-Sha256: YOUR_WEBHOOK_SECRET_HASH' \
--data '{
    "id": 1234567890,
    "title": "Test Product",
    "handle": "test-product",
    "vendor": "Test Vendor",
    "product_type": "Test Type",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
}'
```

**Postman Import:**
- Method: POST
- URL: `http://localhost:5000/webhooks/products/create`
- Headers:
  - `Content-Type`: application/json
  - `X-Shopify-Hmac-Sha256`: YOUR_WEBHOOK_SECRET_HASH (optional for testing)
- Body (raw JSON):
```json
{
    "id": 1234567890,
    "title": "Test Product",
    "handle": "test-product",
    "vendor": "Test Vendor",
    "product_type": "Test Type",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
}
```

---

## 10. Webhook - Order Create (POST)

```bash
curl --location 'http://localhost:5000/webhooks/orders/create' \
--header 'Content-Type: application/json' \
--header 'X-Shopify-Hmac-Sha256: YOUR_WEBHOOK_SECRET_HASH' \
--data '{
    "id": 9876543210,
    "order_number": 1001,
    "financial_status": "paid",
    "total_price": "99.99",
    "currency": "USD",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "line_items": [
        {
            "id": 1111111111,
            "product_id": 1234567890,
            "variant_id": 2222222222,
            "title": "Test Product",
            "quantity": 1,
            "price": "99.99"
        }
    ]
}'
```

**Postman Import:**
- Method: POST
- URL: `http://localhost:5000/webhooks/orders/create`
- Headers:
  - `Content-Type`: application/json
  - `X-Shopify-Hmac-Sha256`: YOUR_WEBHOOK_SECRET_HASH (optional for testing)
- Body (raw JSON):
```json
{
    "id": 9876543210,
    "order_number": 1001,
    "financial_status": "paid",
    "total_price": "99.99",
    "currency": "USD",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "line_items": [
        {
            "id": 1111111111,
            "product_id": 1234567890,
            "variant_id": 2222222222,
            "title": "Test Product",
            "quantity": 1,
            "price": "99.99"
        }
    ]
}
```

---

## Postman Collection Import

To import these into Postman:

1. **Create New Collection**: In Postman, create a new collection called "Shopify Public App API"
2. **Add Requests**: Create requests for each endpoint above
3. **Set Variables**: 
   - Create an environment variable `base_url` = `http://localhost:5000`
   - Create an environment variable `shop` = `your-shop.myshopify.com`
   - Use them in URLs like: `{{base_url}}/api/products?shop={{shop}}`

## Environment Variables for Postman

Create a Postman environment with:
- `base_url`: `http://localhost:5000` (or `https://your-domain.com`)
- `shop`: `your-shop.myshopify.com`
- `webhook_secret`: Your webhook secret (for webhook tests)

---

## Quick Test Checklist

- [ ] Home page responds (GET /)
- [ ] OAuth initiation redirects (GET /auth)
- [ ] Products API returns data or proper error (GET /api/products)
- [ ] Orders API returns data or proper error (GET /api/orders)
- [ ] Inventory API returns data or proper error (GET /api/inventory)
- [ ] Product sync initiates (POST /api/sync/products)
- [ ] Order sync initiates (POST /api/sync/orders)
- [ ] Product webhook processes (POST /webhooks/products/create)
- [ ] Order webhook processes (POST /webhooks/orders/create)

