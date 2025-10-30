"""
Test cases for the Shopify Public App
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from app import app, db
from models import Shop, ProductSync, OrderSync

@pytest.fixture
def client():
    """Test client fixture"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

@pytest.fixture
def sample_shop():
    """Sample shop fixture"""
    shop = Shop(
        shop_domain='test-shop.myshopify.com',
        access_token='test_access_token'
    )
    db.session.add(shop)
    db.session.commit()
    return shop

def test_index_page(client):
    """Test the index page loads correctly"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Shopify Data Manager' in response.data

def test_auth_redirect(client):
    """Test OAuth authentication redirect"""
    response = client.get('/auth?shop=test-shop.myshopify.com')
    assert response.status_code == 302
    assert 'test-shop.myshopify.com' in response.location

def test_auth_missing_shop(client):
    """Test auth endpoint with missing shop parameter"""
    response = client.get('/auth')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_auth_invalid_shop(client):
    """Test auth endpoint with invalid shop domain"""
    response = client.get('/auth?shop=invalid-shop.com')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

@patch('requests.post')
def test_auth_callback_success(mock_post, client):
    """Test successful OAuth callback"""
    # Mock successful token exchange
    mock_response = MagicMock()
    mock_response.json.return_value = {'access_token': 'test_token'}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response
    
    response = client.get('/auth/callback?code=test_code&shop=test-shop.myshopify.com&state=test_state')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'access_token' in data

@patch('requests.post')
def test_auth_callback_failure(mock_post, client):
    """Test failed OAuth callback"""
    # Mock failed token exchange
    mock_post.side_effect = Exception('Token exchange failed')
    
    response = client.get('/auth/callback?code=test_code&shop=test-shop.myshopify.com&state=test_state')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data

@patch('app.get_shopify_session')
def test_get_products_success(mock_session, client, sample_shop):
    """Test successful product fetching"""
    # Mock Shopify products
    mock_product = MagicMock()
    mock_product.id = 1
    mock_product.title = 'Test Product'
    mock_product.handle = 'test-product'
    mock_product.status = 'active'
    mock_product.created_at = '2023-01-01T00:00:00Z'
    mock_product.updated_at = '2023-01-01T00:00:00Z'
    mock_product.variants = []
    
    mock_session.return_value = None
    with patch('shopify.Product.find', return_value=[mock_product]):
        response = client.get('/api/products?shop=test-shop.myshopify.com')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'products' in data
        assert len(data['products']) == 1

def test_get_products_missing_shop(client):
    """Test product fetching with missing shop parameter"""
    response = client.get('/api/products')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_get_products_shop_not_found(client):
    """Test product fetching with non-existent shop"""
    response = client.get('/api/products?shop=nonexistent.myshopify.com')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data

@patch('app.get_shopify_session')
def test_get_orders_success(mock_session, client, sample_shop):
    """Test successful order fetching"""
    # Mock Shopify orders
    mock_order = MagicMock()
    mock_order.id = 1
    mock_order.order_number = '1001'
    mock_order.financial_status = 'paid'
    mock_order.total_price = '29.99'
    mock_order.currency = 'USD'
    mock_order.created_at = '2023-01-01T00:00:00Z'
    mock_order.updated_at = '2023-01-01T00:00:00Z'
    mock_order.line_items = []
    mock_order.customer = None
    
    mock_session.return_value = None
    with patch('shopify.Order.find', return_value=[mock_order]):
        response = client.get('/api/orders?shop=test-shop.myshopify.com')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'orders' in data
        assert len(data['orders']) == 1

@patch('app.get_shopify_session')
def test_get_inventory_success(mock_session, client, sample_shop):
    """Test successful inventory fetching"""
    # Mock Shopify inventory levels
    mock_level = MagicMock()
    mock_level.inventory_item_id = 1
    mock_level.location_id = 1
    mock_level.available = 100
    mock_level.updated_at = '2023-01-01T00:00:00Z'
    
    mock_session.return_value = None
    with patch('shopify.InventoryLevel.find', return_value=[mock_level]):
        response = client.get('/api/inventory?shop=test-shop.myshopify.com')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'inventory_levels' in data
        assert len(data['inventory_levels']) == 1

@patch('tasks.sync_products_task.delay')
def test_sync_products(client, sample_shop, mock_task):
    """Test product synchronization"""
    mock_task.return_value = MagicMock()
    
    response = client.post('/api/sync/products', 
                          json={'shop': 'test-shop.myshopify.com'})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data

@patch('tasks.sync_orders_task.delay')
def test_sync_orders(client, sample_shop, mock_task):
    """Test order synchronization"""
    mock_task.return_value = MagicMock()
    
    response = client.post('/api/sync/orders', 
                          json={'shop': 'test-shop.myshopify.com'})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data

def test_webhook_products_create(client, sample_shop):
    """Test product creation webhook"""
    product_data = {
        'id': 1,
        'title': 'New Product',
        'handle': 'new-product',
        'status': 'active'
    }
    
    # Mock webhook verification
    with patch('app.verify_webhook', return_value=True):
        with patch('tasks.process_product_webhook.delay'):
            response = client.post('/webhooks/products/create',
                                 data=json.dumps(product_data),
                                 content_type='application/json',
                                 headers={'X-Shopify-Hmac-Sha256': 'test_signature'})
            assert response.status_code == 200

def test_webhook_orders_create(client, sample_shop):
    """Test order creation webhook"""
    order_data = {
        'id': 1,
        'order_number': '1001',
        'financial_status': 'paid',
        'total_price': '29.99',
        'currency': 'USD'
    }
    
    # Mock webhook verification
    with patch('app.verify_webhook', return_value=True):
        with patch('tasks.process_order_webhook.delay'):
            response = client.post('/webhooks/orders/create',
                                 data=json.dumps(order_data),
                                 content_type='application/json',
                                 headers={'X-Shopify-Hmac-Sha256': 'test_signature'})
            assert response.status_code == 200

def test_webhook_invalid_signature(client):
    """Test webhook with invalid signature"""
    product_data = {'id': 1, 'title': 'Test'}
    
    with patch('app.verify_webhook', return_value=False):
        response = client.post('/webhooks/products/create',
                             data=json.dumps(product_data),
                             content_type='application/json',
                             headers={'X-Shopify-Hmac-Sha256': 'invalid_signature'})
        assert response.status_code == 401
