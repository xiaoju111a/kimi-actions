---
name: improve
description: Analyze code and provide specific improvement suggestions with code examples.
version: 1.0.0
triggers:
  - improve
  - suggestions
  - optimize
---

# Code Improve Skill

## Task
Analyze code changes and provide specific improvement suggestions with code examples.

## Improvement Categories

### Performance
- Algorithm optimization
- Reduce unnecessary computation
- Cache utilization
- Batch processing

### Readability
- Naming improvements
- Code simplification
- Extract functions/methods
- Reduce nesting

### Security
- Input validation
- Secure API usage
- Sensitive data handling

### Best Practice
- Language idioms
- Design patterns
- Error handling
- Type safety

## Output Format

```yaml
suggestions:
  - relevant_file: "src/example.py"
    language: "python"
    relevant_lines_start: 10
    relevant_lines_end: 15
    label: "performance"
    severity: "medium"
    one_sentence_summary: "Use list comprehension instead of loop"
    suggestion_content: |
      Current code uses for loop to build list, can be simplified with list comprehension.
    existing_code: |
      result = []
      for i in range(100):
          result.append(i * 2)
    improved_code: |
      result = [i * 2 for i in range(100)]
```

## Principles

- Only suggest improvements with real value
- existing_code must be actual code from the PR
- improved_code must be directly usable as replacement
- Prioritize high-impact improvements
