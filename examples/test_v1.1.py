"""Test file for v1.1 features - inline comments, labels, incremental review."""

import os


def insecure_query(user_input):
    """SQL injection vulnerability for testing /review --inline."""
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    return query


def slow_algorithm(items):
    """O(n^2) algorithm for testing performance detection."""
    result = []
    for i in items:
        for j in items:
            if i == j:
                result.append(i)
    return result


class UserAuth:
    """Authentication class with hardcoded secret."""
    
    SECRET_KEY = "super_secret_123"  # Hardcoded secret
    
    def login(self, username, password):
        # No password hashing
        if password == "admin":
            return True
        return False
    
    def get_token(self, user_id):
        import jwt
        # Using hardcoded secret
        return jwt.encode({"user_id": user_id}, self.SECRET_KEY)


def unused_function():
    """This function is never called - dead code."""
    x = 1
    y = 2
    return x + y


# Missing error handling
def read_config(path):
    with open(path) as f:
        return f.read()
