#!/usr/bin/env python3
"""Simple linter script for code review.

Usage: python linter.py --lang python --code "code_snippet"
       python linter.py --file path/to/file.py
"""

import argparse
import re
import sys
from typing import List, Dict


def lint_python(code: str) -> List[Dict]:
    """Basic Python linting rules."""
    issues = []
    lines = code.split('\n')

    for i, line in enumerate(lines, 1):
        # Check line length
        if len(line) > 120:
            issues.append({
                "line": i,
                "severity": "low",
                "message": f"Line too long ({len(line)} > 120 characters)"
            })

        # Check for print statements (debug code)
        if re.search(r'\bprint\s*\(', line) and 'logger' not in line.lower():
            issues.append({
                "line": i,
                "severity": "low",
                "message": "Consider using logging instead of print()"
            })

        # Check for bare except
        if re.search(r'except\s*:', line):
            issues.append({
                "line": i,
                "severity": "medium",
                "message": "Bare except clause - specify exception type"
            })

        # Check for TODO/FIXME
        if re.search(r'#\s*(TODO|FIXME|XXX|HACK)', line, re.IGNORECASE):
            issues.append({
                "line": i,
                "severity": "low",
                "message": "Unresolved TODO/FIXME comment"
            })

        # Check for hardcoded credentials
        if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', line, re.IGNORECASE):
            issues.append({
                "line": i,
                "severity": "critical",
                "message": "Possible hardcoded credential"
            })

    return issues


def lint_javascript(code: str) -> List[Dict]:
    """Basic JavaScript linting rules."""
    issues = []
    lines = code.split('\n')

    for i, line in enumerate(lines, 1):
        # Check for var usage
        if re.search(r'\bvar\s+', line):
            issues.append({
                "line": i,
                "severity": "low",
                "message": "Use 'const' or 'let' instead of 'var'"
            })

        # Check for == instead of ===
        if re.search(r'[^=!]==[^=]', line):
            issues.append({
                "line": i,
                "severity": "medium",
                "message": "Use '===' instead of '==' for strict equality"
            })

        # Check for console.log
        if re.search(r'console\.(log|debug|info)', line):
            issues.append({
                "line": i,
                "severity": "low",
                "message": "Remove console.log before production"
            })

        # Check for alert
        if re.search(r'\balert\s*\(', line):
            issues.append({
                "line": i,
                "severity": "low",
                "message": "Remove alert() - use proper UI feedback"
            })

    return issues


def lint_code(code: str, lang: str) -> List[Dict]:
    """Run linting based on language."""
    linters = {
        "python": lint_python,
        "py": lint_python,
        "javascript": lint_javascript,
        "js": lint_javascript,
        "typescript": lint_javascript,
        "ts": lint_javascript,
    }

    linter = linters.get(lang.lower())
    if linter:
        return linter(code)
    return []


def format_output(issues: List[Dict]) -> str:
    """Format issues as readable output."""
    if not issues:
        return "No issues found."

    output = []
    for issue in sorted(issues, key=lambda x: (x["severity"], x["line"])):
        output.append(f"[{issue['severity'].upper()}] Line {issue['line']}: {issue['message']}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Simple code linter")
    parser.add_argument("--lang", default="python", help="Programming language")
    parser.add_argument("--code", help="Code snippet to lint")
    parser.add_argument("--file", help="File path to lint")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r') as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        code = sys.stdin.read()

    issues = lint_code(code, args.lang)

    if args.json:
        import json
        print(json.dumps(issues, indent=2))
    else:
        print(format_output(issues))

    # Exit with error code if critical issues found
    if any(i["severity"] == "critical" for i in issues):
        sys.exit(1)


if __name__ == "__main__":
    main()
