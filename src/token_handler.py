"""Token handling and intelligent chunking for Kimi Actions.

Features:
- Accurate token estimation for Chinese/English mixed content
- Intelligent diff chunking with priority scoring
- Fallback model support for large PRs
- File filtering (binary, lock files, etc.)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, FrozenSet
from enum import Enum

from diff_processor import should_exclude, DEFAULT_EXCLUDE_PATTERNS

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tiers for fallback strategy."""
    PRIMARY = "primary"
    FALLBACK = "fallback"


@dataclass
class ModelConfig:
    """Model configuration with token limits."""
    name: str
    max_context: int
    max_output: int = 8192
    tier: ModelTier = ModelTier.PRIMARY
    description: str = ""


# Kimi model configurations
KIMI_MODELS: Dict[str, ModelConfig] = {
    "kimi-k2-0905-preview": ModelConfig(
        name="kimi-k2-0905-preview",
        max_context=256000,
        max_output=8192,
        tier=ModelTier.PRIMARY,
        description="Kimi K2 most powerful version"
    ),
    "kimi-k2-turbo-preview": ModelConfig(
        name="kimi-k2-turbo-preview",
        max_context=256000,
        max_output=8192,
        tier=ModelTier.PRIMARY,
        description="Kimi K2 high-speed version (recommended)"
    ),
}

# No fallback needed - K2 models have 256K context
# If diff is too large, use intelligent chunking instead
FALLBACK_CHAIN: List[str] = [
    "kimi-k2-turbo-preview",
]


@dataclass
class TokenStats:
    """Token statistics for content."""
    total_tokens: int
    chinese_tokens: int
    english_tokens: int
    code_tokens: int
    total_chars: int

    @property
    def density(self) -> float:
        """Characters per token ratio."""
        return self.total_chars / max(self.total_tokens, 1)


@dataclass
class DiffChunk:
    """A chunk of diff content with metadata."""
    filename: str
    content: str
    tokens: int
    priority: float = 1.0
    language: str = ""
    change_type: str = ""  # added, modified, deleted

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass
class TokenHandlerConfig:
    """Configuration constants for token handling."""
    # Token estimation ratios (characters per token)
    chinese_chars_per_token: float = 1.5
    english_chars_per_token: float = 4.0
    code_chars_per_token: float = 3.5
    
    # Reserved tokens
    system_prompt_reserve: int = 2000
    response_reserve: int = 8192
    
    # Safety margin (use 90% of available context)
    safety_margin: float = 0.9
    
    # Minimum useful chunk size in tokens
    min_chunk_tokens: int = 500


# Default token handler configuration
DEFAULT_TOKEN_CONFIG = TokenHandlerConfig()


class TokenHandler:
    """Handles token estimation and content chunking."""

    def __init__(
        self,
        model: str = "kimi-k2-turbo-preview",
        config: Optional[TokenHandlerConfig] = None
    ) -> None:
        """Initialize token handler.
        
        Args:
            model: Primary model name
            config: Token handler configuration (uses defaults if None)
        """
        self.model = model
        self.model_config = KIMI_MODELS.get(model, KIMI_MODELS["kimi-k2-turbo-preview"])
        self.config = config or DEFAULT_TOKEN_CONFIG

    @property
    def max_diff_tokens(self) -> int:
        """Maximum tokens available for diff content."""
        available = (
            self.model_config.max_context
            - self.config.system_prompt_reserve
            - self.config.response_reserve
        )
        return int(available * self.config.safety_margin)

    def estimate_tokens(self, text: str) -> TokenStats:
        """Estimate token count for mixed Chinese/English/code content.
        
        Uses different ratios for different content types:
        - Chinese: ~1.5 characters per token
        - English: ~4 characters per token  
        - Code: ~3.5 characters per token
        
        Args:
            text: Input text
            
        Returns:
            TokenStats with detailed breakdown
        """
        if not text:
            return TokenStats(0, 0, 0, 0, 0)

        # Count Chinese characters (CJK Unified Ideographs)
        chinese_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\u20000-\u2a6df]'
        chinese_chars = len(re.findall(chinese_pattern, text))

        # Count code blocks (rough heuristic)
        code_pattern = r'```[\s\S]*?```|`[^`]+`'
        code_matches = re.findall(code_pattern, text)
        code_chars = sum(len(m) for m in code_matches)

        # Remaining is English/other
        other_chars = len(text) - chinese_chars - code_chars

        # Calculate tokens for each type
        chinese_tokens = int(chinese_chars / self.config.chinese_chars_per_token)
        code_tokens = int(code_chars / self.config.code_chars_per_token)
        english_tokens = int(other_chars / self.config.english_chars_per_token)

        total_tokens = chinese_tokens + code_tokens + english_tokens

        return TokenStats(
            total_tokens=total_tokens,
            chinese_tokens=chinese_tokens,
            english_tokens=english_tokens,
            code_tokens=code_tokens,
            total_chars=len(text)
        )

    def count_tokens(self, text: str) -> int:
        """Simple token count (convenience method)."""
        return self.estimate_tokens(text).total_tokens

    def fits_in_context(self, text: str, reserve: int = 0) -> bool:
        """Check if text fits in available context."""
        tokens = self.count_tokens(text)
        return tokens <= (self.max_diff_tokens - reserve)

    def get_fallback_model(self, tokens_needed: int) -> Optional[str]:
        """Get appropriate fallback model for token count.
        
        Args:
            tokens_needed: Number of tokens needed
            
        Returns:
            Model name that can handle the tokens, or None
        """
        for model_name in FALLBACK_CHAIN:
            config = KIMI_MODELS.get(model_name)
            if config:
                available = (
                    config.max_context
                    - self.config.system_prompt_reserve
                    - self.config.response_reserve
                )
                if tokens_needed <= available * self.config.safety_margin:
                    return model_name
        return None


