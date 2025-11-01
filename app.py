"""
Shopify Public App - Main Application
Handles OAuth authentication, data fetching, and webhook processing
"""

import os
import hmac
import hashlib
import json
import logging
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
    """Verify webhook signature"""
    if not WEBHOOK_SECRET:
        return True  # Skip verification in development
    
    hmac_obj = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    )
    return hmac.compare_digest(hmac_obj.hexdigest(), signature)

def get_shopify_session(shop_domain, access_token):
    """Create Shopify session for API calls"""
    session = shopify.Session(shop_domain, '2023-10', access_token)
    shopify.ShopifyResource.activate_session(session)
    return session

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
    """Handle product creation webhook"""
    data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    if not verify_webhook(data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    product_data = request.json
    logger.info(f"Product created: {product_data['id']}")
    
    # Process webhook data
    process_product_webhook.delay(product_data)
    
    return jsonify({'status': 'success'})

@app.route('/webhooks/orders/create', methods=['POST'])
def webhook_orders_create():
    """Handle order creation webhook"""
    data = request.get_data()
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    
    if not verify_webhook(data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    order_data = request.json
    logger.info(f"Order created: {order_data['id']}")
    
    # Process webhook data
    process_order_webhook.delay(order_data)
    
    return jsonify({'status': 'success'})

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8000)
