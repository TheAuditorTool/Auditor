"""
Assignments with multiple source variables (taint tracking).
Tests: assignments JOIN assignment_sources
"""



def calculate_total_price(base_price, tax_rate, discount_code):
    """
    Assignment has 3 sources: base_price, tax_rate, discount_code
    Should create 3 rows in assignment_sources for the 'total' assignment.
    """
    # This assignment uses 3 source variables
    total = base_price * (1 + tax_rate) * get_discount(discount_code)
    return total


def build_user_query(username, email, role):
    """
    SQL injection risk: query string assembled from 3 sources
    Should create 3 rows in assignment_sources for 'query' assignment.
    All 3 sources are potentially tainted (user input).
    """
    # BAD: String concatenation with multiple tainted sources
    query = f"SELECT * FROM users WHERE username = '{username}' " \
            f"AND email = '{email}' " \
            f"AND role = '{role}'"
    return query


def process_payment(amount, card_number, cvv, billing_zip):
    """
    Payment data assembled from 4 sources (all sensitive).
    Should create 4 rows in assignment_sources for 'payment_data' assignment.
    """
    # All 4 sources are sensitive PII
    payment_data = {
        'amount': amount,
        'card': card_number,
        'cvv': cvv,
        'zip': billing_zip
    }
    return send_to_processor(payment_data)


def log_user_activity(user_id, action, ip_address, user_agent):
    """
    Log message assembled from 4 sources.
    Should create 4 rows in assignment_sources.
    Risk: IP and user_agent are PII.
    """
    # Log message uses multiple sources
    log_message = f"User {user_id} performed {action} from {ip_address} ({user_agent})"
    write_to_log(log_message)


def get_discount(code):
    """Helper function."""
    return 0.9 if code == 'SAVE10' else 1.0


def send_to_processor(data):
    """Helper function."""
    pass


def write_to_log(message):
    """Helper function."""
    pass
