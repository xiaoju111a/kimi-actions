"""Sample test module 2 for testing large PR reviews."""


def validate_email(email: str) -> bool:
    """Validate email format."""
    return "@" in email and "." in email


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    return len(phone) >= 10 and phone.isdigit()


class Validator:
    """Input validation class."""
    
    def is_valid_username(self, username: str) -> bool:
        """Check if username is valid."""
        return len(username) >= 3 and username.isalnum()
    
    def is_valid_password(self, password: str) -> bool:
        """Check if password is strong enough."""
        return len(password) >= 8
