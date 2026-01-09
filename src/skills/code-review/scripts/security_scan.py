#!/usr/bin/env python3
"""Security scanner script for code review.

Usage: python security_scan.py --lang python --code "code_snippet"
"""

import argparse
import re
import sys
from typing import List, Dict


SECURITY_PATTERNS = {
    "sql_injection": {
        "pattern": r'(execute|query|cursor\.execute)\s*\(\s*["\'].*%s|{.*}|\+.*\+',
        "message": "Potential SQL injection - use parameterized queries",
        "severity": "critical",
        "languages": ["python", "javascript", "java"]
    },
    "command_injection": {
        "pattern": r'(os\.system|subprocess\.call|exec|eval)\s*\([^)]*\+|{|%',
        "message": "Potential command injection - sanitize input",
        "severity": "critical",
        "languages": ["python"]
    },
    "xss": {
        "pattern": r'innerHTML\s*=|document\.write\s*\(|\.html\s*\([^)]*\+',
        "message": "Potential XSS vulnerability - sanitize output",
        "severity": "high",
        "languages": ["javascript", "typescript"]
    },
    "hardcoded_secret": {
        "pattern": r'(password|secret|api_key|apikey|token|private_key)\s*=\s*["\'][a-zA-Z0-9]{8,}["\']',
        "message": "Hardcoded secret detected - use environment variables",
        "severity": "critical",
        "languages": ["python", "javascript", "typescript", "java", "go"]
    },
    "weak_crypto": {
        "pattern": r'(md5|sha1)\s*\(|DES|RC4',
        "message": "Weak cryptographic algorithm - use SHA-256 or stronger",
        "severity": "high",
        "languages": ["python", "javascript", "java"]
    },
    "path_traversal": {
        "pattern": r'open\s*\([^)]*\+|os\.path\.join\s*\([^)]*request|file_get_contents\s*\(\s*\$',
        "message": "Potential path traversal - validate file paths",
        "severity": "high",
        "languages": ["python", "php"]
    },
    "insecure_random": {
        "pattern": r'random\.(random|randint|choice)\s*\(|Math\.random\s*\(',
        "message": "Insecure random for security context - use secrets module",
        "severity": "medium",
        "languages": ["python", "javascript"]
    },
    "debug_enabled": {
        "pattern": r'DEBUG\s*=\s*True|debug\s*:\s*true',
        "message": "Debug mode enabled - disable in production",
        "severity": "medium",
        "languages": ["python", "javascript"]
    },
    "cors_wildcard": {
        "pattern": r'Access-Control-Allow-Origin.*\*|cors\s*\(\s*\)',
        "message": "CORS wildcard - restrict allowed origins",
        "severity": "medium",
        "languages": ["python", "javascript"]
    },
    "unsafe_deserialization": {
        "pattern": r'pickle\.loads|yaml\.load\s*\([^)]*Loader|unserialize\s*\(',
        "message": "Unsafe deserialization - use safe loaders",
        "severity": "critical",
        "languages": ["python", "php"]
    }
}


def scan_code(code: str, lang: str) -> List[Dict]:
    """Scan code for security issues."""
    issues = []
    lines = code.split('\n')
    
    for name, rule in SECURITY_PATTERNS.items():
        if lang.lower() not in rule["languages"]:
            continue
        
        pattern = re.compile(rule["pattern"], re.IGNORECASE)
        
        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                issues.append({
                    "line": i,
                    "rule": name,
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "code": line.strip()[:80]
                })
    
    return issues


def format_output(issues: List[Dict]) -> str:
    """Format issues as readable output."""
    if not issues:
        return "No security issues found."
    
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_issues = sorted(issues, key=lambda x: (severity_order.get(x["severity"], 4), x["line"]))
    
    output = [f"Found {len(issues)} security issue(s):\n"]
    
    for issue in sorted_issues:
        output.append(f"[{issue['severity'].upper()}] Line {issue['line']}: {issue['rule']}")
        output.append(f"  {issue['message']}")
        output.append(f"  Code: {issue['code']}")
        output.append("")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Security scanner")
    parser.add_argument("--lang", default="python", help="Programming language")
    parser.add_argument("--code", help="Code snippet to scan")
    parser.add_argument("--file", help="File path to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file, 'r') as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        code = sys.stdin.read()
    
    issues = scan_code(code, args.lang)
    
    if args.json:
        import json
        print(json.dumps(issues, indent=2))
    else:
        print(format_output(issues))
    
    # Exit with error code if critical issues found
    critical_count = sum(1 for i in issues if i["severity"] == "critical")
    if critical_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
