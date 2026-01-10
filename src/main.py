"""Main entry point for Kimi Code Review Action."""

import json
import logging
import os
import re
import sys

from action_config import ActionConfig
from kimi_client import KimiClient
from github_client import GitHubClient
from tools import Reviewer, Describe, Improve, Ask, Labels

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_input(name: str, default: str = None) -> str:
    """Get action input from environment."""
    env_name = f"INPUT_{name.upper().replace('-', '_')}"
    return os.environ.get(env_name, default)


def parse_command(comment_body: str) -> tuple:
    """Parse command from comment body.
    
    Returns:
        Tuple of (command, args) or (None, None) if no command found.
    """
    pattern = r'^/(\w+)(?:\s+(.*))?$'
    match = re.match(pattern, comment_body.strip(), re.DOTALL)
    if match:
        command = match.group(1).lower()
        args = match.group(2).strip() if match.group(2) else ""
        return command, args
    return None, None


def handle_pr_event(event: dict, config: ActionConfig):
    """Handle pull_request event (auto review on PR open/sync)."""
    pr_number = event.get("pull_request", {}).get("number")
    repo_name = event.get("repository", {}).get("full_name")
    action = event.get("action")

    if not pr_number or not repo_name:
        logger.error("Invalid pull request event")
        return

    logger.info(f"PR #{pr_number} in {repo_name} - action: {action}")

    # Initialize clients
    try:
        kimi = KimiClient(config.kimi_api_key, config.model)
        github = GitHubClient(config.github_token)
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return

    # Auto actions on PR open/sync
    auto_review = get_input("auto_review", "true").lower() == "true"
    auto_describe = get_input("auto_describe", "false").lower() == "true"
    auto_improve = get_input("auto_improve", "false").lower() == "true"

    try:
        if auto_describe and action in ["opened"]:
            logger.info("Running auto describe...")
            describe = Describe(kimi, github)
            describe.run(repo_name, pr_number, update_pr=True)

        if auto_review:
            logger.info("Running auto review...")
            reviewer = Reviewer(kimi, github)
            result = reviewer.run(repo_name, pr_number, inline=True)
            if result:  # Only post if not empty (inline already posted)
                github.post_comment(repo_name, pr_number, result)

        if auto_improve:
            logger.info("Running auto improve...")
            improve = Improve(kimi, github)
            result = improve.run(repo_name, pr_number)
            github.post_comment(repo_name, pr_number, result)

        logger.info("Done!")
    except Exception as e:
        logger.error(f"Error processing PR: {e}")
        try:
            github.post_comment(repo_name, pr_number, f"❌ Error processing PR: {str(e)}")
        except Exception:
            pass


def handle_review_comment_event(event: dict, config: ActionConfig):
    """Handle pull_request_review_comment event (inline comment command trigger)."""
    action = event.get("action")
    if action != "created":
        return

    comment = event.get("comment", {})
    comment_body = comment.get("body", "")

    # Parse command
    command, args = parse_command(comment_body)
    if not command:
        return

    pr = event.get("pull_request", {})
    pr_number = pr.get("number")
    repo_name = event.get("repository", {}).get("full_name")

    # Get context from inline comment
    file_path = comment.get("path", "")
    line = comment.get("line") or comment.get("original_line", 0)
    diff_hunk = comment.get("diff_hunk", "")

    logger.info(f"Inline command: /{command} {args}")
    logger.info(f"PR #{pr_number} in {repo_name}, file: {file_path}:{line}")

    # Initialize clients
    try:
        kimi = KimiClient(config.kimi_api_key, config.model)
        github = GitHubClient(config.github_token)
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return

    # Handle command with context
    result = None
    try:
        if command == "ask":
            if not args:
                result = "❌ Please provide a question"
            else:
                ask = Ask(kimi, github)
                # Add context about the code location with diff format
                context_question = f"Regarding `{file_path}` line {line}:\n```diff\n{diff_hunk}\n```\n\n{args}"
                result = ask.run(repo_name, pr_number, question=context_question)
        else:
            # For other commands, just run normally
            result = f"ℹ️ Command `/{command}` is better used in the main PR comment area."

    except Exception as e:
        logger.error(f"Error handling inline command /{command}: {e}")
        result = f"❌ Error: {str(e)}"

    # Reply to the inline comment
    if result:
        try:
            github.reply_to_review_comment(repo_name, pr_number, comment.get("id"), result)
        except Exception as e:
            logger.error(f"Failed to reply to review comment: {e}")
            # Fallback to regular comment
            github.post_comment(repo_name, pr_number, f"> /{command} {args}\n\n{result}")


