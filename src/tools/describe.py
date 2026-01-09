"""PR description generation tool for Kimi Actions."""

import yaml
from typing import List, Tuple

from tools.base import BaseTool


class Describe(BaseTool):
    """PR description generation tool."""

    @property
    def skill_name(self) -> str:
        return "describe"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> Tuple[str, str]:
        """Generate PR description.
        
        Args:
            repo_name: Repository name
            pr_number: PR number
            update_pr: Whether to update the PR (default: True)
            
        Returns:
            Tuple of (title, body)
        """
        update_pr = kwargs.get("update_pr", True)

        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        compressed_diff, _, _ = self.get_diff(repo_name, pr_number)
        if not compressed_diff:
            return pr.title, "No changes detected."

        # Get skill
        skill = self.get_skill()
        system_prompt = skill.instructions if skill else "Generate a PR description."

        # Get commit messages
        commits = list(pr.get_commits())
        commit_messages = "\n".join([f"- {c.commit.message.split(chr(10))[0]}" for c in commits[:10]])

        user_prompt = f"""## PR Information
Original Title: {pr.title}
Branch: {pr.head.ref} -> {pr.base.ref}

## Commit History
{commit_messages}

## Code Changes
```diff
{compressed_diff}
```

Please generate PR description."""

        response = self.call_kimi(system_prompt, user_prompt)
        title, body, labels = self._parse_response(response, pr.title)

        if update_pr and self.config.describe.generate_title:
            try:
                pr.edit(title=title, body=body)
                if labels and self.config.describe.generate_labels:
                    pr.set_labels(*labels)
            except Exception as e:
                print(f"Warning: Could not update PR: {e}")

        return title, body

    def _parse_response(self, response: str, default_title: str) -> Tuple[str, str, List[str]]:
        """Parse YAML response."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]

            data = yaml.safe_load(yaml_content)

            title = data.get("title", default_title).strip()
            pr_type = data.get("type", "")
            labels = data.get("labels", [])
            description = data.get("description", "").strip()
            files = data.get("files", [])

            body_parts = []

            type_emojis = {"feature": "✨", "bug_fix": "🐛", "refactor": "♻️", "docs": "📝", "test": "🧪", "chore": "🔧"}
            if pr_type:
                emoji = type_emojis.get(pr_type, "📦")
                body_parts.append(f"## {emoji} {pr_type.replace('_', ' ').title()}\n")

            if description:
                body_parts.append(f"{description}\n")

            if files and self.config.describe.enable_walkthrough:
                body_parts.append("## 📁 Changed Files\n| File | Type | Summary |\n|------|------|---------|")
                change_icons = {"added": "➕", "modified": "📝", "deleted": "🗑️", "renamed": "📛"}
                for f in files:
                    icon = change_icons.get(f.get("change_type", ""), "📄")
                    body_parts.append(f"| `{f.get('filename', '')}` | {icon} | {f.get('summary', '')} |")
                body_parts.append("")

            body_parts.append(self.format_footer())

            return title, "\n".join(body_parts), labels

        except Exception:
            return default_title, response, []

    def generate_comment(self, repo_name: str, pr_number: int) -> str:
        """Generate description as a comment."""
        title, body = self.run(repo_name, pr_number, update_pr=False)
        return f"## 🤖 Kimi PR Description\n\n### Suggested Title\n{title}\n\n### Suggested Description\n{body}"
