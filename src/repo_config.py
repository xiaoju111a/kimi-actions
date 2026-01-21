"""Repository configuration - loaded from user's .kimi-config.yml file.

Configuration Hierarchy:
========================
1. Built-in Skills (src/skills/)
   - Core review logic with scripts and references
   - Maintained by kimi-actions developers
   - Examples: code-review, describe, improve, ask

2. Custom Skills (.kimi/skills/)
   - User-defined skills in Claude Skills standard format
   - Each skill is a folder with SKILL.md + optional scripts/references
   - Can override built-in skills via skill_overrides in config

3. Repository Config (.kimi-config.yml)
   - Category toggles, ignore files, extra instructions
   - skill_overrides to replace built-in skills with custom ones

Custom Skills Format (Claude Skills Standard):
==============================================
  .kimi/skills/
  ├── react-review/
  │   ├── SKILL.md           # Required: core instructions
  │   ├── scripts/           # Optional: executable scripts
  │   └── references/        # Optional: reference documents
  └── company-rules/
      └── SKILL.md

Example .kimi-config.yml:
=========================
  categories:
    bug: true
    security: true
  skill_overrides:
    code-review: my-review  # Replace built-in with custom from .kimi/skills/
  ignore_files:
    - "*.test.ts"
  extra_instructions: |
    Use Chinese for responses.
"""

import logging
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Built-in skill names that are reserved
BUILTIN_SKILL_NAMES = {"code-review", "describe", "improve", "ask"}


@dataclass
class RepoConfig:
    """Repository-level configuration from .kimi-config.yml.

    Note: Custom skills are now loaded from .kimi/skills/ directory
    using the skill_loader module, not from this config file.
    """

    enabled: bool = True
    ignore_files: List[str] = field(default_factory=list)
    extra_instructions: str = ""

    # Category toggles
    enable_bug: bool = True
    enable_performance: bool = True
    enable_security: bool = True

    # Skill overrides: map built-in skill name to custom skill name
    # Custom skills must exist in .kimi/skills/ directory
    skill_overrides: Dict[str, str] = field(default_factory=dict)

    # Validation errors/warnings
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class ConfigValidationResult:
    """Result of config validation."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_config(data: dict) -> ConfigValidationResult:
    """Validate .kimi-config.yml structure and values.

    Returns:
        ConfigValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Check top-level keys
    valid_keys = {
        "enabled",
        "categories",
        "skill_overrides",
        "ignore_files",
        "extra_instructions",
    }
    unknown_keys = set(data.keys()) - valid_keys
    if unknown_keys:
        # Check if user is using old 'skills' key
        if "skills" in unknown_keys:
            warnings.append(
                "The 'skills' key is deprecated. "
                "Please use .kimi/skills/ directory for custom skills. "
                "See documentation for Claude Skills standard format."
            )
            unknown_keys.remove("skills")
        if unknown_keys:
            warnings.append(f"Unknown config keys: {', '.join(unknown_keys)}")

    # Validate 'enabled'
    if "enabled" in data and not isinstance(data["enabled"], bool):
        errors.append("'enabled' must be a boolean")

    # Validate 'categories'
    if "categories" in data:
        categories = data["categories"]
        if not isinstance(categories, dict):
            errors.append("'categories' must be an object")
        else:
            valid_categories = {"bug", "performance", "security"}
            for key, value in categories.items():
                if key not in valid_categories:
                    warnings.append(f"Unknown category: '{key}'")
                if not isinstance(value, bool):
                    errors.append(f"Category '{key}' must be a boolean")

    # Validate 'skill_overrides'
    if "skill_overrides" in data:
        overrides = data["skill_overrides"]
        if not isinstance(overrides, dict):
            errors.append("'skill_overrides' must be an object")
        else:
            for builtin_name, custom_name in overrides.items():
                if builtin_name not in BUILTIN_SKILL_NAMES:
                    warnings.append(
                        f"skill_overrides: '{builtin_name}' is not a built-in skill. "
                        f"Valid names: {', '.join(sorted(BUILTIN_SKILL_NAMES))}"
                    )
                if not isinstance(custom_name, str) or not custom_name:
                    errors.append(
                        f"skill_overrides['{builtin_name}'] must be a non-empty string"
                    )

    # Validate 'ignore_files'
    if "ignore_files" in data:
        ignore_files = data["ignore_files"]
        if not isinstance(ignore_files, list):
            errors.append("'ignore_files' must be an array")
        elif not all(isinstance(f, str) for f in ignore_files):
            errors.append("'ignore_files' must contain only strings")

    # Validate 'extra_instructions'
    if "extra_instructions" in data:
        if not isinstance(data["extra_instructions"], str):
            errors.append("'extra_instructions' must be a string")

    return ConfigValidationResult(
        valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def parse_repo_config(content: str) -> Tuple[RepoConfig, ConfigValidationResult]:
    """Parse and validate .kimi-config.yml content.

    Returns:
        Tuple of (RepoConfig, ConfigValidationResult)
    """
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        result = ConfigValidationResult(valid=False, errors=[f"YAML parse error: {e}"])
        return RepoConfig(), result

    # Validate first
    validation = validate_config(data)

    # Log validation issues
    for error in validation.errors:
        logger.error(f"Config error: {error}")
    for warning in validation.warnings:
        logger.warning(f"Config warning: {warning}")

    # Parse even if there are warnings (but not if there are errors)
    config = RepoConfig()
    config.validation_errors = validation.errors
    config.validation_warnings = validation.warnings

    if not validation.valid:
        return config, validation

    config.enabled = data.get("enabled", True)

    # Category toggles
    categories = data.get("categories", {})
    config.enable_bug = categories.get("bug", True)
    config.enable_performance = categories.get("performance", True)
    config.enable_security = categories.get("security", True)

    # Skill overrides
    config.skill_overrides = data.get("skill_overrides", {})

    config.ignore_files = data.get("ignore_files", [])
    config.extra_instructions = data.get("extra_instructions", "")

    return config, validation


def load_repo_config(
    github_client, repo_name: str, ref: str = None
) -> Tuple[RepoConfig, ConfigValidationResult]:
    """Load repository config from .kimi-config.yml.

    Returns:
        Tuple of (RepoConfig, ConfigValidationResult)
    """
    try:
        repo = github_client.client.get_repo(repo_name)

        for filename in [".kimi-config.yml", ".kimi-config.yaml"]:
            try:
                content = repo.get_contents(filename, ref=ref)
                config_content = content.decoded_content.decode("utf-8")
                logger.info(f"Loaded repo config from {filename}")
                return parse_repo_config(config_content)
            except Exception:
                continue

        logger.debug("No .kimi-config.yml found")
        return RepoConfig(), ConfigValidationResult(valid=True)

    except Exception as e:
        logger.warning(f"Failed to load repo config: {e}")
        return RepoConfig(), ConfigValidationResult(valid=True)
