"""
Flask Taint Test Fixture

Source: request.args, request.form, request.json (user input)
Sink: exec(), eval(), os.system() (code/command execution)

Expected: Taint flow detected from request.* -> dangerous functions
"""

import os
import subprocess

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/execute")
def execute_code():
    user_code = request.args.get("code")
    exec(user_code)
    return jsonify({"status": "executed"})


@app.route("/calculate", methods=["POST"])
def calculate():
    expression = request.form.get("expr")
    result = eval(expression)
    return jsonify({"result": result})


@app.route("/run", methods=["POST"])
def run_command():
    data = request.json
    command = data.get("cmd")
    os.system(command)
    return jsonify({"status": "executed"})


@app.route("/user")
def get_user():
    user_id = request.args.get("id")
    query = f"SELECT * FROM users WHERE id = {user_id}"

    return jsonify({"query": query})


@app.route("/ping")
def ping_host():
    host = request.args.get("host")
    result = subprocess.run(["ping", host], capture_output=True)
    return jsonify({"output": result.stdout.decode()})


if __name__ == "__main__":
    app.run(debug=True)
