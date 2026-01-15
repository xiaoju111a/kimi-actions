#!/usr/bin/env python3
"""Scan codebase for keywords extracted from issue.

This script extracts keywords from issue title/body and searches
the codebase for relevant files and code snippets.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict


# File patterns to search
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.vue', '.svelte'
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '.git', '.venv', 'venv', '__pycache__',
    'dist', 'build', '.next', 'target', 'vendor', '.cache'
}

# Common words to ignore when extracting keywords
STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'must', 'shall',
    'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
    'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'between',
    'under', 'again', 'further', 'then', 'once', 'here', 'there',
    'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
    'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and',
    'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that',
    'these', 'those', 'am', 'what', 'which', 'who', 'whom',
    # Issue-specific stop words
    'issue', 'bug', 'error', 'problem', 'feature', 'request',
    'please', 'help', 'thanks', 'thank', 'work', 'working',
    'expected', 'actual', 'behavior', 'steps', 'reproduce',
    'version', 'environment', 'description', 'fix', 'fixed'
}


def extract_keywords(title: str, body: str) -> List[str]:
    """Extract meaningful keywords from issue title and body."""
    text = f"{title} {body}".lower()

    # Extract potential identifiers (camelCase, snake_case, etc.)
    identifiers = re.findall(r'\b[a-z]+(?:[A-Z][a-z]+)+\b', f"{title} {body}")  # camelCase
    identifiers += re.findall(r'\b[a-z]+(?:_[a-z]+)+\b', text)  # snake_case
    identifiers += re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', f"{title} {body}")  # PascalCase

    # Extract words (alphanumeric, at least 3 chars)
    words = re.findall(r'\b[a-z][a-z0-9]{2,}\b', text)

    # Extract file paths or extensions mentioned
    files = re.findall(r'\b[\w/]+\.(?:py|js|ts|tsx|jsx|go|rs|java|rb)\b', text)

    # Extract quoted strings (likely specific terms)
    quoted = re.findall(r'["\']([^"\']+)["\']', text)

    # Combine and filter
    all_keywords = set()

    # Add identifiers (high priority)
    for ident in identifiers:
        all_keywords.add(ident.lower())

    # Add files
    for f in files:
        all_keywords.add(f)
        # Also add filename without extension
        base = Path(f).stem
        if len(base) >= 3:
            all_keywords.add(base.lower())

    # Add quoted terms
    for q in quoted:
        if len(q) >= 3 and q.lower() not in STOP_WORDS:
            all_keywords.add(q.lower())

    # Add filtered words
    for word in words:
        if word not in STOP_WORDS and len(word) >= 3:
            all_keywords.add(word)

    # Prioritize: identifiers > files > other words
    # Return top 10 most relevant keywords
    keywords = list(all_keywords)

    # Sort by specificity (longer = more specific)
    keywords.sort(key=lambda x: (-len(x) if '_' in x or any(c.isupper() for c in x) else 0, -len(x)))

    return keywords[:10]


def search_files(keywords: List[str], root_dir: str, max_results: int = 5) -> Dict[str, List[Dict]]:
    """Search for files containing keywords."""
    results = {}
    root = Path(root_dir)

    for keyword in keywords:
        matches = []

        # Search using grep if available (faster)
        try:
            cmd = ['grep', '-r', '-l', '-i', '--include=*.py', '--include=*.js',
                   '--include=*.ts', '--include=*.tsx', '--include=*.go',
                   keyword, str(root)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for filepath in result.stdout.strip().split('\n')[:max_results]:
                    if filepath and not any(skip in filepath for skip in SKIP_DIRS):
                        matches.append({
                            'file': filepath.replace(str(root) + '/', ''),
                            'keyword': keyword
                        })
        except Exception:
            # Fallback to Python search
            for path in root.rglob('*'):
                if path.is_file() and path.suffix in CODE_EXTENSIONS:
                    if any(skip in str(path) for skip in SKIP_DIRS):
                        continue
                    try:
                        content = path.read_text(errors='ignore')
                        if keyword.lower() in content.lower():
                            matches.append({
                                'file': str(path.relative_to(root)),
                                'keyword': keyword
                            })
                            if len(matches) >= max_results:
                                break
                    except Exception:
                        continue

        if matches:
            results[keyword] = matches

    return results


def get_code_snippet(filepath: str, keyword: str, context_lines: int = 3) -> str:
    """Get code snippet around keyword occurrence."""
    try:
        path = Path(filepath)
        if not path.exists():
            return ""

        lines = path.read_text(errors='ignore').split('\n')

        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                snippet_lines = lines[start:end]

                # Add line numbers
                numbered = []
                for j, sline in enumerate(snippet_lines):
                    line_num = start + j + 1
                    marker = '>' if j == i - start else ' '
                    numbered.append(f"{marker}{line_num:4d} | {sline}")

                return '\n'.join(numbered)

        return ""
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description='Scan codebase for issue keywords')
    parser.add_argument('--title', type=str, default='', help='Issue title')
    parser.add_argument('--body', type=str, default='', help='Issue body')
    parser.add_argument('--repo_path', type=str, default='.', help='Repository path')
    parser.add_argument('--max_files', type=int, default=5, help='Max files per keyword')
    parser.add_argument('--max_snippets', type=int, default=3, help='Max code snippets to show')

    args = parser.parse_args()

    # Extract keywords
    keywords = extract_keywords(args.title, args.body)

    if not keywords:
        print(json.dumps({
            'keywords': [],
            'files': {},
            'snippets': [],
            'summary': 'No relevant keywords found in issue.'
        }))
        return

    # Search for files
    file_results = search_files(keywords, args.repo_path, args.max_files)

    # Get code snippets for top matches
    snippets = []
    seen_files = set()

    for keyword, matches in file_results.items():
        for match in matches:
            filepath = os.path.join(args.repo_path, match['file'])
            if filepath not in seen_files and len(snippets) < args.max_snippets:
                snippet = get_code_snippet(filepath, keyword)
                if snippet:
                    snippets.append({
                        'file': match['file'],
                        'keyword': keyword,
                        'code': snippet
                    })
                    seen_files.add(filepath)

    # Build summary
    total_files = sum(len(m) for m in file_results.values())
    summary_parts = []

    if total_files > 0:
        summary_parts.append(f"Found {total_files} relevant files for {len(file_results)} keywords.")
        top_files = []
        for kw, matches in list(file_results.items())[:3]:
            for m in matches[:2]:
                top_files.append(m['file'])
        if top_files:
            summary_parts.append(f"Key files: {', '.join(set(top_files)[:5])}")
    else:
        summary_parts.append("No matching files found in codebase.")

    # Output JSON result
    output = {
        'keywords': keywords,
        'files': file_results,
        'snippets': snippets,
        'summary': ' '.join(summary_parts)
    }

    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
