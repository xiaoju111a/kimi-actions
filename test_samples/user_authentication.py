"""
User Authentication Module
Handles user registration, login, password management, and session handling.
"""

import os
import jwt
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict


class UserAuthentication:
    """Service for user authentication and authorization."""
    
    def __init__(self, secret_key: str, database_url: str):
        # SECURITY: Secret key passed as parameter, might be logged
        self.secret_key = secret_key
        self.database_url = database_url
        self.sessions = {}  # BUG: In-memory sessions, not scalable
        
    def register_user(self, username: str, password: str, email: str):
        """Register a new user."""
        # BUG: No input validation
        # SECURITY: No password strength check
        
        # SECURITY: Weak password hashing (MD5)
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        # SECURITY: SQL injection vulnerability
        query = f"INSERT INTO users (username, password, email) VALUES ('{username}', '{password_hash}', '{email}')"
        
        # BUG: No error handling for duplicate username
        self._execute_query(query)
        
        return {"status": "success", "username": username}
    
    def login(self, username: str, password: str):
        """Authenticate user and create session."""
        # BUG: No rate limiting
        # SECURITY: Timing attack vulnerability
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE username = '{username}'"
        user = self._execute_query(query)
        
        if not user:
            # SECURITY: Reveals if username exists
            return {"error": "Username not found"}
        
        # SECURITY: Weak password hashing
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        # SECURITY: Timing attack - simple string comparison
        if user["password"] == password_hash:
            # SECURITY: Predictable session token
            session_token = self._generate_session_token(username)
            
            # BUG: No session expiration
            self.sessions[session_token] = {
                "username": username,
                "created_at": datetime.now().isoformat()
            }
            
            return {"status": "success", "token": session_token}
        else:
            # SECURITY: Reveals password is wrong
            return {"error": "Invalid password"}
    
    def _generate_session_token(self, username: str):
        """Generate session token."""
        # SECURITY: Predictable token generation
        return hashlib.md5(f"{username}{datetime.now()}".encode()).hexdigest()
    
    def logout(self, session_token: str):
        """Logout user and invalidate session."""
        # BUG: No validation of session_token
        if session_token in self.sessions:
            del self.sessions[session_token]
            return {"status": "success"}
        return {"error": "Invalid session"}
    
    def verify_session(self, session_token: str):
        """Verify if session is valid."""
        # BUG: No session expiration check
        return session_token in self.sessions
    
    def change_password(self, username: str, old_password: str, new_password: str):
        """Change user password."""
        # BUG: No verification of current session
        # SECURITY: No password strength validation
        
        # Verify old password
        user = self._get_user(username)
        old_hash = hashlib.md5(old_password.encode()).hexdigest()
        
        if user["password"] != old_hash:
            return {"error": "Invalid old password"}
        
        # SECURITY: Weak hashing
        new_hash = hashlib.md5(new_password.encode()).hexdigest()
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET password = '{new_hash}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def reset_password(self, email: str):
        """Send password reset email."""
        # SECURITY: No rate limiting
        # BUG: No validation of email format
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE email = '{email}'"
        user = self._execute_query(query)
        
        if not user:
            # SECURITY: Reveals if email exists
            return {"error": "Email not found"}
        
        # SECURITY: Predictable reset token
        reset_token = hashlib.md5(f"{email}{datetime.now()}".encode()).hexdigest()
        
        # BUG: No expiration time for reset token
        # SECURITY: SQL injection
        query = f"UPDATE users SET reset_token = '{reset_token}' WHERE email = '{email}'"
        self._execute_query(query)
        
        # BUG: No actual email sending
        print(f"Reset token for {email}: {reset_token}")
        
        return {"status": "success"}
    
    def confirm_password_reset(self, reset_token: str, new_password: str):
        """Confirm password reset with token."""
        # BUG: No token expiration check
        # SECURITY: No password strength validation
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE reset_token = '{reset_token}'"
        user = self._execute_query(query)
        
        if not user:
            return {"error": "Invalid reset token"}
        
        # SECURITY: Weak hashing
        new_hash = hashlib.md5(new_password.encode()).hexdigest()
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET password = '{new_hash}', reset_token = NULL WHERE reset_token = '{reset_token}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def _get_user(self, username: str):
        """Get user by username."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE username = '{username}'"
        return self._execute_query(query)
    
    def _execute_query(self, query: str):
        """Execute database query."""
        # Placeholder for database execution
        pass
    
    def create_jwt_token(self, username: str):
        """Create JWT token for user."""
        # SECURITY: No expiration time
        payload = {
            "username": username,
            "created_at": datetime.now().isoformat()
        }
        
        # SECURITY: Using HS256 which is less secure
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return token
    
    def verify_jwt_token(self, token: str):
        """Verify JWT token."""
        try:
            # BUG: No algorithm verification
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except:
            # BUG: Catching all exceptions
            return None
    
    def get_user_profile(self, username: str):
        """Get user profile information."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE username = '{username}'"
        user = self._execute_query(query)
        
        # SECURITY: Returning password hash
        return user
    
    def update_user_profile(self, username: str, data: dict):
        """Update user profile."""
        # BUG: No validation of data fields
        # SECURITY: SQL injection vulnerability
        
        updates = []
        for key, value in data.items():
            # SECURITY: No sanitization
            updates.append(f"{key} = '{value}'")
        
        update_str = ", ".join(updates)
        query = f"UPDATE users SET {update_str} WHERE username = '{username}'"
        
        self._execute_query(query)
        return {"status": "success"}
    
    def delete_user(self, username: str):
        """Delete user account."""
        # BUG: No confirmation required
        # BUG: No soft delete
        
        # SECURITY: SQL injection
        query = f"DELETE FROM users WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def check_username_available(self, username: str):
        """Check if username is available."""
        # SECURITY: SQL injection
        query = f"SELECT COUNT(*) FROM users WHERE username = '{username}'"
        count = self._execute_query(query)
        
        return count == 0
    
    def generate_api_key(self, username: str):
        """Generate API key for user."""
        # SECURITY: Weak API key generation
        api_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET api_key = '{api_key}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return api_key
    
    def verify_api_key(self, api_key: str):
        """Verify API key."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE api_key = '{api_key}'"
        user = self._execute_query(query)
        
        return user is not None
    
    def enable_two_factor(self, username: str):
        """Enable two-factor authentication."""
        # SECURITY: Weak secret generation
        secret = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET two_factor_secret = '{secret}', two_factor_enabled = 1 WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"secret": secret}
    
    def verify_two_factor_code(self, username: str, code: str):
        """Verify two-factor authentication code."""
        # BUG: No rate limiting
        # SECURITY: Simple string comparison
        
        user = self._get_user(username)
        
        # BUG: Simplified verification, no TOTP implementation
        expected_code = user.get("two_factor_secret", "")[:6]
        
        return code == expected_code
    
    def disable_two_factor(self, username: str, password: str):
        """Disable two-factor authentication."""
        # BUG: No additional verification
        
        user = self._get_user(username)
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        if user["password"] != password_hash:
            return {"error": "Invalid password"}
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET two_factor_enabled = 0 WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def log_login_attempt(self, username: str, success: bool, ip_address: str):
        """Log login attempt."""
        # SECURITY: SQL injection
        query = f"INSERT INTO login_logs (username, success, ip_address, timestamp) VALUES ('{username}', {success}, '{ip_address}', '{datetime.now().isoformat()}')"
        self._execute_query(query)
    
    def get_login_history(self, username: str):
        """Get login history for user."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM login_logs WHERE username = '{username}' ORDER BY timestamp DESC"
        return self._execute_query(query)
    
    def check_password_strength(self, password: str):
        """Check password strength."""
        # BUG: Weak password requirements
        if len(password) < 6:
            return False
        return True
    
    def hash_password(self, password: str):
        """Hash password."""
        # SECURITY: Using MD5 which is broken
        return hashlib.md5(password.encode()).hexdigest()
    
    def verify_email(self, email: str, verification_code: str):
        """Verify user email."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM users WHERE email = '{email}' AND verification_code = '{verification_code}'"
        user = self._execute_query(query)
        
        if user:
            # SECURITY: SQL injection
            query = f"UPDATE users SET email_verified = 1 WHERE email = '{email}'"
            self._execute_query(query)
            return {"status": "success"}
        
        return {"error": "Invalid verification code"}
    
    def send_verification_email(self, email: str):
        """Send email verification."""
        # SECURITY: Predictable verification code
        code = ''.join(random.choices(string.digits, k=6))
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET verification_code = '{code}' WHERE email = '{email}'"
        self._execute_query(query)
        
        # BUG: No actual email sending
        print(f"Verification code for {email}: {code}")
        
        return {"status": "success"}
    
    def lock_account(self, username: str, reason: str):
        """Lock user account."""
        # BUG: No notification to user
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET locked = 1, lock_reason = '{reason}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def unlock_account(self, username: str):
        """Unlock user account."""
        # BUG: No verification required
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET locked = 0, lock_reason = NULL WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def is_account_locked(self, username: str):
        """Check if account is locked."""
        user = self._get_user(username)
        return user.get("locked", False)
    
    def get_failed_login_attempts(self, username: str):
        """Get count of failed login attempts."""
        # SECURITY: SQL injection
        query = f"SELECT COUNT(*) FROM login_logs WHERE username = '{username}' AND success = 0 AND timestamp > '{(datetime.now() - timedelta(hours=1)).isoformat()}'"
        return self._execute_query(query)
    
    def reset_failed_login_attempts(self, username: str):
        """Reset failed login attempt counter."""
        # SECURITY: SQL injection
        query = f"DELETE FROM login_logs WHERE username = '{username}' AND success = 0"
        self._execute_query(query)
    
    def check_account_lockout(self, username: str):
        """Check if account should be locked due to failed attempts."""
        failed_attempts = self.get_failed_login_attempts(username)
        
        # BUG: Hardcoded threshold
        if failed_attempts >= 5:
            self.lock_account(username, "Too many failed login attempts")
            return True
        
        return False
    
    def create_session(self, username: str, ip_address: str):
        """Create user session."""
        # SECURITY: Predictable session ID
        session_id = hashlib.md5(f"{username}{ip_address}{datetime.now()}".encode()).hexdigest()
        
        # BUG: No session expiration
        session_data = {
            "username": username,
            "ip_address": ip_address,
            "created_at": datetime.now().isoformat()
        }
        
        self.sessions[session_id] = session_data
        
        return session_id
    
    def get_session(self, session_id: str):
        """Get session data."""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, data: dict):
        """Update session data."""
        if session_id in self.sessions:
            self.sessions[session_id].update(data)
            return True
        return False
    
    def delete_session(self, session_id: str):
        """Delete session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def get_all_user_sessions(self, username: str):
        """Get all active sessions for user."""
        # PERFORMANCE: Iterating through all sessions
        user_sessions = []
        for session_id, session_data in self.sessions.items():
            if session_data.get("username") == username:
                user_sessions.append({
                    "session_id": session_id,
                    "created_at": session_data.get("created_at"),
                    "ip_address": session_data.get("ip_address")
                })
        return user_sessions
    
    def revoke_all_sessions(self, username: str):
        """Revoke all sessions for user."""
        # PERFORMANCE: Iterating and modifying dict
        sessions_to_delete = []
        for session_id, session_data in self.sessions.items():
            if session_data.get("username") == username:
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            del self.sessions[session_id]
        
        return {"status": "success", "revoked": len(sessions_to_delete)}
    
    def check_permission(self, username: str, permission: str):
        """Check if user has permission."""
        # SECURITY: SQL injection
        query = f"SELECT permissions FROM users WHERE username = '{username}'"
        user = self._execute_query(query)
        
        # BUG: Simple string check, no proper permission system
        permissions = user.get("permissions", "").split(",")
        return permission in permissions
    
    def grant_permission(self, username: str, permission: str):
        """Grant permission to user."""
        # BUG: No validation of permission
        
        user = self._get_user(username)
        current_permissions = user.get("permissions", "").split(",")
        
        if permission not in current_permissions:
            current_permissions.append(permission)
        
        new_permissions = ",".join(current_permissions)
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET permissions = '{new_permissions}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def revoke_permission(self, username: str, permission: str):
        """Revoke permission from user."""
        user = self._get_user(username)
        current_permissions = user.get("permissions", "").split(",")
        
        if permission in current_permissions:
            current_permissions.remove(permission)
        
        new_permissions = ",".join(current_permissions)
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET permissions = '{new_permissions}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def get_user_roles(self, username: str):
        """Get user roles."""
        # SECURITY: SQL injection
        query = f"SELECT roles FROM users WHERE username = '{username}'"
        user = self._execute_query(query)
        
        return user.get("roles", "").split(",")
    
    def assign_role(self, username: str, role: str):
        """Assign role to user."""
        # BUG: No validation of role
        
        current_roles = self.get_user_roles(username)
        
        if role not in current_roles:
            current_roles.append(role)
        
        new_roles = ",".join(current_roles)
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET roles = '{new_roles}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def remove_role(self, username: str, role: str):
        """Remove role from user."""
        current_roles = self.get_user_roles(username)
        
        if role in current_roles:
            current_roles.remove(role)
        
        new_roles = ",".join(current_roles)
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET roles = '{new_roles}' WHERE username = '{username}'"
        self._execute_query(query)
        
        return {"status": "success"}
    
    def validate_session_ip(self, session_id: str, ip_address: str):
        """Validate session IP address."""
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        # BUG: Strict IP matching, doesn't handle dynamic IPs
        return session.get("ip_address") == ip_address
    
    def refresh_session(self, session_id: str):
        """Refresh session expiration."""
        # BUG: No actual expiration implementation
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.now().isoformat()
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        # BUG: No actual expiration check
        # PERFORMANCE: Iterating all sessions
        
        expired = []
        for session_id, session_data in self.sessions.items():
            created_at = datetime.fromisoformat(session_data["created_at"])
            age = (datetime.now() - created_at).total_seconds()
            
            # BUG: Hardcoded expiration time
            if age > 3600:  # 1 hour
                expired.append(session_id)
        
        for session_id in expired:
            del self.sessions[session_id]
        
        return len(expired)
