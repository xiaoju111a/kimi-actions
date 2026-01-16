#!/usr/bin/env python3
"""Evaluate Kimi Actions PR Review quality using Nutanix Code Review dataset.

This evaluation script mirrors the actual kimi-actions reviewer.py processing:
1. Load SKILL.md for system prompt (same as reviewer.py)
2. Use TokenHandler for intelligent diff chunking
3. Use same prompt format and YAML parsing

Usage:
    KIMI_API_KEY=xxx python scripts/eval_nutanix.py --num 10
"""

import os
import sys
import csv
import json
import argparse
import logging
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kimi_client import KimiClient
from skill_loader import SkillManager
from token_handler import TokenHandler, DiffChunker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dataset paths
DATASET_DIR = Path(__file__).parent.parent.parent / "datasets" / "nutanix-codereview"
SUGGESTIONS_FILE = DATASET_DIR / "code_suggestions.csv"
PULL_REQUESTS_FILE = DATASET_DIR / "pull_requests.csv"


@dataclass
class NutanixSuggestion:
    """A suggestion from Nutanix dataset."""
    id: str
    content: str
    existing_code: str
    suggested_code: str
    suggestion_type: str
    pr_id: str


@dataclass
class PRContext:
    """Pull request context from Nutanix dataset."""
    id: str
    pr_url: str
    title: str
    diff: str
    files: List[str]


@dataclass
class EvalResult:
    """Evaluation result for a single PR."""
    pr_id: str
    pr_url: str
    nutanix_suggestions: List[NutanixSuggestion]
    kimi_suggestions: List[Dict]
    kimi_raw_response: str
    overlap_score: float
    processing_time: float
    error: Optional[str] = None


def load_suggestions_by_pr() -> Dict[str, List[NutanixSuggestion]]:
    """Load suggestions grouped by PR ID."""
    suggestions_by_pr = defaultdict(list)
    
    with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            suggestion = NutanixSuggestion(
                id=row.get('id', ''),
                content=row.get('content', ''),
                existing_code=row.get('existing_code_snippet', ''),
                suggested_code=row.get('suggested_code_snippet', ''),
                suggestion_type=row.get('type', ''),
                pr_id=row.get('pull_request_id', '')
            )
            if suggestion.pr_id:
                suggestions_by_pr[suggestion.pr_id].append(suggestion)
    
    return suggestions_by_pr


# Global variable to share suggestions with load_pr_contexts
suggestions_by_pr_global: Dict[str, List[NutanixSuggestion]] = {}


