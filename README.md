<p align="center">
  <img src="logo.jpg" alt="Kimi Code Review" width="128">
</p>

# Kimi Code Review Action

🤖 AI-powered code review using [Kimi](https://kimi.moonshot.cn/) (Moonshot AI)

## Features

- 🔍 `/review` - Intelligent code review for bugs, security issues, and performance problems
- 📝 `/describe` - Auto-generate PR title and description
- ✨ `/improve` - Code improvement suggestions with concrete fixes
- 💬 `/ask` - Interactive Q&A about the PR
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
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' && 
       github.event.issue.pull_request &&
       startsWith(github.event.comment.body, '/'))
    steps:
      - uses: xiaoju111a/kimi-actions@v1
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Commands

Use these commands in PR comments:

| Command | Description |
|---------|-------------|
| `/review` | Perform code review on PR |
| `/review --incremental` | Review only new commits since last review |
| `/review --inline` | Post inline comments on specific code lines |
| `/describe` | Auto-generate PR description (updates PR) |
| `/describe --comment` | Generate description as comment |
| `/improve` | Provide code improvement suggestions |
| `/ask <question>` | Q&A about the PR |
| `/labels` | Auto-generate and apply PR labels |
| `/help` | Show help message |

## Example Output

### /review

```markdown
## 🤖 Kimi Code Review

### 📊 Summary

| Metric | Value |
|--------|-------|
| Code Score | 78/100 |
| Review Effort | 3/5 |
| Files Changed | 5 |

**Summary**: Overall code quality is good, found 2 issues to address.

---

### 🔍 Issues Found

#### 🔴 1. SQL Injection Risk [Critical]

📍 **File**: `src/db.py` (L42-45)
📂 **Type**: Security

**Description**:
User input is directly concatenated into SQL statement, creating injection risk.

**Current Code**:
```python
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)
```

**Suggested Fix**:
```python
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```
```

### /improve

```markdown
## 🤖 Kimi Code Suggestions

Found **3** improvement suggestions

| # | File | Type | Severity |
|---|------|------|----------|
| 1 | `src/utils.py` | ⚡ Performance | 8/10 |
| 2 | `src/api.py` | 🐛 Bug | 7/10 |

---

### ⚡ Suggestion 1: Use list comprehension

📍 **File**: `src/utils.py` (L15-20)

**Current Code**:
```python
result = []
for item in items:
    if item.is_valid():
        result.append(item.value)
```

**Suggested**:
```python
result = [item.value for item in items if item.is_valid()]
```

**Reason**: List comprehension is more concise and typically faster in CPython.
```

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
    model: 'kimi-k2-turbo-preview'  # Kimi model
    review_level: 'normal'          # Review strictness: strict, normal, gentle
    max_files: '10'                 # Max files to review
    exclude_patterns: '*.lock,*.min.js'  # File patterns to exclude
    auto_review: 'true'             # Auto review on PR open
    auto_describe: 'false'          # Auto generate description on PR open
    auto_improve: 'false'           # Auto provide suggestions on PR open
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
| `kimi-k2-turbo-preview` | 256K | Fast, recommended for daily use |
| `kimi-k2-0905-preview` | 256K | Latest K2, most capable |

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
    ├── kimi_client.py          # Kimi API client
    ├── github_client.py        # GitHub API client
    ├── token_handler.py        # Token estimation + chunking
    ├── diff_processor.py       # Diff file filtering
    ├── skill_loader.py         # Skill loading/management
    ├── suggestion_service.py   # Suggestion filtering
    ├── models.py               # Data models
    ├── tools/                  # Command implementations
    │   ├── base.py             # Base class
    │   ├── reviewer.py         # /review
    │   ├── describe.py         # /describe
    │   ├── improve.py          # /improve
    │   └── ask.py              # /ask
    └── skills/                 # Built-in Skills
        ├── code-review/
        │   ├── SKILL.md
        │   └── scripts/
        ├── describe/
        ├── improve/
        └── ask/
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
