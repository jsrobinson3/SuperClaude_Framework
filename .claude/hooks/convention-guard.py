#!/usr/bin/env python3
"""
PreToolUse hook: Guard project conventions before file writes.

Checks that new files follow the project's naming conventions,
are placed in the correct directories, and follow import ordering.

Matcher: Write
Event: PreToolUse
"""

import json
import re
import sys
from pathlib import Path


def check_file_placement(file_path: str, project_dir: str) -> list[str]:
    """Verify file is being created in an appropriate location."""
    issues = []
    rel = Path(file_path).relative_to(project_dir) if file_path.startswith(project_dir) else Path(file_path)
    parts = rel.parts
    name = rel.name
    ext = rel.suffix

    # Test files should be in tests/ directory
    if name.startswith("test_") and ext == ".py":
        if "tests" not in parts and "test" not in parts:
            issues.append(
                f"Test file '{name}' should be in the tests/ directory, "
                f"not {'/'.join(parts[:-1]) or 'root'}."
            )

    # Python files should be in src/ or tests/
    if ext == ".py" and len(parts) > 1:
        if parts[0] not in ("src", "tests", "test", "scripts", "docs"):
            # Not necessarily wrong, but worth flagging
            pass

    # Don't create files in node_modules, .venv, etc.
    protected = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}
    if any(p in protected for p in parts):
        issues.append(f"File is being created inside a protected directory: {'/'.join(parts)}")

    return issues


def check_python_content(content: str, file_path: str) -> list[str]:
    """Check Python file content for convention violations."""
    issues = []
    lines = content.splitlines()
    name = Path(file_path).stem

    # Module naming: should be snake_case
    if not re.match(r'^[a-z_][a-z0-9_]*$', name) and name != "__init__":
        issues.append(f"Module name '{name}' should use snake_case.")

    # Check for wildcard imports
    for i, line in enumerate(lines, 1):
        if re.match(r'^\s*from\s+\S+\s+import\s+\*', line):
            issues.append(f"Line {i}: Wildcard import detected. Import specific names instead.")

    # Check for hardcoded secrets patterns
    secret_patterns = [
        (r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "Potential hardcoded secret"),
        (r'(?:sk-|pk_live_|AKIA)[A-Za-z0-9]+', "Potential API key in source code"),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, msg in secret_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(f"Line {i}: {msg}. Use environment variables instead.")

    return issues


def main():
    hook_input = json.loads(sys.stdin.read())
    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    content = hook_input.get("tool_input", {}).get("content", "")
    cwd = hook_input.get("cwd", "")

    if not file_path:
        sys.exit(0)

    issues = []

    # Check file placement
    issues.extend(check_file_placement(file_path, cwd))

    # Language-specific content checks
    if file_path.endswith(".py") and content:
        issues.extend(check_python_content(content, file_path))

    if issues:
        reason = "Convention issues detected:\n" + "\n".join(f"- {i}" for i in issues)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }
        json.dump(output, sys.stdout)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
