#!/usr/bin/env python3
"""Full evaluation of Kimi Actions PR Review on Nutanix dataset.

Features:
- Checkpoint/resume support
- Progress tracking
- Detailed reporting

Usage:
    KIMI_API_KEY=xxx python scripts/eval_nutanix_full.py --output eval_full_results.json
"""

import os
import sys
import csv
import json
import argparse
import logging
import re
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime

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
    id: str
    content: str
    existing_code: str
    suggested_code: str
    suggestion_type: str
    pr_id: str


@dataclass
class PRContext:
    id: str
    pr_url: str
    title: str
    diff: str
    files: List[str]


@dataclass
class EvalResult:
    pr_id: str
    pr_url: str
    nutanix_count: int
    kimi_count: int
    overlap_score: float
    processing_time: float
    error: Optional[str] = None
    kimi_suggestions: List[Dict] = None


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


suggestions_by_pr_global: Dict[str, List[NutanixSuggestion]] = {}


def load_all_pr_contexts(pr_ids: List[str]) -> Dict[str, PRContext]:
    """Load all PR contexts."""
    csv.field_size_limit(sys.maxsize)
    
    pr_contexts = {}
    pr_ids_set = set(pr_ids)
    
    logger.info(f"Loading PR contexts for {len(pr_ids_set)} PRs...")
    
    with open(PULL_REQUESTS_FILE, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_id = row.get('id', '')
            if pr_id in pr_ids_set:
                try:
                    pr_context_json = row.get('pr_context', '{}')
                    pr_context_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', pr_context_json)
                    
                    try:
                        pr_context = json.loads(pr_context_json)
                    except json.JSONDecodeError:
                        try:
                            import ast
                            pr_context = ast.literal_eval(pr_context_json)
                        except:
                            pr_context = {}
                    
                    diff_parts = []
                    files = []
                    
                    for diff_file in pr_context.get('diff_files', []):
                        filename = diff_file.get('filename', '')
                        patch = diff_file.get('patch', '')
                        if filename:
                            files.append(filename)
                        if patch:
                            diff_parts.append(f"diff --git a/{filename} b/{filename}\n{patch}")
                    
                    if not diff_parts:
                        for git_file in pr_context.get('git_files', []):
                            filename = git_file.get('filename', '')
                            patch = git_file.get('patch', '')
                            if filename:
                                files.append(filename)
                            if patch:
                                diff_parts.append(f"diff --git a/{filename} b/{filename}\n{patch}")
                    
                    diff = "\n\n".join(diff_parts)
                    
                    if diff:
                        pr_contexts[pr_id] = PRContext(
                            id=pr_id,
                            pr_url=row.get('pr_url', ''),
                            title=pr_context.get('pr_title', f'PR #{pr_id}'),
                            diff=diff,
                            files=files if files else ['unknown']
                        )
                        
                except Exception as e:
                    logger.debug(f"Failed to parse PR {pr_id}: {e}")
                    continue
    
    logger.info(f"Loaded {len(pr_contexts)} PR contexts")
    return pr_contexts


class KimiReviewer:
    def __init__(self, api_key: str, review_level: str = "normal"):
        self.kimi = KimiClient(api_key)
        self.skill_manager = SkillManager()
        self.token_handler = TokenHandler()
        self.chunker = DiffChunker(self.token_handler)
        self.review_level = review_level
    
    def get_skill_instructions(self) -> str:
        skill = self.skill_manager.get_skill("code-review")
        if skill:
            return skill.instructions
        return ""
    
    def build_system_prompt(self, diff: str) -> str:
        skill_instructions = self.get_skill_instructions()
        parts = [skill_instructions]
        level_text = {
            "strict": "Review Level: Strict",
            "normal": "Review Level: Normal",
            "gentle": "Review Level: Gentle"
        }
        parts.append(f"\n## {level_text.get(self.review_level, level_text['normal'])}")
        return "\n".join(parts)
    
    def process_diff(self, raw_diff: str) -> Tuple[str, List, List]:
        included, excluded = self.chunker.chunk_diff(raw_diff, max_files=15)
        compressed = self.chunker.build_diff_string(included)
        return compressed, included, excluded
    
    def build_user_prompt(self, pr: PRContext, compressed_diff: str) -> str:
        return f"""## PR Information
Title: {pr.title}
Files: {', '.join(pr.files[:10])}

## Code Changes
```diff
{compressed_diff}
```

Please output review results in YAML format."""
    
    def parse_suggestions(self, response: str) -> List[Dict]:
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
            logger.debug(f"Failed to parse YAML: {e}")
        return []
    
    def review(self, pr: PRContext) -> Tuple[List[Dict], str]:
        compressed_diff, included, excluded = self.process_diff(pr.diff)
        if not compressed_diff:
            return [], "No changes to review"
        
        system_prompt = self.build_system_prompt(compressed_diff)
        user_prompt = self.build_user_prompt(pr, compressed_diff)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.kimi.chat(messages)
        suggestions = self.parse_suggestions(response)
        return suggestions, response


def calculate_overlap(nutanix_suggestions: List[NutanixSuggestion], 
                      kimi_suggestions: List[Dict]) -> float:
    if not nutanix_suggestions or not kimi_suggestions:
        return 0.0
    
    nutanix_terms = set()
    for s in nutanix_suggestions:
        words = s.content.lower().split()
        nutanix_terms.update(w for w in words if len(w) > 4)
        if s.existing_code:
            code_words = s.existing_code.replace('(', ' ').replace(')', ' ').split()
            nutanix_terms.update(w.lower() for w in code_words if len(w) > 3)
    
    matches = 0
    for ks in kimi_suggestions:
        kimi_text = str(ks).lower()
        for term in nutanix_terms:
            if term in kimi_text:
                matches += 1
                break
    
    return matches / len(kimi_suggestions) if kimi_suggestions else 0.0


def evaluate_suggestion_quality(kimi_suggestions: List[Dict]) -> Dict:
    if not kimi_suggestions:
        return {"avg_quality": 0, "has_code_fix_pct": 0, "severity_dist": {}}
    
    quality_scores = []
    has_code_fix = 0
    severity_dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    
    for s in kimi_suggestions:
        score = 0
        if s.get("relevant_file") and s.get("relevant_file") != "unknown":
            score += 1
        if s.get("relevant_lines_start") and s.get("relevant_lines_start") > 0:
            score += 1
        if s.get("one_sentence_summary") and len(s.get("one_sentence_summary", "")) > 20:
            score += 1
        if s.get("suggestion_content") and len(s.get("suggestion_content", "")) > 50:
            score += 1
        if s.get("improved_code"):
            score += 1
            has_code_fix += 1
        quality_scores.append(score)
        severity = s.get("severity", "medium").lower()
        if severity in severity_dist:
            severity_dist[severity] += 1
    
    return {
        "avg_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        "max_quality": 5,
        "has_code_fix_pct": has_code_fix / len(kimi_suggestions) * 100,
        "severity_dist": severity_dist
    }


def load_checkpoint(checkpoint_file: Path) -> Dict:
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            return json.load(f)
    return {"completed": [], "results": []}


def save_checkpoint(checkpoint_file: Path, data: Dict):
    with open(checkpoint_file, 'w') as f:
        json.dump(data, f)


def generate_interim_report(results: List[Dict], count: int, output_base: str):
    """Generate interim report every 100 PRs."""
    successful = [r for r in results if not r.get("error")]
    failed = [r for r in results if r.get("error")]
    
    if not successful:
        return
    
    total_nutanix = sum(r["nutanix_count"] for r in successful)
    total_kimi = sum(r["kimi_count"] for r in successful)
    avg_overlap = sum(r["overlap_score"] for r in successful) / len(successful)
    avg_time = sum(r["processing_time"] for r in successful) / len(successful)
    
    all_suggestions = []
    for r in successful:
        if r.get("kimi_suggestions"):
            all_suggestions.extend(r["kimi_suggestions"])
    quality = evaluate_suggestion_quality(all_suggestions)
    
    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "prs_evaluated": count,
            "type": "interim"
        },
        "summary": {
            "total_prs": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_nutanix_suggestions": total_nutanix,
            "total_kimi_suggestions": total_kimi,
            "kimi_nutanix_ratio": total_kimi / total_nutanix if total_nutanix else 0,
            "avg_overlap_score": avg_overlap,
            "avg_processing_time": avg_time
        },
        "quality": quality
    }
    
    # Save interim report
    interim_file = output_base.replace('.json', f'_interim_{count}.json')
    with open(interim_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print interim summary
    print(f"\n{'='*60}")
    print(f"INTERIM REPORT @ {count} PRs")
    print(f"{'='*60}")
    print(f"Successful: {len(successful)}, Failed: {len(failed)}")
    print(f"Nutanix: {total_nutanix}, Kimi: {total_kimi}")
    print(f"Kimi/Nutanix ratio: {total_kimi/total_nutanix:.2f}" if total_nutanix else "N/A")
    print(f"Avg overlap: {avg_overlap:.2f}, Avg time: {avg_time:.1f}s")
    print(f"Quality: {quality['avg_quality']:.1f}/5, Code fix: {quality['has_code_fix_pct']:.0f}%")
    print(f"Saved to: {interim_file}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Full Nutanix evaluation")
    parser.add_argument("--output", type=str, default="eval/eval_full_results.json")
    parser.add_argument("--checkpoint", type=str, default="eval/eval_checkpoint.json")
    parser.add_argument("--min-suggestions", type=int, default=2)
    parser.add_argument("--review-level", type=str, default="normal")
    parser.add_argument("--limit", type=int, default=0, help="Limit PRs (0=all)")
    args = parser.parse_args()
    
    api_key = os.environ.get("KIMI_API_KEY")
    if not api_key:
        logger.error("KIMI_API_KEY not set")
        sys.exit(1)
    
    print("=" * 60)
    print("Nutanix Full Dataset Evaluation")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Load suggestions
    logger.info("Loading suggestions...")
    suggestions_by_pr = load_suggestions_by_pr()
    global suggestions_by_pr_global
    suggestions_by_pr_global = suggestions_by_pr
    
    # Filter PRs
    candidate_prs = [
        pr_id for pr_id, suggestions in suggestions_by_pr.items()
        if len(suggestions) >= args.min_suggestions
    ]
    logger.info(f"Found {len(candidate_prs)} PRs with >= {args.min_suggestions} suggestions")
    
    if args.limit > 0:
        candidate_prs = candidate_prs[:args.limit]
        logger.info(f"Limited to {len(candidate_prs)} PRs")
    
    # Load PR contexts
    pr_contexts = load_all_pr_contexts(candidate_prs)
    
    # Load checkpoint
    checkpoint_file = Path(args.checkpoint)
    checkpoint = load_checkpoint(checkpoint_file)
    completed_ids = set(checkpoint["completed"])
    results = checkpoint["results"]
    
    logger.info(f"Checkpoint: {len(completed_ids)} already completed")
    
    # Filter to remaining PRs
    remaining_prs = [
        (pr_id, pr_contexts[pr_id], suggestions_by_pr[pr_id])
        for pr_id in candidate_prs
        if pr_id in pr_contexts and pr_id not in completed_ids
    ]
    
    total_to_eval = len(remaining_prs) + len(completed_ids)
    logger.info(f"Remaining: {len(remaining_prs)} PRs to evaluate")
    
    if not remaining_prs:
        logger.info("All PRs already evaluated!")
    else:
        # Initialize reviewer
        reviewer = KimiReviewer(api_key, review_level=args.review_level)
        
        # Evaluate
        start_time = time.time()
        for idx, (pr_id, pr_context, nutanix_suggestions) in enumerate(remaining_prs, 1):
            current_idx = len(completed_ids) + idx
            logger.info(f"[{current_idx}/{total_to_eval}] Evaluating PR {pr_id}...")
            
            eval_start = time.time()
            try:
                kimi_suggestions, response = reviewer.review(pr_context)
                overlap = calculate_overlap(nutanix_suggestions, kimi_suggestions)
                
                result = EvalResult(
                    pr_id=pr_id,
                    pr_url=pr_context.pr_url,
                    nutanix_count=len(nutanix_suggestions),
                    kimi_count=len(kimi_suggestions),
                    overlap_score=overlap,
                    processing_time=time.time() - eval_start,
                    kimi_suggestions=kimi_suggestions
                )
            except Exception as e:
                logger.error(f"Error: {e}")
                result = EvalResult(
                    pr_id=pr_id,
                    pr_url=pr_context.pr_url,
                    nutanix_count=len(nutanix_suggestions),
                    kimi_count=0,
                    overlap_score=0,
                    processing_time=time.time() - eval_start,
                    error=str(e)
                )
            
            results.append(asdict(result))
            completed_ids.add(pr_id)
            
            # Save checkpoint every 10 PRs
            if idx % 10 == 0:
                checkpoint["completed"] = list(completed_ids)
                checkpoint["results"] = results
                save_checkpoint(checkpoint_file, checkpoint)
                
                # Progress report
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining_time = avg_time * (len(remaining_prs) - idx)
                logger.info(f"Progress: {current_idx}/{total_to_eval} ({current_idx/total_to_eval*100:.1f}%)")
                logger.info(f"ETA: {remaining_time/3600:.1f} hours")
            
            # Generate interim report every 100 PRs
            if current_idx % 100 == 0:
                generate_interim_report(results, current_idx, args.output)
    
    # Final save
    checkpoint["completed"] = list(completed_ids)
    checkpoint["results"] = results
    save_checkpoint(checkpoint_file, checkpoint)
    
    # Generate report
    successful = [r for r in results if not r.get("error")]
    failed = [r for r in results if r.get("error")]
    
    total_nutanix = sum(r["nutanix_count"] for r in successful)
    total_kimi = sum(r["kimi_count"] for r in successful)
    avg_overlap = sum(r["overlap_score"] for r in successful) / len(successful) if successful else 0
    avg_time = sum(r["processing_time"] for r in successful) / len(successful) if successful else 0
    
    # Quality analysis
    all_suggestions = []
    for r in successful:
        if r.get("kimi_suggestions"):
            all_suggestions.extend(r["kimi_suggestions"])
    quality = evaluate_suggestion_quality(all_suggestions)
    
    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "review_level": args.review_level,
            "min_suggestions": args.min_suggestions
        },
        "summary": {
            "total_prs": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_nutanix_suggestions": total_nutanix,
            "total_kimi_suggestions": total_kimi,
            "kimi_nutanix_ratio": total_kimi / total_nutanix if total_nutanix else 0,
            "avg_overlap_score": avg_overlap,
            "avg_processing_time": avg_time
        },
        "quality": quality,
        "results": results
    }
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(f"Total PRs evaluated: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Total Nutanix suggestions: {total_nutanix}")
    print(f"Total Kimi suggestions: {total_kimi}")
    print(f"Kimi/Nutanix ratio: {total_kimi/total_nutanix:.2f}" if total_nutanix else "N/A")
    print(f"Average overlap score: {avg_overlap:.2f}")
    print(f"Average processing time: {avg_time:.1f}s")
    print(f"\n--- Quality Metrics ---")
    print(f"Average quality score: {quality['avg_quality']:.1f}/5")
    print(f"Has code fix: {quality['has_code_fix_pct']:.0f}%")
    print(f"Severity distribution: {quality['severity_dist']}")
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
