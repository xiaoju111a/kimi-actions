# P3 (Low Priority) Issues Checklist

This document provides a comprehensive checklist for P3 issues that can be flagged during code review.

## When to Check P3 Issues

- Only check P3 issues if there are few or no P0-P2 issues
- Focus on issues that are trivial to fix (1-line changes)
- Prioritize issues that genuinely improve code quality

## Typos and Documentation

### Spelling Errors
- [ ] Typos in comments
- [ ] Typos in docstrings
- [ ] Typos in error messages
- [ ] Typos in log messages
- [ ] Typos in variable names
- [ ] Typos in function names
- [ ] Typos in class names

**Common typos to watch for:**
- recieve → receive
- occured → occurred
- seperate → separate
- definately → definitely
- enviroment → environment
- dependancy → dependency
- succesful → successful
- necesary → necessary
- relevent → relevant
- buisness → business

**Handling multiple instances:**
If the same typo appears multiple times in one file, create ONE suggestion:
```
"Typo 'enviroment' appears 5 times, should be 'environment'"
```

### Documentation Issues
- [ ] Outdated comments that don't match code
- [ ] Missing docstrings for public functions
- [ ] Incorrect docstrings (wrong return type, parameters)
- [ ] Broken links in documentation
- [ ] HTTP links that should be HTTPS
- [ ] TODO/FIXME comments (if configured to flag)

## Code Formatting

### Indentation
- [ ] Mixed tabs and spaces
- [ ] Incorrect indentation level
- [ ] Inconsistent indentation within same file
- [ ] Python: Indentation errors that cause syntax errors

### Whitespace
- [ ] Trailing whitespace at end of lines
- [ ] Missing newline at end of file
- [ ] Excessive blank lines (>2 consecutive)
- [ ] Inconsistent spacing around operators

## Unused Code

### Imports
- [ ] Unused import statements
- [ ] Duplicate imports
- [ ] Imports that can be combined

**Example:**
```python
import os
import sys  # ← Not used
from typing import List, Dict, Optional  # ← Optional not used
```

### Variables
- [ ] Variables declared but never used
- [ ] Function parameters that are never used
- [ ] Class attributes that are never accessed

**Example:**
```python
def process(data, format):  # format is never used
    result = []  # result is never used
    return data.upper()
```

### Dead Code
- [ ] Commented-out code blocks
- [ ] Unreachable code after return/break
- [ ] Functions that are never called

## Debug Code

### Print Statements
- [ ] `print()` statements in Python
- [ ] `console.log()` in JavaScript
- [ ] `fmt.Println()` in Go
- [ ] `System.out.println()` in Java

**Should be replaced with proper logging:**
```python
# ❌ Bad
print(f"Debug: {value}")

# ✅ Good
logger.debug(f"Processing value: {value}")
```

### Debug Flags
- [ ] Hardcoded debug flags set to True
- [ ] Development-only code paths
- [ ] Test data in production code

## Naming Issues

### Inconsistent Naming Style
- [ ] Mixing snake_case and camelCase in same language
- [ ] Inconsistent capitalization
- [ ] Abbreviations used inconsistently

**Python example:**
```python
# ❌ Bad: Inconsistent
user_name = "John"
getUserAge = lambda: 25

# ✅ Good: Consistent snake_case
user_name = "John"
get_user_age = lambda: 25
```

**JavaScript example:**
```javascript
// ❌ Bad: Inconsistent
const user_name = "John";
const getUserAge = () => 25;

// ✅ Good: Consistent camelCase
const userName = "John";
const getUserAge = () => 25;
```

### Misspelled Identifiers
- [ ] Function names with typos
- [ ] Variable names with typos
- [ ] Class names with typos

**Example:**
```python
def calcualte_total():  # ← Typo: calcualte
    pass
```

## Code Duplication

### Repeated Logic
- [ ] Same code block repeated 2+ times
- [ ] Similar functions with minor variations
- [ ] Copy-pasted code with small changes

**Example:**
```python
# ❌ Bad: Duplicated
if user.is_admin:
    log.info(f"Admin {user.name} logged in")
    send_notification(user)

if user.is_moderator:
    log.info(f"Moderator {user.name} logged in")
    send_notification(user)

# ✅ Good: Extracted
def handle_login(user, role):
    log.info(f"{role} {user.name} logged in")
    send_notification(user)
```

## Language-Specific Issues

### Python
- [ ] Using `==` to compare with `None` instead of `is`
- [ ] Using `!=` to compare with `None` instead of `is not`
- [ ] Bare `except:` clauses
- [ ] Mutable default arguments

**Examples:**
```python
# ❌ Bad
if value == None:
    pass

# ✅ Good
if value is None:
    pass

# ❌ Bad
def foo(items=[]):
    items.append(1)

# ✅ Good
def foo(items=None):
    items = items or []
```

### JavaScript/TypeScript
- [ ] Using `==` instead of `===`
- [ ] Using `!=` instead of `!==`
- [ ] Missing `await` on async functions
- [ ] Unhandled promise rejections

**Examples:**
```javascript
// ❌ Bad
if (value == null) { }

// ✅ Good
if (value === null || value === undefined) { }

// ❌ Bad
async function foo() {
    fetchData(); // Missing await
}

// ✅ Good
async function foo() {
    await fetchData();
}
```

### Go
- [ ] Ignoring error return values with `_`
- [ ] Not checking errors before using values
- [ ] Unused function parameters

**Examples:**
```go
// ❌ Bad
data, _ := readFile()

// ✅ Good
data, err := readFile()
if err != nil {
    return fmt.Errorf("read failed: %w", err)
}
```

### Java
- [ ] Empty catch blocks
- [ ] Using `==` to compare strings
- [ ] Not closing resources

**Examples:**
```java
// ❌ Bad
try {
    riskyOperation();
} catch (Exception e) {
    // Empty catch
}

// ✅ Good
try {
    riskyOperation();
} catch (Exception e) {
    logger.error("Operation failed", e);
    throw e;
}
```

## Git and Repository Issues

### Version Control
- [ ] Large binary files committed
- [ ] Log files committed
- [ ] Temporary files committed
- [ ] IDE-specific files not in .gitignore

### Dependencies
- [ ] Outdated dependencies with known vulnerabilities
- [ ] Unnecessary version pinning
- [ ] Missing version constraints

## Priority Guidelines

**Always flag (even if many P0-P2 issues):**
- Typos in user-facing error messages
- Python indentation errors
- Debug print statements in production code

**Flag if few higher priority issues:**
- Typos in comments
- Unused imports
- Trailing whitespace
- Inconsistent naming

**Only flag if no higher priority issues:**
- Missing newline at end of file
- Excessive blank lines
- Minor code duplication

## Output Format

For P3 issues, always use:
- `severity: "low"`
- `label: "documentation"` (for most P3 issues)
- `label: "bug"` (only if it affects correctness, like Python indentation)

Keep `suggestion_content` brief for P3 issues - no need for lengthy explanations.
