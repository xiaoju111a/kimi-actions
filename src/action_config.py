"""Action configuration - loaded from GitHub Actions environment variables.

This configuration is set by the Action user in their workflow file:
  - uses: xiaoju/kimi-actions@v1
    with:
      kimi_api_key: ${{ secrets.KIMI_API_KEY }}
      model: kimi-k2-thinking
      review_level: normal
"""

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class ReviewConfig:
    """Review tool configuration."""

    require_security_review: bool = True
    require_tests_review: bool = True
    require_score: bool = True
    num_max_findings: int = 20
    extra_instructions: str = ""


@dataclass
class DescribeConfig:
    """Describe tool configuration."""

    generate_title: bool = True
    generate_labels: bool = True
    enable_walkthrough: bool = True
    extra_instructions: str = ""


@dataclass
class ImproveConfig:
    """Improve tool configuration."""

    num_suggestions: int = 20
    focus_on_problems: bool = True
    include_line_numbers: bool = True
    extra_instructions: str = ""


@dataclass
class ActionConfig:
    """Main Action configuration class.

    Loaded from GitHub Actions inputs (environment variables).
    """

    # API settings
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    github_token: str = ""
    model: str = "kimi-k2-thinking"

    # General settings
    language: str = "en-US"  # zh-CN or en-US
    review_level: str = "normal"  # strict, normal, gentle
    max_files: int = 50
    max_tokens: int = 100000

    # File filtering
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "*.lock",
            "*.min.js",
            "*.min.css",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "*.map",
        ]
    )

    # Tool configs
    review: ReviewConfig = field(default_factory=ReviewConfig)
    describe: DescribeConfig = field(default_factory=DescribeConfig)
    improve: ImproveConfig = field(default_factory=ImproveConfig)

    # Labels
    auto_labels: bool = True
    label_mapping: Dict[str, str] = field(
        default_factory=lambda: {
            "bug_fix": "bug",
            "feature": "enhancement",
            "refactor": "refactor",
            "docs": "documentation",
            "test": "test",
            "security": "security",
        }
    )

    @classmethod
    def from_env(cls) -> "ActionConfig":
        """Load configuration from GitHub Actions inputs."""
        config = cls()

        # API keys (from GitHub Actions inputs)
        config.kimi_api_key = os.environ.get("INPUT_KIMI_API_KEY", "")
        config.kimi_base_url = os.environ.get(
            "INPUT_KIMI_BASE_URL", "https://api.moonshot.cn/v1"
        )
        config.github_token = os.environ.get("INPUT_GITHUB_TOKEN", "")

        # General settings
        config.language = os.environ.get("INPUT_LANGUAGE", "en-US")
        config.model = os.environ.get("INPUT_MODEL", "kimi-k2-thinking")
        config.review_level = os.environ.get("INPUT_REVIEW_LEVEL", "normal")
        config.max_files = int(os.environ.get("INPUT_MAX_FILES", "50"))

        # Exclude patterns
        exclude_str = os.environ.get("INPUT_EXCLUDE_PATTERNS", "")
        if exclude_str:
            config.exclude_patterns = [
                p.strip() for p in exclude_str.split(",") if p.strip()
            ]

        # Extra instructions
        config.review.extra_instructions = os.environ.get(
            "INPUT_REVIEW_EXTRA_INSTRUCTIONS", ""
        )
        config.describe.extra_instructions = os.environ.get(
            "INPUT_DESCRIBE_EXTRA_INSTRUCTIONS", ""
        )
        config.improve.extra_instructions = os.environ.get(
            "INPUT_IMPROVE_EXTRA_INSTRUCTIONS", ""
        )

        return config


# Context variable for thread-safe configuration storage
# This replaces the global _config variable for better isolation in tests and async contexts
_config_var: ContextVar[Optional[ActionConfig]] = ContextVar(
    "action_config", default=None
)


def get_action_config() -> ActionConfig:
    """Get the Action configuration instance.

    Uses context variables for thread-safe access.
    Creates a new config from environment if not set.
    """
    config = _config_var.get()
    if config is None:
        config = ActionConfig.from_env()
        _config_var.set(config)
    return config


def set_action_config(config: ActionConfig) -> None:
    """Set the Action configuration instance.

    Useful for testing or programmatic configuration.
    """
    _config_var.set(config)


def reset_action_config() -> None:
    """Reset the configuration to None.

    Useful for testing to ensure clean state between tests.
    """
    _config_var.set(None)
