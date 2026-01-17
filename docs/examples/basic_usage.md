# Basic Usage Examples

## Review Command

```yaml
- name: Code Review
  uses: xiaoju111a/kimi-actions@v1
  with:
    kimi_api_key: ${{ secrets.KIMI_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Describe Command

Use `/describe` in PR comments to auto-generate PR description.

## Improve Command

Use `/improve` to get code improvement suggestions.
