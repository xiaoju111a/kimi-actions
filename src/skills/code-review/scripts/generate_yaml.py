#!/usr/bin/env python3
"""Generate and validate YAML output for code review.

This script helps the Agent generate valid YAML by:
1. Taking structured data as input
2. Generating properly formatted YAML
3. Validating the YAML syntax
4. Returning the valid YAML string

Usage in Agent:
    # Generate YAML from Python data
    python scripts/generate_yaml.py generate '{"summary": "...", "score": 85, ...}'
    
    # Validate existing YAML
    python scripts/generate_yaml.py validate "summary: test"
    
    # See example
    python scripts/generate_yaml.py example
"""

import sys
import json
import yaml
from typing import Dict, Any


def generate_review_yaml(data: Dict[str, Any]) -> str:
    """Generate valid YAML for code review output.
    
    Args:
        data: Dict with keys: summary, score, file_summaries, suggestions
    
    Returns:
        Valid YAML string wrapped in code block
    """
    # Ensure required fields
    if 'summary' not in data:
        data['summary'] = "Code review completed"
    if 'score' not in data:
        data['score'] = 80
    if 'file_summaries' not in data:
        data['file_summaries'] = []
    if 'suggestions' not in data:
        data['suggestions'] = []
    
    # Generate YAML with proper formatting
    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Validate by parsing it back
    try:
        yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Generated invalid YAML: {e}")
    
    # Return wrapped in code block
    return f"```yaml\n{yaml_str}```"


def validate_yaml(yaml_str: str) -> tuple[bool, str]:
    """Validate YAML syntax.
    
    Args:
        yaml_str: YAML string to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        yaml.safe_load(yaml_str)
        return True, "Valid YAML"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"


def fix_common_yaml_errors(yaml_str: str) -> str:
    """Attempt to fix common YAML formatting errors.
    
    Args:
        yaml_str: Potentially malformed YAML string
    
    Returns:
        Fixed YAML string
    """
    # Remove any text before first yaml key
    lines = yaml_str.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith('#'):
            if ':' in line or line.strip().startswith('-'):
                start_idx = i
                break
    
    yaml_str = '\n'.join(lines[start_idx:])
    
    # Fix common quote issues in multiline strings
    # Convert unquoted multiline values to quoted
    import re
    
    # Fix: existing_code: "some code without closing quote
    yaml_str = re.sub(r'(existing_code|improved_code|suggestion_content):\s*"([^"]*?)$', 
                      r'\1: |\n  \2', yaml_str, flags=re.MULTILINE)
    
    return yaml_str


def main():
    """CLI interface for YAML generation."""
    if len(sys.argv) < 2:
        print("Usage: generate_yaml.py <command> [args]")
        print("\nCommands:")
        print("  generate <json_data>    - Generate YAML from JSON data")
        print("  validate <yaml_string>  - Validate YAML syntax")
        print("  fix <yaml_string>       - Attempt to fix common YAML errors")
        print("  example                 - Show example usage")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "generate":
        if len(sys.argv) < 3:
            print("Error: Missing JSON data")
            print("Example: generate_yaml.py generate '{\"summary\": \"test\", \"score\": 85}'")
            sys.exit(1)
        
        try:
            data = json.loads(sys.argv[2])
            yaml_output = generate_review_yaml(data)
            print(yaml_output)
            sys.exit(0)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif command == "validate":
        if len(sys.argv) < 3:
            print("Error: Missing YAML string to validate")
            sys.exit(1)
        
        yaml_str = sys.argv[2]
        is_valid, message = validate_yaml(yaml_str)
        print(message)
        sys.exit(0 if is_valid else 1)
    
    elif command == "fix":
        if len(sys.argv) < 3:
            print("Error: Missing YAML string to fix")
            sys.exit(1)
        
        yaml_str = sys.argv[2]
        try:
            fixed = fix_common_yaml_errors(yaml_str)
            is_valid, message = validate_yaml(fixed)
            if is_valid:
                print("Fixed YAML:")
                print(fixed)
                sys.exit(0)
            else:
                print(f"Could not fix YAML: {message}")
                sys.exit(1)
        except Exception as e:
            print(f"Error fixing YAML: {e}")
            sys.exit(1)
    
    elif command == "example":
        example_data = {
            'summary': 'Added new authentication feature with JWT tokens',
            'score': 85,
            'file_summaries': [
                {
                    'file': 'src/auth.py',
                    'description': 'Implemented JWT token generation and validation with expiration handling'
                },
                {
                    'file': 'tests/test_auth.py',
                    'description': 'Added comprehensive tests for authentication flow including edge cases'
                }
            ],
            'suggestions': [
                {
                    'relevant_file': 'src/auth.py',
                    'language': 'python',
                    'severity': 'medium',
                    'label': 'security',
                    'one_sentence_summary': 'Token expiration should be configurable',
                    'suggestion_content': 'Hardcoded token expiration time makes it difficult to adjust for different environments.',
                    'existing_code': 'EXPIRATION = 3600',
                    'improved_code': 'EXPIRATION = int(os.getenv("TOKEN_EXPIRATION", "3600"))',
                    'relevant_lines_start': 15,
                    'relevant_lines_end': 15
                }
            ]
        }
        
        print("Example usage:")
        print("\n1. Generate YAML from Python dict:")
        print(f"   python generate_yaml.py generate '{json.dumps(example_data)}'")
        print("\n2. Output:")
        print(generate_review_yaml(example_data))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
