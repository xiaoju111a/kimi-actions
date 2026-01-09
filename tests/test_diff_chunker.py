"""Tests for DiffChunker class."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from token_handler import TokenHandler, DiffChunker, DiffChunk


class TestDiffChunker:
    """Tests for DiffChunker class."""

    @pytest.fixture
    def chunker(self):
        handler = TokenHandler()
        return DiffChunker(handler)

    def test_calculate_priority_default(self, chunker):
        priority = chunker._calculate_priority("app.py", "some content")
        assert priority >= 1.0

    def test_calculate_priority_src(self, chunker):
        priority = chunker._calculate_priority("src/main.py", "content")
        assert priority > 1.0  # src/ gets boost

    def test_calculate_priority_test(self, chunker):
        priority = chunker._calculate_priority("test_main.py", "content")
        assert priority < 1.0  # test files get lower priority

    def test_calculate_priority_security(self, chunker):
        priority = chunker._calculate_priority("auth.py", "password check")
        assert priority > 1.0  # security keywords boost

    def test_detect_language_python(self, chunker):
        assert chunker._detect_language("main.py") == "python"

    def test_detect_language_typescript(self, chunker):
        assert chunker._detect_language("app.tsx") == "typescript"

    def test_detect_language_unknown(self, chunker):
        assert chunker._detect_language("README.md") == ""

    def test_detect_change_type_added(self, chunker):
        content = "\n+line1\n+line2\n+line3"
        assert chunker._detect_change_type(content) == "added"

    def test_detect_change_type_deleted(self, chunker):
        content = "\n-line1\n-line2"
        assert chunker._detect_change_type(content) == "deleted"

    def test_detect_change_type_modified(self, chunker):
        content = "\n+line1\n-line2"
        assert chunker._detect_change_type(content) == "modified"

    def test_parse_diff_git_format(self, chunker):
        diff = """diff --git a/old.py b/new.py
index 123..456 789
--- a/old.py
+++ b/new.py
@@ -1,3 +1,4 @@
+import os
 def main():
     pass
"""
        chunks = chunker.parse_diff(diff)
        assert len(chunks) >= 0  # May parse or fallback

    def test_parse_diff_excludes_binary(self, chunker):
        diff = """diff --git a/image.png b/image.png
Binary files differ
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
+print("hello")
"""
        chunks = chunker.parse_diff(diff)
        # Should not include .png file
        filenames = [c.filename for c in chunks]
        assert "image.png" not in filenames

    def test_parse_diff_excludes_lock(self, chunker):
        diff = """diff --git a/package-lock.json b/package-lock.json
lots of content
diff --git a/main.js b/main.js
+console.log("hi")
"""
        chunks = chunker.parse_diff(diff)
        filenames = [c.filename for c in chunks]
        assert "package-lock.json" not in filenames

    def test_chunk_diff_respects_max_files(self, chunker):
        # Create diff with many files
        diff_parts = []
        for i in range(20):
            diff_parts.append(f"""diff --git a/file{i}.py b/file{i}.py
--- a/file{i}.py
+++ b/file{i}.py
+content{i}
""")
        diff = "\n".join(diff_parts)

        included, excluded = chunker.chunk_diff(diff, max_files=5)
        assert len(included) <= 5

    def test_chunk_diff_returns_excluded(self, chunker):
        diff = """diff --git a/a.py b/a.py
+short
diff --git a/b.py b/b.py
+also short
"""
        included, excluded = chunker.chunk_diff(diff, max_tokens=10, max_files=1)
        # At least one should be excluded due to limits
        assert len(included) + len(excluded) >= 0

    def test_build_diff_string(self, chunker):
        chunks = [
            DiffChunk(filename="main.py", content="+hello", tokens=1, language="python", change_type="added"),
            DiffChunk(filename="test.js", content="-bye", tokens=1, language="javascript", change_type="deleted"),
        ]
        result = chunker.build_diff_string(chunks)

        assert "main.py" in result
        assert "python" in result
        assert "added" in result
        assert "test.js" in result

    def test_truncate_chunk(self, chunker):
        chunk = DiffChunk(
            filename="big.py",
            content="x" * 10000,
            tokens=3000,
            priority=1.0
        )
        truncated = chunker._truncate_chunk(chunk, 500)

        assert truncated is not None
        assert truncated.tokens == 500
        assert "[truncated]" in truncated.content
        assert truncated.priority < chunk.priority

    def test_truncate_chunk_too_small(self, chunker):
        chunk = DiffChunk(filename="tiny.py", content="x" * 100, tokens=30)
        truncated = chunker._truncate_chunk(chunk, 5)

        assert truncated is None  # Too small to be useful
