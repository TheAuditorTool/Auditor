"""
SQL queries with multiple table JOINs.
Tests: sql_queries JOIN sql_query_tables
"""

import sqlite3


def get_user_order_summary(user_id):
    """
    Query touches 3 tables: users, orders, order_items
    Should create 3 rows in sql_query_tables.
    """
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.username, u.email,
               o.id as order_id, o.total,
               oi.product_name, oi.quantity, oi.price
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN order_items oi ON o.id = oi.order_id
        WHERE u.id = ?
    """,
        (user_id,),
    )

    return cursor.fetchall()


def get_payment_with_user(payment_id):
    """
    Query touches 2 tables: payments, users
    Should create 2 rows in sql_query_tables.
    """
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT p.amount, p.status,
               u.username, u.email
        FROM payments p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    """,
        (payment_id,),
    )

    return cursor.fetchone()


def admin_dashboard_stats():
    """
    Complex query touching 4 tables: users, orders, payments, products
    Should create 4 rows in sql_query_tables.
    Taint risk: All 4 tables contain sensitive data.
    """
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(DISTINCT u.id) as total_users,
            COUNT(DISTINCT o.id) as total_orders,
            SUM(p.amount) as total_revenue,
            COUNT(DISTINCT pr.id) as total_products
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        LEFT JOIN payments p ON o.id = p.order_id
        LEFT JOIN products pr ON pr.id IN (
            SELECT product_id FROM order_items WHERE order_id = o.id
        )
    """)

    return cursor.fetchone()
