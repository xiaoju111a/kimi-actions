"""Base tool class for Kimi Actions.

Provides common functionality for all tools:
- Diff processing with intelligent chunking
- Skill loading and management
- Agent SDK interaction
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List

from action_config import get_action_config
from github_client import GitHubClient
from token_handler import TokenHandler, DiffChunker, select_model_for_diff, DiffChunk
from skill_loader import SkillManager, Skill
from repo_config import load_repo_config, RepoConfig

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools.
    
    Subclasses must implement:
    - skill_name: The default skill to use
    - run(): The main execution logic
    """

    def __init__(self, github: GitHubClient):
        self.github = github
        self.config = get_action_config()

        # Token handling
        self.token_handler = TokenHandler(self.config.model)
        self.chunker = DiffChunker(
            self.token_handler,
            exclude_patterns=self.config.exclude_patterns
        )

        # Skill management
        self.skill_manager = SkillManager()
        self.repo_config: Optional[RepoConfig] = None

        # Track actual model used (may change due to fallback)
        self.actual_model: str = self.config.model

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """Default skill name for this tool."""
        pass

    @abstractmethod
    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Execute the tool's main logic."""
        pass

    def load_context(self, repo_name: str, ref: str = None) -> None:
        """Load repository config and custom skills."""
        self.repo_config, validation = load_repo_config(self.github, repo_name, ref=ref)

        if not validation.valid:
            logger.error(f"Config validation failed: {validation.errors}")
        if validation.warnings:
            logger.warning(f"Config warnings: {validation.warnings}")

        self.skill_manager.load_from_repo(self.github, repo_name, ref=ref)

        if self.repo_config and self.repo_config.ignore_files:
            self.chunker.exclude_patterns = list(self.chunker.exclude_patterns) + self.repo_config.ignore_files

    def get_skill(self) -> Optional[Skill]:
        """Get the skill for this tool, respecting overrides."""
        skill_to_use = self.skill_name

        if self.repo_config and self.repo_config.skill_overrides:
            override = self.repo_config.skill_overrides.get(self.skill_name)
            if override:
                logger.info(f"Using skill override: {self.skill_name} -> {override}")
                skill_to_use = override

        skill = self.skill_manager.get_skill(skill_to_use)
        if not skill:
            logger.warning(f"Skill not found: {skill_to_use}")

        return skill

    def get_diff(self, repo_name: str, pr_number: int) -> Tuple[str, List[DiffChunk], List[DiffChunk]]:
        """Get and process PR diff with intelligent chunking."""
        diff = self.github.get_pr_diff(repo_name, pr_number)
        if not diff:
            return "", [], []

        self.actual_model, estimated_tokens = select_model_for_diff(diff, self.config.model)

        if self.actual_model != self.config.model:
            logger.info(f"Using fallback model: {self.actual_model}")

        included, excluded = self.chunker.chunk_diff(diff, max_files=self.config.max_files)
        compressed = self.chunker.build_diff_string(included)

        logger.info(
            f"Diff processed: {len(included)} files included, "
            f"{len(excluded)} excluded, ~{estimated_tokens} tokens"
        )

        return compressed, included, excluded

    def format_footer(self, extra_info: str = "") -> str:
        """Generate standard footer for tool output."""
        model_info = f"`{self.actual_model}`"
        if self.actual_model != self.config.model:
            model_info += f" (fallback from `{self.config.model}`)"

        footer = f"---\n<sub>Powered by [Kimi](https://kimi.moonshot.cn/) | Model: {model_info}"
        if extra_info:
            footer += f" | {extra_info}"
        footer += "</sub>"

        return footer

    # Agent SDK configuration
    AGENT_MODEL = "kimi-k2-thinking"
    AGENT_BASE_URL = "https://api.moonshot.cn/v1"

    def setup_agent_env(self) -> Optional[str]:
        """Setup environment variables for Agent SDK.
        
        Returns:
            API key if available, None otherwise.
        """
        api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("INPUT_KIMI_API_KEY")
        if not api_key:
            return None
        
        os.environ["KIMI_API_KEY"] = api_key
        os.environ["KIMI_BASE_URL"] = self.AGENT_BASE_URL
        os.environ["KIMI_MODEL_NAME"] = self.AGENT_MODEL
        return api_key