@dataclass
class DiffChunkerConfig:
    """Configuration for diff chunking."""
    # File priority weights
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        # High priority - core logic
        "src/": 1.5,
        "lib/": 1.4,
        "app/": 1.4,
        "core/": 1.5,
        # Medium priority
        "api/": 1.2,
        "services/": 1.2,
        "controllers/": 1.2,
        "models/": 1.2,
        # Lower priority
        "test": 0.7,
        "spec": 0.7,
        "__test__": 0.6,
        "__mock__": 0.5,
        # Config files
        "config": 0.8,
        ".config": 0.6,
        # Docs
        "docs/": 0.5,
        "README": 0.6,
        ".md": 0.5,
    })
    
    # Language detection patterns
    language_patterns: Dict[str, str] = field(default_factory=lambda: {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".swift": "swift",
        ".kt": "kotlin",
    })
    
    # Security keywords for priority boost
    security_keywords: FrozenSet[str] = field(default_factory=lambda: frozenset({
        "auth", "password", "token", "secret", "key", "crypt", "security"
    }))
    
    # Priority boost factors
    additions_boost: float = 1.1
    security_boost: float = 1.3
    truncated_penalty: float = 0.8


# Default chunker configuration
DEFAULT_CHUNKER_CONFIG = DiffChunkerConfig()


