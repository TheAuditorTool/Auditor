"""Controller layer - receives user input (TAINT SOURCE)."""

from flask import Flask, jsonify, request

from .service import SearchService

app = Flask(__name__)
search_service = SearchService()


@app.route("/search")
def search_endpoint():
    """
    TAINT SOURCE: request.args.get('query')

    Expected taint flow:
      user_input (tainted) → search_service.search(user_input) → [cross-file to service.py]
    """

    user_input = request.args.get("query", "")

    results = search_service.search(user_input)

    return jsonify({"results": results})


@app.route("/user/<user_id>")
def get_user(user_id):
    """
    TAINT SOURCE: request.view_args['user_id']

    Expected taint flow:
      user_id (tainted) → search_service.get_user_by_id(user_id) → [cross-file to service.py]
    """

    user_data = search_service.get_user_by_id(user_id)

    return jsonify(user_data)


@app.route("/filter", methods=["POST"])
def filter_data():
    """
    TAINT SOURCE: request.json.get('filter')

    Expected taint flow:
      filter_expr (tainted) → search_service.filter_records(filter_expr) → [cross-file to service.py]
    """

    filter_expr = request.json.get("filter", "")

    filtered = search_service.filter_records(filter_expr)

    return jsonify({"data": filtered})
