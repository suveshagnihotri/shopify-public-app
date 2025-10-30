"""
Background tasks for the Shopify Public App
"""

import logging
from datetime import datetime
from celery import current_task
from celery_app import celery
from models import db, Shop, ProductSync, ProductVariant, OrderSync, OrderLineItem, InventoryLevel, WebhookLog
from shopify_client import ShopifyClient

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def sync_products_task(self, shop_id, shop_domain, access_token):
    """Background task to sync products from Shopify"""
    try:
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Starting product sync...'})
        
        # Get shop record
        shop = Shop.query.get(shop_id)
        if not shop:
            raise Exception(f"Shop with ID {shop_id} not found")
        
        # Initialize Shopify client
        client = ShopifyClient(shop_domain, access_token)
        
        # Test connection
        if not client.test_connection():
            raise Exception("Failed to connect to Shopify")
        
        # Fetch products
        self.update_state(state='PROGRESS', meta={'status': 'Fetching products from Shopify...'})
        products_data = client.get_products(limit=250)
        
        synced_count = 0
        for product_data in products_data['products']:
            try:
                # Check if product already exists
                existing = ProductSync.query.filter_by(
                    shop_id=shop_id,
                    product_id=product_data['id']
                ).first()
                
                if existing:
                    # Update existing product
                    existing.title = product_data['title']
                    existing.handle = product_data['handle']
                    existing.status = product_data['status']
                    existing.product_type = product_data.get('product_type')
                    existing.vendor = product_data.get('vendor')
                    existing.tags = product_data.get('tags')
                    existing.shopify_created_at = product_data.get('created_at')
                    existing.shopify_updated_at = product_data.get('updated_at')
                    existing.last_synced = datetime.utcnow()
                else:
                    # Create new product
                    new_product = ProductSync(
                        shop_id=shop_id,
                        product_id=product_data['id'],
                        title=product_data['title'],
                        handle=product_data['handle'],
                        status=product_data['status'],
                        product_type=product_data.get('product_type'),
                        vendor=product_data.get('vendor'),
                        tags=product_data.get('tags'),
                        shopify_created_at=product_data.get('created_at'),
                        shopify_updated_at=product_data.get('updated_at')
                    )
                    db.session.add(new_product)
                    existing = new_product
                
                # Sync variants
                for variant_data in product_data.get('variants', []):
                    existing_variant = ProductVariant.query.filter_by(
                        product_sync_id=existing.id,
                        variant_id=variant_data['id']
                    ).first()
                    
                    if existing_variant:
                        # Update existing variant
                        existing_variant.title = variant_data['title']
                        existing_variant.price = variant_data['price']
                        existing_variant.sku = variant_data.get('sku')
                        existing_variant.barcode = variant_data.get('barcode')
                        existing_variant.inventory_quantity = variant_data.get('inventory_quantity', 0)
                        existing_variant.inventory_management = variant_data.get('inventory_management')
                        existing_variant.inventory_policy = variant_data.get('inventory_policy')
                        existing_variant.weight = variant_data.get('weight')
                        existing_variant.weight_unit = variant_data.get('weight_unit')
                        existing_variant.last_synced = datetime.utcnow()
                    else:
                        # Create new variant
                        new_variant = ProductVariant(
                            product_sync_id=existing.id,
                            variant_id=variant_data['id'],
                            title=variant_data['title'],
                            price=variant_data['price'],
                            sku=variant_data.get('sku'),
                            barcode=variant_data.get('barcode'),
                            inventory_quantity=variant_data.get('inventory_quantity', 0),
                            inventory_management=variant_data.get('inventory_management'),
                            inventory_policy=variant_data.get('inventory_policy'),
                            weight=variant_data.get('weight'),
                            weight_unit=variant_data.get('weight_unit')
                        )
                        db.session.add(new_variant)
                
                synced_count += 1
                
                # Update progress
                if synced_count % 10 == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={'status': f'Synced {synced_count} products...'}
                    )
                
            except Exception as e:
                logger.error(f"Error syncing product {product_data['id']}: {e}")
                continue
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"Successfully synced {synced_count} products for shop {shop_domain}")
        
        return {
            'status': 'completed',
            'synced_count': synced_count,
            'total_products': len(products_data['products'])
        }
        
    except Exception as e:
        logger.error(f"Error in sync_products_task: {e}")
        db.session.rollback()
        raise

