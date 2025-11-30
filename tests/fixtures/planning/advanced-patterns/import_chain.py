"""
Import chain analysis (multiple names from single import).
Tests: imports JOIN import_style_names
"""

from auth import admin_required, check_permissions


from database import connection as db_conn
from database import execute_query as exec_sql
from flask import Blueprint, g, jsonify, request, session


from models import Order, Payment, User


from utils import *


def create_admin_api():
    """Uses multiple imported names in a single function."""

    admin_bp = Blueprint("admin", __name__)

    @admin_bp.route("/api/admin/users")
    @admin_required
    def list_users():
        page = request.args.get("page", 1)
        users = User.query.paginate(page=page)
        return jsonify([u.to_dict() for u in users.items])

    return admin_bp


def process_order_payment(order_id):
    """Uses multiple imported names across DB operations."""

    order = Order.query.get(order_id)
    payment = Payment(order_id=order.id, amount=order.total)

    with db_conn() as conn:
        exec_sql(conn, "INSERT INTO payments ...")

    return payment


def check_user_session():
    """Uses session and g objects (Flask globals)."""

    user_id = session.get("user_id")
    g.user = User.query.get(user_id)

    if not check_permissions(g.user, "admin"):
        raise PermissionError("Not authorized")

    return g.user
