---
name: triage
description: Auto-triage issues by classifying type, priority, and suggesting labels
version: 1.0.0
author: xiaoju111a
triggers:
  - triage
  - classify
  - categorize
---

# Issue Triage Skill

Automatically classify and triage GitHub issues to help maintainers quickly process incoming issues.

## Purpose

- Classify issue type (bug, feature, question, docs, etc.)
- Assess priority based on impact and urgency
- Suggest appropriate labels from repository's label set
- Provide actionable recommendations for maintainers

## Issue Type Classification

| Type | Description | Signals |
|------|-------------|---------|
| `bug` | Something isn't working | "error", "crash", "not working", "broken", "fails", stack traces, error messages |
| `feature` | New functionality request | "would be nice", "add support", "implement", "request", "new feature" |
| `enhancement` | Improvement to existing feature | "improve", "better", "enhance", "upgrade existing" |
| `question` | Help or clarification needed | "how to", "is it possible", "can I", "help", "?", "wondering" |
| `documentation` | Docs improvements | "documentation", "readme", "example", "typo", ".md files" |
| `help wanted` | Needs community help | Complex issues, good for contribution |
| `good first issue` | Suitable for newcomers | Well-defined, small scope, good docs |

## Priority Assessment

| Priority | Criteria | Examples |
|----------|----------|----------|
| **Critical (P0)** | System down, security vulnerability, data loss | Security breach, complete service outage, data corruption |
| **High (P1)** | Major feature broken, significant user impact | Core feature not working, affects many users |
| **Medium (P2)** | Important but not urgent, workarounds exist | Non-critical bugs, moderate improvements |
| **Low (P3)** | Minor issues, nice-to-have | Cosmetic issues, minor enhancements, edge cases |

## Priority Signals

### Critical/High Priority Signals
- Security-related keywords: "vulnerability", "CVE", "security", "exploit", "injection"
- Data issues: "data loss", "corruption", "deleted", "missing data"
- Availability: "down", "unavailable", "500 error", "timeout"
- Scale: "all users", "everyone", "production"

### Low Priority Signals
- Cosmetic: "typo", "formatting", "color", "alignment"
- Edge cases: "rare", "edge case", "specific scenario"
- Nice-to-have: "would be nice", "minor", "small improvement"

## Analysis Guidelines

1. **Read the full issue** - Title and body together provide context
2. **Check for reproduction steps** - Well-documented bugs are easier to assess
3. **Consider the author** - First-time contributors may phrase things differently
4. **Look at linked issues/PRs** - May provide additional context
5. **Assess impact scope** - How many users are affected?

## Output Format

```json
{
    "type": "bug|feature|enhancement|question|documentation|other",
    "priority": "critical|high|medium|low",
    "labels": ["label1", "label2", "label3"],
    "confidence": "high|medium|low",
    "summary": "One-line summary of the issue",
    "reason": "Brief explanation of classification reasoning"
}
```

## Rules

1. **Be conservative** - Only suggest labels you're confident about
2. **Maximum 4 labels** - Don't over-label issues
3. **Use repo labels** - Only suggest labels that exist in the repository
4. **Acknowledge uncertainty** - If unsure, set confidence to "low" and explain
5. **Consider context** - Repository type matters (library vs app vs docs)

## Special Cases

### Needs More Information
If the issue lacks critical details:
- Set confidence to "low"
- Note what information is missing in the reason
- Consider suggesting "needs-info" or "needs-triage" label if available

### Duplicates
If the issue appears to be a duplicate:
- Note in the reason
- Suggest "duplicate" label if available
- Don't assign other type labels

### Multi-Type Issues
If an issue contains both a bug report and feature request:
- Classify based on the primary concern
- Note the secondary aspect in the reason
- Recommend splitting if appropriate
