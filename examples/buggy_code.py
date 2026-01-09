"""Example buggy code for testing Kimi Actions."""

import sqlite3


def get_user(user_id):
    """Get user by ID - has SQL injection vulnerability."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # BUG: SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()


def divide(a, b):
    """Divide two numbers - missing zero check."""
    # BUG: No check for division by zero
    return a / b


def process_items(items):
    """Process items - inefficient O(n²) algorithm."""
    result = []
    for item in items:
        # BUG: O(n²) complexity - checking 'in' on list
        if item not in result:
            result.append(item)
    return result


def read_file(filename):
    """Read file - no error handling."""
    # BUG: No try-except, file might not exist
    f = open(filename, "r")
    content = f.read()
    # BUG: File not closed properly
    return content


def authenticate(password):
    """Check password - hardcoded secret."""
    # BUG: Hardcoded password
    if password == "admin123":
        return True
    return False


class UserManager:
    """User manager with issues."""
    
    def __init__(self):
        self.users = []
    
    def add_user(self, user):
        # BUG: No validation
        self.users.append(user)
    
    def find_user(self, name):
        # BUG: Returns None without explicit handling
        for user in self.users:
            if user.get("name") == name:
                return user
