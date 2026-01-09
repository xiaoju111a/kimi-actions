"""Tests for token_handler module."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from token_handler import (
    TokenHandler, TokenStats, DiffChunker, DiffChunk,
    ModelConfig, ModelTier, KIMI_MODELS, FALLBACK_CHAIN,
    select_model_for_diff
)


class TestTokenHandler:
    """Tests for TokenHandler class."""
    
    def test_init_default_model(self):
        handler = TokenHandler()
        assert handler.model == "kimi-k2-turbo-preview"
        assert handler.model_config.max_context == 256000
    
    def test_init_custom_model(self):
        handler = TokenHandler("moonshot-v1-128k")
        assert handler.model == "moonshot-v1-128k"
        assert handler.model_config.max_context == 128000
    
    def test_estimate_tokens_empty(self):
        handler = TokenHandler()
        stats = handler.estimate_tokens("")
        assert stats.total_tokens == 0
        assert stats.total_chars == 0
    
    def test_estimate_tokens_english(self):
        handler = TokenHandler()
        text = "This is a simple English text for testing."
        stats = handler.estimate_tokens(text)
        
        assert stats.total_tokens > 0
        # English text should have some english tokens
        assert stats.total_chars == len(text)
    
    def test_estimate_tokens_chinese(self):
        handler = TokenHandler()
        text = "这是一段中文测试文本"
        stats = handler.estimate_tokens(text)
        
        assert stats.total_tokens > 0
        assert stats.chinese_tokens > 0
        # ~1.5 chars per token for Chinese
        assert stats.chinese_tokens == int(len(text) / 1.5)
    
    def test_estimate_tokens_mixed(self):
        handler = TokenHandler()
        text = "Hello 你好 World 世界"
        stats = handler.estimate_tokens(text)
        
        assert stats.total_tokens > 0
        assert stats.chinese_tokens > 0
        # Mixed content should have total chars
        assert stats.total_chars == len(text)
    
    def test_estimate_tokens_code(self):
        handler = TokenHandler()
        text = "```python\ndef hello():\n    print('world')\n```"
        stats = handler.estimate_tokens(text)
        
        assert stats.total_tokens > 0
        assert stats.code_tokens > 0
    
    def test_count_tokens(self):
        handler = TokenHandler()
        text = "Simple test text"
        count = handler.count_tokens(text)
        stats = handler.estimate_tokens(text)
        
        assert count == stats.total_tokens
    
    def test_fits_in_context_small(self):
        handler = TokenHandler()
        small_text = "Hello world"
        assert handler.fits_in_context(small_text) is True
    
    def test_fits_in_context_large(self):
        handler = TokenHandler("moonshot-v1-32k")
        # Create text that exceeds 32k context
        large_text = "x" * 200000
        assert handler.fits_in_context(large_text) is False
    
    def test_max_diff_tokens(self):
        handler = TokenHandler()
        # Should be less than max_context due to reserves
        assert handler.max_diff_tokens < handler.model_config.max_context
        assert handler.max_diff_tokens > 0
    
    def test_get_fallback_model_small(self):
        handler = TokenHandler()
        # Small token count should return primary model
        model = handler.get_fallback_model(1000)
        assert model == "kimi-k2-turbo-preview"
    
    def test_get_fallback_model_medium(self):
        handler = TokenHandler()
        # Medium token count might need fallback
        model = handler.get_fallback_model(200000)
        assert model in FALLBACK_CHAIN
    
    def test_get_fallback_model_too_large(self):
        handler = TokenHandler()
        # Extremely large token count
        model = handler.get_fallback_model(10000000)
        assert model is None


class TestTokenStats:
    """Tests for TokenStats dataclass."""
    
    def test_density(self):
        stats = TokenStats(
            total_tokens=100,
            chinese_tokens=50,
            english_tokens=30,
            code_tokens=20,
            total_chars=400
        )
        assert stats.density == 4.0
    
    def test_density_zero_tokens(self):
        stats = TokenStats(0, 0, 0, 0, 100)
        assert stats.density == 100.0  # Avoid division by zero


class TestDiffChunk:
    """Tests for DiffChunk dataclass."""
    
    def test_size(self):
        chunk = DiffChunk(
            filename="test.py",
            content="hello world",
            tokens=3
        )
        assert chunk.size == 11
    
    def test_defaults(self):
        chunk = DiffChunk(filename="test.py", content="", tokens=0)
        assert chunk.priority == 1.0
        assert chunk.language == ""
        assert chunk.change_type == ""
