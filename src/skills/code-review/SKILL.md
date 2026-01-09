---
name: code-review
description: AI-powered code review for quality, security, and best practices. Triggers on PR diffs.
version: 1.0.0
author: xiaoju
license: MIT
triggers:
  - review
  - diff
  - pull request
---

# Code Review Skill

## Trigger Conditions
Activated when user provides code diff and requests review.

## Review Workflow

### Step 1: Understand Context
- Analyze PR title, branch name, scope of changes
- Identify programming language and framework
- Ask for more context if needed

### Step 2: Run Automated Checks
If scripts are available, execute:
- `scripts/linter.py` - Code style check
- `scripts/security_scan.py` - Security vulnerability scan

### Step 3: Identify Issues
Check by priority:

**Critical/High (Must Fix)**
- Security vulnerabilities (injection, auth bypass, data leak)
- Bugs that cause crashes
- Data corruption risks
- Resource leaks

**Medium (Should Fix)**
- Logic errors
- Performance issues
- Incomplete error handling

**Low (Optional Improvement)**
- Code style
- Naming optimization

### Step 4: Provide Suggestions
- Acknowledge positives first, then suggest improvements (Sandwich method)
- Reference specific line numbers
- Provide fix code examples

### Step 5: Summary and Score
- Score from 0-100
- Key points list

## Output Format

```yaml
summary: |
  One sentence summary of PR quality
score: 85
estimated_effort: 3
suggestions:
  - relevant_file: "path/to/file.py"
    language: "python"
    relevant_lines_start: 10
    relevant_lines_end: 15
    label: "bug|performance|security"
    severity: "critical|high|medium|low"
    one_sentence_summary: "Brief description of issue"
    suggestion_content: |
      Detailed explanation and fix suggestion
    existing_code: |
      Current code
    improved_code: |
      Improved code
```

## Issue Categories

### Bug
- Unhandled exceptions
- Null pointer / undefined access
- Type errors
- Logic errors
- Race conditions
- Resource leaks

### Security
- SQL/NoSQL/Command injection
- XSS/CSRF
- Authentication/Authorization flaws
- Sensitive data exposure

### Performance
- High algorithm complexity
- Database N+1 queries
- Blocking I/O
