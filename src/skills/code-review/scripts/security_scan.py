#!/usr/bin/env python3
"""Security vulnerability scanner using Semgrep.

This script runs Semgrep with security-focused rules on the provided code
and returns findings in a structured format for LLM analysis.

Usage:
    python security_scan.py --lang python --code "code content"
    python security_scan.py --lang python --file path/to/file.py
    python security_scan.py --dir /path/to/repo
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Optional


# Semgrep rule sets for different languages
SECURITY_RULESETS = {
    "python": ["p/python", "p/security-audit", "p/owasp-top-ten"],
    "javascript": ["p/javascript", "p/security-audit", "p/owasp-top-ten"],
    "typescript": ["p/typescript", "p/security-audit", "p/owasp-top-ten"],
    "go": ["p/golang", "p/security-audit"],
    "java": ["p/java", "p/security-audit", "p/owasp-top-ten"],
    "default": ["p/security-audit", "p/owasp-top-ten"],
}

# Severity mapping
SEVERITY_MAP = {
    "ERROR": "critical",
    "WARNING": "high",
    "INFO": "medium",
}


def check_semgrep_installed() -> bool:
    """Check if semgrep is installed."""
    try:
        subprocess.run(
            ["semgrep", "--version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_semgrep(
    target: str,
    lang: str = "default",
    timeout: int = 60
) -> Optional[Dict]:
    """Run semgrep on target and return results."""
    rulesets = SECURITY_RULESETS.get(lang, SECURITY_RULESETS["default"])
    
    cmd = [
        "semgrep",
        "--json",
        "--quiet",
        "--timeout", str(timeout),
    ]
    
    # Add rulesets
    for ruleset in rulesets:
        cmd.extend(["--config", ruleset])
    
    cmd.append(target)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10
        )
        
        if result.stdout:
            return json.loads(result.stdout)
        return None
        
    except subprocess.TimeoutExpired:
        return {"error": "Semgrep scan timed out"}
    except json.JSONDecodeError:
        return {"error": "Failed to parse semgrep output"}
    except Exception as e:
        return {"error": str(e)}


def format_findings(semgrep_output: Dict) -> str:
    """Format semgrep findings for LLM consumption."""
    if not semgrep_output:
        return "No security issues found."
    
    if "error" in semgrep_output:
        return f"Security scan error: {semgrep_output['error']}"
    
    results = semgrep_output.get("results", [])
    if not results:
        return "✅ No security vulnerabilities detected."
    
    findings: List[str] = []
    findings.append(f"⚠️ Found {len(results)} potential security issue(s):\n")
    
    for i, result in enumerate(results[:10], 1):  # Limit to 10 findings
        check_id = result.get("check_id", "unknown")
        message = result.get("extra", {}).get("message", "No description")
        severity = SEVERITY_MAP.get(
            result.get("extra", {}).get("severity", "INFO"),
            "medium"
        )
        path = result.get("path", "unknown")
        line = result.get("start", {}).get("line", 0)
        code = result.get("extra", {}).get("lines", "")
        
        finding = f"""### {i}. {check_id}
- **Severity**: {severity}
- **File**: `{path}:{line}`
- **Issue**: {message}
"""
        if code:
            finding += f"- **Code**: `{code.strip()[:100]}`\n"
        
        findings.append(finding)
    
    if len(results) > 10:
        findings.append(f"\n... and {len(results) - 10} more issues.")
    
    return "\n".join(findings)


def scan_code_string(code: str, lang: str) -> str:
    """Scan a code string by writing to temp file."""
    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "go": ".go",
        "java": ".java",
    }
    ext = ext_map.get(lang, ".txt")
    
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=ext,
        delete=False
    ) as f:
        f.write(code)
        temp_path = f.name
    
    try:
        result = run_semgrep(temp_path, lang)
        return format_findings(result)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Security vulnerability scanner")
    parser.add_argument("--lang", default="python", help="Programming language")
    parser.add_argument("--code", help="Code string to scan")
    parser.add_argument("--file", help="File path to scan")
    parser.add_argument("--dir", help="Directory to scan")
    
    args = parser.parse_args()
    
    # Check if semgrep is installed
    if not check_semgrep_installed():
        print("Semgrep not installed. Skipping security scan.")
        print("Install with: pip install semgrep")
        return
    
    if args.code:
        result = scan_code_string(args.code, args.lang)
    elif args.file:
        semgrep_result = run_semgrep(args.file, args.lang)
        result = format_findings(semgrep_result)
    elif args.dir:
        semgrep_result = run_semgrep(args.dir, args.lang)
        result = format_findings(semgrep_result)
    else:
        print("Please provide --code, --file, or --dir")
        sys.exit(1)
    
    print(result)


if __name__ == "__main__":
    main()
