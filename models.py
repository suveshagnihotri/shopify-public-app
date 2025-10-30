"""
Database models for the Shopify Public App
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Single SQLAlchemy instance shared with the app
db = SQLAlchemy()

class Shop(db.Model):
    """Shop model to store authenticated shops"""
    __tablename__ = 'shops'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    shop_domain = db.Column(db.String(255), unique=True, nullable=False, index=True)
    access_token = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    products = db.relationship('ProductSync', backref='shop', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('OrderSync', backref='shop', lazy=True, cascade='all, delete-orphan')
    inventory_levels = db.relationship('InventoryLevel', backref='shop', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Shop {self.shop_domain}>'

class ProductSync(db.Model):
    """Product synchronization model"""
    __tablename__ = 'product_sync'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    product_id = db.Column(db.BigInteger, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    handle = db.Column(db.String(255), nullable=False, index=True)
    status = db.Column(db.String(50), default='active', nullable=False)
    product_type = db.Column(db.String(100))
    vendor = db.Column(db.String(100))
    tags = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    shopify_created_at = db.Column(db.DateTime)
    shopify_updated_at = db.Column(db.DateTime)
    
    # Relationships
    variants = db.relationship('ProductVariant', backref='product', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ProductSync {self.product_id}: {self.title}>'

class ProductVariant(db.Model):
    """Product variant model"""
    __tablename__ = 'product_variants'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    product_sync_id = db.Column(db.Integer, db.ForeignKey('product_sync.id'), nullable=False, index=True)
    variant_id = db.Column(db.BigInteger, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    sku = db.Column(db.String(100), index=True)
    barcode = db.Column(db.String(100))
    inventory_quantity = db.Column(db.Integer, default=0)
    inventory_management = db.Column(db.String(50))
    inventory_policy = db.Column(db.String(50))
    weight = db.Column(db.Numeric(8, 2))
    weight_unit = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<ProductVariant {self.variant_id}: {self.title}>'

class OrderSync(db.Model):
    """Order synchronization model"""
    __tablename__ = 'order_sync'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    order_id = db.Column(db.BigInteger, nullable=False, index=True)
    order_number = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False)
    financial_status = db.Column(db.String(50))
    fulfillment_status = db.Column(db.String(50))
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal_price = db.Column(db.Numeric(10, 2))
    total_tax = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10), nullable=False)
    customer_email = db.Column(db.String(255))
    customer_phone = db.Column(db.String(50))
    shipping_address = db.Column(db.Text)  # JSON string
    billing_address = db.Column(db.Text)   # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    shopify_created_at = db.Column(db.DateTime)
    shopify_updated_at = db.Column(db.DateTime)
    
    # Relationships
    line_items = db.relationship('OrderLineItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<OrderSync {self.order_id}: {self.order_number}>'

class OrderLineItem(db.Model):
    """Order line item model"""
    __tablename__ = 'order_line_items'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    order_sync_id = db.Column(db.Integer, db.ForeignKey('order_sync.id'), nullable=False, index=True)
    line_item_id = db.Column(db.BigInteger, nullable=False, index=True)
    product_id = db.Column(db.BigInteger, index=True)
    variant_id = db.Column(db.BigInteger, index=True)
    title = db.Column(db.String(255), nullable=False)
    variant_title = db.Column(db.String(255))
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    total_discount = db.Column(db.Numeric(10, 2))
    sku = db.Column(db.String(100))
    vendor = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<OrderLineItem {self.line_item_id}: {self.title}>'

class InventoryLevel(db.Model):
    """Inventory level model"""
    __tablename__ = 'inventory_levels'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    inventory_item_id = db.Column(db.BigInteger, nullable=False, index=True)
    location_id = db.Column(db.BigInteger, nullable=False, index=True)
    available = db.Column(db.Integer, nullable=False)
    location_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<InventoryLevel {self.inventory_item_id} at {self.location_id}: {self.available}>'

class WebhookLog(db.Model):
    """Webhook processing log model"""
    __tablename__ = 'webhook_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    webhook_type = db.Column(db.String(50), nullable=False)
    resource_id = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, error, pending
    error_message = db.Column(db.Text)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    retry_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<WebhookLog {self.webhook_type}: {self.resource_id}>'
