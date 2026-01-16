"""Skill loader - loads skills from folder structure.

Each skill is a folder containing:
- SKILL.md (required) - Main instructions with YAML frontmatter
- scripts/ (optional) - Executable scripts
- references/ (optional) - Reference documents
"""

import re
import yaml
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Built-in skills directory
SKILLS_DIR = Path(__file__).parent / "skills"

# Script execution constants
SCRIPT_TIMEOUT_SECONDS: int = 30
SCRIPT_INTERPRETER: str = "python3"


@dataclass
class Skill:
    """A loaded skill."""
    name: str
    description: str
    version: str = "1.0.0"
    triggers: List[str] = field(default_factory=list)
    instructions: str = ""
    scripts: Dict[str, Path] = field(default_factory=dict)
    references: Dict[str, str] = field(default_factory=dict)
    path: Optional[Path] = None

    def matches(self, text: str) -> bool:
        """Check if text matches this skill's triggers."""
        text_lower = text.lower()
        if self.name.lower() in text_lower:
            return True
        return any(t.lower() in text_lower for t in self.triggers)

    def run_script(self, script_name: str, **kwargs: Any) -> Optional[str]:
        """Run a script and return output.
        
        Args:
            script_name: Name of the script to run
            **kwargs: Arguments to pass to the script
            
        Returns:
            Script stdout on success, stderr on failure, None if script not found
        """
        script_path = self.scripts.get(script_name)
        if not script_path or not script_path.exists():
            logger.debug(f"Script not found: {script_name}")
            return None

        try:
            cmd = [SCRIPT_INTERPRETER, str(script_path)]
            for key, value in kwargs.items():
                cmd.extend([f"--{key}", str(value)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SCRIPT_TIMEOUT_SECONDS,
                check=False  # Don't raise on non-zero exit
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(
                    f"Script {script_name} exited with code {result.returncode}: "
                    f"{result.stderr[:200] if result.stderr else 'no error output'}"
                )
                return result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error(f"Script {script_name} timed out after {SCRIPT_TIMEOUT_SECONDS}s")
            return None
        except FileNotFoundError:
            logger.error(f"Interpreter not found: {SCRIPT_INTERPRETER}")
            return None
        except Exception as e:
            logger.warning(f"Script {script_name} failed: {e}")
            return None

    def get_reference(self, ref_name: str) -> str:
        """Get a reference document content."""
        return self.references.get(ref_name, "")


def parse_skill_md(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse SKILL.md content into metadata and instructions.
    
    Args:
        content: Raw SKILL.md file content
        
    Returns:
        Tuple of (metadata dict, instructions string)
    """
    # Extract YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)

    if not match:
        return {}, content

    try:
        metadata = yaml.safe_load(match.group(1)) or {}
        instructions = match.group(2).strip()
        return metadata, instructions
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse SKILL.md frontmatter: {e}")
        return {}, content


def load_skill_from_dir(skill_dir: Path) -> Optional[Skill]:
    """Load a skill from a directory."""
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        logger.warning(f"No SKILL.md found in {skill_dir}")
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
        metadata, instructions = parse_skill_md(content)

        skill = Skill(
            name=metadata.get("name", skill_dir.name),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0.0"),
            triggers=metadata.get("triggers", []),
            instructions=instructions,
            path=skill_dir
        )

        # Load scripts
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for script_file in scripts_dir.glob("*.py"):
                skill.scripts[script_file.stem] = script_file

        # Load references
        refs_dir = skill_dir / "references"
        if refs_dir.exists():
            for ref_file in refs_dir.glob("*.md"):
                skill.references[ref_file.stem] = ref_file.read_text(encoding="utf-8")

        logger.info(f"Loaded skill: {skill.name}")
        return skill

    except Exception as e:
        logger.error(f"Failed to load skill from {skill_dir}: {e}")
        return None


def load_builtin_skills() -> Dict[str, Skill]:
    """Load all built-in skills."""
    skills: Dict[str, Skill] = {}

    if not SKILLS_DIR.exists():
        logger.warning(f"Skills directory not found: {SKILLS_DIR}")
        return skills

    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skill = load_skill_from_dir(skill_dir)
            if skill:
                skills[skill.name] = skill

    return skills


def load_custom_skills_from_repo(
    github_client: Any,
    repo_name: str,
    ref: Optional[str] = None
) -> Dict[str, Skill]:
    """Load custom skills from repository's .kimi/skills/ directory."""
    skills: Dict[str, Skill] = {}

    try:
        repo = github_client.client.get_repo(repo_name)

        try:
            contents = repo.get_contents(".kimi/skills", ref=ref)
        except Exception:
            return skills

        for item in contents:
            if item.type == "dir":
                skill = _load_skill_from_github(repo, item.path, ref)
                if skill:
                    skills[skill.name] = skill

    except Exception as e:
        logger.warning(f"Failed to load custom skills: {e}")

    return skills


def _load_skill_from_github(
    repo: Any,
    skill_path: str,
    ref: Optional[str] = None
) -> Optional[Skill]:
    """Load a skill from GitHub repository."""
    try:
        skill_md_path = f"{skill_path}/SKILL.md"
        content = repo.get_contents(skill_md_path, ref=ref)
        skill_content = content.decoded_content.decode("utf-8")

        metadata, instructions = parse_skill_md(skill_content)

        skill = Skill(
            name=metadata.get("name", skill_path.split("/")[-1]),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0.0"),
            triggers=metadata.get("triggers", []),
            instructions=instructions
        )

        # Load references
        try:
            refs_contents = repo.get_contents(f"{skill_path}/references", ref=ref)
            for ref_file in refs_contents:
                if ref_file.name.endswith(".md"):
                    ref_content = repo.get_contents(ref_file.path, ref=ref)
                    skill.references[ref_file.name[:-3]] = ref_content.decoded_content.decode("utf-8")
        except Exception:
            pass

        logger.info(f"Loaded custom skill: {skill.name}")
        return skill

    except Exception as e:
        logger.warning(f"Failed to load skill from {skill_path}: {e}")
        return None


class SkillManager:
    """Manages skill loading and execution.
    
    Skills are loaded from two sources:
    1. Built-in skills from src/skills/
    2. Custom skills from repository's .kimi/skills/
    
    Custom skills with the same name as built-in skills will override them.
    """

    def __init__(self) -> None:
        self.builtin_skills: Dict[str, Skill] = {}
        self.custom_skills: Dict[str, Skill] = {}
        self._load_builtin()

    def _load_builtin(self) -> None:
        """Load built-in skills."""
        self.builtin_skills = load_builtin_skills()

    def load_from_repo(
        self,
        github_client: Any,
        repo_name: str,
        ref: Optional[str] = None
    ) -> None:
        """Load custom skills from repository.
        
        Custom skills override built-in skills with the same name.
        """
        self.custom_skills = load_custom_skills_from_repo(github_client, repo_name, ref)

        # Log overrides
        for name in self.custom_skills:
            if name in self.builtin_skills:
                logger.info(f"Custom skill '{name}' overrides built-in skill")

    @property
    def skills(self) -> Dict[str, Skill]:
        """Get all skills (custom overrides built-in)."""
        merged = dict(self.builtin_skills)
        merged.update(self.custom_skills)  # Custom overrides built-in
        return merged

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name.
        
        Priority: custom > built-in
        """
        # Check custom first
        if name in self.custom_skills:
            return self.custom_skills[name]
        # Fall back to built-in
        return self.builtin_skills.get(name)

    def get_builtin_skill(self, name: str) -> Optional[Skill]:
        """Get a built-in skill by name (ignoring custom overrides)."""
        return self.builtin_skills.get(name)

    def list_skills(self) -> Dict[str, Dict[str, Any]]:
        """List all available skills with their source.
        
        Returns:
            Dict mapping skill name to {skill, source, overridden}
        """
        result: Dict[str, Dict[str, Any]] = {}

        for name, skill in self.builtin_skills.items():
            result[name] = {
                "skill": skill,
                "source": "builtin",
                "overridden": name in self.custom_skills
            }

        for name, skill in self.custom_skills.items():
            if name in result:
                result[name]["skill"] = skill
                result[name]["source"] = "custom (override)"
            else:
                result[name] = {
                    "skill": skill,
                    "source": "custom",
                    "overridden": False
                }

        return result

    def find_matching_skills(self, text: str) -> List[Skill]:
        """Find skills that match the given text."""
        return [s for s in self.skills.values() if s.matches(text)]

    def find_by_trigger(self, trigger: str) -> List[Skill]:
        """Find skills by trigger keyword."""
        trigger_lower = trigger.lower()
        return [
            s for s in self.skills.values()
            if trigger_lower in [t.lower() for t in s.triggers]
        ]

    def build_prompt(self, skill_name: str, **context: Any) -> str:
        """Build prompt from skill instructions."""
        skill = self.get_skill(skill_name)
        if not skill:
            return ""

        prompt_parts = [skill.instructions]

        # Add relevant references based on context
        if "language" in context:
            lang = context["language"].lower()
            ref_name = f"{lang}-best-practices"
            if ref_name in skill.references:
                prompt_parts.append(f"\n## {lang.title()} Reference\n{skill.references[ref_name]}")

        return "\n\n".join(prompt_parts)
