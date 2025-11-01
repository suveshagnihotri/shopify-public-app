"""
Shopify Public App - Main Application
Handles OAuth authentication, data fetching, and webhook processing
"""

import os
import hmac
import hashlib
import json
import logging
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs

import shopify
import requests
import redis
from flask import Flask, request, jsonify, redirect, session, render_template
from flask_migrate import Migrate
from flask_session import Session
from dotenv import load_dotenv
from celery import Celery

# Load environment variables
load_dotenv()

# Configure logging early (before other components that might use logger)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///shopify_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure session settings for OAuth
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cross-site redirects but maintain CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)  # Session timeout

# Configure Flask-Session to use Redis for session storage (required for multiple workers)
# In Docker, use service name 'redis', locally use 'localhost'
default_redis = 'redis://redis:6379/0' if os.getenv('FLASK_ENV') == 'production' else 'redis://localhost:6379/0'
redis_url = os.getenv('REDIS_URL', default_redis)
# Use a different Redis database for sessions (db 1) to avoid conflicts with Celery (db 0)
session_redis_url = redis_url.rsplit('/', 1)[0] + '/1'  # Change db number to 1

# Wait for Redis to be ready with retries (important for Docker startup)
redis_client = None
max_retries = 5
retry_delay = 2
import time
for attempt in range(max_retries):
    try:
        redis_client = redis.from_url(session_redis_url, decode_responses=False, socket_connect_timeout=5)
        # Test connection
        redis_client.ping()
        logger.info("Successfully connected to Redis for sessions")
        break
    except (redis.ConnectionError, redis.TimeoutError) as e:
        if attempt < max_retries - 1:
            logger.warning(f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
        else:
            logger.error(f"Failed to connect to Redis after {max_retries} attempts: {e}")
            raise

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_client
app.config['SESSION_KEY_PREFIX'] = 'session:'

# Initialize extensions (use the shared db from models)
from models import db, Shop, ProductSync, ProductVariant, OrderSync, OrderLineItem, InventoryLevel, WebhookLog
db.init_app(app)
migrate = Migrate(app, db)

# Initialize Flask-Session after app config
try:
    Session(app)
    logger.info("Flask-Session initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Flask-Session: {e}")
    raise

# Shopify configuration
SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET')
SHOPIFY_SCOPES = os.getenv('SHOPIFY_SCOPES', 'read_products,write_products,read_orders,write_orders,read_inventory,write_inventory')
SHOPIFY_REDIRECT_URI = os.getenv('SHOPIFY_REDIRECT_URI')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')

# Configure Shopify API
shopify.ShopifyResource.set_site("https://{shop}.myshopify.com/admin/api/2023-10")

# Initialize Celery
# Use the same redis_url we configured for sessions above
celery = Celery(
    app.import_name,
    broker=redis_url,
    backend=redis_url
)

# Database Models are now imported from models.py

# Utility functions
def verify_webhook(data, signature):
    """
    Verify webhook signature using HMAC-SHA256
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    
    Args:
        data: Raw request body (bytes)
        signature: X-Shopify-Hmac-Sha256 header value (base64-encoded)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not set - skipping verification (not recommended for production)")
        # In production, this should return False, but for development/testing, allow it
        # TODO: Set WEBHOOK_SECRET in production
        return True  # Skip verification in development
    
    if not signature:
        logger.error("Missing webhook signature header")
        return False
    
    try:
        # Calculate HMAC-SHA256 digest
        hmac_obj = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            data,
            hashlib.sha256
        )
        # Calculate HMAC and encode to base64 (Shopify sends signature as base64)
        calculated_hmac = hmac_obj.digest()  # Get bytes
        calculated_hmac_base64 = base64.b64encode(calculated_hmac).decode('utf-8')
        
        # Shopify signature is already base64-encoded, compare base64 strings
        # Use timing-safe comparison to prevent timing attacks
        if len(calculated_hmac_base64) != len(signature):
            logger.error(f"HMAC length mismatch: calculated={len(calculated_hmac_base64)}, received={len(signature)}")
            return False
        
        # Compare base64-encoded strings (timing-safe)
        is_valid = hmac.compare_digest(calculated_hmac_base64.encode('utf-8'), signature.encode('utf-8'))
        
        if not is_valid:
            logger.debug(f"HMAC mismatch - Calculated: {calculated_hmac_base64[:20]}..., Received: {signature[:20]}...")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False

def get_shopify_session(shop_domain, access_token):
    """Create Shopify session for API calls"""
    session = shopify.Session(shop_domain, '2023-10', access_token)
    shopify.ShopifyResource.activate_session(session)
    return session

def register_compliance_webhooks(shop_domain, access_token):
    """
    Register mandatory compliance webhooks with Shopify
    Required for app review: https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
    
    Args:
        shop_domain: Shop domain (e.g., 'shop.myshopify.com')
        access_token: Shopify access token for API calls
    """
    # Get app URL from environment
    app_url = os.getenv('SHOPIFY_REDIRECT_URI', '').replace('/auth/callback', '')
    if not app_url:
        app_url = os.getenv('APP_URL', 'https://peeq.co.in')
    
    # Ensure URL doesn't end with slash
    app_url = app_url.rstrip('/')
    
    # Define mandatory compliance webhooks
    compliance_webhooks = [
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
    
    # Register each webhook
    webhook_url = f"https://{shop_domain}/admin/api/2023-10/webhooks.json"
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    for webhook in compliance_webhooks:
        try:
            # Check if webhook already exists
            list_response = requests.get(webhook_url, headers=headers, params={'topic': webhook['topic']})
            
            if list_response.status_code == 200:
                existing_webhooks = list_response.json().get('webhooks', [])
                # Check if webhook with same topic and address exists
                existing = next(
                    (w for w in existing_webhooks if w.get('topic') == webhook['topic'] and w.get('address') == webhook['address']),
                    None
                )
                
                if existing:
                    logger.info(f"Webhook {webhook['topic']} already registered: {existing.get('id')}")
                    continue
            
            # Register new webhook
            response = requests.post(
                webhook_url,
                json={'webhook': webhook},
                headers=headers
            )
            response.raise_for_status()
            webhook_response = response.json().get('webhook', {})
            logger.info(f"Registered webhook {webhook['topic']}: {webhook_response.get('id')}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register webhook {webhook['topic']}: {e}")
            # Continue with other webhooks even if one fails
            continue

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/auth')
def auth():
    """Initiate OAuth flow"""
    shop = request.args.get('shop')
    if not shop:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    # Validate shop domain
    if not shop.endswith('.myshopify.com'):
        return jsonify({'error': 'Invalid shop domain'}), 400
    
    # Generate state parameter for security
    state = os.urandom(16).hex()
    session['oauth_state'] = state
    session.permanent = True  # Make session permanent so it survives the OAuth redirect
    logger.info(f"OAuth initiated for shop: {shop}, State: {state[:8]}...")
    
    # Build authorization URL
    params = {
        'client_id': SHOPIFY_API_KEY,
        'scope': SHOPIFY_SCOPES,
        'redirect_uri': SHOPIFY_REDIRECT_URI,
        'state': state,
        'grant_options[]': 'per-user'
    }
    
    auth_url = f"https://{shop}/admin/oauth/authorize?" + urlencode(params)
    return redirect(auth_url)

@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback"""
    code = request.args.get('code')
    shop = request.args.get('shop')
    state = request.args.get('state')
    
    # Log callback for debugging
    logger.info(f"OAuth callback received - Shop: {shop}, State present: {bool(state)}, Code present: {bool(code)}")
    logger.info(f"Session state stored: {session.get('oauth_state')}, Received state: {state}")
    
    # Verify state parameter
    stored_state = session.get('oauth_state')
    if not state:
        logger.error("State parameter missing from callback")
        return jsonify({'error': 'Missing state parameter'}), 400
    
    if not stored_state:
        logger.error("No state found in session - session may have expired or cookie not set")
        return jsonify({
            'error': 'Invalid state parameter',
            'message': 'Session expired or not found. Please try the OAuth flow again.',
            'hint': 'Make sure cookies are enabled and you complete the flow in the same browser session.'
        }), 400
    
    if state != stored_state:
        logger.error(f"State mismatch - Stored: {stored_state}, Received: {state}")
        return jsonify({
            'error': 'Invalid state parameter',
            'message': 'State parameter does not match. This may indicate a security issue or session problem.',
            'hint': 'Please try the OAuth flow again from the beginning.'
        }), 400
    
    if not code or not shop:
        logger.error(f"Missing required parameters - Code: {bool(code)}, Shop: {bool(shop)}")
        return jsonify({'error': 'Missing authorization code or shop'}), 400
    
    # Exchange code for access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    token_data = {
        'client_id': SHOPIFY_API_KEY,
        'client_secret': SHOPIFY_API_SECRET,
        'code': code
    }
    
    try:
        response = requests.post(token_url, json=token_data)
        response.raise_for_status()
        token_response = response.json()
        access_token = token_response['access_token']
        
        # Store shop and access token
        shop_record = Shop.query.filter_by(shop_domain=shop).first()
        if shop_record:
            shop_record.access_token = access_token
            shop_record.updated_at = datetime.utcnow()
        else:
            shop_record = Shop(shop_domain=shop, access_token=access_token)
            db.session.add(shop_record)
        
        db.session.commit()
        
        # Register mandatory compliance webhooks (required for app review)
        try:
            register_compliance_webhooks(shop, access_token)
            logger.info(f"Registered compliance webhooks for shop: {shop}")
        except Exception as e:
            logger.error(f"Failed to register compliance webhooks: {e}")
            # Don't fail the OAuth flow if webhook registration fails
            # It can be done manually via Partner Dashboard
        
        # Clear OAuth state
        session.pop('oauth_state', None)
        
        return jsonify({
            'message': 'Authentication successful',
            'shop': shop,
            'access_token': access_token
        })
        
    except requests.RequestException as e:
        logger.error(f"Token exchange failed: {e}")
        return jsonify({'error': 'Failed to exchange code for token'}), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    """Fetch products from Shopify"""
    shop_domain = request.args.get('shop')
    if not shop_domain:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
    if not shop_record:
        return jsonify({'error': 'Shop not found'}), 404
    
    try:
        # Set up Shopify session
        get_shopify_session(shop_domain, shop_record.access_token)
        
        # Fetch products
        products = shopify.Product.find(limit=50)
        products_data = []
        
        for product in products:
            product_data = {
                'id': product.id,
                'title': product.title,
                'handle': product.handle,
                'status': product.status,
                'created_at': product.created_at,
                'updated_at': product.updated_at,
                'variants': []
            }
            
            # Add variants
            for variant in product.variants:
                variant_data = {
                    'id': variant.id,
                    'title': variant.title,
                    'price': variant.price,
                    'sku': variant.sku,
                    'inventory_quantity': variant.inventory_quantity,
                    'inventory_management': variant.inventory_management
                }
                product_data['variants'].append(variant_data)
            
            products_data.append(product_data)
        
        return jsonify({
            'products': products_data,
            'count': len(products_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return jsonify({'error': 'Failed to fetch products'}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Fetch orders from Shopify"""
    shop_domain = request.args.get('shop')
    if not shop_domain:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
    if not shop_record:
        return jsonify({'error': 'Shop not found'}), 404
    
    try:
        # Set up Shopify session
        get_shopify_session(shop_domain, shop_record.access_token)
        
        # Fetch orders
        orders = shopify.Order.find(limit=50, status='any')
        orders_data = []
        
        for order in orders:
            order_data = {
                'id': order.id,
                'order_number': order.order_number,
                'status': order.financial_status,
                'total_price': float(order.total_price),
                'currency': order.currency,
                'created_at': order.created_at,
                'updated_at': order.updated_at,
                'line_items': []
            }
            
            # Add line items
            for item in order.line_items:
                item_data = {
                    'id': item.id,
                    'product_id': item.product_id,
                    'variant_id': item.variant_id,
                    'title': item.title,
                    'quantity': item.quantity,
                    'price': float(item.price)
                }
                order_data['line_items'].append(item_data)
            
            orders_data.append(order_data)
        
        return jsonify({
            'orders': orders_data,
            'count': len(orders_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return jsonify({'error': 'Failed to fetch orders'}), 500

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Fetch inventory levels from Shopify"""
    shop_domain = request.args.get('shop')
    if not shop_domain:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
    if not shop_record:
        return jsonify({'error': 'Shop not found'}), 404
    
    try:
        # Set up Shopify session
        get_shopify_session(shop_domain, shop_record.access_token)
        
        # Fetch inventory levels
        inventory_levels = shopify.InventoryLevel.find()
        inventory_data = []
        
        for level in inventory_levels:
            inventory_data.append({
                'inventory_item_id': level.inventory_item_id,
                'location_id': level.location_id,
                'available': level.available,
                'updated_at': level.updated_at
            })
        
        return jsonify({
            'inventory_levels': inventory_data,
            'count': len(inventory_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return jsonify({'error': 'Failed to fetch inventory'}), 500

@app.route('/api/sync/products', methods=['POST'])
def sync_products():
    """Sync products to local database"""
    shop_domain = request.json.get('shop')
    if not shop_domain:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
    if not shop_record:
        return jsonify({'error': 'Shop not found'}), 404
    
    # Queue background task
    sync_products_task.delay(shop_record.id, shop_domain, shop_record.access_token)
    
    return jsonify({'message': 'Product sync started'})

@app.route('/api/sync/orders', methods=['POST'])
def sync_orders():
    """Sync orders to local database"""
    shop_domain = request.json.get('shop')
    if not shop_domain:
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
    if not shop_record:
        return jsonify({'error': 'Shop not found'}), 404
    
    # Queue background task
    sync_orders_task.delay(shop_record.id, shop_domain, shop_record.access_token)
    
    return jsonify({'message': 'Order sync started'})

@app.route('/webhooks/products/create', methods=['POST'])
def webhook_products_create():
    """
    Handle product creation webhook
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    """
    # Get raw body for HMAC verification (before any parsing)
    raw_data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    # Validate webhook origin (Step 2: Validate the origin)
    if not verify_webhook(raw_data, signature):
        logger.error("Invalid webhook signature for products/create")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse JSON from raw data (after verification)
    try:
        product_data = json.loads(raw_data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Queue webhook for async processing (Step 3: Queue your webhooks)
    # This ensures we respond quickly (< 5 seconds, ideally < 1 second)
    try:
        process_product_webhook.delay(product_data)
        logger.info(f"Product webhook queued: {product_data.get('id', 'unknown')}")
    except Exception as e:
        logger.error(f"Failed to queue product webhook: {e}")
        # Still return 200 to prevent retry loops
        return jsonify({'status': 'queued with errors'}), 200
    
    # Step 1: Respond with 200 OK quickly
    return jsonify({'status': 'success'}), 200

@app.route('/webhooks/orders/create', methods=['POST'])
def webhook_orders_create():
    """
    Handle order creation webhook
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    """
    # Get raw body for HMAC verification (before any parsing)
    raw_data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    # Validate webhook origin (Step 2: Validate the origin)
    if not verify_webhook(raw_data, signature):
        logger.error("Invalid webhook signature for orders/create")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse JSON from raw data (after verification)
    try:
        order_data = json.loads(raw_data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Queue webhook for async processing (Step 3: Queue your webhooks)
    # This ensures we respond quickly (< 5 seconds, ideally < 1 second)
    try:
        process_order_webhook.delay(order_data)
        logger.info(f"Order webhook queued: {order_data.get('id', 'unknown')}")
    except Exception as e:
        logger.error(f"Failed to queue order webhook: {e}")
        # Still return 200 to prevent retry loops
        return jsonify({'status': 'queued with errors'}), 200
    
    # Step 1: Respond with 200 OK quickly
    return jsonify({'status': 'success'}), 200

# Mandatory compliance webhooks for customer privacy (GDPR/CCPA)
@app.route('/webhooks/customers/data_request', methods=['POST'])
def webhook_customers_data_request():
    """
    Mandatory webhook: Handle customer data request (GDPR compliance)
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    
    When a customer requests their data, Shopify will send this webhook.
    """
    # Get raw body for HMAC verification (before any parsing)
    raw_data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    # Validate webhook origin (Step 2: Validate the origin)
    if not verify_webhook(raw_data, signature):
        logger.error("Invalid webhook signature for customers/data_request")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse JSON from raw data (after verification)
    try:
        webhook_data = json.loads(raw_data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Queue compliance processing asynchronously (Step 3: Queue your webhooks)
    # This ensures we respond quickly (< 5 seconds, ideally < 1 second)
    try:
        process_customer_data_request.delay(webhook_data)
        shop_domain = webhook_data.get('shop_domain')
        customer_id = webhook_data.get('customer', {}).get('id') if isinstance(webhook_data.get('customer'), dict) else webhook_data.get('customer_id')
        logger.info(f"Customer data request webhook queued for shop: {shop_domain}, customer: {customer_id}")
    except Exception as e:
        logger.error(f"Failed to queue customer data request webhook: {e}")
        # Still return 200 to prevent retry loops (Shopify will retry if we return error)
        return jsonify({'status': 'queued with errors'}), 200
    
    # Step 1: Respond with 200 OK quickly
    return jsonify({'status': 'success'}), 200

@app.route('/webhooks/customers/redact', methods=['POST'])
def webhook_customers_redact():
    """
    Mandatory webhook: Handle customer data deletion request (GDPR/CCPA compliance)
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    
    When a customer requests data deletion, Shopify will send this webhook.
    You must delete or anonymize all customer data from your systems.
    """
    # Get raw body for HMAC verification (before any parsing)
    raw_data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    # Validate webhook origin (Step 2: Validate the origin)
    if not verify_webhook(raw_data, signature):
        logger.error("Invalid webhook signature for customers/redact")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse JSON from raw data (after verification)
    try:
        webhook_data = json.loads(raw_data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Queue compliance processing asynchronously (Step 3: Queue your webhooks)
    # This ensures we respond quickly (< 5 seconds, ideally < 1 second)
    try:
        process_customer_redact.delay(webhook_data)
        shop_domain = webhook_data.get('shop_domain')
        customer_id = webhook_data.get('customer', {}).get('id') if isinstance(webhook_data.get('customer'), dict) else webhook_data.get('customer_id')
        logger.info(f"Customer redact webhook queued for shop: {shop_domain}, customer: {customer_id}")
    except Exception as e:
        logger.error(f"Failed to queue customer redact webhook: {e}")
        # Still return 200 to prevent retry loops (Shopify will retry if we return error)
        return jsonify({'status': 'queued with errors'}), 200
    
    # Step 1: Respond with 200 OK quickly
    return jsonify({'status': 'success'}), 200

@app.route('/webhooks/shop/redact', methods=['POST'])
def webhook_shop_redact():
    """
    Mandatory webhook: Handle shop uninstall data deletion request
    Following Shopify's best practices: https://shopify.dev/docs/apps/build/webhooks/subscribe/https
    
    When a shop uninstalls your app, Shopify will send this webhook.
    You must delete all shop-related data from your systems.
    """
    # Get raw body for HMAC verification (before any parsing)
    raw_data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    # Validate webhook origin (Step 2: Validate the origin)
    if not verify_webhook(raw_data, signature):
        logger.error("Invalid webhook signature for shop/redact")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse JSON from raw data (after verification)
    try:
        webhook_data = json.loads(raw_data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Queue compliance processing asynchronously (Step 3: Queue your webhooks)
    # This ensures we respond quickly (< 5 seconds, ideally < 1 second)
    try:
        process_shop_redact.delay(webhook_data)
        shop_domain = webhook_data.get('shop_domain')
        logger.info(f"Shop redact webhook queued for shop: {shop_domain}")
    except Exception as e:
        logger.error(f"Failed to queue shop redact webhook: {e}")
        # Still return 200 to prevent retry loops (Shopify will retry if we return error)
        return jsonify({'status': 'queued with errors'}), 200
    
    # Step 1: Respond with 200 OK quickly
    return jsonify({'status': 'success'}), 200

# Background tasks
@celery.task
def sync_products_task(shop_id, shop_domain, access_token):
    """Background task to sync products"""
    try:
        get_shopify_session(shop_domain, access_token)
        products = shopify.Product.find(limit=250)
        
        for product in products:
            # Check if product already exists
            existing = ProductSync.query.filter_by(
                shop_id=shop_id, 
                product_id=product.id
            ).first()
            
            if existing:
                existing.title = product.title
                existing.handle = product.handle
                existing.last_synced = datetime.utcnow()
            else:
                new_product = ProductSync(
                    shop_id=shop_id,
                    product_id=product.id,
                    title=product.title,
                    handle=product.handle
                )
                db.session.add(new_product)
        
        db.session.commit()
        logger.info(f"Synced {len(products)} products for shop {shop_domain}")
        
    except Exception as e:
        logger.error(f"Error syncing products: {e}")

@celery.task
def sync_orders_task(shop_id, shop_domain, access_token):
    """Background task to sync orders"""
    try:
        get_shopify_session(shop_domain, access_token)
        orders = shopify.Order.find(limit=250, status='any')
        
        for order in orders:
            # Check if order already exists
            existing = OrderSync.query.filter_by(
                shop_id=shop_id,
                order_id=order.id
            ).first()
            
            if existing:
                existing.status = order.financial_status
                existing.total_price = float(order.total_price)
                existing.currency = order.currency
                existing.last_synced = datetime.utcnow()
            else:
                new_order = OrderSync(
                    shop_id=shop_id,
                    order_id=order.id,
                    order_number=order.order_number,
                    status=order.financial_status,
                    total_price=float(order.total_price),
                    currency=order.currency
                )
                db.session.add(new_order)
        
        db.session.commit()
        logger.info(f"Synced {len(orders)} orders for shop {shop_domain}")
        
    except Exception as e:
        logger.error(f"Error syncing orders: {e}")

@celery.task
def process_product_webhook(product_data):
    """Process product webhook data"""
    try:
        shop_domain = product_data.get('shop_domain')
        if not shop_domain:
            return
        
        shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
        if not shop_record:
            return
        
        # Update or create product record
        existing = ProductSync.query.filter_by(
            shop_id=shop_record.id,
            product_id=product_data['id']
        ).first()
        
        if existing:
            existing.title = product_data['title']
            existing.handle = product_data['handle']
            existing.last_synced = datetime.utcnow()
        else:
            new_product = ProductSync(
                shop_id=shop_record.id,
                product_id=product_data['id'],
                title=product_data['title'],
                handle=product_data['handle']
            )
            db.session.add(new_product)
        
        db.session.commit()
        logger.info(f"Processed product webhook: {product_data['id']}")
        
    except Exception as e:
        logger.error(f"Error processing product webhook: {e}")

@celery.task
def process_order_webhook(order_data):
    """Process order webhook data"""
    try:
        shop_domain = order_data.get('shop_domain')
        if not shop_domain:
            return
        
        shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
        if not shop_record:
            return
        
        # Update or create order record
        existing = OrderSync.query.filter_by(
            shop_id=shop_record.id,
            order_id=order_data['id']
        ).first()
        
        if existing:
            existing.status = order_data['financial_status']
            existing.total_price = float(order_data['total_price'])
            existing.currency = order_data['currency']
            existing.last_synced = datetime.utcnow()
        else:
            new_order = OrderSync(
                shop_id=shop_record.id,
                order_id=order_data['id'],
                order_number=order_data['order_number'],
                status=order_data['financial_status'],
                total_price=float(order_data['total_price']),
                currency=order_data['currency']
            )
            db.session.add(new_order)
        
        db.session.commit()
        logger.info(f"Processed order webhook: {order_data['id']}")
        
    except Exception as e:
        logger.error(f"Error processing order webhook: {e}")

# Compliance webhook processing tasks
@celery.task
def process_customer_data_request(webhook_data):
    """
    Process customer data request webhook (GDPR compliance)
    Following Shopify's privacy law compliance: https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
    
    Payload structure:
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
    
    Must complete action within 30 days of receiving the request.
    Queued for async processing to ensure fast webhook response.
    """
    try:
        shop_id = webhook_data.get('shop_id')
        shop_domain = webhook_data.get('shop_domain')
        customer = webhook_data.get('customer', {})
        customer_id = customer.get('id') if isinstance(customer, dict) else None
        customer_email = customer.get('email') if isinstance(customer, dict) else None
        orders_requested = webhook_data.get('orders_requested', [])
        data_request_id = webhook_data.get('data_request', {}).get('id') if isinstance(webhook_data.get('data_request'), dict) else None
        
        logger.info(f"Processing customer data request for shop: {shop_domain} (ID: {shop_id}), customer: {customer_id} ({customer_email}), data_request_id: {data_request_id}, orders: {orders_requested}")
        
        # Log the data request for compliance tracking
        webhook_log = WebhookLog(
            shop_id=None,  # Will be set if shop found
            webhook_type='customers/data_request',
            resource_id=str(customer_id) if customer_id else str(data_request_id) if data_request_id else 'unknown',
            status='processing',
            payload=json.dumps(webhook_data)
        )
        
        # Try to find shop record
        shop_record = None
        if shop_domain:
            shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
            if shop_record:
                webhook_log.shop_id = shop_record.id
        
        db.session.add(webhook_log)
        db.session.commit()
        
        # TODO: Implement actual data collection and delivery
        # According to Shopify requirements:
        # 1. Collect all customer data from your database
        # 2. Compile it in a format the customer/store owner can access
        # 3. Send it via email or make it available through your app
        # 4. Must complete within 30 days
        
        # Example implementation:
        # if shop_record and customer_id:
        #     # Collect all data for this customer
        #     # - Customer records
        #     # - Order data for orders in orders_requested list
        #     # - Any other customer-related data
        #     
        #     # Compile into accessible format (JSON, PDF, etc.)
        #     # Send to store owner or customer
        #     pass
        
        webhook_log.status = 'completed'
        db.session.commit()
        
        logger.info(f"Completed customer data request for customer {customer_id} (data_request_id: {data_request_id})")
        
    except Exception as e:
        logger.error(f"Error processing customer data request: {e}")
        if 'webhook_log' in locals():
            webhook_log.status = 'failed'
            db.session.commit()

@celery.task
def process_customer_redact(webhook_data):
    """
    Process customer redact webhook (GDPR/CCPA compliance)
    Following Shopify's privacy law compliance: https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
    
    Payload structure:
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
    
    If customer hasn't placed an order in past 6 months, webhook is sent 10 days after request.
    Otherwise, webhook is sent 6 months after request.
    Must complete action within 30 days (unless legally required to retain data).
    Queued for async processing to ensure fast webhook response.
    """
    try:
        shop_id = webhook_data.get('shop_id')
        shop_domain = webhook_data.get('shop_domain')
        customer = webhook_data.get('customer', {})
        customer_id = customer.get('id') if isinstance(customer, dict) else None
        customer_email = customer.get('email') if isinstance(customer, dict) else None
        orders_to_redact = webhook_data.get('orders_to_redact', [])
        
        logger.info(f"Processing customer redact for shop: {shop_domain} (ID: {shop_id}), customer: {customer_id} ({customer_email}), orders to redact: {orders_to_redact}")
        
        # Log the redact request for compliance tracking
        webhook_log = WebhookLog(
            shop_id=None,
            webhook_type='customers/redact',
            resource_id=str(customer_id) if customer_id else 'unknown',
            status='processing',
            payload=json.dumps(webhook_data)
        )
        
        # Try to find shop record
        shop_record = None
        if shop_domain:
            shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
            if shop_record:
                webhook_log.shop_id = shop_record.id
        
        db.session.add(webhook_log)
        db.session.commit()
        
        # TODO: Implement actual data deletion/anonymization
        # According to Shopify requirements:
        # 1. Delete or anonymize all customer personal data from your database
        # 2. Delete or anonymize all orders in orders_to_redact list
        # 3. Delete any other customer-related records
        # 4. Must complete within 30 days (unless legally required to retain)
        
        # Example implementation:
        # if shop_record and customer_id:
        #     # Delete customer data
        #     # Anonymize order data for orders in orders_to_redact
        #     # If orders are linked to customers, you'd need customer_id in OrderSync model
        #     for order_id in orders_to_redact:
        #         order = OrderSync.query.filter_by(shop_id=shop_record.id, order_id=order_id).first()
        #         if order:
        #             # Anonymize order data instead of deleting (for business records)
        #             # or delete if not needed
        #             pass
        
        webhook_log.status = 'completed'
        db.session.commit()
        
        logger.info(f"Completed customer redact for customer {customer_id}, redacted {len(orders_to_redact)} orders")
        
    except Exception as e:
        logger.error(f"Error processing customer redact: {e}")
        if 'webhook_log' in locals():
            webhook_log.status = 'failed'
            db.session.commit()

@celery.task
def process_shop_redact(webhook_data):
    """
    Process shop redact webhook (shop uninstall data deletion)
    Following Shopify's privacy law compliance: https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
    
    Payload structure:
    {
        "shop_id": 954889,
        "shop_domain": "{shop}.myshopify.com"
    }
    
    This webhook is sent 48 hours after a store owner uninstalls your app.
    Must delete all shop-related data from your database.
    Queued for async processing to ensure fast webhook response.
    """
    try:
        shop_id = webhook_data.get('shop_id')
        shop_domain = webhook_data.get('shop_domain')
        
        logger.info(f"Processing shop redact for shop: {shop_domain} (ID: {shop_id})")
        
        # Log the redact request for compliance tracking
        webhook_log = WebhookLog(
            shop_id=None,
            webhook_type='shop/redact',
            resource_id=shop_domain or str(shop_id) or 'unknown',
            status='processing',
            payload=json.dumps(webhook_data)
        )
        
        # Find shop record
        shop_record = None
        if shop_domain:
            shop_record = Shop.query.filter_by(shop_domain=shop_domain).first()
            if shop_record:
                webhook_log.shop_id = shop_record.id
        
        db.session.add(webhook_log)
        db.session.commit()
        
        # Delete all shop-related data (as required by Shopify)
        if shop_record:
            deleted_counts = {}
            
            # Delete all orders for this shop
            deleted_orders = OrderSync.query.filter_by(shop_id=shop_record.id).count()
            OrderSync.query.filter_by(shop_id=shop_record.id).delete()
            deleted_counts['orders'] = deleted_orders
            
            # Delete all products for this shop
            deleted_products = ProductSync.query.filter_by(shop_id=shop_record.id).count()
            ProductSync.query.filter_by(shop_id=shop_record.id).delete()
            deleted_counts['products'] = deleted_products
            
            # Delete all inventory levels
            deleted_inventory = InventoryLevel.query.filter_by(shop_id=shop_record.id).count()
            InventoryLevel.query.filter_by(shop_id=shop_record.id).delete()
            deleted_counts['inventory'] = deleted_inventory
            
            # Delete all order line items
            from models import OrderLineItem
            deleted_line_items = OrderLineItem.query.filter_by(shop_id=shop_record.id).count()
            OrderLineItem.query.filter_by(shop_id=shop_record.id).delete()
            deleted_counts['line_items'] = deleted_line_items
            
            # Delete all webhook logs for this shop (except this one)
            deleted_webhooks = WebhookLog.query.filter_by(shop_id=shop_record.id).filter(WebhookLog.id != webhook_log.id).count()
            WebhookLog.query.filter_by(shop_id=shop_record.id).filter(WebhookLog.id != webhook_log.id).delete()
            deleted_counts['webhook_logs'] = deleted_webhooks
            
            # Delete the shop record itself
            db.session.delete(shop_record)
            
            logger.info(f"Deleted all data for shop: {shop_domain} - {deleted_counts}")
        
        webhook_log.status = 'completed'
        db.session.commit()
        
        logger.info(f"Completed shop redact for shop {shop_domain} (ID: {shop_id})")
        
    except Exception as e:
        logger.error(f"Error processing shop redact: {e}")
        if 'webhook_log' in locals():
            webhook_log.status = 'failed'
            db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8000)
