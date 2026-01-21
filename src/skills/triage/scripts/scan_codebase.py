#!/usr/bin/env python3
"""Scan codebase for keywords extracted from issue.

This script extracts keywords from issue title/body and searches
the codebase for relevant files and code snippets.

Enhanced to better identify:
- Class names (PascalCase)
- Function/method names (snake_case, camelCase)
- File names mentioned in issue
- Code identifiers in backticks
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict


# File patterns to search
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".vue",
    ".svelte",
    ".md",
    ".yml",
    ".yaml",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "target",
    "vendor",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".tox",
    "egg-info",
}

# Common words to ignore when extracting keywords
STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "and",
    "but",
    "if",
    "or",
    "because",
    "until",
    "while",
    "this",
    "that",
    "these",
    "those",
    "am",
    "what",
    "which",
    "who",
    "whom",
    # Issue-specific stop words
    "issue",
    "bug",
    "error",
    "problem",
    "feature",
    "request",
    "please",
    "help",
    "thanks",
    "thank",
    "work",
    "working",
    "expected",
    "actual",
    "behavior",
    "steps",
    "reproduce",
    "version",
    "environment",
    "description",
    "fix",
    "fixed",
    "using",
    "use",
    "used",
    "want",
    "like",
    "get",
    "set",
    "new",
    "add",
    "added",
    "remove",
    "removed",
    "change",
    "changed",
}

# High-priority code patterns (class names, function names, etc.)
CODE_PATTERNS = {
    "class": r"\bclass\s+(\w+)",
    "function": r"\bdef\s+(\w+)",
    "method": r"\.(\w+)\s*\(",
    "variable": r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b",  # PascalCase
}


def extract_keywords(title: str, body: str) -> List[Tuple[str, int]]:
    """Extract meaningful keywords from issue title and body.

    Returns list of (keyword, priority) tuples.
    Priority: 3=highest (code in backticks), 2=identifiers, 1=normal words
    """
    text = f"{title} {body}"
    text_lower = text.lower()

    keywords_with_priority = {}

    # 1. HIGHEST PRIORITY: Code in backticks (e.g., `kimi_client`, `BaseTool`)
    backtick_code = re.findall(r"`([^`]+)`", text)
    for code in backtick_code:
        code = code.strip()
        if len(code) >= 2 and code.lower() not in STOP_WORDS:
            # Could be a file path, class name, function name, etc.
            keywords_with_priority[code] = 3
            # Also extract parts if it's a path
            if "/" in code or "." in code:
                parts = re.split(r"[/.]", code)
                for part in parts:
                    if len(part) >= 3 and part.lower() not in STOP_WORDS:
                        keywords_with_priority[part] = 3

    # 2. HIGH PRIORITY: PascalCase identifiers (class names)
    pascal_case = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text)
    for ident in pascal_case:
        if ident not in keywords_with_priority:
            keywords_with_priority[ident] = 2

    # 3. HIGH PRIORITY: snake_case identifiers (function/variable names)
    snake_case = re.findall(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", text_lower)
    for ident in snake_case:
        if ident not in keywords_with_priority and ident not in STOP_WORDS:
            keywords_with_priority[ident] = 2

    # 4. HIGH PRIORITY: camelCase identifiers
    camel_case = re.findall(r"\b([a-z]+(?:[A-Z][a-z]+)+)\b", text)
    for ident in camel_case:
        if ident.lower() not in keywords_with_priority:
            keywords_with_priority[ident.lower()] = 2

    # 5. MEDIUM PRIORITY: File paths or extensions mentioned
    files = re.findall(
        r"\b([\w/]+\.(?:py|js|ts|tsx|jsx|go|rs|java|rb|yml|yaml|json|md))\b", text_lower
    )
    for f in files:
        if f not in keywords_with_priority:
            keywords_with_priority[f] = 2
        # Also add filename without extension
        base = Path(f).stem
        if len(base) >= 3 and base not in keywords_with_priority:
            keywords_with_priority[base] = 2

    # 6. MEDIUM PRIORITY: Quoted strings (likely specific terms)
    quoted = re.findall(r'["\']([^"\']+)["\']', text)
    for q in quoted:
        q = q.strip()
        if len(q) >= 3 and q.lower() not in STOP_WORDS:
            if q not in keywords_with_priority:
                keywords_with_priority[q] = 2

    # 7. LOWER PRIORITY: Regular words (but still useful)
    words = re.findall(r"\b([a-z][a-z0-9]{2,})\b", text_lower)
    for word in words:
        if word not in STOP_WORDS and word not in keywords_with_priority:
            # Only add if it looks like a code term (not common English)
            if "_" in word or len(word) >= 5:
                keywords_with_priority[word] = 1

    # Sort by priority (descending) then by length (longer = more specific)
    sorted_keywords = sorted(
        keywords_with_priority.items(), key=lambda x: (-x[1], -len(x[0]))
    )

    return sorted_keywords[:15]  # Return top 15 keywords with priorities


def search_files(
    keywords: List[Tuple[str, int]], root_dir: str, max_results: int = 5
) -> Dict[str, List[Dict]]:
    """Search for files containing keywords.

    Args:
        keywords: List of (keyword, priority) tuples
        root_dir: Root directory to search
        max_results: Max files per keyword

    Returns:
        Dict mapping keyword to list of file matches
    """
    results = {}
    root = Path(root_dir)
    all_matched_files = set()  # Track all matched files for deduplication

    for keyword, priority in keywords:
        matches = []

        # First, check if keyword matches a filename directly
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in CODE_EXTENSIONS:
                if any(skip in str(path) for skip in SKIP_DIRS):
                    continue

                # Check if keyword is in filename (without extension)
                filename = path.stem.lower()
                if keyword.lower() in filename or filename in keyword.lower():
                    rel_path = str(path.relative_to(root))
                    if rel_path not in all_matched_files:
                        matches.append(
                            {
                                "file": rel_path,
                                "keyword": keyword,
                                "priority": priority
                                + 1,  # Boost priority for filename match
                            }
                        )
                        all_matched_files.add(rel_path)

        # Then use grep for content search
        try:
            # Build grep command with multiple file types
            cmd = [
                "grep",
                "-r",
                "-l",
                "-i",
                "--include=*.py",
                "--include=*.js",
                "--include=*.ts",
                "--include=*.tsx",
                "--include=*.go",
                "--include=*.java",
                "--include=*.yml",
                "--include=*.yaml",
                "--include=*.md",
                keyword,
                str(root),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for filepath in result.stdout.strip().split("\n"):
                    if not filepath:
                        continue
                    # Skip excluded directories
                    if any(skip in filepath for skip in SKIP_DIRS):
                        continue

                    rel_path = filepath.replace(str(root) + "/", "")

                    # Prioritize files not yet matched
                    if rel_path not in all_matched_files:
                        matches.append(
                            {"file": rel_path, "keyword": keyword, "priority": priority}
                        )
                        all_matched_files.add(rel_path)

                    if len(matches) >= max_results:
                        break

        except subprocess.TimeoutExpired:
            pass
        except Exception:
            # Fallback to Python search
            for path in root.rglob("*"):
                if path.is_file() and path.suffix in CODE_EXTENSIONS:
                    if any(skip in str(path) for skip in SKIP_DIRS):
                        continue
                    try:
                        content = path.read_text(errors="ignore")
                        if keyword.lower() in content.lower():
                            rel_path = str(path.relative_to(root))
                            if rel_path not in all_matched_files:
                                matches.append(
                                    {
                                        "file": rel_path,
                                        "keyword": keyword,
                                        "priority": priority,
                                    }
                                )
                                all_matched_files.add(rel_path)
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

        lines = path.read_text(errors="ignore").split("\n")

        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                snippet_lines = lines[start:end]

                # Add line numbers
                numbered = []
                for j, sline in enumerate(snippet_lines):
                    line_num = start + j + 1
                    marker = ">" if j == i - start else " "
                    numbered.append(f"{marker}{line_num:4d} | {sline}")

                return "\n".join(numbered)

        return ""
    except Exception:
        return ""


def aggregate_files(
    file_results: Dict[str, List[Dict]], max_files: int = 10
) -> List[Dict]:
    """Aggregate and rank files from all keyword matches.

    Returns a deduplicated list of files ranked by:
    1. Number of keyword matches
    2. Highest priority keyword matched
    3. File path relevance (src/ > tests/)
    """
    file_scores = defaultdict(lambda: {"keywords": [], "max_priority": 0, "score": 0})

    for keyword, matches in file_results.items():
        for match in matches:
            filepath = match["file"]
            priority = match.get("priority", 1)

            file_scores[filepath]["keywords"].append(keyword)
            file_scores[filepath]["max_priority"] = max(
                file_scores[filepath]["max_priority"], priority
            )

    # Calculate final score
    for filepath, data in file_scores.items():
        # Base score from keyword matches
        score = len(data["keywords"]) * 10

        # Bonus for high-priority keywords
        score += data["max_priority"] * 5

        # Bonus for source files (not tests)
        if "src/" in filepath or "lib/" in filepath:
            score += 3
        elif "test" in filepath.lower():
            score -= 2

        # Bonus for Python files (project is Python)
        if filepath.endswith(".py"):
            score += 2

        data["score"] = score

    # Sort by score and return top files
    sorted_files = sorted(file_scores.items(), key=lambda x: -x[1]["score"])

    return [
        {"file": filepath, "keywords": data["keywords"], "score": data["score"]}
        for filepath, data in sorted_files[:max_files]
    ]


def main():
    parser = argparse.ArgumentParser(description="Scan codebase for issue keywords")
    parser.add_argument("--title", type=str, default="", help="Issue title")
    parser.add_argument("--body", type=str, default="", help="Issue body")
    parser.add_argument("--repo_path", type=str, default=".", help="Repository path")
    parser.add_argument("--max_files", type=int, default=10, help="Max files to return")
    parser.add_argument(
        "--max_snippets", type=int, default=3, help="Max code snippets to show"
    )

    args = parser.parse_args()

    # Extract keywords with priorities
    keywords = extract_keywords(args.title, args.body)

    if not keywords:
        print(
            json.dumps(
                {
                    "keywords": [],
                    "files": {},
                    "ranked_files": [],
                    "snippets": [],
                    "summary": "No relevant keywords found in issue.",
                }
            )
        )
        return

    # Search for files
    file_results = search_files(keywords, args.repo_path, max_results=5)

    # Aggregate and rank files
    ranked_files = aggregate_files(file_results, max_files=args.max_files)

    # Get code snippets for top matches
    snippets = []
    seen_files = set()

    # Prioritize snippets from ranked files
    for ranked in ranked_files[: args.max_snippets]:
        filepath = os.path.join(args.repo_path, ranked["file"])
        if filepath not in seen_files:
            # Use the first keyword that matched this file
            keyword = ranked["keywords"][0] if ranked["keywords"] else ""
            if keyword:
                snippet = get_code_snippet(filepath, keyword)
                if snippet:
                    snippets.append(
                        {"file": ranked["file"], "keyword": keyword, "code": snippet}
                    )
                    seen_files.add(filepath)

    # Build summary
    total_files = len(ranked_files)
    keyword_list = [kw for kw, _ in keywords]

    summary_parts = []
    if total_files > 0:
        summary_parts.append(
            f"Found {total_files} relevant files matching {len(file_results)} keywords."
        )
        top_files = [f["file"] for f in ranked_files[:5]]
        if top_files:
            summary_parts.append(f"Key files: {', '.join(top_files)}")
    else:
        summary_parts.append("No matching files found in codebase.")

    # Output JSON result
    output = {
        "keywords": keyword_list,
        "files": file_results,
        "ranked_files": ranked_files,
        "snippets": snippets,
        "summary": " ".join(summary_parts),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
