# Shopify Public App - Data Management System

A comprehensive Shopify public app built with Python Flask that provides catalog, inventory, pricing, and orders data management with push/pull capabilities.

## Features

- 🔐 **OAuth Authentication** - Secure Shopify app authentication
- 📦 **Product Management** - Fetch, sync, and manage product catalogs
- 📊 **Inventory Tracking** - Real-time inventory level monitoring
- 🛒 **Order Processing** - Pull and push order data
- 🔄 **Bidirectional Sync** - Real-time data synchronization
- 📡 **Webhook Support** - Instant updates via webhooks
- ⚡ **Background Tasks** - Celery-powered async processing
- 🐳 **Docker Ready** - Containerized deployment

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Shopify API   │◄──►│   Flask App     │◄──►│   PostgreSQL    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │     Redis       │
                       │   (Celery)      │
                       └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Shopify Partner Account

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd shopify_public_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

2. **Run in production**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SHOPIFY_API_KEY` | Your Shopify app API key | Yes |
| `SHOPIFY_API_SECRET` | Your Shopify app secret | Yes |
| `SHOPIFY_SCOPES` | Required permissions | Yes |
| `SHOPIFY_REDIRECT_URI` | OAuth redirect URI | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `SECRET_KEY` | Flask secret key | Yes |
| `WEBHOOK_SECRET` | Webhook verification secret | Yes |

### Shopify App Setup

1. **Create a Shopify Partner Account**
   - Go to [partners.shopify.com](https://partners.shopify.com)
   - Create a new app

2. **Configure App Settings**
   - Set App URL: `https://your-domain.com`
   - Set Allowed redirection URL: `https://your-domain.com/auth/callback`
   - Enable required scopes:
     - `read_products`
     - `write_products`
     - `read_orders`
     - `write_orders`
     - `read_inventory`
     - `write_inventory`

3. **Set up Webhooks**
   - Product creation: `https://your-domain.com/webhooks/products/create`
   - Order creation: `https://your-domain.com/webhooks/orders/create`

## API Endpoints

### Authentication

- `GET /auth?shop=your-shop.myshopify.com` - Initiate OAuth flow
- `GET /auth/callback` - OAuth callback handler

### Data Fetching

- `GET /api/products?shop=your-shop.myshopify.com` - Fetch products
- `GET /api/orders?shop=your-shop.myshopify.com` - Fetch orders
- `GET /api/inventory?shop=your-shop.myshopify.com` - Fetch inventory levels

### Data Synchronization

- `POST /api/sync/products` - Sync products to local database
- `POST /api/sync/orders` - Sync orders to local database
- `POST /api/sync/inventory` - Sync inventory levels

### Webhooks

- `POST /webhooks/products/create` - Product creation webhook
- `POST /webhooks/orders/create` - Order creation webhook

## Usage Examples

### Fetching Products

```python
import requests

# Fetch products from a shop
response = requests.get(
    'https://your-app.com/api/products',
    params={'shop': 'your-shop.myshopify.com'}
)
products = response.json()['products']
```

### Syncing Data

```python
# Sync products to local database
response = requests.post(
    'https://your-app.com/api/sync/products',
    json={'shop': 'your-shop.myshopify.com'}
)
```

### Creating Products

```python
from shopify_client import ShopifyClient

client = ShopifyClient('your-shop.myshopify.com', 'access_token')

product_data = {
    'title': 'New Product',
    'body_html': '<p>Product description</p>',
    'vendor': 'Your Vendor',
    'product_type': 'Electronics',
    'variants': [{
        'title': 'Default Title',
        'price': '29.99',
        'sku': 'PROD-001',
        'inventory_quantity': 100
    }]
}

result = client.create_product(product_data)
```

## Database Schema

### Core Tables

- `shops` - Authenticated Shopify stores
- `product_sync` - Synced products
- `product_variants` - Product variants
- `order_sync` - Synced orders
- `order_line_items` - Order line items
- `inventory_levels` - Inventory levels
- `webhook_logs` - Webhook processing logs

## Background Tasks

The app uses Celery for background processing:

- **Product Sync** - Syncs products from Shopify
- **Order Sync** - Syncs orders from Shopify
- **Inventory Sync** - Syncs inventory levels
- **Webhook Processing** - Processes incoming webhooks

### Running Celery Worker

```bash
celery -A celery_app worker --loglevel=info
```

### Running Celery Beat (for scheduled tasks)

```bash
celery -A celery_app beat --loglevel=info
```

## Security

- OAuth 2.0 authentication with Shopify
- Webhook signature verification
- SQL injection protection via SQLAlchemy ORM
- Environment variable configuration
- Non-root Docker container

## Monitoring

- Webhook processing logs
- Background task status tracking
- Error logging and reporting
- Database connection monitoring

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Formatting

```bash
black .
isort .
```

### Database Migrations

```bash
# Create migration
flask db migrate -m "Description"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

## Deployment

### Production Checklist

- [ ] Set up PostgreSQL database
- [ ] Configure Redis instance
- [ ] Set up SSL certificates
- [ ] Configure environment variables
- [ ] Set up monitoring and logging
- [ ] Configure webhook endpoints
- [ ] Test OAuth flow
- [ ] Set up backup strategy

### Scaling

- Use multiple Celery workers
- Implement database connection pooling
- Add Redis clustering for high availability
- Use load balancer for multiple app instances

## Troubleshooting

### Common Issues

1. **OAuth Authentication Fails**
   - Check API key and secret
   - Verify redirect URI configuration
   - Ensure HTTPS is enabled

2. **Webhook Verification Fails**
   - Check webhook secret configuration
   - Verify webhook URL accessibility
   - Check webhook payload format

3. **Database Connection Issues**
   - Verify DATABASE_URL format
   - Check database server status
   - Ensure proper permissions

4. **Celery Tasks Not Processing**
   - Check Redis connection
   - Verify worker is running
   - Check task queue status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review Shopify API documentation

## Changelog

### Version 1.0.0
- Initial release
- OAuth authentication
- Product, order, and inventory management
- Webhook support
- Background task processing
- Docker deployment
