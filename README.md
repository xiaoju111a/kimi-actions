# Kimi Code Review Action

基于 [Kimi](https://kimi.moonshot.cn/) (月之暗面 AI) 的智能代码审查工具

这是一个自动化的 GitHub Action，通过 AI 技术为 Pull Request 提供智能代码审查、问题分类和改进建议。

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
│  │  │   • clone_repo()    • run_agent()       • format_footer()        │  │  │
│  │  │   • get_diff()      • get_skill()       • post_inline_comments() │  │  │
│  │  │   • load_context()  • get_skills_dir()  • parse_yaml_response()  │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│           ┌──────────────────────────┼──────────────────────────┐            │
│           ▼                          ▼                          ▼            │
│   ┌──────────────┐         ┌──────────────┐          ┌──────────────────┐    │
│   │ SkillManager │         │ DiffChunker  │          │SuggestionService │    │
│   │  (SKILL.md)  │         │  (Large PRs) │          │(Post-processing) │    │
│   │ • Load skills│         │ • Prioritize │          │ • Filter/dedupe  │    │
│   │ • Set skills_│         │ • Chunk diff │          │ • Validate       │    │
│   │   dir for SDK│         │ • Exclude    │          │ • Score/sort     │    │
│   └──────────────┘         └──────────────┘          └──────────────────┘    │
│                                      │                                       │
│           ┌──────────────────────────┴──────────────────────────┐            │
│           ▼                                                     ▼            │
│   ┌──────────────────────────────────────────┐        ┌──────────────┐       │
│   │         Kimi Agent SDK                   │        │  GitHub API  │       │
│   │         (kimi-k2-thinking-turbo)         │        │    (REST)    │       │
│   │                                          │        │              │       │
│   │  • Automatic token management            │        │              │       │
│   │  • Automatic script execution            │        │              │       │
│   │  • Context window management             │        │              │       │
│   │  • Built-in tools (read/write/bash)      │        │              │       │
│   │  • Skills directory integration          │        │              │       │
│   └──────────────────────────────────────────┘        └──────────────┘       │
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
5. (Optional) Add `KIMI_BASE_URL` if using a custom API endpoint (defaults to `https://api.moonshot.cn/v1`)

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

      - uses: xiaoju111a/kimi-actions@main
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Optional
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

      - uses: xiaoju111a/kimi-actions@main
        with:
          kimi_api_key: ${{ secrets.KIMI_API_KEY }}
          kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Optional
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_triage: 'false'
```

## Commands

### PR Commands

Use these commands in PR comments:

| Command | Description | Usage Location |
|---------|-------------|----------------|
| `/review` | Smart code review with inline comments (auto-detects incremental) | PR comment area |
| `/describe` | Auto-generate PR description | PR comment area |
| `/describe --comment` | Generate description as comment | PR comment area |
| `/improve` | Code improvement suggestions | PR comment area |
| `/ask <question>` | Q&A about the PR or specific code | PR comment area **or** Files changed tab (inline) |
| `/labels` | Auto-generate and apply PR labels | PR comment area |
| `/help` | Show help message | PR comment area |

**🧠 Smart Incremental Review:**

The `/review` command automatically detects the best review strategy:
- **First review**: Full review of all changes
- **Subsequent reviews**: Only reviews new commits since last review (if previous review <7 days old)
- **Old reviews**: Automatically does full re-review if previous review is >7 days old
- **No new commits**: Shows "✅ No new changes since last review" message

No parameters needed - it intelligently adapts to your workflow! 🎯

**💡 Using `/ask` for code-specific questions:**
- **In PR comment area**: Ask general questions about the entire PR
- **In Files changed tab**: Click the **+** button next to a line of code, then use `/ask <question>` to ask about that specific code

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
- uses: xiaoju111a/kimi-actions@main
  with:
    # Required
    kimi_api_key: ${{ secrets.KIMI_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    
    # Optional
    kimi_base_url: ${{ secrets.KIMI_BASE_URL }}  # Custom API endpoint (optional, defaults to https://api.moonshot.cn/v1)
    language: 'en-US'               # Response language: zh-CN, en-US
    model: 'kimi-k2-thinking-turbo' # Kimi model (default: kimi-k2-thinking-turbo, or kimi-k2-thinking for more thorough analysis)
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
| `kimi-k2-thinking-turbo` | 256K | **Default**, faster thinking model, good balance |
| `kimi-k2-thinking` | 256K | More thorough reasoning, slower |
| `kimi-k2-turbo-preview` | 256K | Fast, for simple tasks |

All commands use **Kimi Agent SDK** with `kimi-k2-thinking-turbo` model by default for best speed/quality balance.

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
├── tests/                      # Unit tests (235 tests)
└── src/
    ├── main.py                 # Entry point, event routing
    ├── action_config.py        # Action config (env vars)
    ├── repo_config.py          # Repo config (.kimi-config.yml)
    ├── github_client.py        # GitHub API client
    ├── diff_chunker.py         # Intelligent diff chunking for large PRs
    ├── diff_processor.py       # Diff file filtering (binary, lock files)
    ├── skill_loader.py         # Skill loading/management
    ├── suggestion_service.py   # Suggestion post-processing
    ├── models.py               # Data models
    ├── tools/                  # Command implementations (Agent SDK)
    │   ├── base.py             # Base class (common functionality)
    │   ├── reviewer.py         # /review - Code review
    │   ├── describe.py         # /describe - PR description
    │   ├── improve.py          # /improve - Code improvements
    │   ├── ask.py              # /ask - Q&A
    │   ├── labels.py           # /labels - Label generation
    │   └── triage.py           # /triage - Issue classification
    └── skills/                 # Built-in Skills
        ├── code-review/
        │   ├── SKILL.md        # Review instructions
        │   └── scripts/        # Review scripts (called by Agent SDK)
        ├── describe/
        ├── improve/
        ├── ask/
        ├── labels/
        └── triage/
            └── scripts/
                └── scan_codebase.py
```

### Key Components

| Component | Purpose | Notes |
|-----------|---------|-------|
| **diff_chunker.py** | Handle large PRs | Priority-based file selection, token-aware chunking |
| **skill_loader.py** | Manage skills | Load SKILL.md, set skills_dir for Agent SDK |
| **suggestion_service.py** | Post-process suggestions | Filter, dedupe, validate, score, sort |
| **base.py** | Common tool functionality | Diff fetching, repo cloning, Agent SDK execution |
| **Agent SDK** | LLM execution | Automatic token management, script execution, context handling |

## FAQ

### Q: How to get Kimi API Key?

Visit [Moonshot AI Platform](https://platform.moonshot.cn/), register and create an API Key in the management page. New users get free credits.

### Q: Does it support private repositories?

Yes. Just ensure `GITHUB_TOKEN` has permission to read repository contents.

### Q: What if PR is too large?

The action uses **intelligent diff chunking**:
1. **Priority-based selection**: Security files and core logic prioritized over tests/docs
2. **Token-aware chunking**: Automatically fits within Agent SDK context limits (256K tokens)
3. **File filtering**: Excludes binary files, lock files, minified files

Agent SDK automatically manages token counting and context windows.

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
