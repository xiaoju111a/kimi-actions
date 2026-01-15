#!/usr/bin/env python3
"""Smart context gatherer for code review.

Analyzes diff to extract relevant context from the codebase:
- Import dependencies and their signatures
- Called functions/methods definitions
- Class hierarchies and base classes
- Related test files

Usage: python context_gatherer.py --diff "diff_content" --repo /path/to/repo
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    name: str
    file: str
    lineno: int
    signature: str
    docstring: Optional[str] = None
    body_preview: str = ""


@dataclass
class ClassInfo:
    name: str
    file: str
    lineno: int
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ContextResult:
    imports: Dict[str, str] = field(default_factory=dict)  # module -> file path
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)


def parse_diff_files(diff: str) -> List[Tuple[str, List[str]]]:
    """Extract changed files and their added lines from diff."""
    files = []
    current_file = None
    added_lines = []
    
    for line in diff.split('\n'):
        if line.startswith('diff --git') or line.startswith('--- a/') or line.startswith('+++ b/'):
            if line.startswith('+++ b/'):
                if current_file and added_lines:
                    files.append((current_file, added_lines))
                current_file = line[6:]  # Remove '+++ b/'
                added_lines = []
        elif line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:])  # Remove leading '+'
    
    if current_file and added_lines:
        files.append((current_file, added_lines))
    
    return files


def extract_imports(code_lines: List[str]) -> Set[str]:
    """Extract import statements from code."""
    imports = set()
    
    for line in code_lines:
        line = line.strip()
        
        # import module
        match = re.match(r'^import\s+([\w.]+)', line)
        if match:
            imports.add(match.group(1).split('.')[0])
            continue
        
        # from module import ...
        match = re.match(r'^from\s+([\w.]+)\s+import', line)
        if match:
            imports.add(match.group(1).split('.')[0])
    
    return imports


def extract_function_calls(code_lines: List[str]) -> Set[str]:
    """Extract function/method calls from code."""
    calls = set()
    
    code = '\n'.join(code_lines)
    
    # Match function calls: func_name(...)
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    for match in re.finditer(pattern, code):
        name = match.group(1)
        # Filter out keywords and builtins
        if name not in {'if', 'for', 'while', 'with', 'except', 'print', 'len', 'str', 'int', 'list', 'dict', 'set', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'isinstance', 'hasattr', 'getattr', 'setattr', 'super', 'type', 'open', 'format'}:
            calls.add(name)
    
    # Match method calls: obj.method(...)
    pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    for match in re.finditer(pattern, code):
        calls.add(match.group(1))
    
    return calls


def extract_class_references(code_lines: List[str]) -> Set[str]:
    """Extract class references (inheritance, instantiation)."""
    classes = set()
    code = '\n'.join(code_lines)
    
    # class Foo(Bar, Baz):
    pattern = r'class\s+\w+\s*\(([^)]+)\)'
    for match in re.finditer(pattern, code):
        bases = match.group(1).split(',')
        for base in bases:
            base = base.strip().split('.')[0]
            if base and base[0].isupper():
                classes.add(base)
    
    # Type hints: def foo(x: SomeClass) -> OtherClass:
    pattern = r':\s*([A-Z][a-zA-Z0-9_]*)'
    for match in re.finditer(pattern, code):
        classes.add(match.group(1))
    
    return classes


def find_module_file(module_name: str, repo_path: Path, changed_file: str) -> Optional[Path]:
    """Find the file path for a module name."""
    # Try relative to changed file
    changed_dir = Path(changed_file).parent
    
    candidates = [
        repo_path / changed_dir / f"{module_name}.py",
        repo_path / changed_dir / module_name / "__init__.py",
        repo_path / f"{module_name}.py",
        repo_path / module_name / "__init__.py",
        repo_path / "src" / f"{module_name}.py",
        repo_path / "src" / module_name / "__init__.py",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Search in repo
    for py_file in repo_path.rglob(f"{module_name}.py"):
        if '__pycache__' not in str(py_file) and '.venv' not in str(py_file):
            return py_file
    
    return None


def parse_python_file(file_path: Path) -> Tuple[List[FunctionInfo], List[ClassInfo]]:
    """Parse a Python file and extract function/class definitions."""
    functions = []
    classes = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content)
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Build signature
                args = []
                for arg in node.args.args:
                    arg_str = arg.arg
                    if arg.annotation:
                        arg_str += f": {ast.unparse(arg.annotation)}"
                    args.append(arg_str)
                
                returns = ""
                if node.returns:
                    returns = f" -> {ast.unparse(node.returns)}"
                
                async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                signature = f"{async_prefix}def {node.name}({', '.join(args)}){returns}"
                
                # Get docstring
                docstring = ast.get_docstring(node)
                if docstring and len(docstring) > 200:
                    docstring = docstring[:200] + "..."
                
                # Get body preview (first few lines)
                body_lines = []
                if node.body:
                    start = node.body[0].lineno - 1
                    end = min(start + 5, len(lines))
                    body_lines = lines[start:end]
                
                functions.append(FunctionInfo(
                    name=node.name,
                    file=str(file_path),
                    lineno=node.lineno,
                    signature=signature,
                    docstring=docstring,
                    body_preview='\n'.join(body_lines)
                ))
            
            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(base) for base in node.bases]
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                docstring = ast.get_docstring(node)
                if docstring and len(docstring) > 200:
                    docstring = docstring[:200] + "..."
                
                classes.append(ClassInfo(
                    name=node.name,
                    file=str(file_path),
                    lineno=node.lineno,
                    bases=bases,
                    methods=methods[:10],  # Limit methods
                    docstring=docstring
                ))
    
    except Exception:
        pass  # Skip files that can't be parsed
    
    return functions, classes


def find_function_definition(func_name: str, repo_path: Path, searched_files: Set[Path]) -> Optional[FunctionInfo]:
    """Search for a function definition in the repo."""
    for py_file in repo_path.rglob("*.py"):
        if '__pycache__' in str(py_file) or '.venv' in str(py_file):
            continue
        if py_file in searched_files:
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Quick check before parsing
            if f"def {func_name}" not in content and f"async def {func_name}" not in content:
                continue
            
            functions, _ = parse_python_file(py_file)
            for func in functions:
                if func.name == func_name:
                    return func
        except Exception:
            continue
    
    return None


def find_class_definition(class_name: str, repo_path: Path, searched_files: Set[Path]) -> Optional[ClassInfo]:
    """Search for a class definition in the repo."""
    for py_file in repo_path.rglob("*.py"):
        if '__pycache__' in str(py_file) or '.venv' in str(py_file):
            continue
        if py_file in searched_files:
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if f"class {class_name}" not in content:
                continue
            
            _, classes = parse_python_file(py_file)
            for cls in classes:
                if cls.name == class_name:
                    return cls
        except Exception:
            continue
    
    return None


def find_related_tests(changed_files: List[str], repo_path: Path) -> List[str]:
    """Find test files related to changed files."""
    test_files = []
    
    for changed_file in changed_files:
        if not changed_file.endswith('.py'):
            continue
        
        base_name = Path(changed_file).stem
        
        # Common test file patterns
        patterns = [
            f"test_{base_name}.py",
            f"{base_name}_test.py",
            f"tests/test_{base_name}.py",
            f"test/test_{base_name}.py",
        ]
        
        for pattern in patterns:
            for test_file in repo_path.rglob(pattern):
                if '__pycache__' not in str(test_file):
                    rel_path = test_file.relative_to(repo_path)
                    if str(rel_path) not in test_files:
                        test_files.append(str(rel_path))
    
    return test_files[:5]  # Limit to 5 test files


def gather_context(diff: str, repo_path: str) -> ContextResult:
    """Main function to gather context from diff and repo."""
    repo = Path(repo_path)
    result = ContextResult()
    searched_files: Set[Path] = set()
    
    # Parse diff
    diff_files = parse_diff_files(diff)
    if not diff_files:
        return result
    
    all_imports = set()
    all_calls = set()
    all_classes = set()
    changed_file_names = []
    
    for file_path, added_lines in diff_files:
        changed_file_names.append(file_path)
        
        if file_path.endswith('.py'):
            all_imports.update(extract_imports(added_lines))
            all_calls.update(extract_function_calls(added_lines))
            all_classes.update(extract_class_references(added_lines))
    
    # Find imported modules
    for module in all_imports:
        module_file = find_module_file(module, repo, changed_file_names[0] if changed_file_names else "")
        if module_file:
            result.imports[module] = str(module_file.relative_to(repo))
            searched_files.add(module_file)
            
            # Parse the module for functions/classes
            functions, classes = parse_python_file(module_file)
            
            # Add relevant functions (those that are called)
            for func in functions:
                if func.name in all_calls:
                    result.functions.append(func)
            
            # Add relevant classes
            for cls in classes:
                if cls.name in all_classes:
                    result.classes.append(cls)
    
    # Search for called functions not found in imports
    remaining_calls = all_calls - {f.name for f in result.functions}
    for func_name in list(remaining_calls)[:10]:  # Limit search
        func_info = find_function_definition(func_name, repo, searched_files)
        if func_info:
            result.functions.append(func_info)
    
    # Search for referenced classes not found
    remaining_classes = all_classes - {c.name for c in result.classes}
    for class_name in list(remaining_classes)[:5]:  # Limit search
        class_info = find_class_definition(class_name, repo, searched_files)
        if class_info:
            result.classes.append(class_info)
    
    # Find related test files
    result.related_files = find_related_tests(changed_file_names, repo)
    
    return result


def format_output(result: ContextResult) -> str:
    """Format context result as readable output for AI."""
    output = []
    
    if result.imports:
        output.append("## Imported Modules")
        for module, path in result.imports.items():
            output.append(f"- {module} -> {path}")
        output.append("")
    
    if result.functions:
        output.append("## Related Function Definitions")
        for func in result.functions:
            output.append(f"### {func.name} ({func.file}:{func.lineno})")
            output.append("```python")
            output.append(func.signature)
            if func.docstring:
                output.append(f'    """{func.docstring}"""')
            if func.body_preview:
                output.append("    # Body preview:")
                for line in func.body_preview.split('\n')[:3]:
                    output.append(f"    {line}")
            output.append("```")
            output.append("")
    
    if result.classes:
        output.append("## Related Class Definitions")
        for cls in result.classes:
            output.append(f"### {cls.name} ({cls.file}:{cls.lineno})")
            bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
            output.append("```python")
            output.append(f"class {cls.name}{bases_str}:")
            if cls.docstring:
                output.append(f'    """{cls.docstring}"""')
            if cls.methods:
                output.append(f"    # Methods: {', '.join(cls.methods)}")
            output.append("```")
            output.append("")
    
    if result.related_files:
        output.append("## Related Test Files")
        for test_file in result.related_files:
            output.append(f"- {test_file}")
        output.append("")
    
    if not output:
        return "No additional context found."
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Smart context gatherer for code review")
    parser.add_argument("--diff", help="Diff content")
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.diff:
        diff = args.diff
    else:
        diff = sys.stdin.read()
    
    result = gather_context(diff, args.repo)
    
    if args.json:
        import json
        output = {
            "imports": result.imports,
            "functions": [
                {"name": f.name, "file": f.file, "signature": f.signature, "docstring": f.docstring}
                for f in result.functions
            ],
            "classes": [
                {"name": c.name, "file": c.file, "bases": c.bases, "methods": c.methods}
                for c in result.classes
            ],
            "related_files": result.related_files
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_output(result))


if __name__ == "__main__":
    main()
