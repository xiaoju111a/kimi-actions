"""Tests for diff_processor module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diff_processor import (
    is_binary_file, should_exclude, filter_files,
    NON_TEXT_SUFFIXES, DEFAULT_EXCLUDE_PATTERNS
)


class TestIsBinaryFile:
    """Tests for is_binary_file function."""
    
    def test_image_files(self):
        assert is_binary_file("photo.png") is True
        assert is_binary_file("image.jpg") is True
        assert is_binary_file("icon.gif") is True
        assert is_binary_file("logo.svg") is True
    
    def test_document_files(self):
        assert is_binary_file("doc.pdf") is True
        assert is_binary_file("report.docx") is True
        assert is_binary_file("data.xlsx") is True
    
    def test_archive_files(self):
        assert is_binary_file("archive.zip") is True
        assert is_binary_file("backup.gz") is True  # .gz is in list
        assert is_binary_file("package.7z") is True
    
    def test_binary_executables(self):
        assert is_binary_file("app.exe") is True
        assert is_binary_file("lib.dll") is True
        assert is_binary_file("module.so") is True
        assert is_binary_file("cache.pyc") is True
    
    def test_text_files(self):
        assert is_binary_file("main.py") is False
        assert is_binary_file("app.js") is False
        assert is_binary_file("README.md") is False
        assert is_binary_file("config.yaml") is False
    
    def test_case_insensitive(self):
        assert is_binary_file("IMAGE.PNG") is True
        assert is_binary_file("Photo.JPG") is True


class TestShouldExclude:
    """Tests for should_exclude function."""
    
    def test_lock_files(self):
        assert should_exclude("package-lock.json") is True
        assert should_exclude("yarn.lock") is True
        assert should_exclude("pnpm-lock.yaml") is True
    
    def test_minified_files(self):
        assert should_exclude("bundle.min.js") is True
        assert should_exclude("styles.min.css") is True
    
    def test_source_maps(self):
        assert should_exclude("app.js.map") is True
        assert should_exclude("styles.css.map") is True
    
    def test_binary_files(self):
        assert should_exclude("image.png") is True
        assert should_exclude("font.woff2") is True
    
    def test_normal_files(self):
        assert should_exclude("main.py") is False
        assert should_exclude("app.tsx") is False
        assert should_exclude("README.md") is False
    
    def test_custom_patterns(self):
        patterns = ["*.log", "temp/*"]
        assert should_exclude("debug.log", patterns) is True
        assert should_exclude("main.py", patterns) is False
    
    def test_empty_patterns(self):
        # With empty patterns, only binary check applies
        assert should_exclude("main.py", []) is False
        assert should_exclude("image.png", []) is True


class TestFilterFiles:
    """Tests for filter_files function."""
    
    def test_filter_mixed_files(self):
        files = [
            "main.py",
            "package-lock.json",
            "image.png",
            "app.tsx",
            "bundle.min.js"
        ]
        filtered = filter_files(files)
        
        assert "main.py" in filtered
        assert "app.tsx" in filtered
        assert "package-lock.json" not in filtered
        assert "image.png" not in filtered
        assert "bundle.min.js" not in filtered
    
    def test_filter_all_valid(self):
        files = ["a.py", "b.js", "c.go"]
        filtered = filter_files(files)
        assert filtered == files
    
    def test_filter_all_excluded(self):
        files = ["a.png", "b.lock", "c.min.js"]
        filtered = filter_files(files)
        assert filtered == []
    
    def test_filter_empty_list(self):
        assert filter_files([]) == []
    
    def test_filter_custom_patterns(self):
        files = ["main.py", "debug.log", "test.py"]
        filtered = filter_files(files, ["*.log"])
        
        assert "main.py" in filtered
        assert "test.py" in filtered
        assert "debug.log" not in filtered