def handle_comment_event(event: dict, config: ActionConfig):
    """Handle issue_comment event (command trigger)."""
    action = event.get("action")
    if action not in ["created", "edited"]:
        return

    comment = event.get("comment", {})
    comment_body = comment.get("body", "")

    # Check if this is a PR comment
    issue = event.get("issue", {})
    if "pull_request" not in issue:
        logger.info("Not a PR comment, skipping")
        return

    # Parse command
    command, args = parse_command(comment_body)
    if not command:
        return

    pr_number = issue.get("number")
    repo_name = event.get("repository", {}).get("full_name")

    logger.info(f"Command: /{command} {args}")
    logger.info(f"PR #{pr_number} in {repo_name}")

    # Initialize clients
    try:
        kimi = KimiClient(config.kimi_api_key, config.model)
        github = GitHubClient(config.github_token)
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return

    # Add reaction to show we're processing
    github.add_reaction(repo_name, pr_number, comment.get("id"), "eyes")

    # Handle commands
    result = None

    try:
        if command == "review":
            reviewer = Reviewer(kimi, github)
            # Check for flags
            incremental = "--incremental" in args or "-i" in args
            # inline is default True, --no-inline to disable
            inline = "--no-inline" not in args
            result = reviewer.run(repo_name, pr_number, incremental=incremental, inline=inline)

        elif command == "describe":
            describe = Describe(kimi, github)
            if args == "--comment":
                result = describe.generate_comment(repo_name, pr_number)
            else:
                describe.run(repo_name, pr_number, update_pr=True)
                result = "✅ PR description updated"

        elif command == "improve":
            improve = Improve(kimi, github)
            result = improve.run(repo_name, pr_number)

        elif command == "ask":
            if not args:
                result = "❌ Please provide a question, e.g.: `/ask What does this function do?`"
            else:
                ask = Ask(kimi, github)
                result = ask.run(repo_name, pr_number, question=args)

        elif command == "labels" or command == "label":
            labels_tool = Labels(kimi, github)
            result = labels_tool.run(repo_name, pr_number)

        elif command == "help":
            result = get_help_message()

        else:
            result = f"❌ Unknown command: `/{command}`\n\nUse `/help` to see available commands."

    except Exception as e:
        logger.error(f"Error handling command /{command}: {e}")
        result = f"❌ Error executing command: {str(e)}"

    # Post result with command quote
    if result:
        try:
            # Quote the original command
            original_command = f"/{command}"
            if args:
                original_command += f" {args}"
            quoted_result = f"> {original_command}\n\n{result}"
            github.post_comment(repo_name, pr_number, quoted_result)
        except Exception as e:
            logger.error(f"Failed to post result: {e}")

    logger.info("Done!")


def get_help_message() -> str:
    """Get help message with available commands."""
    return """## 🤖 Kimi Actions Help

### Available Commands

| Command | Description |
|---------|-------------|
| `/review` | Perform code review on PR |
| `/review --incremental` | Review only new commits |
| `/review --inline` | Post inline comments on code |
| `/describe` | Auto-generate PR description |
| `/describe --comment` | Generate description as comment |
| `/improve` | Provide code improvement suggestions |
| `/ask <question>` | Q&A about the PR |
| `/labels` | Auto-generate and apply PR labels |
| `/help` | Show this help message |

### Examples

```bash
/review
/review --incremental
/review --no-inline
/ask What is the time complexity of this function?
/labels
```

---
<sub>Powered by [Kimi](https://kimi.moonshot.cn/)</sub>
"""


def main():
    # Configure logging level from env
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    logger.info("Kimi Actions starting...")

    # Load config
    config = ActionConfig.from_env()

    # Validate required inputs
    if not config.kimi_api_key:
        logger.error("KIMI_API_KEY is required")
        sys.exit(1)
    if not config.github_token:
        logger.error("GITHUB_TOKEN is required")
        sys.exit(1)

    # Load GitHub event
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        logger.error("GITHUB_EVENT_PATH not set")
        sys.exit(1)

    with open(event_path, "r") as f:
        event = json.load(f)

    event_name = os.environ.get("GITHUB_EVENT_NAME")
    logger.info(f"Event: {event_name}")

    # Route to appropriate handler
    if event_name in ["pull_request", "pull_request_target"]:
        handle_pr_event(event, config)
    elif event_name == "issue_comment":
        handle_comment_event(event, config)
    elif event_name == "pull_request_review_comment":
        handle_review_comment_event(event, config)
    else:
        logger.warning(f"Unsupported event: {event_name}")
        sys.exit(0)


if __name__ == "__main__":
    main()