class DiffChunker:
    """Intelligent diff chunking with priority-based selection."""

    def __init__(
        self,
        token_handler: TokenHandler,
        exclude_patterns: Optional[List[str]] = None,
        config: Optional[DiffChunkerConfig] = None
    ) -> None:
        """Initialize chunker with token handler.
        
        Args:
            token_handler: TokenHandler instance
            exclude_patterns: File patterns to exclude (uses defaults if None)
            config: Chunker configuration (uses defaults if None)
        """
        self.token_handler = token_handler
        self.exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS
        self.config = config or DEFAULT_CHUNKER_CONFIG

    def _calculate_priority(self, filename: str, content: str) -> float:
        """Calculate priority score for a file.
        
        Higher priority = more important to review.
        """
        priority = 1.0
        filename_lower = filename.lower()

        # Apply path-based weights
        for pattern, weight in self.config.priority_weights.items():
            if pattern in filename_lower:
                priority *= weight

        # Boost files with more additions
        additions = content.count("\n+")
        deletions = content.count("\n-")
        if additions > deletions:
            priority *= self.config.additions_boost

        # Boost files with security-related changes
        content_lower = content.lower()
        if any(kw in filename_lower or kw in content_lower for kw in self.config.security_keywords):
            priority *= self.config.security_boost

        return priority

    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename."""
        for ext, lang in self.config.language_patterns.items():
            if filename.endswith(ext):
                return lang
        return ""

    def _detect_change_type(self, content: str) -> str:
        """Detect type of change (added, modified, deleted)."""
        additions = content.count("\n+")
        deletions = content.count("\n-")

        if deletions == 0 and additions > 0:
            return "added"
        elif additions == 0 and deletions > 0:
            return "deleted"
        else:
            return "modified"

    def parse_diff(self, diff: str) -> List[DiffChunk]:
        """Parse diff into prioritized chunks.
        
        Args:
            diff: Raw diff string
            
        Returns:
            List of DiffChunk objects sorted by priority
        """
        # Split by file headers
        file_pattern = r'^diff --git a/(.+?) b/(.+?)$'
        parts = re.split(file_pattern, diff, flags=re.MULTILINE)

        chunks: List[DiffChunk] = []
        i = 1
        while i < len(parts):
            if i + 2 < len(parts):
                filename = parts[i + 1]  # Use 'b/' path (new filename)

                # Skip excluded files (binary, lock files, etc.)
                if should_exclude(filename, self.exclude_patterns):
                    i += 3
                    continue

                # Find content until next diff header
                content_start = i + 2
                content = parts[content_start] if content_start < len(parts) else ""

                # Calculate tokens and priority
                tokens = self.token_handler.count_tokens(content)
                priority = self._calculate_priority(filename, content)
                language = self._detect_language(filename)
                change_type = self._detect_change_type(content)

                chunks.append(DiffChunk(
                    filename=filename,
                    content=content,
                    tokens=tokens,
                    priority=priority,
                    language=language,
                    change_type=change_type
                ))
            i += 3

        # Fallback: simple parsing if git diff format not detected
        if not chunks:
            chunks = self._parse_simple_diff(diff)

        # Sort by priority (highest first)
        chunks.sort(key=lambda x: x.priority, reverse=True)

        return chunks

    def _parse_simple_diff(self, diff: str) -> List[DiffChunk]:
        """Fallback parser for simple diff format."""
        file_pattern = r'^--- (.+?)$'
        parts = re.split(file_pattern, diff, flags=re.MULTILINE)

        chunks: List[DiffChunk] = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                filename = parts[i].strip()
                if filename.startswith("a/"):
                    filename = filename[2:]

                # Skip excluded files
                if should_exclude(filename, self.exclude_patterns):
                    continue

                content = parts[i + 1].strip()
                tokens = self.token_handler.count_tokens(content)
                priority = self._calculate_priority(filename, content)

                chunks.append(DiffChunk(
                    filename=filename,
                    content=content,
                    tokens=tokens,
                    priority=priority,
                    language=self._detect_language(filename),
                    change_type=self._detect_change_type(content)
                ))

        return chunks

    def chunk_diff(
        self,
        diff: str,
        max_tokens: Optional[int] = None,
        max_files: int = 15
    ) -> Tuple[List[DiffChunk], List[DiffChunk]]:
        """Intelligently chunk diff to fit token limits.
        
        Uses priority-based selection to include most important files first.
        
        Args:
            diff: Raw diff string
            max_tokens: Maximum tokens (default: handler's max_diff_tokens)
            max_files: Maximum number of files to include
            
        Returns:
            Tuple of (included_chunks, excluded_chunks)
        """
        if max_tokens is None:
            max_tokens = self.token_handler.max_diff_tokens

        chunks = self.parse_diff(diff)

        included: List[DiffChunk] = []
        excluded: List[DiffChunk] = []
        current_tokens = 0

        for chunk in chunks:
            # Check file limit
            if len(included) >= max_files:
                excluded.append(chunk)
                continue

            # Check token limit
            if current_tokens + chunk.tokens <= max_tokens:
                included.append(chunk)
                current_tokens += chunk.tokens
            else:
                # Try to include truncated version
                remaining_tokens = max_tokens - current_tokens
                min_chunk_tokens = self.token_handler.config.min_chunk_tokens
                if remaining_tokens > min_chunk_tokens:
                    truncated = self._truncate_chunk(chunk, remaining_tokens)
                    if truncated:
                        included.append(truncated)
                        current_tokens += truncated.tokens
                excluded.append(chunk)

        logger.info(
            f"Chunked diff: {len(included)} files included ({current_tokens} tokens), "
            f"{len(excluded)} files excluded"
        )

        return included, excluded

    def _truncate_chunk(self, chunk: DiffChunk, max_tokens: int) -> Optional[DiffChunk]:
        """Truncate a chunk to fit token limit."""
        # Estimate chars needed
        chars_per_token = chunk.size / max(chunk.tokens, 1)
        max_chars = int(max_tokens * chars_per_token * 0.9)

        min_chars = 200
        if max_chars < min_chars:
            return None

        truncated_content = chunk.content[:max_chars] + "\n... [truncated]"

        return DiffChunk(
            filename=chunk.filename,
            content=truncated_content,
            tokens=max_tokens,
            priority=chunk.priority * self.config.truncated_penalty,
            language=chunk.language,
            change_type=chunk.change_type
        )

    def build_diff_string(self, chunks: List[DiffChunk]) -> str:
        """Build diff string from chunks."""
        parts: List[str] = []
        for chunk in chunks:
            header = f"## File: {chunk.filename}"
            if chunk.language:
                header += f" ({chunk.language})"
            if chunk.change_type:
                header += f" [{chunk.change_type}]"

            parts.append(f"{header}\n{chunk.content}")

        return "\n\n".join(parts)


def select_model_for_diff(diff: str, preferred_model: str = "kimi-k2-turbo-preview") -> Tuple[str, int]:
    """Select appropriate model based on diff size.
    
    Args:
        diff: Raw diff string
        preferred_model: Preferred model to use
        
    Returns:
        Tuple of (model_name, estimated_tokens)
    """
    handler = TokenHandler(preferred_model)
    tokens = handler.count_tokens(diff)

    # Check if preferred model can handle it
    if handler.fits_in_context(diff):
        return preferred_model, tokens

    # Find fallback model
    fallback = handler.get_fallback_model(tokens)
    if fallback:
        logger.warning(
            f"Diff too large for {preferred_model} ({tokens} tokens), "
            f"falling back to {fallback}"
        )
        return fallback, tokens

    # No model can handle it - will need chunking
    logger.warning(f"Diff too large for any model ({tokens} tokens), chunking required")
    return preferred_model, tokens
