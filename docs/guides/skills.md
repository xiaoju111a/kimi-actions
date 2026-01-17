# Skills System

## What are Skills?

Skills are modular capabilities that extend the review functionality.

## Built-in Skills

- `code-review`: Main code review skill
- `triage`: Issue classification skill

## Custom Skills

Create custom skills in `.kimi/skills/` directory:

```
.kimi/skills/
  my-skill/
    SKILL.md
    scripts/
      my_script.py
```

## Skill Configuration

Configure in `.kimi-config.yml`:

```yaml
skill_overrides:
  code-review: my-custom-review
```