@celery.task(bind=True)
def sync_orders_task(self, shop_id, shop_domain, access_token):
    """Background task to sync orders from Shopify"""
    try:
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Starting order sync...'})
        
        # Get shop record
        shop = Shop.query.get(shop_id)
        if not shop:
            raise Exception(f"Shop with ID {shop_id} not found")
        
        # Initialize Shopify client
        client = ShopifyClient(shop_domain, access_token)
        
        # Test connection
        if not client.test_connection():
            raise Exception("Failed to connect to Shopify")
        
        # Fetch orders
        self.update_state(state='PROGRESS', meta={'status': 'Fetching orders from Shopify...'})
        orders_data = client.get_orders(limit=250, status='any')
        
        synced_count = 0
        for order_data in orders_data['orders']:
            try:
                # Check if order already exists
                existing = OrderSync.query.filter_by(
                    shop_id=shop_id,
                    order_id=order_data['id']
                ).first()
                
                if existing:
                    # Update existing order
                    existing.status = order_data['status']
                    existing.financial_status = order_data.get('financial_status')
                    existing.fulfillment_status = order_data.get('fulfillment_status')
                    existing.total_price = order_data['total_price']
                    existing.subtotal_price = order_data.get('subtotal_price')
                    existing.total_tax = order_data.get('total_tax')
                    existing.currency = order_data['currency']
                    existing.customer_email = order_data.get('customer_email')
                    existing.customer_phone = order_data.get('customer_phone')
                    existing.shipping_address = str(order_data.get('shipping_address', {}))
                    existing.billing_address = str(order_data.get('billing_address', {}))
                    existing.shopify_created_at = order_data.get('created_at')
                    existing.shopify_updated_at = order_data.get('updated_at')
                    existing.last_synced = datetime.utcnow()
                else:
                    # Create new order
                    new_order = OrderSync(
                        shop_id=shop_id,
                        order_id=order_data['id'],
                        order_number=order_data['order_number'],
                        status=order_data['status'],
                        financial_status=order_data.get('financial_status'),
                        fulfillment_status=order_data.get('fulfillment_status'),
                        total_price=order_data['total_price'],
                        subtotal_price=order_data.get('subtotal_price'),
                        total_tax=order_data.get('total_tax'),
                        currency=order_data['currency'],
                        customer_email=order_data.get('customer_email'),
                        customer_phone=order_data.get('customer_phone'),
                        shipping_address=str(order_data.get('shipping_address', {})),
                        billing_address=str(order_data.get('billing_address', {})),
                        shopify_created_at=order_data.get('created_at'),
                        shopify_updated_at=order_data.get('updated_at')
                    )
                    db.session.add(new_order)
                    existing = new_order
                
                # Sync line items
                for item_data in order_data.get('line_items', []):
                    existing_item = OrderLineItem.query.filter_by(
                        order_sync_id=existing.id,
                        line_item_id=item_data['id']
                    ).first()
                    
                    if existing_item:
                        # Update existing line item
                        existing_item.title = item_data['title']
                        existing_item.variant_title = item_data.get('variant_title')
                        existing_item.quantity = item_data['quantity']
                        existing_item.price = item_data['price']
                        existing_item.total_discount = item_data.get('total_discount', 0)
                        existing_item.sku = item_data.get('sku')
                        existing_item.vendor = item_data.get('vendor')
                    else:
                        # Create new line item
                        new_item = OrderLineItem(
                            order_sync_id=existing.id,
                            line_item_id=item_data['id'],
                            product_id=item_data.get('product_id'),
                            variant_id=item_data.get('variant_id'),
                            title=item_data['title'],
                            variant_title=item_data.get('variant_title'),
                            quantity=item_data['quantity'],
                            price=item_data['price'],
                            total_discount=item_data.get('total_discount', 0),
                            sku=item_data.get('sku'),
                            vendor=item_data.get('vendor')
                        )
                        db.session.add(new_item)
                
                synced_count += 1
                
                # Update progress
                if synced_count % 10 == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={'status': f'Synced {synced_count} orders...'}
                    )
                
            except Exception as e:
                logger.error(f"Error syncing order {order_data['id']}: {e}")
                continue
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"Successfully synced {synced_count} orders for shop {shop_domain}")
        
        return {
            'status': 'completed',
            'synced_count': synced_count,
            'total_orders': len(orders_data['orders'])
        }
        
    except Exception as e:
        logger.error(f"Error in sync_orders_task: {e}")
        db.session.rollback()
        raise