def load_pr_contexts(pr_ids: List[str], max_prs: int = 100) -> Dict[str, PRContext]:
    """Load PR contexts for given PR IDs."""
    csv.field_size_limit(sys.maxsize)
    
    pr_contexts = {}
    pr_ids_set = set(pr_ids)
    loaded_count = 0
    
    logger.info(f"Loading PR contexts for {len(pr_ids_set)} PRs...")
    
    with open(PULL_REQUESTS_FILE, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_id = row.get('id', '')
            if pr_id in pr_ids_set:
                try:
                    pr_context_json = row.get('pr_context', '{}')
                    # Clean control characters
                    pr_context_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', pr_context_json)
                    
                    try:
                        pr_context = json.loads(pr_context_json)
                    except json.JSONDecodeError:
                        try:
                            import ast
                            pr_context = ast.literal_eval(pr_context_json)
                        except:
                            pr_context = {}
                            title_match = re.search(r'"pr_title":\s*"([^"]*)"', pr_context_json)
                            if title_match:
                                pr_context['pr_title'] = title_match.group(1)
                    
                    # Extract diff from diff_files (more complete than git_files)
                    diff_parts = []
                    files = []
                    
                    for diff_file in pr_context.get('diff_files', []):
                        filename = diff_file.get('filename', '')
                        patch = diff_file.get('patch', '')
                        if filename:
                            files.append(filename)
                        if patch:
                            diff_parts.append(f"diff --git a/{filename} b/{filename}\n{patch}")
                    
                    # Fallback to git_files if no diff_files
                    if not diff_parts:
                        for git_file in pr_context.get('git_files', []):
                            filename = git_file.get('filename', '')
                            patch = git_file.get('patch', '')
                            if filename:
                                files.append(filename)
                            if patch:
                                diff_parts.append(f"diff --git a/{filename} b/{filename}\n{patch}")
                    
                    diff = "\n\n".join(diff_parts)
                    
                    if not diff:
                        continue
                    
                    pr_contexts[pr_id] = PRContext(
                        id=pr_id,
                        pr_url=row.get('pr_url', ''),
                        title=pr_context.get('pr_title', f'PR #{pr_id}'),
                        diff=diff,
                        files=files if files else ['unknown']
                    )
                    
                    loaded_count += 1
                    if loaded_count >= max_prs:
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to parse PR {pr_id}: {e}")
                    continue
    
    logger.info(f"Loaded {len(pr_contexts)} PR contexts")
    return pr_contexts


class KimiReviewer:
    """Mirrors the actual kimi-actions reviewer processing."""
    
    def __init__(self, api_key: str, review_level: str = "normal"):
        self.kimi = KimiClient(api_key)
        self.skill_manager = SkillManager()
        self.token_handler = TokenHandler()
        self.chunker = DiffChunker(self.token_handler)
        self.review_level = review_level
    
    def get_skill_instructions(self) -> str:
        """Get code-review skill instructions (same as reviewer.py)."""
        skill = self.skill_manager.get_skill("code-review")
        if skill:
            return skill.instructions
        return ""
    
    def build_system_prompt(self, diff: str) -> str:
        """Build system prompt from skill (mirrors reviewer._build_system_prompt)."""
        skill_instructions = self.get_skill_instructions()
        
        parts = [skill_instructions]
        
        # Review level (same as reviewer.py)
        level_text = {
            "strict": """Review Level: Strict - Perform thorough analysis including:
- Thread safety and race condition detection
- Stub/mock/simulation code detection
- Error handling completeness
- Cache key collision detection
- All items in the Strict Mode Checklist""",
            "normal": "Review Level: Normal - Focus on functional issues and common bugs",
            "gentle": "Review Level: Gentle - Only flag critical issues that would break functionality"
        }
        parts.append(f"\n## {level_text.get(self.review_level, level_text['normal'])}")
        
        return "\n".join(parts)
    
    def process_diff(self, raw_diff: str) -> Tuple[str, List, List]:
        """Process diff using TokenHandler and DiffChunker (same as reviewer.get_diff)."""
        included, excluded = self.chunker.chunk_diff(raw_diff, max_files=15)
        compressed = self.chunker.build_diff_string(included)
        return compressed, included, excluded
    
    def build_user_prompt(self, pr: PRContext, compressed_diff: str) -> str:
        """Build user prompt (same format as reviewer.py)."""
        return f"""## PR Information
Title: {pr.title}
Files: {', '.join(pr.files[:10])}

## Code Changes
```diff
{compressed_diff}
```

Please output review results in YAML format."""
    
    def parse_suggestions(self, response: str) -> List[Dict]:
        """Parse YAML response (same as reviewer._parse_suggestions)."""
        import yaml
        
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            
            data = yaml.safe_load(yaml_content)
            if data and 'suggestions' in data:
                return data['suggestions']
        except Exception as e:
            logger.warning(f"Failed to parse YAML: {e}")
        
        return []
    
    def review(self, pr: PRContext) -> Tuple[List[Dict], str]:
        """Run review on a PR (mirrors reviewer.run flow)."""
        # Process diff with chunking
        compressed_diff, included, excluded = self.process_diff(pr.diff)
        
        if not compressed_diff:
            return [], "No changes to review"
        
        # Build prompts
        system_prompt = self.build_system_prompt(compressed_diff)
        user_prompt = self.build_user_prompt(pr, compressed_diff)
        
        # Call Kimi
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.kimi.chat(messages)
        suggestions = self.parse_suggestions(response)
        
        return suggestions, response


def calculate_overlap(nutanix_suggestions: List[NutanixSuggestion], 
                      kimi_suggestions: List[Dict]) -> float:
    """Calculate overlap score between Nutanix and Kimi suggestions."""
    if not nutanix_suggestions or not kimi_suggestions:
        return 0.0
    
    # Extract key terms from Nutanix suggestions
    nutanix_terms = set()
    for s in nutanix_suggestions:
        words = s.content.lower().split()
        nutanix_terms.update(w for w in words if len(w) > 4)
        if s.existing_code:
            code_words = s.existing_code.replace('(', ' ').replace(')', ' ').split()
            nutanix_terms.update(w.lower() for w in code_words if len(w) > 3)
    
    # Check overlap with Kimi suggestions
    matches = 0
    for ks in kimi_suggestions:
        kimi_text = str(ks).lower()
        for term in nutanix_terms:
            if term in kimi_text:
                matches += 1
                break
    
    return matches / len(kimi_suggestions) if kimi_suggestions else 0.0


def evaluate_suggestion_quality(kimi_suggestions: List[Dict]) -> Dict:
    """Evaluate quality of Kimi suggestions."""
    if not kimi_suggestions:
        return {"avg_quality": 0, "has_code_fix": 0, "severity_dist": {}}
    
    quality_scores = []
    has_code_fix = 0
    severity_dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    
    for s in kimi_suggestions:
        score = 0
        
        # Has specific file reference (+1)
        if s.get("relevant_file") and s.get("relevant_file") != "unknown":
            score += 1
        
        # Has line numbers (+1)
        if s.get("relevant_lines_start") and s.get("relevant_lines_start") > 0:
            score += 1
        
        # Has clear summary (+1)
        summary = s.get("one_sentence_summary", "")
        if summary and len(summary) > 20:
            score += 1
        
        # Has detailed explanation (+1)
        content = s.get("suggestion_content", "")
        if content and len(content) > 50:
            score += 1
        
        # Has code fix (+1)
        if s.get("improved_code"):
            score += 1
            has_code_fix += 1
        
        quality_scores.append(score)
        
        # Count severity
        severity = s.get("severity", "medium").lower()
        if severity in severity_dist:
            severity_dist[severity] += 1
    
    return {
        "avg_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        "max_quality": 5,
        "has_code_fix_pct": has_code_fix / len(kimi_suggestions) * 100,
        "severity_dist": severity_dist
    }


def evaluate_pr(reviewer: KimiReviewer, pr: PRContext, 
                nutanix_suggestions: List[NutanixSuggestion]) -> EvalResult:
    """Evaluate Kimi's review on a single PR."""
    import time
    
    start_time = time.time()
    
    try:
        kimi_suggestions, response = reviewer.review(pr)
        overlap = calculate_overlap(nutanix_suggestions, kimi_suggestions)
        
        return EvalResult(
            pr_id=pr.id,
            pr_url=pr.pr_url,
            nutanix_suggestions=nutanix_suggestions,
            kimi_suggestions=kimi_suggestions,
            kimi_raw_response=response,
            overlap_score=overlap,
            processing_time=time.time() - start_time
        )
        
    except Exception as e:
        logger.error(f"Error evaluating PR {pr.id}: {e}")
        return EvalResult(
            pr_id=pr.id,
            pr_url=pr.pr_url,
            nutanix_suggestions=nutanix_suggestions,
            kimi_suggestions=[],
            kimi_raw_response="",
            overlap_score=0.0,
            processing_time=time.time() - start_time,
            error=str(e)
        )


def print_result(result: EvalResult, idx: int):
    """Print evaluation result for a single PR."""
    print(f"\n{'='*60}")
    print(f"[{idx}] PR #{result.pr_id}")
    print(f"    URL: {result.pr_url}")
    print(f"    Nutanix suggestions: {len(result.nutanix_suggestions)}")
    print(f"    Kimi suggestions: {len(result.kimi_suggestions)}")
    print(f"    Overlap score: {result.overlap_score:.2f}")
    print(f"    Time: {result.processing_time:.1f}s")
    
    if result.error:
        print(f"    ❌ Error: {result.error}")
    else:
        print(f"    ✅ Success")
    
    if result.nutanix_suggestions:
        print(f"\n    Nutanix sample:")
        for s in result.nutanix_suggestions[:2]:
            print(f"      - [{s.suggestion_type}] {s.content[:100]}...")
    
    if result.kimi_suggestions:
        print(f"\n    Kimi sample:")
        for s in result.kimi_suggestions[:2]:
            summary = s.get('one_sentence_summary', s.get('suggestion_content', ''))[:100]
            print(f"      - [{s.get('severity', 'unknown')}] {summary}...")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Kimi PR Review with Nutanix dataset")
    parser.add_argument("--num", type=int, default=10, help="Number of PRs to evaluate")
    parser.add_argument("--min-suggestions", type=int, default=2, 
                        help="Minimum Nutanix suggestions per PR")
    parser.add_argument("--review-level", type=str, default="normal",
                        choices=["strict", "normal", "gentle"],
                        help="Review level (strict/normal/gentle)")
    parser.add_argument("--output", type=str, help="Output JSON file")
    args = parser.parse_args()
    
    api_key = os.environ.get("KIMI_API_KEY")
    if not api_key:
        logger.error("KIMI_API_KEY environment variable not set")
        sys.exit(1)
    
    if not SUGGESTIONS_FILE.exists():
        logger.error(f"Dataset not found: {SUGGESTIONS_FILE}")
        sys.exit(1)
    
    print("=" * 60)
    print("Nutanix Code Review Dataset Evaluation")
    print(f"Using SKILL.md from kimi-actions (review_level={args.review_level})")
    print("=" * 60)
    
    # Load suggestions
    logger.info("Loading Nutanix suggestions...")
    suggestions_by_pr = load_suggestions_by_pr()
    logger.info(f"Loaded suggestions for {len(suggestions_by_pr)} PRs")
    
    global suggestions_by_pr_global
    suggestions_by_pr_global = suggestions_by_pr
    
    # Filter PRs with enough suggestions
    candidate_prs = [
        pr_id for pr_id, suggestions in suggestions_by_pr.items()
        if len(suggestions) >= args.min_suggestions
    ]
    logger.info(f"Found {len(candidate_prs)} PRs with >= {args.min_suggestions} suggestions")
    
    # Load PR contexts
    pr_contexts = load_pr_contexts(candidate_prs[:args.num * 3], max_prs=args.num * 3)
    
    # Filter to PRs we have context for
    eval_prs = [
        (pr_id, pr_contexts[pr_id], suggestions_by_pr[pr_id])
        for pr_id in candidate_prs
        if pr_id in pr_contexts
    ][:args.num]
    
    if not eval_prs:
        logger.error("No PRs found with both suggestions and context")
        sys.exit(1)
    
    print(f"\nEvaluating {len(eval_prs)} PRs...")
    
    # Initialize reviewer (mirrors kimi-actions)
    reviewer = KimiReviewer(api_key, review_level=args.review_level)
    
    # Run evaluation
    results = []
    for idx, (pr_id, pr_context, nutanix_suggestions) in enumerate(eval_prs, 1):
        logger.info(f"[{idx}/{len(eval_prs)}] Evaluating PR {pr_id}...")
        result = evaluate_pr(reviewer, pr_context, nutanix_suggestions)
        results.append(result)
        print_result(result, idx)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    successful = [r for r in results if not r.error]
    
    if successful:
        avg_overlap = sum(r.overlap_score for r in successful) / len(successful)
        avg_time = sum(r.processing_time for r in successful) / len(successful)
        total_nutanix = sum(len(r.nutanix_suggestions) for r in successful)
        total_kimi = sum(len(r.kimi_suggestions) for r in successful)
        
        # Collect all Kimi suggestions for quality analysis
        all_kimi_suggestions = []
        for r in successful:
            all_kimi_suggestions.extend(r.kimi_suggestions)
        
        quality = evaluate_suggestion_quality(all_kimi_suggestions)
        
        print(f"PRs evaluated: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(results) - len(successful)}")
        print(f"Average overlap score: {avg_overlap:.2f}")
        print(f"Average processing time: {avg_time:.1f}s")
        print(f"Total Nutanix suggestions: {total_nutanix}")
        print(f"Total Kimi suggestions: {total_kimi}")
        print(f"Kimi/Nutanix ratio: {total_kimi/total_nutanix:.2f}" if total_nutanix else "N/A")
        
        print(f"\n--- Suggestion Quality ---")
        print(f"Average quality score: {quality['avg_quality']:.1f}/{quality['max_quality']}")
        print(f"Has code fix: {quality['has_code_fix_pct']:.0f}%")
        print(f"Severity distribution: {quality['severity_dist']}")
    
    # Save results
    output_file = args.output or "eval/eval_nutanix_results.json"
    output_data = {
        "summary": {
            "total_prs": len(results),
            "successful": len(successful),
            "avg_overlap": avg_overlap if successful else 0,
            "avg_time": avg_time if successful else 0,
            "review_level": args.review_level,
        },
        "results": [
            {
                "pr_id": r.pr_id,
                "pr_url": r.pr_url,
                "nutanix_count": len(r.nutanix_suggestions),
                "kimi_count": len(r.kimi_suggestions),
                "overlap_score": r.overlap_score,
                "processing_time": r.processing_time,
                "error": r.error,
                "kimi_suggestions": r.kimi_suggestions,
            }
            for r in results
        ]
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
