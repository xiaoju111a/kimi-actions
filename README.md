# Kimi Code Review Action

🌗 AI-powered code review using [Kimi](https://kimi.moonshot.cn/) (Moonshot AI)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              GitHub                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PR Events  │  PR Comments  │  Inline Comments               │   │
│  │             │  /review      │  /ask                          │   │
│  │             │  /ask         │                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Docker)                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      main.py                                  │ │
│  │  Event Router: PR events → /review, /ask commands             │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Tools Layer                                │ │
│  │                                                               │ │
│  │  ┌──────────┐              ┌──────────┐                       │ │
│  │  │ Reviewer │              │   Ask    │                       │ │
│  │  │ /review  │              │  /ask    │                       │ │
│  │  └────┬─────┘              └────┬─────┘                       │ │
│  │       └──────────┬──────────────┘                             │ │
│  │                  ▼                                            │ │
│  │         ┌────────────────┐                                    │ │
│  │         │    BaseTool    │                                    │ │
│  │         │  • clone_repo  │                                    │ │
│  │         │  • run_agent   │                                    │ │
│  │         │  • get_skill   │                                    │ │
│  │         └────────────────┘                                    │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   SkillManager                                │ │
│  │  Load SKILL.md and set skills_dir for Agent SDK               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│         ┌────────────────────┴────────────────────┐                │
│         ▼                                         ▼                │
│  ┌──────────────────┐                   ┌──────────────────┐       │
│  │  Kimi Agent SDK  │                   │   GitHub API     │       │
│  │   (kimi-k2.5)    │                   │     (REST)       │       │
│  │                  │                   │                  │       │
│  │ • Auto token mgmt│                   │ • Get PR diff    │       │
│  │ • Script exec    │                   │ • Post comments  │       │
│  │ • Context mgmt   │                   │ • Get PR info    │       │
│  │ • Markdown output│                   │                  │       │
│  └──────────────────┘                   └──────────────────┘       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Features

- 🔍 `/review` - Comprehensive code review of all PR changes
- 💬 `/ask` - Interactive Q&A about the PR or specific code
- 🧠 **Agent Skills** - Modular capability extension with custom review rules
- 🌐 Multi-language support (English/Chinese)
- ⚙️ Configurable review strictness
- 🎯 **Direct Markdown Output** - Clean, readable reviews powered by Agent SDK
- 🚀 **Simplified Architecture** - Agent SDK handles all context and token management

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
5. (Optional) Add `KIMI_BASE_URL` if using a custom API endpoint (defaults to `https://api.moonshot.cn/v1`)

### 3. Create Workflow File

```yaml
# .github/workflows/kimi-review.yml
name: Kimi Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write

jobs:
  kimi-review:
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

      - uses: xiaoju111a/kimi-actions@main
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Optional
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_review: 'false'  # Use /review command instead
```

## Commands

### PR Commands

Use these commands in PR comments:

| Command | Description | Usage Location |
|---------|-------------|----------------|
| `/review` | Comprehensive code review of all PR changes | PR comment area |
| `/ask <question>` | Q&A about the PR or specific code | PR comment area **or** Files changed tab (inline) |
| `/help` | Show help message | PR comment area |

**💡 Using `/ask` for code-specific questions:**
- **In PR comment area**: Ask general questions about the entire PR
- **In Files changed tab**: Click the **+** button next to a line of code, then use `/ask <question>` to ask about that specific code

**🔄 Avoiding Duplicate Reviews:**
- The bot tracks the last reviewed commit SHA
- If you run `/review` again without new commits, it will show "✅ No new changes since last review"
- This prevents wasting tokens on unchanged code

## Configuration

### Action Inputs

