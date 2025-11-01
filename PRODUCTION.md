# Production Deployment Guide

This guide walks you through deploying the Shopify Public App to production.

## Prerequisites

1. **Docker and Docker Compose** installed
2. **Domain name** configured (for production)
3. **Environment variables** configured in `.env` file

## Quick Start

```bash
# 1. Build and start production services
./scripts/start_prod.sh

# 2. Check service status
./scripts/check_prod.sh

# 3. Test endpoints
./scripts/test_endpoints.sh
```

## Step-by-Step Deployment

### 1. Configure Environment Variables

Copy the example environment file and update it:

```bash
cp env.example .env
```

Edit `.env` with your production values:

```bash
# Shopify App Configuration
SHOPIFY_API_KEY=your_production_api_key
SHOPIFY_API_SECRET=your_production_api_secret
SHOPIFY_SCOPES=read_products,write_products,read_orders,write_orders,read_inventory,write_inventory
SHOPIFY_REDIRECT_URI=https://your-domain.com/auth/callback

# App Configuration
FLASK_ENV=production
SECRET_KEY=your_strong_secret_key_here  # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
WEBHOOK_SECRET=your_webhook_secret_here

# Database Configuration (for Docker Compose, use service name)
DATABASE_URL=postgresql://postgres:password@db:5432/shopify_app_db

# Redis Configuration (for Docker Compose, use service name)
REDIS_URL=redis://redis:6379/0
```

### 2. Update Nginx Configuration

Edit `nginx/peeq.conf` and replace `peeq.co.in` with your domain:

```bash
sed -i '' 's/peeq.co.in/your-domain.com/g' nginx/peeq.conf
```

### 3. Build and Start Services

**Option A: Use the start script (Recommended)**
```bash
./scripts/start_prod.sh
```

**Option B: Manual steps**
```bash
# Build images
DOCKER_BUILDKIT=0 docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
docker-compose -f docker-compose.prod.yml exec app flask db upgrade

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### 4. Run Database Migrations

If this is a fresh deployment:

```bash
# Initialize database (first time only)
docker-compose -f docker-compose.prod.yml exec app flask db init

# Create migration
docker-compose -f docker-compose.prod.yml exec app flask db migrate -m "Initial migration"

# Apply migrations
docker-compose -f docker-compose.prod.yml exec app flask db upgrade
```

### 5. Configure SSL Certificate (Optional)

For production, set up SSL with Let's Encrypt:

```bash
# Make sure domain points to your server
# Then run certbot
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com \
  -d www.your-domain.com

# Update nginx config to use HTTPS
# Then restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### 6. Onboard a Shopify Store

Once your application is deployed, you can onboard Shopify stores using the OAuth flow.

#### Step 1: Access the Application

Navigate to your application URL:
- **Web UI**: `https://your-domain.com/`
- **Direct API**: Use the `/auth` endpoint

#### Step 2: Initiate OAuth Flow

**Option A: Using the Web UI**

1. Visit `https://your-domain.com/`
2. Enter the shop domain (e.g., `your-shop.myshopify.com` or just `your-shop`)
3. Click "Connect to Shopify"
4. You'll be redirected to Shopify's OAuth authorization page

**Option B: Using API Directly**

```bash
# Replace with your shop domain
curl -L "https://your-domain.com/auth?shop=your-shop.myshopify.com"
```

**Option C: Using cURL (for testing)**

```bash
curl -L "https://your-domain.com/auth?shop=your-shop.myshopify.com" \
  -H "Cookie: session=your-session-cookie"
```

#### Step 3: Authorize the App

1. Shopify will redirect the merchant to your app's authorization page
2. The merchant will review and approve the requested permissions
3. Upon approval, Shopify redirects to: `https://your-domain.com/auth/callback`

#### Step 4: OAuth Callback Handling

The application automatically:
- Exchanges the authorization code for an access token
- Stores the shop domain and access token in the database
- Creates or updates the `Shop` record

#### Step 5: Verify Store Onboarding

**Check if store is onboarded:**

```bash
# Using the database
docker-compose -f docker-compose.prod.yml exec app python -c "
from app import app
from models import db, Shop
with app.app_context():
    shops = Shop.query.all()
    for shop in shops:
        print(f'{shop.shop_domain} - Created: {shop.created_at}')
"

# Or via API (requires authentication)
curl "https://your-domain.com/api/products?shop=your-shop.myshopify.com"
```

