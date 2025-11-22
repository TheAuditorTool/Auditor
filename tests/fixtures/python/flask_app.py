"""Flask fixture covering routes, blueprints, and auth decorators."""

from functools import wraps

from flask import Blueprint, jsonify, request

api = Blueprint("api", __name__, url_prefix="/api")


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def audit_event(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@api.route("/ping")
def ping():
    return "pong"


@api.route("/users", methods=["GET"])
@login_required
@audit_event
def list_users():
    return jsonify([])


@api.route("/users", methods=["POST"])
@login_required
def create_user():
    payload = request.get_json() or {}
    return jsonify({"email": payload.get("email")}), 201


@api.route("/users/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id: int):
    return jsonify({"id": user_id})


@api.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id: int):
    return "", 204


@api.route("/users/<int:user_id>/reset-password", methods=["POST"])
def reset_password(user_id: int):
    return jsonify({"id": user_id, "status": "queued"})
