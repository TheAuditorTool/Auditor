"""
Product management API (greenfield development).

This fixture demonstrates:
- API endpoints with authentication controls (api_endpoint_controls)
- Multiple decorator chaining (require_auth + require_role + require_permission)
- Taint flows from request parameters to SQL queries
- Raw SQL queries for search (sql_queries + sql_query_tables)
- Multi-source assignments in query building
"""

import os
import sqlite3

from flask import Blueprint, jsonify, request
from middleware.auth import rate_limit, require_auth, require_permission, require_role
from models import Product, db

products_bp = Blueprint('products', __name__)


@products_bp.route('/api/products', methods=['GET'])
@rate_limit(requests_per_minute=100)
def list_products():
    """
    List all products with pagination.

    No authentication required (public endpoint).
    This tests endpoints WITHOUT auth controls in api_endpoint_controls.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    products = Product.query.paginate(page=page, per_page=per_page)

    return jsonify({
        'products': [p.to_dict() for p in products.items],
        'total': products.total,
        'page': page,
        'per_page': per_page
    })


@products_bp.route('/api/products/search', methods=['GET'])
@require_auth
def search_products():
    """
    Search products using raw SQL.

    This demonstrates:
    - API endpoint with single auth control (@require_auth)
    - TAINT FLOW: search term from query params -> SQL query
    - MULTI-SOURCE ASSIGNMENT: Building query from multiple sources
    - Raw SQL query (sql_queries table)
    - Query touches 'products' table (sql_query_tables)

    Authentication: Required
    """
    # TAINT SOURCE: User input from query params
    search_term = request.args.get('q', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    # Get database connection
    db_path = os.getenv('DATABASE_PATH', 'app.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # MULTI-SOURCE ASSIGNMENT: Building query from multiple variables
    base_query = "SELECT id, name, description, price, stock, category FROM products"
    where_conditions = []
    params = []

    # Add search term condition
    if search_term:
        where_conditions.append("(name LIKE ? OR description LIKE ?)")
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern])

    # Add category filter
    if category:
        where_conditions.append("category = ?")
        params.append(category)

    # Add price range filters
    if min_price is not None:
        where_conditions.append("price >= ?")
        params.append(min_price)

    if max_price is not None:
        where_conditions.append("price <= ?")
        params.append(max_price)

    # MULTI-SOURCE: Combine all parts into final query
    query = base_query
    if where_conditions:
        query = query + " WHERE " + " AND ".join(where_conditions)

    query = query + " ORDER BY name LIMIT 100"

    # Execute raw SQL query (touches 'products' table)
    cursor.execute(query, params)

    results = cursor.fetchall()
    conn.close()

    # Convert results to dict
    products = [
        {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': float(row[3]),
            'stock': row[4],
            'category': row[5]
        }
        for row in results
    ]

    return jsonify({'products': products, 'count': len(products)})


@products_bp.route('/api/products', methods=['POST'])
@require_auth
@require_role('admin')
@require_permission('products:create')
def create_product():
    """
    Create new product.

    This demonstrates:
    - Multiple stacked decorators (3 controls)
    - Tests api_endpoint_controls with multiple rows for one endpoint
    - TAINT FLOW: Product data from request body

    Authentication: Required
    Authorization: Admin role + products:create permission
    """
    # TAINT SOURCE: User input from request body
    data = request.get_json()

    product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        stock=data.get('stock', 0),
        category=data.get('category', 'general')
    )

    db.session.add(product)
    db.session.commit()

    return jsonify(product.to_dict()), 201


@products_bp.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """
    Get product by ID.

    No authentication required (public endpoint).
    """
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())


@products_bp.route('/api/products/<int:product_id>', methods=['PUT'])
@require_auth
@require_permission('products:update')
def update_product(product_id):
    """
    Update existing product.

    This demonstrates:
    - Two decorators (auth + permission)
    - TAINT FLOW: Update data from request body

    Authentication: Required
    Authorization: products:update permission
    """
    product = Product.query.get_or_404(product_id)

    # TAINT SOURCE: User input from request body
    data = request.get_json()

    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.price = data.get('price', product.price)
    product.stock = data.get('stock', product.stock)
    product.category = data.get('category', product.category)

    db.session.commit()

    return jsonify(product.to_dict())


@products_bp.route('/api/products/<int:product_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
def delete_product(product_id):
    """
    Delete product.

    This demonstrates:
    - Two decorators (auth + role)

    Authentication: Required
    Authorization: Admin role
    """
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()

    return '', 204


@products_bp.route('/api/products/<int:product_id>/analytics', methods=['GET'])
@require_auth
@require_role('admin')
def get_product_analytics(product_id):
    """
    Get product analytics using raw SQL.

    This demonstrates:
    - Raw SQL with JOINs across multiple tables
    - Query touches 'products', 'order_items', 'orders' tables
    - Aggregation queries

    Authentication: Required
    Authorization: Admin role
    """
    db_path = os.getenv('DATABASE_PATH', 'app.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Raw SQL query with JOIN touching multiple tables
    cursor.execute("""
        SELECT
            p.id,
            p.name,
            COUNT(oi.id) AS times_ordered,
            SUM(oi.quantity) AS total_quantity_sold,
            SUM(oi.quantity * oi.price) AS total_revenue
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id
        WHERE p.id = ?
        GROUP BY p.id, p.name
    """, (product_id,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return jsonify({'error': 'Product not found'}), 404

    return jsonify({
        'product_id': result[0],
        'product_name': result[1],
        'times_ordered': result[2] or 0,
        'total_quantity_sold': result[3] or 0,
        'total_revenue': float(result[4]) if result[4] else 0.0
    })