**Expected Response:**
- If onboarded: Returns products or data
- If not onboarded: `{"error": "Shop not found"}` with 404 status

#### Step 6: Test API Access

Once onboarded, you can use the API:

```bash
# Fetch products
curl "https://your-domain.com/api/products?shop=your-shop.myshopify.com"

# Fetch orders
curl "https://your-domain.com/api/orders?shop=your-shop.myshopify.com"

# Fetch inventory
curl "https://your-domain.com/api/inventory?shop=your-shop.myshopify.com"

# Sync products to database
curl -X POST "https://your-domain.com/api/sync/products" \
  -H "Content-Type: application/json" \
  -d '{"shop": "your-shop.myshopify.com"}'

# Sync orders to database
curl -X POST "https://your-domain.com/api/sync/orders" \
  -H "Content-Type: application/json" \
  -d '{"shop": "your-shop.myshopify.com"}'
```

#### Troubleshooting Onboarding

**Issue: "Shop not found" error**
- **Solution**: Ensure the store completed OAuth and the callback was successful
- **Check**: Verify the shop record exists in the database

**Issue: OAuth redirect fails**
- **Solution**: Verify `SHOPIFY_REDIRECT_URI` matches exactly what's configured in Shopify Partner Dashboard
- **Check**: Must be `https://your-domain.com/auth/callback` (exact match, including protocol and path)

**Issue: "Invalid state parameter" error**

This is a common OAuth issue where the session cookie doesn't persist between the `/auth` request and the `/auth/callback` request. Common causes:

1. **Session cookie not being set properly**
   - **Solution**: Ensure `SECRET_KEY` is set in `.env` file
   - **Fix**: The app now configures session cookies with proper settings

2. **Cookies blocked or SameSite issues**
   - **Solution**: The app uses `SameSite=Lax` which allows cross-site redirects
   - **Fix**: Ensure cookies are enabled in browser

3. **Multiple app instances without shared session storage**
   - **Cause**: If using load balancing, sessions must be stored in Redis or a shared database
   - **Solution**: Use Redis-backed sessions or ensure sticky sessions

4. **Session expires between requests**
   - **Cause**: OAuth flow takes too long and session times out
   - **Fix**: Session lifetime is set to 15 minutes (should be sufficient)

5. **Domain mismatch**
   - **Cause**: Session cookie domain doesn't match the callback URL domain
   - **Fix**: Ensure the callback URL domain matches where the app is served

**Debugging Steps:**

Check the application logs for detailed error messages:
```bash
docker-compose -f docker-compose.prod.yml logs -f app | grep "OAuth"
```

The logs will show:
- Whether state was stored in session
- What state was received in callback
- Any session-related errors

**Fix**: The code now includes:
- Better session cookie configuration
- Improved error messages with hints
- Logging for debugging
- Permanent session flag to survive redirects

If the issue persists, ensure:
- ✅ `SECRET_KEY` is set in `.env` file
- ✅ Cookies are enabled in browser
- ✅ Using HTTPS in production (required for secure cookies)
- ✅ No proxy/firewall is stripping cookies
- ✅ Browser allows cookies from your domain

**Issue: Token exchange fails**
- **Solution**: Check that `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` are correct
- **Verify**: Test credentials in Shopify Partner Dashboard

### 7. Configure Shopify Callback URL

The callback URL is where Shopify redirects merchants after they authorize your app. This must be configured in two places:

#### Step 1: Configure in Your `.env` File

Set the `SHOPIFY_REDIRECT_URI` environment variable:

**For Production:**
```bash
SHOPIFY_REDIRECT_URI=https://your-domain.com/auth/callback
```

**For Development (Local):**
```bash
SHOPIFY_REDIRECT_URI=http://localhost:5000/auth/callback
```

**For Development with ngrok/tunneling:**
```bash
SHOPIFY_REDIRECT_URI=https://your-ngrok-url.ngrok.io/auth/callback
```

#### Step 2: Configure in Shopify Partner Dashboard

