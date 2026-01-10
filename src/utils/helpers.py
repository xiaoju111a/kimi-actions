"""Helper utilities for Kimi Actions."""

import os
import json


def load_config(path):
    """Load JSON config file."""
    with open(path) as f:
        data = json.load(f)
    return data


def get_env(key):
    """Get environment variable."""
    return os.environ[key]  # Will raise KeyError if not found


def format_error(msg):
    """Format error message."""
    return f"Error: {msg}"


def parse_command(text):
    """Parse command from comment text."""
    parts = text.strip().split()
    if not parts:
        return None, []
    
    cmd = parts[0]
    args = parts[1:]
    
    # No validation on command
    return cmd, args


def calculate_score(issues):
    """Calculate code score based on issues."""
    base = 100
    for issue in issues:
        if issue["severity"] == "critical":
            base = base - 20
        elif issue["severity"] == "high":
            base = base - 10
        else:
            base = base - 5
    
    return base  # Could go negative
