# Event Handling

## Pull Request Events

### pull_request
Triggered on PR open, synchronize, reopened.

### pull_request_review_comment
Triggered on inline PR comments.

### issue_comment
Triggered on PR comments.

## Issue Events

### issues
Triggered on issue open, edited.

### issue_comment
Triggered on issue comments.

## Event Handlers

- `handle_pr_event()`: Process PR events
- `handle_comment_event()`: Process comment events
- `handle_review_comment_event()`: Process inline comments
- `handle_issue_event()`: Process issue events
