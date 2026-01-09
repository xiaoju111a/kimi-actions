"""Tests for skill_loader module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skill_loader import (
    Skill, parse_skill_md, load_skill_from_dir,
    SkillManager
)


class TestSkill:
    """Tests for Skill dataclass."""

    def test_matches_name(self):
        skill = Skill(name="code-review", description="Review code")
        assert skill.matches("code-review") is True
        assert skill.matches("CODE-REVIEW") is True
        assert skill.matches("something else") is False

    def test_matches_trigger(self):
        skill = Skill(
            name="review",
            description="Review",
            triggers=["review", "check", "analyze"]
        )
        assert skill.matches("please review this") is True
        assert skill.matches("check my code") is True
        assert skill.matches("random text") is False

    def test_get_reference(self):
        skill = Skill(
            name="test",
            description="Test",
            references={"guide": "# Guide content"}
        )
        assert skill.get_reference("guide") == "# Guide content"
        assert skill.get_reference("nonexistent") == ""


class TestParseSkillMd:
    """Tests for parse_skill_md function."""

    def test_parse_with_frontmatter(self):
        content = """---
name: test-skill
description: A test skill
version: 1.0.0
triggers:
  - test
  - check
---

# Instructions

Do the thing.
"""
        metadata, instructions = parse_skill_md(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill"
        assert metadata["version"] == "1.0.0"
        assert "test" in metadata["triggers"]
        assert "# Instructions" in instructions

    def test_parse_without_frontmatter(self):
        content = "# Just instructions\n\nNo frontmatter here."
        metadata, instructions = parse_skill_md(content)

        assert metadata == {}
        assert content == instructions

    def test_parse_empty_frontmatter(self):
        content = """---
---

Instructions only."""
        metadata, instructions = parse_skill_md(content)

        assert metadata == {}
        assert "Instructions only" in instructions

    def test_parse_invalid_yaml(self):
        content = """---
invalid: yaml: content: here
---

Instructions."""
        metadata, instructions = parse_skill_md(content)

        # Should handle gracefully
        assert isinstance(metadata, dict)


class TestLoadSkillFromDir:
    """Tests for load_skill_from_dir function."""

    def test_load_missing_skill_md(self, tmp_path):
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()

        skill = load_skill_from_dir(skill_dir)
        assert skill is None

    def test_load_valid_skill(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: my-skill
description: My test skill
triggers:
  - myskill
---

# Instructions
Do something useful.
""")

        skill = load_skill_from_dir(skill_dir)

        assert skill is not None
        assert skill.name == "my-skill"
        assert skill.description == "My test skill"
        assert "myskill" in skill.triggers
        assert "Do something useful" in skill.instructions

    def test_load_skill_with_scripts(self, tmp_path):
        skill_dir = tmp_path / "scripted-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("---\nname: scripted\n---\nInstructions")

        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "check.py").write_text("print('check')")
        (scripts_dir / "analyze.py").write_text("print('analyze')")

        skill = load_skill_from_dir(skill_dir)

        assert skill is not None
        assert "check" in skill.scripts
        assert "analyze" in skill.scripts

    def test_load_skill_with_references(self, tmp_path):
        skill_dir = tmp_path / "ref-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("---\nname: ref\n---\nInstructions")

        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        (refs_dir / "guide.md").write_text("# Guide")
        (refs_dir / "examples.md").write_text("# Examples")

        skill = load_skill_from_dir(skill_dir)

        assert skill is not None
        assert "guide" in skill.references
        assert "examples" in skill.references
        assert skill.references["guide"] == "# Guide"


class TestSkillManager:
    """Tests for SkillManager class."""

    def test_init_loads_builtin(self):
        manager = SkillManager()
        # Should have loaded built-in skills
        assert isinstance(manager.builtin_skills, dict)

    def test_get_skill_builtin(self):
        manager = SkillManager()
        # Assuming code-review is a built-in skill
        skill = manager.get_skill("code-review")
        if skill:
            assert skill.name == "code-review"

    def test_get_skill_not_found(self):
        manager = SkillManager()
        skill = manager.get_skill("nonexistent-skill")
        assert skill is None

    def test_custom_overrides_builtin(self):
        manager = SkillManager()

        # Add a custom skill with same name as builtin
        custom_skill = Skill(
            name="code-review",
            description="Custom review",
            instructions="Custom instructions"
        )
        manager.custom_skills["code-review"] = custom_skill

        # Should return custom version
        skill = manager.get_skill("code-review")
        assert skill.description == "Custom review"

    def test_get_builtin_skill_ignores_custom(self):
        manager = SkillManager()

        # Add custom override
        manager.custom_skills["code-review"] = Skill(
            name="code-review",
            description="Custom"
        )

        # get_builtin_skill should return original
        builtin = manager.get_builtin_skill("code-review")
        if builtin:
            assert builtin.description != "Custom"

    def test_list_skills(self):
        manager = SkillManager()
        skills_list = manager.list_skills()

        assert isinstance(skills_list, dict)
        for name, info in skills_list.items():
            assert "skill" in info
            assert "source" in info
            assert "overridden" in info

    def test_find_matching_skills(self):
        manager = SkillManager()
        manager.builtin_skills["test"] = Skill(
            name="test",
            description="Test skill",
            triggers=["test", "check"]
        )

        matches = manager.find_matching_skills("please test this")
        assert any(s.name == "test" for s in matches)

    def test_find_by_trigger(self):
        manager = SkillManager()
        manager.builtin_skills["review"] = Skill(
            name="review",
            description="Review",
            triggers=["review", "check"]
        )

        matches = manager.find_by_trigger("review")
        assert any(s.name == "review" for s in matches)

    def test_build_prompt(self):
        manager = SkillManager()
        manager.builtin_skills["test"] = Skill(
            name="test",
            description="Test",
            instructions="Do the test thing."
        )

        prompt = manager.build_prompt("test")
        assert "Do the test thing" in prompt

    def test_build_prompt_not_found(self):
        manager = SkillManager()
        prompt = manager.build_prompt("nonexistent")
        assert prompt == ""