@celery.task(bind=True)
def sync_inventory_task(self, shop_id, shop_domain, access_token):
    """Background task to sync inventory levels from Shopify"""
    try:
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Starting inventory sync...'})
        
        # Get shop record
        shop = Shop.query.get(shop_id)
        if not shop:
            raise Exception(f"Shop with ID {shop_id} not found")
        
        # Initialize Shopify client
        client = ShopifyClient(shop_domain, access_token)
        
        # Test connection
        if not client.test_connection():
            raise Exception("Failed to connect to Shopify")
        
        # Fetch inventory levels
        self.update_state(state='PROGRESS', meta={'status': 'Fetching inventory levels from Shopify...'})
        inventory_data = client.get_inventory_levels()
        
        synced_count = 0
        for level_data in inventory_data['inventory_levels']:
            try:
                # Check if inventory level already exists
                existing = InventoryLevel.query.filter_by(
                    shop_id=shop_id,
                    inventory_item_id=level_data['inventory_item_id'],
                    location_id=level_data['location_id']
                ).first()
                
                if existing:
                    # Update existing inventory level
                    existing.available = level_data['available']
                    existing.last_synced = datetime.utcnow()
                else:
                    # Create new inventory level
                    new_level = InventoryLevel(
                        shop_id=shop_id,
                        inventory_item_id=level_data['inventory_item_id'],
                        location_id=level_data['location_id'],
                        available=level_data['available']
                    )
                    db.session.add(new_level)
                
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error syncing inventory level: {e}")
                continue
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"Successfully synced {synced_count} inventory levels for shop {shop_domain}")
        
        return {
            'status': 'completed',
            'synced_count': synced_count,
            'total_levels': len(inventory_data['inventory_levels'])
        }
        
    except Exception as e:
        logger.error(f"Error in sync_inventory_task: {e}")
        db.session.rollback()
        raise

@celery.task(bind=True)
def process_product_webhook(self, product_data, shop_domain):
    """Process product webhook data"""
    try:
        # Get shop record
        shop = Shop.query.filter_by(shop_domain=shop_domain).first()
        if not shop:
            logger.error(f"Shop {shop_domain} not found for webhook processing")
            return
        
        # Log webhook
        webhook_log = WebhookLog(
            shop_id=shop.id,
            webhook_type='product',
            resource_id=product_data['id'],
            status='processing'
        )
        db.session.add(webhook_log)
        
        # Process product data
        existing = ProductSync.query.filter_by(
            shop_id=shop.id,
            product_id=product_data['id']
        ).first()
        
        if existing:
            # Update existing product
            existing.title = product_data['title']
            existing.handle = product_data['handle']
            existing.status = product_data.get('status', 'active')
            existing.last_synced = datetime.utcnow()
        else:
            # Create new product
            new_product = ProductSync(
                shop_id=shop.id,
                product_id=product_data['id'],
                title=product_data['title'],
                handle=product_data['handle'],
                status=product_data.get('status', 'active')
            )
            db.session.add(new_product)
        
        webhook_log.status = 'success'
        db.session.commit()
        
        logger.info(f"Processed product webhook: {product_data['id']}")
        
    except Exception as e:
        logger.error(f"Error processing product webhook: {e}")
        if 'webhook_log' in locals():
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            db.session.commit()
        raise

@celery.task(bind=True)
def process_order_webhook(self, order_data, shop_domain):
    """Process order webhook data"""
    try:
        # Get shop record
        shop = Shop.query.filter_by(shop_domain=shop_domain).first()
        if not shop:
            logger.error(f"Shop {shop_domain} not found for webhook processing")
            return
        
        # Log webhook
        webhook_log = WebhookLog(
            shop_id=shop.id,
            webhook_type='order',
            resource_id=order_data['id'],
            status='processing'
        )
        db.session.add(webhook_log)
        
        # Process order data
        existing = OrderSync.query.filter_by(
            shop_id=shop.id,
            order_id=order_data['id']
        ).first()
        
        if existing:
            # Update existing order
            existing.status = order_data.get('financial_status', 'pending')
            existing.financial_status = order_data.get('financial_status')
            existing.fulfillment_status = order_data.get('fulfillment_status')
            existing.total_price = float(order_data.get('total_price', 0))
            existing.currency = order_data.get('currency', 'USD')
            existing.last_synced = datetime.utcnow()
        else:
            # Create new order
            new_order = OrderSync(
                shop_id=shop.id,
                order_id=order_data['id'],
                order_number=order_data.get('order_number', str(order_data['id'])),
                status=order_data.get('financial_status', 'pending'),
                financial_status=order_data.get('financial_status'),
                fulfillment_status=order_data.get('fulfillment_status'),
                total_price=float(order_data.get('total_price', 0)),
                currency=order_data.get('currency', 'USD')
            )
            db.session.add(new_order)
        
        webhook_log.status = 'success'
        db.session.commit()
        
        logger.info(f"Processed order webhook: {order_data['id']}")
        
    except Exception as e:
        logger.error(f"Error processing order webhook: {e}")
        if 'webhook_log' in locals():
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            db.session.commit()
        raise
