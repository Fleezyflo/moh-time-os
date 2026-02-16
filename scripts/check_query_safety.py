#!/usr/bin/env python3
"""
Check for unsafe database query patterns.

Detects:
- SELECT without LIMIT (unbounded queries)
- N+1 query patterns (queries in loops)
- Missing WHERE clauses on UPDATE/DELETE
"""

import ast
import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "migration"]

# Patterns for unsafe queries
UNBOUNDED_SELECT = re.compile(
    r'SELECT\s+.*?\s+FROM\s+\w+(?:\s+WHERE\s+[^;]+)?(?:\s+ORDER\s+BY\s+[^;]+)?(?:\s*;|\s*$|"""|\'\'\')' ,
    re.IGNORECASE | re.DOTALL
)

# Safe patterns (have LIMIT)
HAS_LIMIT = re.compile(r'\bLIMIT\s+\d+', re.IGNORECASE)
HAS_FETCHONE = re.compile(r'\.fetchone\(\)', re.IGNORECASE)
HAS_COUNT = re.compile(r'SELECT\s+COUNT\s*\(', re.IGNORECASE)
HAS_EXISTS = re.compile(r'SELECT\s+EXISTS', re.IGNORECASE)
HAS_PRAGMA = re.compile(r'PRAGMA\s+', re.IGNORECASE)

# Dangerous patterns
DELETE_NO_WHERE = re.compile(r'DELETE\s+FROM\s+\w+\s*(?:;|$|""")', re.IGNORECASE)
UPDATE_NO_WHERE = re.compile(r'UPDATE\s+\w+\s+SET\s+[^;]+(?:;|$|""")', re.IGNORECASE)


def check_file(filepath: Path) -> list[str]:
    """Check a file for unsafe query patterns."""
    violations = []
    
    try:
        content = filepath.read_text()
        lines = content.split("\n")
        
        # Check for unbounded SELECTs
        for match in UNBOUNDED_SELECT.finditer(content):
            query = match.group(0)
            
            # Skip if safe pattern
            if HAS_LIMIT.search(query):
                continue
            if HAS_COUNT.search(query):
                continue
            if HAS_EXISTS.search(query):
                continue
            if HAS_PRAGMA.search(query):
                continue
            
            # Find line number
            start = match.start()
            lineno = content[:start].count("\n") + 1
            
            # Check if fetchone is used nearby (within 3 lines)
            nearby = "\n".join(lines[max(0, lineno-1):lineno+3])
            if HAS_FETCHONE.search(nearby):
                continue
            
            # This is potentially unbounded
            query_preview = query[:60].replace("\n", " ")
            violations.append(f"  {filepath}:{lineno}: Unbounded SELECT: {query_preview}...")
        
        # Check for DELETE without WHERE
        for match in DELETE_NO_WHERE.finditer(content):
            if "WHERE" not in match.group(0).upper():
                start = match.start()
                lineno = content[:start].count("\n") + 1
                violations.append(f"  {filepath}:{lineno}: DELETE without WHERE clause")
        
        # Check for UPDATE without WHERE  
        for match in UPDATE_NO_WHERE.finditer(content):
            if "WHERE" not in match.group(0).upper():
                start = match.start()
                lineno = content[:start].count("\n") + 1
                violations.append(f"  {filepath}:{lineno}: UPDATE without WHERE clause")
                
    except (OSError, UnicodeDecodeError):
        pass
    
    return violations


def check_n_plus_one(filepath: Path) -> list[str]:
    """Check for N+1 query patterns (query in loop)."""
    violations = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
        
        # Find all for loops
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                # Check if there's a database call inside
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr in ("execute", "fetchone", "fetchall", "fetchmany"):
                                violations.append(
                                    f"  {filepath}:{node.lineno}: Potential N+1 query in loop"
                                )
                                break
                                
    except (SyntaxError, OSError, UnicodeDecodeError):
        pass
    
    return violations[:5]  # Limit per file


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def main() -> int:
    """Main entry point."""
    all_violations = []
    
    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue
            
            violations = check_file(py_file)
            all_violations.extend(violations)
            
            n1_violations = check_n_plus_one(py_file)
            all_violations.extend(n1_violations)
    
    if all_violations:
        print("🔍 UNSAFE QUERY PATTERNS:")
        print("\n".join(all_violations[:40]))
        if len(all_violations) > 40:
            print(f"  ... and {len(all_violations) - 40} more")
        print("\nAdd LIMIT to unbounded SELECTs, WHERE to UPDATE/DELETE.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ No unsafe query patterns detected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
