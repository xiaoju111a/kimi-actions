"""Sample test module 4 for testing large PR reviews."""
from datetime import datetime, timedelta


def get_current_timestamp() -> int:
    """Get current Unix timestamp."""
    return int(datetime.now().timestamp())


def format_date(dt: datetime) -> str:
    """Format datetime to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class DateUtils:
    """Date and time utilities."""
    
    def add_days(self, dt: datetime, days: int) -> datetime:
        """Add days to datetime."""
        return dt + timedelta(days=days)
    
    def is_weekend(self, dt: datetime) -> bool:
        """Check if date is weekend."""
        return dt.weekday() >= 5