1. **Go to Shopify Partners Dashboard**
   - Navigate to [partners.shopify.com](https://partners.shopify.com)
   - Log in to your partner account

2. **Select Your App**
   - Go to "Apps" → Select your app

3. **Configure Redirect URL**
   - Click on "App setup" or "Configuration"
   - Find "Allowed redirection URL(s)" section
   - Add your callback URL: `https://your-domain.com/auth/callback`

**Important:** The URL in Shopify Partner Dashboard must match EXACTLY:
- ✅ **Protocol**: `https://` (required for production)
- ✅ **Domain**: Your exact domain (e.g., `peeq.co.in`)
- ✅ **Path**: `/auth/callback` (must match the route in `app.py`)

**Example:**
```
✅ Correct: https://peeq.co.in/auth/callback
❌ Wrong:   https://peeq.co.in/auth/callback/
❌ Wrong:   http://peeq.co.in/auth/callback  (HTTP not allowed in production)
❌ Wrong:   https://www.peeq.co.in/auth/callback  (if www is not your main domain)
```

#### Step 3: Verify the Configuration

The callback route is defined in `app.py` at line 110:
```python
@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback"""
    # ... processes the OAuth callback
```

**Test the callback URL:**
```bash
# Check if the route exists (should return JSON error if not authenticated)
curl "https://your-domain.com/auth/callback?code=test&shop=test-shop.myshopify.com&state=test"
```

#### Development Setup

For local development, you'll need a public URL. Options:

**Option 1: Using ngrok (Recommended)**
```bash
# Install ngrok: https://ngrok.com/download
ngrok http 5000

# Use the ngrok URL in both .env and Shopify Partner Dashboard
SHOPIFY_REDIRECT_URI=https://abc123.ngrok.io/auth/callback
```

**Option 2: Using localtunnel**
```bash
# Install localtunnel
npm install -g localtunnel

# Create tunnel
lt --port 5000

# Use the tunnel URL in .env and Shopify Partner Dashboard
SHOPIFY_REDIRECT_URI=https://your-tunnel-url.loca.lt/auth/callback
```

**Option 3: Using Docker with exposed ports**
If using Docker Compose, ensure port 5000 is exposed, then use your server's IP:
```bash
SHOPIFY_REDIRECT_URI=http://your-server-ip:5000/auth/callback
```

#### Multiple Environments

If you have multiple environments (dev, staging, production), you can add multiple redirect URLs in Shopify Partner Dashboard:

```
https://dev.your-domain.com/auth/callback
https://staging.your-domain.com/auth/callback
https://your-domain.com/auth/callback
```

Each environment's `.env` file should have its corresponding `SHOPIFY_REDIRECT_URI`.

#### Common Callback URL Issues

**Issue: "redirect_uri_mismatch" error**
- **Cause**: The callback URL in your `.env` doesn't match what's configured in Shopify Partner Dashboard
- **Solution**: Ensure exact match (protocol, domain, path)

**Issue: Callback URL not accessible**
- **Cause**: Your server/domain is not publicly accessible or HTTPS not configured
- **Solution**: 
  - Verify DNS points to your server
  - Ensure HTTPS is configured (SSL certificate)
  - Check firewall/security group allows HTTPS traffic on port 443

**Issue: "Invalid state parameter" in callback**
- **Cause**: Session expired or browser cookies cleared during OAuth flow
- **Solution**: Complete the OAuth flow in one browser session without clearing cookies

**Issue: Callback receives errors from Shopify**
- **Cause**: App not properly configured in Shopify Partner Dashboard
- **Solution**: 
  - Verify app credentials (API Key/Secret)
  - Check required scopes are enabled
  - Ensure app is not paused or deleted

#### Verification Checklist

- [ ] `SHOPIFY_REDIRECT_URI` is set in `.env` file
- [ ] Callback URL matches exactly in Shopify Partner Dashboard
- [ ] URL uses HTTPS for production (required by Shopify)
- [ ] Domain is publicly accessible and DNS configured
- [ ] SSL certificate is valid and active
- [ ] Route `/auth/callback` exists and is accessible
- [ ] App credentials are correct in `.env`

#### Quick Test

Test if your callback URL is configured correctly:

```bash
# Replace with your domain
curl -I "https://your-domain.com/auth/callback"

# Should return HTTP 200 or 400 (not 404)
# If 404, the route is not accessible
```

#### Onboarding Multiple Stores

Each store must complete the OAuth flow individually. The application supports multiple stores:
- Each store is stored as a separate `Shop` record
- Access tokens are unique per store
- Data syncing works independently for each store

#### Re-authenticating a Store

If a store's access token expires or becomes invalid:

1. Delete the shop record from the database (optional)
2. Repeat the onboarding process from Step 2
3. The system will update the existing shop record with the new token

**Remove a shop manually:**
```bash
docker-compose -f docker-compose.prod.yml exec app python -c "
from app import app
from models import db, Shop
with app.app_context():
    shop = Shop.query.filter_by(shop_domain='your-shop.myshopify.com').first()
    if shop:
        db.session.delete(shop)
        db.session.commit()
        print('Shop removed')
    else:
        print('Shop not found')
"
```

## Service Management

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f app
docker-compose -f docker-compose.prod.yml logs -f worker
docker-compose -f docker-compose.prod.yml logs -f db
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### Restart Services

```bash
# Restart all services
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart app
docker-compose -f docker-compose.prod.yml restart worker
```

### Stop Services

```bash
# Stop services (containers remain)
docker-compose -f docker-compose.prod.yml stop

# Stop and remove containers
docker-compose -f docker-compose.prod.yml down

# Stop and remove containers + volumes (⚠️ deletes data)
docker-compose -f docker-compose.prod.yml down -v
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild images
DOCKER_BUILDKIT=0 docker-compose -f docker-compose.prod.yml build

# Restart services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations if needed
docker-compose -f docker-compose.prod.yml exec app flask db upgrade
```

## Health Checks

### Check Service Status

```bash
./scripts/check_prod.sh
```

### Test API Endpoints

```bash
# Test all endpoints
./scripts/test_endpoints.sh

# Or test specific endpoint
curl http://localhost/api/products?shop=your-shop.myshopify.com
```

### Database Health

```bash
# Check database connection
docker-compose -f docker-compose.prod.yml exec db pg_isready -U postgres

# Connect to database
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d shopify_app_db
```

### Redis Health

```bash
# Check Redis connection
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Should return: PONG
```

### Worker Health

```bash
# Check Celery worker status
docker-compose -f docker-compose.prod.yml exec worker celery -A celery_app inspect active
```

## Troubleshooting

### App Service Not Running

If the `app` service is not running, follow these diagnostic steps:

#### Step 1: Check Docker Daemon

First, ensure Docker is running:

```bash
# Check Docker status
docker ps

# If you get "Cannot connect to Docker daemon", start Docker Desktop or Docker service:
# macOS: Open Docker Desktop application
# Linux: sudo systemctl start docker
```

#### Step 2: Check Service Status

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Check specific app service status
docker-compose -f docker-compose.prod.yml ps app

# See detailed status including exit codes
docker-compose -f docker-compose.prod.yml ps -a
```

#### Step 3: Check App Service Logs

```bash
# View recent logs
docker-compose -f docker-compose.prod.yml logs --tail=100 app

# Follow logs in real-time
docker-compose -f docker-compose.prod.yml logs -f app
```

Common log errors to look for:
- **Database connection errors**: Check if `db` service is running
- **Redis connection errors**: Check if `redis` service is running
- **Environment variable errors**: Check `.env` file
- **Port binding errors**: Check if port 5000 is already in use
- **Import errors**: Check if dependencies are installed correctly

#### Step 4: Check Dependencies

The `app` service depends on `db` and `redis`. Verify they're running:

```bash
# Check if dependencies are running
docker-compose -f docker-compose.prod.yml ps db redis

# If not running, start all services
docker-compose -f docker-compose.prod.yml up -d db redis

# Wait a few seconds for them to be ready
sleep 5

# Then start app
docker-compose -f docker-compose.prod.yml up -d app
```

#### Step 5: Verify Environment Variables

```bash
# Check if .env file exists
ls -la .env

# Verify critical variables are set
docker-compose -f docker-compose.prod.yml config | grep -A 5 "SHOPIFY_API_KEY"
docker-compose -f docker-compose.prod.yml config | grep -A 5 "DATABASE_URL"
docker-compose -f docker-compose.prod.yml config | grep -A 5 "REDIS_URL"
```

#### Step 6: Restart the Service

If the service is stopped or exited:

```bash
# Restart the app service
docker-compose -f docker-compose.prod.yml restart app

# Or recreate it (removes and recreates container)
docker-compose -f docker-compose.prod.yml up -d --force-recreate app

# Or restart all services
docker-compose -f docker-compose.prod.yml restart
```

#### Step 7: Complete Service Restart

If the above doesn't work, try a full restart:

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Start services in order
docker-compose -f docker-compose.prod.yml up -d db redis
sleep 5
docker-compose -f docker-compose.prod.yml up -d app worker nginx

# Or use the start script
./scripts/start_prod.sh
```

#### Step 8: Check Container Health

```bash
# Inspect the app container
docker-compose -f docker-compose.prod.yml exec app echo "Container is running"

# Check container resource usage
docker stats $(docker-compose -f docker-compose.prod.yml ps -q app)

# Check if port is listening inside container
docker-compose -f docker-compose.prod.yml exec app netstat -tuln | grep 5000
```

#### Common Issues and Solutions

**Issue: Container exits immediately after starting**
- **Solution**: Check logs for startup errors
- **Fix**: Verify environment variables, database connection, or application code

**Issue: "Cannot connect to Docker daemon"**
- **Solution**: Start Docker Desktop (macOS/Windows) or Docker service (Linux)
- **Fix**: `sudo systemctl start docker` on Linux

**Issue: Port 5000 already in use**
- **Solution**: Check what's using the port: `lsof -i :5000` (macOS) or `netstat -tuln | grep 5000` (Linux)
- **Fix**: Stop the conflicting process or change the port in docker-compose

**Issue: Database connection refused**
- **Solution**: Wait for database to be ready (can take 30-60 seconds)
- **Fix**: Ensure `db` service is running and `DATABASE_URL` uses service name (`db:5432`)

**Issue: Redis connection refused**
- **Solution**: Wait for Redis to be ready
- **Fix**: Ensure `redis` service is running and `REDIS_URL` uses service name (`redis:6379`)

**Issue: Missing environment variables**
- **Solution**: Verify `.env` file exists and has all required variables
- **Fix**: Copy from `env.example` and fill in values

#### Quick Diagnostic Command

Run this to get a complete status:

```bash
./scripts/check_prod.sh
```

### Services Won't Start

1. Check logs: `docker-compose -f docker-compose.prod.yml logs`
2. Verify environment variables in `.env`
3. Check port availability: `netstat -an | grep -E ':(80|443|5000)'`
4. Verify Docker has enough resources

### Database Connection Issues

#### For Local Docker Database

1. Wait for database to be ready (can take 30-60 seconds)
2. Check DATABASE_URL matches service name (`db:5432` not `localhost:5432`)
3. Verify database credentials in `.env`

#### For AWS RDS Database

If you're connecting to AWS RDS PostgreSQL, ensure your `DATABASE_URL` is correctly formatted:

**Correct RDS Connection String Format:**
```bash
DATABASE_URL=postgresql://username:password@shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com:5432/database_name
```

**Common Issues with RDS Connections:**

**Issue: "Connection refused" or "connection to server on socket failed"**

This usually means:
1. **Incorrect connection string format** - The URL must start with `postgresql://` or `postgresql+psycopg2://`
2. **Missing username/password** - The connection string must include credentials
3. **Network/security group issues** - Your server/container may not have access to RDS

**Solution: Verify Connection String Format**

The connection string MUST follow this format:
```
postgresql://[username]:[password]@[hostname]:[port]/[database_name]
```

Example for RDS:
```bash
DATABASE_URL=postgresql://postgres:your_password@shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com:5432/shopify_app_db
```

**Special characters in password:** If your password contains special characters (like `@`, `:`, `/`, `#`, etc.), URL-encode them:
- `@` becomes `%40`
- `:` becomes `%3A`
- `/` becomes `%2F`
- `#` becomes `%23`

**Example with encoded password:**
```bash
# If password is "p@ss:w#rd/123"
DATABASE_URL=postgresql://postgres:p%40ss%3Aw%23rd%2F123@shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com:5432/shopify_app_db
```

**Issue: "Connection timed out"**

This usually means:
1. **Security group not configured** - RDS security group must allow inbound traffic from your server/container
2. **VPC/subnet issues** - Server and RDS must be in compatible networks
3. **Network ACLs blocking traffic** - Check AWS VPC network ACLs

**Solution: Configure RDS Security Group**
1. Go to AWS RDS Console → Select your database → Security tab
2. Check security group inbound rules
3. Add rule to allow PostgreSQL (port 5432) from:
   - Your server's IP address
   - Your VPC CIDR block (if server is in same VPC)
   - Security group ID (if server uses a security group)

**Issue: "FATAL: password authentication failed"**

This means:
1. **Wrong password** - Verify the password is correct
2. **Wrong username** - Check the master username in RDS
3. **Password changed but not updated** - Update `.env` file with new password

**Solution: Test Connection**

Test the RDS connection from your server:

```bash
# Using psql (if installed)
psql "postgresql://username:password@shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com:5432/database_name"

# Or using Python
python -c "
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
print(f'Testing connection to: {db_url.split(\"@\")[1] if \"@\" in db_url else \"invalid URL\"}')
try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute('SELECT version();')
        print('✅ Connection successful!')
        print(result.fetchone()[0])
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

**Issue: Connection works locally but not from Docker container**

If connection works from your local machine but not from Docker:

1. **Network mode** - Container might not have internet access
2. **DNS resolution** - Container might not resolve RDS hostname
3. **Security group** - Security group might only allow your local IP, not container IP

**Solution: Check Container Network**

```bash
# Test DNS resolution from container
docker-compose -f docker-compose.prod.yml exec app nslookup shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com

# Test connection from container
docker-compose -f docker-compose.prod.yml exec app python -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

try:
    # Parse connection string
    db_url = os.getenv('DATABASE_URL')
    # Extract components and test
    conn = psycopg2.connect(db_url)
    print('✅ Connection successful!')
    conn.close()
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

**Alternative: Use postgresql+psycopg2://**

If `postgresql://` doesn't work, try explicitly specifying the driver:

```bash
DATABASE_URL=postgresql+psycopg2://username:password@shopify-db.cenke4ki6iif.us-east-1.rds.amazonaws.com:5432/database_name
```

**Verifying Connection String in Production**

```bash
# Check what DATABASE_URL is being used (without exposing password)
docker-compose -f docker-compose.prod.yml exec app python -c "
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL')
if db_url:
    # Show URL without password
    if '@' in db_url:
        parts = db_url.split('@')
        if '://' in parts[0]:
            print(f'Database: {parts[0].split(\"://\")[0]}://***@{parts[1]}')
        else:
            print('Invalid DATABASE_URL format')
    else:
        print('Invalid DATABASE_URL format - missing @')
else:
    print('DATABASE_URL not set')
"
```

### Application Errors

1. Check application logs: `docker-compose -f docker-compose.prod.yml logs app`
2. Verify all environment variables are set
3. Check database migrations: `docker-compose -f docker-compose.prod.yml exec app flask db current`

### Nginx Not Serving Traffic

1. Check nginx logs: `docker-compose -f docker-compose.prod.yml logs nginx`
2. Verify nginx config: `docker-compose -f docker-compose.prod.yml exec nginx nginx -t`
3. Ensure app service is running: `docker-compose -f docker-compose.prod.yml ps app`

## Production Checklist

- [ ] `.env` file configured with production values
- [ ] `SHOPIFY_REDIRECT_URI` matches your domain
- [ ] Database migrations run
- [ ] SSL certificate configured (if using HTTPS)
- [ ] Domain DNS points to server
- [ ] Nginx configuration updated with your domain
- [ ] All services running (`./scripts/check_prod.sh`)
- [ ] API endpoints testable (`./scripts/test_endpoints.sh`)
- [ ] Worker processing tasks
- [ ] Database backups configured (recommended)

## Security Notes

1. **Never commit `.env` file** - It contains secrets
2. Use strong `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
3. Use HTTPS in production - Configure SSL certificates
4. Regularly update Docker images for security patches
5. Configure firewall to only allow necessary ports (80, 443, 22)
6. Use strong database passwords in production

## Monitoring

### Resource Usage

```bash
# Check container resource usage
docker stats

# Check disk usage
docker system df
```

### Application Monitoring

Consider adding:
- Application logging (already configured)
- Health check endpoints
- Monitoring services (e.g., Sentry for error tracking)
- Uptime monitoring for your domain

## Backup

### Database Backup

```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres shopify_app_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
cat backup_file.sql | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres shopify_app_db
```

## Support

For issues, check:
1. Application logs: `docker-compose -f docker-compose.prod.yml logs -f`
2. Service status: `docker-compose -f docker-compose.prod.yml ps`
3. Health check script: `./scripts/check_prod.sh`

