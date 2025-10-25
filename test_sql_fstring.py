"""Test Python f-string SQL extraction."""
import sqlite3

def test_case_1(cursor):
    """F-string with static content should be extracted."""
    user_id = 123
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

def test_case_2(cursor):
    """String concatenation should be extracted."""
    query = "SELECT * " + "FROM users"
    cursor.execute(query)

def test_case_3(cursor):
    """Format string should be extracted."""
    query = "SELECT * FROM {}".format("users")
    cursor.execute(query)

def test_case_4(cursor):
    """Plain string (already working) should still be extracted."""
    cursor.execute("SELECT * FROM users")
