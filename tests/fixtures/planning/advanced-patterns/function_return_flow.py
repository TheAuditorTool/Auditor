"""
Cross-function taint flow (function returns → assignments).
Tests: function_return_sources JOIN assignment_sources
"""


def get_user_input():
    """
    Returns tainted data from user input.
    Should create 1 row in function_return_sources: 'user_data'
    """
    user_data = input("Enter username: ")
    return user_data


def fetch_api_data(endpoint):
    """
    Returns data from external API (potentially tainted).
    Should create 1 row in function_return_sources: 'response_data'
    """
    import requests
    response_data = requests.get(endpoint).json()
    return response_data


def build_sql_query():
    """
    Returns SQL query string (source for injection).
    Should create 1 row in function_return_sources: 'query'
    """
    # Get tainted input
    username = get_user_input()  # Tainted source

    # Build query with tainted data
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return query


def execute_dangerous_query():
    """
    Executes query from another function (sink for SQL injection).
    Taint flow: get_user_input() → build_sql_query() → execute_dangerous_query()
    """
    import sqlite3

    # Get query from another function (tainted)
    sql = build_sql_query()  # Assignment from function return

    # Execute tainted SQL (SINK)
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute(sql)  # SQL INJECTION
    return cursor.fetchall()


def process_payment_data():
    """
    Returns sensitive payment info.
    Should create 3 rows in function_return_sources: card_number, cvv, amount
    """
    card_number = "4111111111111111"
    cvv = "123"
    amount = 99.99
    return card_number, cvv, amount


def log_payment():
    """
    Logs payment data from another function (data leak risk).
    Taint flow: process_payment_data() → log_payment()
    """
    # Get sensitive data from function
    card, cvv, amt = process_payment_data()  # 3 assignments from function return

    # BAD: Logging sensitive data
    print(f"Payment: card={card}, cvv={cvv}, amount={amt}")


def chain_taint_flow():
    """
    Multi-hop taint flow across 3 functions.
    get_user_input() → fetch_api_data() → chain_taint_flow()
    """
    # Get tainted input
    user_id = get_user_input()

    # Use tainted input in API call
    api_url = f"https://api.example.com/users/{user_id}"
    user_data = fetch_api_data(api_url)  # user_id taints the URL

    # Use API data in SQL query (double taint)
    email = user_data.get('email')
    query = f"SELECT * FROM logs WHERE email = '{email}'"

    import sqlite3
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute(query)  # SINK: SQL injection from multi-hop taint
    return cursor.fetchall()
