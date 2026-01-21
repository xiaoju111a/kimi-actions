"""Tests for repo_config module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repo_config import (
    RepoConfig,
    validate_config,
    parse_repo_config,
    BUILTIN_SKILL_NAMES,
)


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_minimal_config(self):
        data = {}
        result = validate_config(data)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_full_config(self):
        data = {
            "enabled": True,
            "categories": {"bug": True, "security": False, "performance": True},
            "skill_overrides": {"code-review": "my-review"},
            "ignore_files": ["*.test.ts"],
            "extra_instructions": "Use Chinese",
        }
        result = validate_config(data)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_unknown_keys_warning(self):
        data = {"unknown_key": "value", "another_unknown": 123}
        result = validate_config(data)
        assert result.valid is True  # Warnings don't fail validation
        assert len(result.warnings) == 1
        assert "unknown_key" in result.warnings[0]

    def test_deprecated_skills_key_warning(self):
        data = {"skills": [{"name": "test", "instructions": "do stuff"}]}
        result = validate_config(data)
        assert result.valid is True
        assert any("deprecated" in w.lower() for w in result.warnings)

    def test_invalid_enabled_type(self):
        data = {"enabled": "yes"}  # Should be bool
        result = validate_config(data)
        assert result.valid is False
        assert any("enabled" in e for e in result.errors)

    def test_invalid_categories_type(self):
        data = {"categories": ["bug", "security"]}  # Should be dict
        result = validate_config(data)
        assert result.valid is False
        assert any("categories" in e for e in result.errors)

    def test_invalid_category_value(self):
        data = {"categories": {"bug": "yes"}}  # Should be bool
        result = validate_config(data)
        assert result.valid is False
        assert any("bug" in e for e in result.errors)

    def test_unknown_category_warning(self):
        data = {"categories": {"bug": True, "unknown_cat": True}}
        result = validate_config(data)
        assert result.valid is True
        assert any("unknown_cat" in w for w in result.warnings)

    def test_skill_overrides_invalid_builtin(self):
        data = {"skill_overrides": {"not-a-builtin": "custom"}}
        result = validate_config(data)
        assert result.valid is True  # Warning, not error
        assert any("not-a-builtin" in w for w in result.warnings)

    def test_skill_overrides_valid(self):
        data = {"skill_overrides": {"code-review": "my-review"}}
        result = validate_config(data)
        assert result.valid is True
        assert len(result.warnings) == 0

    def test_skill_overrides_empty_value(self):
        data = {"skill_overrides": {"code-review": ""}}
        result = validate_config(data)
        assert result.valid is False
        assert any("non-empty" in e for e in result.errors)

    def test_ignore_files_not_array(self):
        data = {"ignore_files": "*.test.ts"}
        result = validate_config(data)
        assert result.valid is False
        assert any("ignore_files" in e for e in result.errors)

    def test_extra_instructions_not_string(self):
        data = {"extra_instructions": ["line1", "line2"]}
        result = validate_config(data)
        assert result.valid is False
        assert any("extra_instructions" in e for e in result.errors)


class TestParseRepoConfig:
    """Tests for parse_repo_config function."""

    def test_parse_valid_yaml(self):
        content = """
enabled: true
categories:
  bug: true
  security: false
skill_overrides:
  code-review: my-review
ignore_files:
  - "*.test.ts"
extra_instructions: |
  Use Chinese
"""
        config, result = parse_repo_config(content)

        assert result.valid is True
        assert config.enabled is True
        assert config.enable_bug is True
        assert config.enable_security is False
        assert config.skill_overrides == {"code-review": "my-review"}
        assert "*.test.ts" in config.ignore_files
        assert "Chinese" in config.extra_instructions

    def test_parse_invalid_yaml(self):
        content = "invalid: yaml: content: here"
        config, result = parse_repo_config(content)

        assert result.valid is False
        assert any("YAML" in e or "parse" in e.lower() for e in result.errors)

    def test_parse_empty_content(self):
        content = ""
        config, result = parse_repo_config(content)

        assert result.valid is True
        assert config.enabled is True  # Default

    def test_parse_with_validation_errors(self):
        content = """
enabled: "not-a-bool"
"""
        config, result = parse_repo_config(content)

        assert result.valid is False
        assert len(config.validation_errors) > 0

    def test_parse_with_deprecated_skills(self):
        content = """
skills:
  - name: old-style
    instructions: Do stuff
"""
        config, result = parse_repo_config(content)

        assert result.valid is True
        assert len(config.validation_warnings) > 0
        assert any("deprecated" in w.lower() for w in config.validation_warnings)


class TestRepoConfig:
    """Tests for RepoConfig dataclass."""

    def test_defaults(self):
        config = RepoConfig()
        assert config.enabled is True
        assert config.enable_bug is True
        assert config.enable_performance is True
        assert config.enable_security is True
        assert config.ignore_files == []
        assert config.extra_instructions == ""
        assert config.skill_overrides == {}


class TestBuiltinSkillNames:
    """Tests for BUILTIN_SKILL_NAMES constant."""

    def test_contains_expected_skills(self):
        assert "code-review" in BUILTIN_SKILL_NAMES
        assert "describe" in BUILTIN_SKILL_NAMES
        assert "improve" in BUILTIN_SKILL_NAMES
        assert "ask" in BUILTIN_SKILL_NAMES

    def test_is_set(self):
        assert isinstance(BUILTIN_SKILL_NAMES, set)
