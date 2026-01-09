---
name: describe
description: Generate clear, professional PR descriptions based on code changes.
version: 1.0.0
triggers:
  - describe
  - pr description
---

# PR Description Skill

## Task
Automatically generate clear, professional PR descriptions based on code changes.

## Workflow

1. **Analyze Changes**: Understand the purpose and scope of code changes
2. **Generate Title**: Concise and clear, no more than 60 characters
3. **Categorize Type**: feature, bug_fix, refactor, docs, test, chore
4. **Write Description**: Include background, changes, impact scope
5. **File Summary**: Change description for each file

## Output Format

```yaml
title: |
  Concise PR title
type: "feature"
labels:
  - "enhancement"
description: |
  ## Background
  Why this change is needed
  
  ## Changes
  What was done
  
  ## Impact
  What features are affected
files:
  - filename: "src/example.py"
    change_type: "modified"
    summary: "Added user validation logic"
```

## Principles

- Title starts with a verb (Add, Fix, Update, Remove)
- Description should be understandable by those unfamiliar with the code
- File summary highlights key changes
