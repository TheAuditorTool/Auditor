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


# VULNERABLE: request.args flows to exec
@app.route('/execute')
def execute_code():
    user_code = request.args.get('code')
    exec(user_code)  # SINK: Code injection
    return jsonify({'status': 'executed'})


# VULNERABLE: request.form flows to eval
@app.route('/calculate', methods=['POST'])
def calculate():
    expression = request.form.get('expr')
    result = eval(expression)  # SINK: Code injection
    return jsonify({'result': result})


# VULNERABLE: request.json flows to os.system
@app.route('/run', methods=['POST'])
def run_command():
    data = request.json
    command = data.get('cmd')
    os.system(command)  # SINK: Command injection
    return jsonify({'status': 'executed'})


# VULNERABLE: request.args flows to SQL query
@app.route('/user')
def get_user():
    user_id = request.args.get('id')
    query = f"SELECT * FROM users WHERE id = {user_id}"  # SINK: SQL injection
    # cursor.execute(query)
    return jsonify({'query': query})


# VULNERABLE: request.args flows to subprocess
@app.route('/ping')
def ping_host():
    host = request.args.get('host')
    result = subprocess.run(['ping', host], capture_output=True)  # SINK: Command injection
    return jsonify({'output': result.stdout.decode()})


if __name__ == '__main__':
    app.run(debug=True)
