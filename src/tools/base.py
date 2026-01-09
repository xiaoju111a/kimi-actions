"""Base tool class for Kimi Actions.

Provides common functionality for all tools:
- Diff processing with intelligent chunking
- Skill loading and management
- Kimi API interaction
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List

from action_config import get_action_config
from kimi_client import KimiClient
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

    def __init__(self, kimi: KimiClient, github: GitHubClient):
        self.kimi = kimi
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
        """Load repository config and custom skills.
        
        Args:
            repo_name: Repository name (owner/repo)
            ref: Git ref (commit SHA, branch, tag)
        """
        self.repo_config, validation = load_repo_config(self.github, repo_name, ref=ref)

        # Log validation issues
        if not validation.valid:
            logger.error(f"Config validation failed: {validation.errors}")
        if validation.warnings:
            logger.warning(f"Config warnings: {validation.warnings}")

        self.skill_manager.load_from_repo(self.github, repo_name, ref=ref)

        # Apply custom ignore patterns
        if self.repo_config and self.repo_config.ignore_files:
            self.chunker.exclude_patterns.extend(self.repo_config.ignore_files)

    def get_skill(self) -> Optional[Skill]:
        """Get the skill for this tool, respecting overrides.
        
        Priority:
        1. User override in .kimi-config.yml (skill_overrides)
        2. Custom skill from .kimi/skills/ with same name
        3. Built-in skill
        """
        skill_to_use = self.skill_name

        # Check for override in config
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
        """Get and process PR diff with intelligent chunking.
        
        Returns:
            Tuple of (compressed_diff, included_chunks, excluded_chunks)
        """
        diff = self.github.get_pr_diff(repo_name, pr_number)
        if not diff:
            return "", [], []

        # Select model based on diff size
        self.actual_model, estimated_tokens = select_model_for_diff(diff, self.config.model)

        # Update kimi client model if fallback needed
        if self.actual_model != self.config.model:
            logger.info(f"Using fallback model: {self.actual_model}")
            self.kimi.model = self.actual_model

        # Chunk diff with priority scoring
        included, excluded = self.chunker.chunk_diff(diff, max_files=self.config.max_files)
        compressed = self.chunker.build_diff_string(included)

        logger.info(
            f"Diff processed: {len(included)} files included, "
            f"{len(excluded)} excluded, ~{estimated_tokens} tokens"
        )

        return compressed, included, excluded

    def call_kimi(self, system_prompt: str, user_prompt: str) -> str:
        """Call Kimi API with system and user prompts.
        
        Args:
            system_prompt: System message (skill instructions)
            user_prompt: User message (PR context + diff)
            
        Returns:
            Kimi response content
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.kimi.chat(messages)

    def format_footer(self, extra_info: str = "") -> str:
        """Generate standard footer for tool output.
        
        Args:
            extra_info: Additional info to include
            
        Returns:
            Formatted footer string
        """
        model_info = f"`{self.actual_model}`"
        if self.actual_model != self.config.model:
            model_info += f" (fallback from `{self.config.model}`)"

        footer = f"---\n<sub>Powered by [Kimi](https://kimi.moonshot.cn/) | Model: {model_info}"
        if extra_info:
            footer += f" | {extra_info}"
        footer += "</sub>"

        return footer
