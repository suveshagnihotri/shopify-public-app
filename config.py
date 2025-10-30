"""
Configuration settings for the Shopify Public App
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///shopify_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Public/App URLs
    APP_URL = os.getenv('APP_URL', 'http://localhost:5000')
    PUBLIC_URL = os.getenv('PUBLIC_URL', APP_URL)  # if behind a proxy

    # Route paths
    AUTH_START_PATH = '/auth'
    AUTH_CALLBACK_PATH = '/auth/callback'
    API_PREFIX = '/api'
    WEBHOOK_BASE_PATH = '/webhooks'
    WEBHOOK_PRODUCTS_CREATE_PATH = WEBHOOK_BASE_PATH + '/products/create'
    WEBHOOK_ORDERS_CREATE_PATH = WEBHOOK_BASE_PATH + '/orders/create'

    # Shopify Configuration
    SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
    SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET')
    SHOPIFY_SCOPES = os.getenv('SHOPIFY_SCOPES', 'read_products,write_products,read_orders,write_orders,read_inventory,write_inventory')
    SHOPIFY_REDIRECT_URI = os.getenv('SHOPIFY_REDIRECT_URI')
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
    
    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # API Configuration
    SHOPIFY_API_VERSION = '2023-10'
    MAX_PRODUCTS_PER_REQUEST = 250
    MAX_ORDERS_PER_REQUEST = 250

    # Derived Shopify URL templates (format with shop domain and version)
    SHOPIFY_OAUTH_AUTHORIZE_URL = 'https://{shop}/admin/oauth/authorize'
    SHOPIFY_OAUTH_ACCESS_TOKEN_URL = 'https://{shop}/admin/oauth/access_token'
    SHOPIFY_ADMIN_API_BASE = 'https://{shop}/admin/api/{version}'
    
    @classmethod
    def shopify_authorize_url(cls, shop_domain: str) -> str:
        return cls.SHOPIFY_OAUTH_AUTHORIZE_URL.format(shop=shop_domain)

    @classmethod
    def shopify_access_token_url(cls, shop_domain: str) -> str:
        return cls.SHOPIFY_OAUTH_ACCESS_TOKEN_URL.format(shop=shop_domain)

    @classmethod
    def shopify_admin_api_base(cls, shop_domain: str, version: str | None = None) -> str:
        api_version = version or cls.SHOPIFY_API_VERSION
        return cls.SHOPIFY_ADMIN_API_BASE.format(shop=shop_domain, version=api_version)
    
    # Webhook Configuration
    WEBHOOK_TIMEOUT = 30
    WEBHOOK_RETRY_ATTEMPTS = 3

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
