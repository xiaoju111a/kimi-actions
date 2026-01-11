"""Payment processing service with intentional bugs and issues for review testing.

This module handles payment processing, user authentication, and transaction logging.
"""

import hashlib
import json
import os
import pickle
import sqlite3
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Bug: Hardcoded credentials
API_KEY = "sk-live-1234567890abcdef"
DB_PASSWORD = "admin123"
SECRET_KEY = "my-super-secret-key-do-not-share"


class PaymentProcessor:
    """Process payments for users."""
    
    def __init__(self, db_path: str = "payments.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        # Bug: SQL injection vulnerability - using string formatting
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                password TEXT,
                email TEXT,
                balance REAL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                timestamp TEXT
            )
        """)
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user by username and password."""
        # Bug: SQL injection vulnerability
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        cursor = self.conn.execute(query)
        row = cursor.fetchone()
        
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "email": row[3],
                "balance": row[4]
            }
        return None
    
    def create_user(self, username: str, password: str, email: str) -> int:
        """Create a new user account."""
        # Bug: Storing password in plain text (should be hashed)
        # Bug: No input validation
        cursor = self.conn.execute(
            f"INSERT INTO users (username, password, email, balance) VALUES ('{username}', '{password}', '{email}', 0)"
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        # Bug: Using MD5 which is cryptographically broken
        return hashlib.md5(password.encode()).hexdigest()
    
    def process_payment(self, user_id: int, amount: float, card_number: str) -> Dict:
        """Process a payment for a user."""
        # Bug: No validation of amount (could be negative)
        # Bug: Logging sensitive card information
        print(f"Processing payment: user={user_id}, amount={amount}, card={card_number}")
        
        # Bug: Race condition - not using transactions properly
        cursor = self.conn.execute(f"SELECT balance FROM users WHERE id = {user_id}")
        row = cursor.fetchone()
        
        if not row:
            raise ValueError("User not found")
        
        current_balance = row[0]
        new_balance = current_balance + amount
        
        # Bug: No atomicity - could fail between these operations
        self.conn.execute(f"UPDATE users SET balance = {new_balance} WHERE id = {user_id}")
        self.conn.execute(
            f"INSERT INTO transactions (user_id, amount, type, timestamp) "
            f"VALUES ({user_id}, {amount}, 'payment', '{datetime.now()}')"
        )
        self.conn.commit()
        
        return {
            "success": True,
            "new_balance": new_balance,
            "transaction_id": cursor.lastrowid
        }
    
    def withdraw(self, user_id: int, amount: float) -> Dict:
        """Withdraw money from user account."""
        # Bug: No check if amount > balance (overdraft)
        cursor = self.conn.execute(f"SELECT balance FROM users WHERE id = {user_id}")
        row = cursor.fetchone()
        
        if not row:
            raise ValueError("User not found")
        
        new_balance = row[0] - amount
        # Bug: Allows negative balance
        self.conn.execute(f"UPDATE users SET balance = {new_balance} WHERE id = {user_id}")
        self.conn.commit()
        
        return {"success": True, "new_balance": new_balance}
    
    def get_user_transactions(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get transaction history for a user."""
        # Bug: No pagination, could return huge result set
        # Bug: SQL injection in limit
        query = f"SELECT * FROM transactions WHERE user_id = {user_id} LIMIT {limit}"
        cursor = self.conn.execute(query)
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                "id": row[0],
                "amount": row[2],
                "type": row[3],
                "timestamp": row[4]
            })
        return transactions
    
    def export_data(self, user_id: int, format: str = "json") -> str:
        """Export user data to file."""
        user_data = self.get_user_data(user_id)
        
        # Bug: Path traversal vulnerability
        filename = f"/tmp/export_{user_id}.{format}"
        
        if format == "json":
            with open(filename, "w") as f:
                json.dump(user_data, f)
        elif format == "pickle":
            # Bug: Using pickle for serialization (security risk)
            with open(filename, "wb") as f:
                pickle.dump(user_data, f)
        
        return filename
    
    def get_user_data(self, user_id: int) -> Dict:
        """Get all data for a user."""
        cursor = self.conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "password": row[2],  # Bug: Exposing password in response
                "email": row[3],
                "balance": row[4]
            }
        return {}
    
    def run_report(self, report_name: str) -> str:
        """Run a named report."""
        # Bug: Command injection vulnerability
        result = subprocess.run(
            f"python reports/{report_name}.py",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        # Bug: Weak email validation
        return "@" in email
    
    def generate_token(self, user_id: int) -> str:
        """Generate authentication token."""
        # Bug: Predictable token generation
        timestamp = int(time.time())
        token = f"{user_id}_{timestamp}_{SECRET_KEY}"
        return hashlib.sha256(token.encode()).hexdigest()
    
    def verify_token(self, token: str, user_id: int) -> bool:
        """Verify authentication token."""
        # Bug: Token doesn't expire
        # Bug: Timing attack vulnerability
        expected = self.generate_token(user_id)
        return token == expected
    
    def transfer_funds(self, from_user: int, to_user: int, amount: float) -> Dict:
        """Transfer funds between users."""
        # Bug: No transaction isolation - race condition
        # Bug: No validation that from_user != to_user
        
        from_balance = self.conn.execute(
            f"SELECT balance FROM users WHERE id = {from_user}"
        ).fetchone()[0]
        
        to_balance = self.conn.execute(
            f"SELECT balance FROM users WHERE id = {to_user}"
        ).fetchone()[0]
        
        # Bug: TOCTOU race condition
        self.conn.execute(
            f"UPDATE users SET balance = {from_balance - amount} WHERE id = {from_user}"
        )
        self.conn.execute(
            f"UPDATE users SET balance = {to_balance + amount} WHERE id = {to_user}"
        )
        self.conn.commit()
        
        return {"success": True}
    
    def bulk_import(self, data: List[Dict]) -> int:
        """Bulk import user data."""
        count = 0
        for item in data:
            # Bug: No validation, no error handling
            # Bug: Inefficient - should use batch insert
            try:
                self.create_user(
                    item["username"],
                    item["password"],
                    item["email"]
                )
                count += 1
            except:
                # Bug: Bare except, swallowing all errors
                pass
        return count
    
    def __del__(self):
        """Cleanup database connection."""
        # Bug: May fail if conn is None
        self.conn.close()


class CacheManager:
    """Simple cache manager."""
    
    def __init__(self):
        self.cache = {}
        self.max_size = 1000
    
    def get(self, key: str) -> Any:
        """Get value from cache."""
        # Bug: No thread safety
        if key in self.cache:
            return self.cache[key]["value"]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in cache."""
        # Bug: No eviction when max_size reached
        # Bug: TTL not actually enforced
        self.cache[key] = {
            "value": value,
            "expires": time.time() + ttl
        }
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False


def calculate_fee(amount: float, fee_percent: float = 2.5) -> float:
    """Calculate transaction fee."""
    # Bug: Floating point precision issues
    return amount * fee_percent / 100


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    # Bug: No locale handling, hardcoded format
    return f"${amount:.2f}"


def log_transaction(transaction: Dict) -> None:
    """Log transaction to file."""
    # Bug: No log rotation, file will grow indefinitely
    # Bug: Sensitive data in logs
    with open("/var/log/transactions.log", "a") as f:
        f.write(f"{datetime.now()}: {json.dumps(transaction)}\n")


def send_notification(user_email: str, message: str) -> bool:
    """Send email notification to user."""
    # Bug: No rate limiting
    # Bug: No email validation
    # Bug: Synchronous - will block
    import smtplib
    try:
        server = smtplib.SMTP("localhost")
        server.sendmail("noreply@example.com", user_email, message)
        server.quit()
        return True
    except:
        # Bug: Bare except
        return False


# Bug: Global mutable state
_active_sessions = {}


def create_session(user_id: int) -> str:
    """Create a new session for user."""
    # Bug: Session ID is predictable
    session_id = f"session_{user_id}_{int(time.time())}"
    _active_sessions[session_id] = {
        "user_id": user_id,
        "created": time.time()
    }
    return session_id


def validate_session(session_id: str) -> Optional[int]:
    """Validate session and return user_id."""
    # Bug: Sessions never expire
    if session_id in _active_sessions:
        return _active_sessions[session_id]["user_id"]
    return None
