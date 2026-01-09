"""Diff processing utilities - file filtering and binary detection.

Note: Diff parsing and chunking moved to token_handler.py (DiffChunker class).
This module now focuses on file filtering only.
"""

import fnmatch
from pathlib import PurePath


# Non-text file suffixes (binary files to skip)
NON_TEXT_SUFFIXES = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    # Audio/Video
    ".mp3", ".wav", ".mp4", ".avi", ".mov",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2",
    # Binaries
    ".exe", ".dll", ".so", ".dylib", ".pyc", ".class", ".jar",
    # Database
    ".sqlite", ".db",
}

# Default exclude patterns
DEFAULT_EXCLUDE_PATTERNS = [
    "*.lock",
    "*.min.js",
    "*.min.css",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "*.map",
]


def is_binary_file(filename: str) -> bool:
    """Check if file is binary based on extension."""
    suffix = PurePath(filename).suffix.lower()
    return suffix in NON_TEXT_SUFFIXES


def should_exclude(filename: str, patterns: list = None) -> bool:
    """Check if file should be excluded from review.
    
    Args:
        filename: File path to check
        patterns: List of glob patterns to exclude
        
    Returns:
        True if file should be excluded
    """
    patterns = patterns or DEFAULT_EXCLUDE_PATTERNS
    
    # Check explicit patterns
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    
    # Check if file is binary
    if is_binary_file(filename):
        return True
    
    return False


def filter_files(files: list, patterns: list = None) -> list:
    """Filter out excluded files.
    
    Args:
        files: List of file paths
        patterns: List of glob patterns to exclude
        
    Returns:
        Filtered list of files
    """
    return [f for f in files if not should_exclude(f, patterns)]
