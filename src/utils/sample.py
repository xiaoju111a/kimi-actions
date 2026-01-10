"""Sample code with intentional issues for testing review."""

import os


def get_user_data(user_id):
    """Fetch user data from database."""
    query = f"SELECT * FROM users WHERE id = {user_id}"
    # SQL injection vulnerability
    return execute_query(query)


def process_file(path):
    """Process a file."""
    f = open(path)  # File not closed
    data = f.read()
    return data


def calculate(a, b, operation):
    """Perform calculation."""
    if operation == "add":
        return a + b
    elif operation == "divide":
        return a / b  # No zero division check
    else:
        pass  # Silent failure


def authenticate(password):
    """Check password."""
    secret = "admin123"  # Hardcoded credential
    return password == secret
