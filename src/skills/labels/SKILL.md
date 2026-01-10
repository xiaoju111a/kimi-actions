---
name: labels
description: Auto-generate PR labels based on content analysis
version: 1.0.0
author: xiaoju111a
triggers:
  - labels
  - label
  - tag
---

# Label Generation Skill

Analyze PR content and suggest appropriate labels.

## Label Categories

| Label | When to Use |
|-------|-------------|
| `bug` | Fixes a bug or defect |
| `feature` / `enhancement` | Adds new functionality |
| `documentation` | Documentation-only changes |
| `refactor` | Code restructuring without behavior change |
| `test` | Test additions or modifications |
| `chore` | Build, config, CI/CD changes |
| `breaking-change` | Breaking API or behavior changes |
| `dependencies` | Dependency updates |
| `security` | Security fixes or improvements |
| `performance` | Performance optimizations |

## Rules

1. **Be conservative** - Only suggest labels you're confident about
2. **Maximum 3 labels** - Don't over-label
3. **Use repo labels** - Only suggest labels that exist in the repo
4. **Consider scope** - Look at file paths, not just content

## Signals

- `bug`: Fix, patch, resolve, issue, error, crash
- `feature`: Add, new, implement, introduce
- `docs`: README, .md files, comments only
- `refactor`: Rename, move, restructure, clean
- `test`: test/, spec/, __tests__, .test., .spec.
- `chore`: .github/, config, CI, build
- `deps`: package.json, requirements.txt, go.mod
- `security`: auth, password, token, vulnerability, CVE
- `perf`: optimize, cache, speed, performance

## Output Format

```json
{
  "labels": ["bug", "security"],
  "reason": "Fixes authentication bypass vulnerability"
}
```
