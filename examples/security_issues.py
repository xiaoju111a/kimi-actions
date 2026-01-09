"""Security issues for testing."""

import os
import pickle


# BUG 1: Command injection
def run_command(user_input):
    os.system(f"echo {user_input}")


# BUG 2: Insecure deserialization
def load_data(data):
    return pickle.loads(data)


# BUG 3: Hardcoded credentials
API_KEY = "sk-1234567890abcdef"
PASSWORD = "admin123"


# BUG 4: Path traversal
def read_user_file(filename):
    with open(f"/data/{filename}", "r") as f:
        return f.read()