```yaml
- uses: xiaoju111a/kimi-actions@main
  with:
    # Required
    kimi_api_key: ${{ secrets.KIMI_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    
    # Optional
    kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Custom API endpoint (optional, defaults to https://api.moonshot.cn/v1)
    language: 'en-US'               # Response language: zh-CN, en-US
    model: 'kimi-k2.5'              # Kimi model (default: kimi-k2.5)
    review_level: 'normal'          # Review strictness: strict, normal, gentle
    max_files: '50'                 # Max files to review
    exclude_patterns: '*.lock,*.min.js'  # File patterns to exclude
    auto_review: 'false'            # Auto review on PR open (default: false, use /review command instead)
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
| `kimi-k2.5` | 256K | **Default**, latest model with best performance |
| `kimi-k2-thinking-turbo` | 256K | Faster thinking model |
| `kimi-k2-thinking` | 256K | More thorough reasoning, slower |

All commands use **Kimi Agent SDK** with `kimi-k2.5` model by default.

The Agent SDK automatically handles large PRs with its 256K context window.

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
├── tests/                      # Unit tests (115 tests)
└── src/
    ├── main.py                 # Entry point, event routing
    ├── action_config.py        # Action config (env vars)
    ├── repo_config.py          # Repo config (.kimi-config.yml)
    ├── github_client.py        # GitHub API client
    ├── skill_loader.py         # Skill loading/management
    ├── tools/                  # Command implementations (Agent SDK)
    │   ├── base.py             # Base class (common functionality)
    │   ├── reviewer.py         # /review - Code review
    │   └── ask.py              # /ask - Q&A
    └── skills/                 # Built-in Skills
        ├── code-review/
        │   ├── SKILL.md        # Review instructions
        │   └── references/     # Reference documents
        └── ask/
            └── SKILL.md
```

### Key Components

| Component | Purpose | Notes |
|-----------|---------|-------|
| **skill_loader.py** | Manage skills | Load SKILL.md, set skills_dir for Agent SDK |
| **base.py** | Common tool functionality | Repo cloning, Agent SDK execution |
| **Agent SDK** | LLM execution | Automatic token management, script execution, context handling, direct Markdown output |

## FAQ

### Q: How to get Kimi API Key?

Visit [Moonshot AI Platform](https://platform.moonshot.cn/), register and create an API Key in the management page. New users get free credits.

### Q: Does it support private repositories?

Yes. Just ensure `GITHUB_TOKEN` has permission to read repository contents.

### Q: What if PR is too large?

The **Kimi Agent SDK** automatically handles large PRs:
- **256K token context window**: Can handle very large PRs
- **Automatic context management**: SDK intelligently manages what to include
- **Smart file filtering**: Excludes binary files, lock files, minified files

No manual chunking needed - the Agent SDK handles everything automatically.

### Q: What is Agent SDK and why use it?

**Kimi Agent SDK** is an intelligent agent framework that:
- **Automatic token management**: No need to manually count tokens or manage context
- **Dynamic script execution**: Automatically calls skill scripts when needed
- **Built-in tools**: Provides file operations (read/write) and bash execution
- **Context optimization**: Intelligently manages conversation context

This allows the action to focus on **what to review** (skills, rules) rather than **how to execute** (token counting, script running).

### Q: How do skills work with Agent SDK?

Skills define **what the agent should do**:
1. **SKILL.md** contains instructions for the agent
2. **scripts/** contains executable tools (Python scripts)
3. Agent SDK automatically calls scripts when needed based on instructions

Example flow:
```
1. Load skill: code-review
2. Pass skills_dir to Agent SDK
3. Agent reads SKILL.md instructions
4. Agent automatically calls scripts/check_security.py when analyzing code
5. Agent generates review based on script output + instructions
```

### Q: How to customize review rules?

Create `.kimi-config.yml` in your repo root, or add custom Skills in `.kimi/skills/` directory. See Configuration section above.

### Q: How to use a custom API endpoint?

If you're using a proxy or custom Kimi API endpoint, add `KIMI_BASE_URL` to your repository secrets:

1. Go to `Settings` → `Secrets and variables` → `Actions`
2. Click `New repository secret`
3. Add `KIMI_BASE_URL` with your custom endpoint (e.g., `https://your-proxy.example.com/v1`)

Then use it in your workflow:

```yaml
- uses: xiaoju111a/kimi-actions@main
  with:
    kimi_api_key: ${{ secrets.KIMI_API_KEY }}
    kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Custom endpoint from secrets
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

**Note:** If `KIMI_BASE_URL` is not set, it defaults to `https://api.moonshot.cn/v1`.

This is useful for:
- Using a corporate proxy
- Testing with a local development server
- Using alternative API gateways
- Keeping endpoint URLs private

## Acknowledgments

- [Moonshot AI](https://www.moonshot.cn/) - Kimi LLM
- [Kimi Agent SDK](https://github.com/MoonshotAI/kimi-agent-sdk) - Agent framework
- [pr-agent](https://github.com/qodo-ai/pr-agent) - Architecture reference
- [kimi-cli](https://github.com/MoonshotAI/kimi-cli) - Kimi CLI tool
- [kodus-ai](https://github.com/kodustech/kodus-ai) - AI code review reference

## License

MIT
