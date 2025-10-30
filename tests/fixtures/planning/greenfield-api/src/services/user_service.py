"""
User service with raw SQL queries.

This fixture demonstrates:
- Raw SQL queries (not ORM) for sql_queries table population
- SQL queries touching specific tables (sql_query_tables junction table)
- Taint flows from parameters to SQL queries
- Multi-source assignments in query building
"""

import sqlite3
import os
from typing import Optional, Dict, List


def get_database_connection():
    """Get database connection."""
    db_path = os.getenv('DATABASE_PATH', 'app.db')
    return sqlite3.connect(db_path)


def get_user_role(user_id: int) -> Optional[str]:
    """
    Get user role by ID using raw SQL.

    This demonstrates:
    - Raw SQL query (populates sql_queries table)
    - Query touches 'users' and 'roles' tables (sql_query_tables)
    - TAINT FLOW: user_id parameter flows into query

    Args:
        user_id: User ID (TAINT SOURCE from g.user_id)

    Returns:
        Role name or None
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # Raw SQL query with JOIN touching multiple tables
    cursor.execute("""
        SELECT r.name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.id = ?
    """, (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Fetch user by email using raw SQL.

    This demonstrates:
    - Raw SQL query touching 'users' table
    - TAINT FLOW: email parameter (potential user input)

    Args:
        email: User email (potential TAINT SOURCE)

    Returns:
        User dict or None
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # Query touches 'users' table
    cursor.execute("""
        SELECT id, username, email, password_hash, role_id, created_at
        FROM users
        WHERE email = ?
    """, (email,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'id': result[0],
            'username': result[1],
            'email': result[2],
            'password_hash': result[3],
            'role_id': result[4],
            'created_at': result[5]
        }

    return None


def get_admin_users() -> List[Dict]:
    """
    Fetch all admin users using raw SQL.

    This demonstrates:
    - Raw SQL with JOIN touching 'users' and 'roles' tables
    - Query filtering by role

    Returns:
        List of admin user dicts
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # Query touches 'users' AND 'roles' tables
    cursor.execute("""
        SELECT u.id, u.username, u.email, r.name AS role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE r.name = 'admin'
    """)

    results = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'role': row[3]
        }
        for row in results
    ]


def search_users(search_term: str, role_filter: Optional[str] = None) -> List[Dict]:
    """
    Search users with dynamic query building.

    This demonstrates:
    - MULTI-SOURCE ASSIGNMENT: query built from multiple variables
    - TAINT FLOW: search_term and role_filter from user input
    - Dynamic SQL construction (potential SQL injection if not parameterized)

    Args:
        search_term: Search term (TAINT SOURCE - user input)
        role_filter: Optional role filter (TAINT SOURCE - user input)

    Returns:
        List of matching users
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # MULTI-SOURCE ASSIGNMENT: Building query from multiple sources
    base_query = "SELECT u.id, u.username, u.email, r.name AS role_name FROM users u"
    join_clause = " LEFT JOIN roles r ON u.role_id = r.id"
    where_conditions = []
    params = []

    # Add search condition
    if search_term:
        where_conditions.append("(u.username LIKE ? OR u.email LIKE ?)")
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern])

    # Add role filter
    if role_filter:
        where_conditions.append("r.name = ?")
        params.append(role_filter)

    # MULTI-SOURCE: Combine all parts into final query
    query = base_query + join_clause
    if where_conditions:
        query = query + " WHERE " + " AND ".join(where_conditions)

    # Execute query (touches 'users' and 'roles' tables)
    cursor.execute(query, params)

    results = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'role': row[3]
        }
        for row in results
    ]


def get_user_order_stats(user_id: int) -> Dict:
    """
    Get user order statistics using raw SQL with aggregation.

    This demonstrates:
    - Raw SQL with JOIN across multiple tables
    - Touches 'users', 'orders', 'order_items' tables
    - Aggregation queries

    Args:
        user_id: User ID (TAINT SOURCE)

    Returns:
        Stats dict
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # Query touches 'orders' and 'order_items' tables with JOIN
    cursor.execute("""
        SELECT
            COUNT(DISTINCT o.id) AS order_count,
            SUM(o.total_amount) AS total_spent,
            COUNT(oi.id) AS items_purchased
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    conn.close()

    return {
        'order_count': result[0] or 0,
        'total_spent': float(result[1]) if result[1] else 0.0,
        'items_purchased': result[2] or 0
    }


def log_user_activity(user_id: int, action: str, details: str):
    """
    Log user activity to database.

    This demonstrates:
    - INSERT query (sql_queries table)
    - Query touches 'activity_log' table (sql_query_tables)
    - TAINT SINK: Logging user actions

    Args:
        user_id: User ID
        action: Action type (e.g., 'login', 'create_order')
        details: Action details (potential TAINT SOURCE)
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    # INSERT query touching 'activity_log' table
    cursor.execute("""
        INSERT INTO activity_log (user_id, action, details, created_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (user_id, action, details))

    conn.commit()
    conn.close()
