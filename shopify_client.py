"""
Shopify API client for handling all Shopify operations
"""

import shopify
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ShopifyClient:
    """Client for interacting with Shopify API"""
    
    def __init__(self, shop_domain: str, access_token: str, api_version: str = '2023-10'):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = api_version
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """Setup Shopify session"""
        try:
            self.session = shopify.Session(
                self.shop_domain, 
                self.api_version, 
                self.access_token
            )
            shopify.ShopifyResource.activate_session(self.session)
        except Exception as e:
            logger.error(f"Failed to setup Shopify session: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test if the connection to Shopify is working"""
        try:
            shop = shopify.Shop.current()
            return shop is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_products(self, limit: int = 250, page_info: str = None) -> Dict[str, Any]:
        """Fetch products from Shopify"""
        try:
            if page_info:
                products = shopify.Product.find(from_=page_info, limit=limit)
            else:
                products = shopify.Product.find(limit=limit)
            
            products_data = []
            for product in products:
                product_data = {
                    'id': product.id,
                    'title': product.title,
                    'handle': product.handle,
                    'status': product.status,
                    'product_type': product.product_type,
                    'vendor': product.vendor,
                    'tags': product.tags,
                    'created_at': product.created_at,
                    'updated_at': product.updated_at,
                    'variants': []
                }
                
                # Add variants
                for variant in product.variants:
                    variant_data = {
                        'id': variant.id,
                        'title': variant.title,
                        'price': float(variant.price),
                        'sku': variant.sku,
                        'barcode': variant.barcode,
                        'inventory_quantity': variant.inventory_quantity,
                        'inventory_management': variant.inventory_management,
                        'inventory_policy': variant.inventory_policy,
                        'weight': float(variant.weight) if variant.weight else None,
                        'weight_unit': variant.weight_unit,
                        'created_at': variant.created_at,
                        'updated_at': variant.updated_at
                    }
                    product_data['variants'].append(variant_data)
                
                products_data.append(product_data)
            
            return {
                'products': products_data,
                'count': len(products_data),
                'has_next_page': hasattr(products, 'next_page_info'),
                'next_page_info': getattr(products, 'next_page_info', None)
            }
            
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            raise
    
    def get_orders(self, limit: int = 250, status: str = 'any', page_info: str = None) -> Dict[str, Any]:
        """Fetch orders from Shopify"""
        try:
            params = {'limit': limit, 'status': status}
            if page_info:
                params['page_info'] = page_info
            
            orders = shopify.Order.find(**params)
            
            orders_data = []
            for order in orders:
                order_data = {
                    'id': order.id,
                    'order_number': order.order_number,
                    'status': order.financial_status,
                    'financial_status': order.financial_status,
                    'fulfillment_status': order.fulfillment_status,
                    'total_price': float(order.total_price),
                    'subtotal_price': float(order.subtotal_price),
                    'total_tax': float(order.total_tax),
                    'currency': order.currency,
                    'customer_email': order.customer.email if order.customer else None,
                    'customer_phone': order.customer.phone if order.customer else None,
                    'shipping_address': self._serialize_address(order.shipping_address),
                    'billing_address': self._serialize_address(order.billing_address),
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
                        'variant_title': item.variant_title,
                        'quantity': item.quantity,
                        'price': float(item.price),
                        'total_discount': float(item.total_discount) if item.total_discount else 0,
                        'sku': item.sku,
                        'vendor': item.vendor
                    }
                    order_data['line_items'].append(item_data)
                
                orders_data.append(order_data)
            
            return {
                'orders': orders_data,
                'count': len(orders_data),
                'has_next_page': hasattr(orders, 'next_page_info'),
                'next_page_info': getattr(orders, 'next_page_info', None)
            }
            
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise
    
    def get_inventory_levels(self, location_ids: List[int] = None) -> Dict[str, Any]:
        """Fetch inventory levels from Shopify"""
        try:
            params = {}
            if location_ids:
                params['location_ids'] = ','.join(map(str, location_ids))
            
            inventory_levels = shopify.InventoryLevel.find(**params)
            
            inventory_data = []
            for level in inventory_levels:
                inventory_data.append({
                    'inventory_item_id': level.inventory_item_id,
                    'location_id': level.location_id,
                    'available': level.available,
                    'updated_at': level.updated_at
                })
            
            return {
                'inventory_levels': inventory_data,
                'count': len(inventory_data)
            }
            
        except Exception as e:
            logger.error(f"Error fetching inventory levels: {e}")
            raise
    
    def get_locations(self) -> Dict[str, Any]:
        """Fetch store locations"""
        try:
            locations = shopify.Location.find()
            
            locations_data = []
            for location in locations:
                locations_data.append({
                    'id': location.id,
                    'name': location.name,
                    'address1': location.address1,
                    'address2': location.address2,
                    'city': location.city,
                    'province': location.province,
                    'country': location.country,
                    'zip': location.zip,
                    'phone': location.phone,
                    'active': location.active
                })
            
            return {
                'locations': locations_data,
                'count': len(locations_data)
            }
            
        except Exception as e:
            logger.error(f"Error fetching locations: {e}")
            raise
    
    def update_inventory_level(self, inventory_item_id: int, location_id: int, available: int) -> bool:
        """Update inventory level for a specific item and location"""
        try:
            inventory_level = shopify.InventoryLevel()
            inventory_level.inventory_item_id = inventory_item_id
            inventory_level.location_id = location_id
            inventory_level.available = available
            
            return inventory_level.save()
            
        except Exception as e:
            logger.error(f"Error updating inventory level: {e}")
            raise
    
    def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product in Shopify"""
        try:
            product = shopify.Product()
            product.title = product_data['title']
            product.body_html = product_data.get('body_html', '')
            product.vendor = product_data.get('vendor', '')
            product.product_type = product_data.get('product_type', '')
            product.tags = product_data.get('tags', '')
            
            # Add variants
            if 'variants' in product_data:
                for variant_data in product_data['variants']:
                    variant = shopify.Variant()
                    variant.title = variant_data.get('title', 'Default Title')
                    variant.price = variant_data.get('price', '0.00')
                    variant.sku = variant_data.get('sku', '')
                    variant.inventory_quantity = variant_data.get('inventory_quantity', 0)
                    variant.inventory_management = variant_data.get('inventory_management', 'shopify')
                    product.variants.append(variant)
            
            if product.save():
                return {
                    'id': product.id,
                    'title': product.title,
                    'handle': product.handle,
                    'status': product.status
                }
            else:
                raise Exception(f"Failed to create product: {product.errors}")
                
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise
    
    def update_product(self, product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing product in Shopify"""
        try:
            product = shopify.Product.find(product_id)
            
            if 'title' in product_data:
                product.title = product_data['title']
            if 'body_html' in product_data:
                product.body_html = product_data['body_html']
            if 'vendor' in product_data:
                product.vendor = product_data['vendor']
            if 'product_type' in product_data:
                product.product_type = product_data['product_type']
            if 'tags' in product_data:
                product.tags = product_data['tags']
            
            if product.save():
                return {
                    'id': product.id,
                    'title': product.title,
                    'handle': product.handle,
                    'status': product.status
                }
            else:
                raise Exception(f"Failed to update product: {product.errors}")
                
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            raise
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new order in Shopify"""
        try:
            order = shopify.Order()
            order.line_items = []
            
            # Add line items
            for item_data in order_data.get('line_items', []):
                line_item = shopify.LineItem()
                line_item.variant_id = item_data['variant_id']
                line_item.quantity = item_data['quantity']
                order.line_items.append(line_item)
            
            # Set customer information
            if 'customer' in order_data:
                customer = shopify.Customer()
                customer.email = order_data['customer'].get('email')
                customer.first_name = order_data['customer'].get('first_name')
                customer.last_name = order_data['customer'].get('last_name')
                order.customer = customer
            
            # Set shipping address
            if 'shipping_address' in order_data:
                shipping_address = shopify.Address()
                addr = order_data['shipping_address']
                shipping_address.first_name = addr.get('first_name')
                shipping_address.last_name = addr.get('last_name')
                shipping_address.address1 = addr.get('address1')
                shipping_address.city = addr.get('city')
                shipping_address.province = addr.get('province')
                shipping_address.country = addr.get('country')
                shipping_address.zip = addr.get('zip')
                order.shipping_address = shipping_address
            
            if order.save():
                return {
                    'id': order.id,
                    'order_number': order.order_number,
                    'status': order.financial_status,
                    'total_price': float(order.total_price)
                }
            else:
                raise Exception(f"Failed to create order: {order.errors}")
                
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            raise
    
    def _serialize_address(self, address) -> Optional[Dict[str, str]]:
        """Serialize address object to dictionary"""
        if not address:
            return None
        
        return {
            'first_name': address.first_name,
            'last_name': address.last_name,
            'address1': address.address1,
            'address2': address.address2,
            'city': address.city,
            'province': address.province,
            'country': address.country,
            'zip': address.zip,
            'phone': address.phone
        }
