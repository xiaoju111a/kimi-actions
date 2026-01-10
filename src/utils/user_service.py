"""User service module with various issues for testing."""

import os
import pickle
import hashlib
import subprocess


class UserService:
    """Service for managing users."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.cache = {}
        self.secret_key = "super_secret_key_123"  # Hardcoded secret

    def get_user(self, user_id):
        """Get user by ID."""
        # SQL injection vulnerability
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return self.db.execute(query)

    def authenticate(self, username, password):
        """Authenticate user."""
        # Weak password hashing
        hashed = hashlib.md5(password.encode()).hexdigest()
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{hashed}'"
        return self.db.execute(query)

    def create_user(self, data):
        """Create a new user."""
        # No input validation
        username = data["username"]
        email = data["email"]
        password = data["password"]
        
        # Storing plain text password
        query = f"INSERT INTO users (username, email, password) VALUES ('{username}', '{email}', '{password}')"
        self.db.execute(query)
        return {"status": "created"}

    def delete_user(self, user_id):
        """Delete user - no authorization check."""
        query = f"DELETE FROM users WHERE id = {user_id}"
        self.db.execute(query)

    def export_users(self, filename):
        """Export users to file."""
        users = self.db.execute("SELECT * FROM users")
        # Path traversal vulnerability
        with open(f"/data/exports/{filename}", "w") as f:
            f.write(str(users))

    def import_users(self, data):
        """Import users from serialized data."""
        # Unsafe deserialization
        users = pickle.loads(data)
        for user in users:
            self.create_user(user)

    def run_report(self, report_name):
        """Run a report script."""
        # Command injection
        result = subprocess.run(f"python reports/{report_name}.py", shell=True, capture_output=True)
        return result.stdout

    def get_user_avatar(self, user_id):
        """Get user avatar URL."""
        user = self.get_user(user_id)
        # SSRF vulnerability - no URL validation
        avatar_url = user.get("avatar_url", "")
        import requests
        response = requests.get(avatar_url)
        return response.content

    def update_profile(self, user_id, profile_data):
        """Update user profile."""
        # Mass assignment vulnerability
        for key, value in profile_data.items():
            query = f"UPDATE users SET {key} = '{value}' WHERE id = {user_id}"
            self.db.execute(query)

    def search_users(self, search_term):
        """Search users by name."""
        # XSS vulnerability - no output encoding
        query = f"SELECT * FROM users WHERE name LIKE '%{search_term}%'"
        results = self.db.execute(query)
        return f"<div>Found: {results}</div>"

    def log_action(self, action, details):
        """Log user action."""
        # Sensitive data in logs
        print(f"Action: {action}, Details: {details}, Secret: {self.secret_key}")

    def calculate_age(self, birth_year):
        """Calculate user age."""
        # No error handling
        current_year = 2024
        return current_year - int(birth_year)

    def process_payment(self, amount, card_number):
        """Process payment."""
        # Logging sensitive data
        print(f"Processing payment: {amount} with card {card_number}")
        # No validation
        return {"status": "success", "amount": amount}
