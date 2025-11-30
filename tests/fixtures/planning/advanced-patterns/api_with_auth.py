"""
Advanced API pattern testing - Multiple authentication controls per endpoint.
Tests: api_endpoints JOIN api_endpoint_controls
"""

from decorators import admin_required, login_required, rate_limit
from flask import Blueprint, jsonify

admin_api = Blueprint("admin", __name__)


@admin_api.route("/api/admin/users", methods=["GET"])
@login_required
@admin_required
@rate_limit(requests=100, window=3600)
def list_all_users():
    """
    This endpoint should create 3 rows in api_endpoint_controls:
    - (endpoint_id, 'login_required')
    - (endpoint_id, 'admin_required')
    - (endpoint_id, 'rate_limit')
    """
    from models import User

    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@admin_api.route("/api/admin/payments", methods=["GET"])
@login_required
@admin_required
def list_payments():
    """
    This endpoint should create 2 rows in api_endpoint_controls.
    Missing rate_limit = security finding.
    """
    from models import Payment

    payments = Payment.query.all()
    return jsonify([p.to_dict() for p in payments])


@admin_api.route("/api/public/health", methods=["GET"])
def health_check():
    """
    This endpoint has NO controls = 0 rows in api_endpoint_controls.
    Should be flagged if accessing sensitive data.
    """

    from models import Payment

    count = Payment.query.count()
    return jsonify({"status": "ok", "payment_count": count})
