# Kimi Code Review Action

🌗 AI-powered code review using [Kimi](https://kimi.moonshot.cn/) (Moonshot AI)

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                  GitHub                                       │
│ ┌────────────────────────────────────────┐  ┌───────────────────────────────┐ │
│ │           Pull Request Events          │  │         Issue Events          │ │
│ │ ┌─────────┐ ┌──────────┐ ┌───────────┐ │  │ ┌───────────┐ ┌─────────────┐ │ │
│ │ │   PR    │ │PR Comment│ │  Inline   │ │  │ │  Issue    │ │Issue Comment│ │ │
│ │ │ Events  │ │ /review  │ │  Comment  │ │  │ │  Events   │ │  /triage    │ │ │
│ │ └────┬────┘ └────┬─────┘ └─────┬─────┘ │  │ └─────┬─────┘ └──────┬──────┘ │ │
│ └──────┼───────────┼─────────────┼───────┘  └───────┼──────────────┼────────┘ │
└────────┼───────────┼─────────────┼──────────────────┼──────────────┼──────────┘
         │           │             │                  │              │
         ▼           ▼             ▼                  ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions Workflow (Docker)                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                          main.py (Entry Point)                         │  │
│  │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ │  │
│  │ │handle_pr_    │ │handle_comment│ │handle_review_│ │handle_issue_    │ │  │
│  │ │event()       │ │_event()      │ │comment_event │ │event/comment()  │ │  │
│  │ └──────────────┘ └──────────────┘ └──────────────┘ └─────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                            Tools Layer                                 │  │
│  │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐  │  │
│  │ │Reviewer│ │Describe│ │Improve │ │  Ask   │ │ Labels │ │  Triage    │  │  │
│  │ │ /review│ │/describe│ │/improve││  /ask  │ │/labels │ │  /triage   │  │  │
│  │ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └──────┬─────┘  │  │
│  │     └──────────┴──────────┴──────────┴──────────┴─────────────┘        │  │
│  │                                 │                                      │  │
│  │                                 ▼                                      │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │                          BaseTool                                │  │  │
│  │  │   • get_diff()      • call_kimi()       • format_footer()        │  │  │
│  │  │   • load_context()  • get_skill()                                │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│           ┌──────────────────────────┼──────────────────────────┐            │
│           ▼                          ▼                          ▼            │
│   ┌──────────────┐         ┌──────────────┐          ┌──────────────┐        │
│   │ SkillManager │         │ TokenHandler │          │ DiffProcessor│        │
│   │  (SKILL.md)  │         │  (Chunking)  │          │  (Filtering) │        │
│   └──────────────┘         └──────────────┘          └──────────────┘        │
│                                      │                                       │
│           ┌──────────────────────────┴──────────────────────────┐            │
│           ▼                                                     ▼            │
│   ┌──────────────┐                                     ┌──────────────┐      │
│   │   Kimi API   │◄─────────  LLM Request  ───────────►│  GitHub API  │      │
│   │  (Moonshot)  │                                     │    (REST)    │      │
│   └──────────────┘                                     └──────────────┘      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Features

- 🔍 `/review` - Intelligent code review for bugs, security issues, and performance problems
- 📝 `/describe` - Auto-generate PR title and description
- ✨ `/improve` - Code improvement suggestions with concrete fixes
- 💬 `/ask` - Interactive Q&A about the PR
- 🏷️ `/labels` - Auto-generate and apply PR labels based on content
- 🎯 `/triage` - Auto-classify issues (bug/feature/question) with priority and labels
- 🧠 **Agent Skills** - Modular capability extension with custom review rules
- 🌐 Multi-language support (English/Chinese)
- ⚙️ Configurable review strictness
- 📦 Smart handling of large PRs (auto-chunking + model fallback)

## Quick Start

### 1. Get Kimi API Key

1. Visit [Moonshot AI Platform](https://platform.moonshot.cn/)
2. Register/Login
3. Go to "API Key Management"
4. Click "Create API Key"
5. Copy the generated API Key

### 2. Configure GitHub Secrets

1. Go to your GitHub repository
2. Click `Settings` → `Secrets and variables` → `Actions`
3. Click `New repository secret`
4. Add `KIMI_API_KEY` with the API Key from step 1

### 3. Create Workflow File

```yaml
# .github/workflows/kimi-review.yml
name: Kimi Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issues:
    types: [opened, reopened]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  # Job for PR-related events (review, describe, improve, ask, labels)
  pr-review:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       github.event.issue.pull_request &&
       startsWith(github.event.comment.body, '/')) ||
      (github.event_name == 'pull_request_review_comment' &&
       startsWith(github.event.comment.body, '/'))
    steps:
      - name: Get PR ref (for comments)
        id: get-pr
        if: github.event_name == 'issue_comment' || github.event_name == 'pull_request_review_comment'
        uses: actions/github-script@v7
        with:
          script: |
            const prNumber = context.issue?.number || context.payload.pull_request?.number;
            const pr = await github.rest.pulls.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: prNumber
            });
            core.setOutput('ref', pr.data.head.ref);
            core.setOutput('sha', pr.data.head.sha);

      - uses: actions/checkout@v4
        with:
          ref: ${{ (github.event_name == 'issue_comment' || github.event_name == 'pull_request_review_comment') && steps.get-pr.outputs.ref || github.head_ref }}

      - uses: xiaoju111a/kimi-actions@v1
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_review: 'false'

  # Job for Issue-related events (triage)
  issue-triage:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'issues' ||
      (github.event_name == 'issue_comment' &&
       !github.event.issue.pull_request &&
       startsWith(github.event.comment.body, '/'))
    steps:
      - uses: actions/checkout@v4

      - uses: xiaoju111a/kimi-actions@v1
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_triage: 'false'
```

## Commands

### PR Commands

Use these commands in PR comments:

| Command | Description |
|---------|-------------|
| `/review` | Code review with inline comments |
| `/review --incremental` | Review only new commits |
| `/describe` | Auto-generate PR description |
| `/describe --comment` | Generate description as comment |
| `/improve` | Code improvement suggestions |
| `/ask <question>` | Q&A about the PR |
| `/labels` | Auto-generate and apply PR labels |
| `/help` | Show help message |

### Issue Commands

Use these commands in Issue comments:

| Command | Description |
|---------|-------------|
| `/triage` | Auto-classify issue type and apply labels |
| `/triage --no-apply` | Classify without applying labels |
| `/help` | Show help message |

## Configuration

### Action Inputs

```yaml
- uses: xiaoju111a/kimi-actions@v1
  with:
    # Required
    kimi_api_key: ${{ secrets.KIMI_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    
    # Optional
    language: 'en-US'               # Response language: zh-CN, en-US
    model: 'kimi-k2-thinking'       # Kimi model (default: kimi-k2-thinking)
    review_level: 'normal'          # Review strictness: strict, normal, gentle
    max_files: '10'                 # Max files to review
    exclude_patterns: '*.lock,*.min.js'  # File patterns to exclude
    auto_review: 'true'             # Auto review on PR open
    auto_describe: 'false'          # Auto generate description on PR open
    auto_improve: 'false'           # Auto provide suggestions on PR open
    auto_triage: 'false'            # Auto triage issues on open
```

### Repository Config (.kimi-config.yml)

Create `.kimi-config.yml` in your repo root to customize behavior:

```yaml
# Category toggles
categories:
  bug: true
  performance: true
  security: true

# Replace built-in skills with custom ones
skill_overrides:
  code-review: my-company-review

# Ignore files
ignore_files:
  - "*.test.ts"
  - "**/__mocks__/**"

# Extra instructions
extra_instructions: |
  Focus on security issues.
```

### Custom Skills (Claude Skills Standard)

Create `.kimi/skills/` directory in your repo, each skill is a folder:

```
.kimi/skills/
├── react-review/
│   ├── SKILL.md           # Required: core instructions
│   ├── scripts/           # Optional: executable scripts
│   │   └── check_hooks.py
│   └── references/        # Optional: reference documents
│       └── hooks-rules.md
└── company-rules/
    └── SKILL.md
```

SKILL.md format:

```markdown
---
name: react-review
description: React code review expert
triggers:
  - react
  - jsx
  - hooks
---

# React Review Focus

## Hooks Rules
- Hooks can only be called at the top level of function components
- Cannot call Hooks inside conditionals

## Performance
- Check if useMemo/useCallback is needed
```

Skills are automatically triggered based on PR code content.

## Models

| Model | Context | Notes |
|-------|---------|-------|
| `kimi-k2-thinking` | 256K | Default, best reasoning capability |
| `kimi-k2-thinking-turbo` | 256K | Faster thinking model |
| `kimi-k2-turbo-preview` | 256K | Fast, for simple tasks |

All commands use **Kimi Agent SDK** with `kimi-k2-thinking` model for best results.

When PR is too large, the action uses intelligent chunking to prioritize important files.

## Review Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Bug** | Code defects | Unhandled exceptions, null pointers, logic errors |
| **Security** | Security vulnerabilities | SQL injection, XSS, auth flaws |
| **Performance** | Performance issues | O(n²) algorithms, N+1 queries |

## Project Structure

```
kimi-actions/
├── action.yml                  # GitHub Action definition
├── Dockerfile                  # Docker container config
├── requirements.txt            # Python dependencies
├── tests/                      # Unit tests
└── src/
    ├── main.py                 # Entry point, event routing
    ├── action_config.py        # Action config (env vars)
    ├── repo_config.py          # Repo config (.kimi-config.yml)
    ├── github_client.py        # GitHub API client
    ├── token_handler.py        # Token estimation + chunking
    ├── diff_processor.py       # Diff file filtering
    ├── skill_loader.py         # Skill loading/management
    ├── suggestion_service.py   # Suggestion filtering
    ├── models.py               # Data models
    ├── tools/                  # Command implementations (Agent SDK)
    │   ├── base.py             # Base class (Agent config)
    │   ├── reviewer.py         # /review
    │   ├── describe.py         # /describe
    │   ├── improve.py          # /improve
    │   ├── ask.py              # /ask
    │   ├── labels.py           # /labels
    │   └── triage.py           # /triage
    └── skills/                 # Built-in Skills
        ├── code-review/
        │   ├── SKILL.md
        │   └── scripts/
        ├── describe/
        ├── improve/
        ├── ask/
        ├── labels/
        └── triage/
```

## FAQ

### Q: How to get Kimi API Key?

Visit [Moonshot AI Platform](https://platform.moonshot.cn/), register and create an API Key in the management page. New users get free credits.

### Q: Does it support private repositories?

Yes. Just ensure `GITHUB_TOKEN` has permission to read repository contents.

### Q: What if PR is too large?

The action automatically:
1. Prioritizes important files (src/ > test/)
2. Chunks diff intelligently, keeping critical code
3. Falls back to larger context models

### Q: How to customize review rules?

Create `.kimi-config.yml` in your repo root, or add custom Skills in `.kimi/skills/` directory. See Configuration section above.

## Acknowledgments

- [Moonshot AI](https://www.moonshot.cn/) - Kimi LLM
- [pr-agent](https://github.com/qodo-ai/pr-agent) - Architecture reference
- [kimi-cli](https://github.com/MoonshotAI/kimi-cli) - Kimi CLI tool
- [kodus-ai](https://github.com/kodustech/kodus-ai) - AI code review reference

## License

MIT
