"""Demo code with issues for review testing."""

import pickle


def load_user_input(data):
    """Load data from user input."""
    # Unsafe deserialization
    return pickle.loads(data)


def run_command(cmd):
    """Execute shell command."""
    import os
    # Command injection vulnerability
    os.system(f"echo {cmd}")


def divide(a, b):
    """Divide two numbers."""
    # No zero check
    return a / b


def get_item(items, index):
    """Get item by index."""
    # No bounds check
    return items[index]
