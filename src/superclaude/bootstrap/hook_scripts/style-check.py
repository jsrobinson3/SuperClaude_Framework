#!/usr/bin/env python3
"""
PostToolUse hook: Enforce code style conventions.

Checks function length, file length, nesting depth, and naming conventions.
Configurable via .claude/hooks-config.json in the project root.

Matcher: Write|Edit
Event: PostToolUse
"""

import json
import re
import sys
from pathlib import Path

# ── Defaults (overridable via .claude/hooks-config.json) ───────────────
DEFAULT_CONFIG = {
    "max_function_lines": 50,
    "max_file_lines": 500,
    "max_line_length": 120,
    "max_nesting_depth": 4,
    "check_naming": True,
}


def load_config() -> dict:
    """Load hook config, merging project overrides with defaults."""
    config = dict(DEFAULT_CONFIG)
    for candidate in [
        Path.cwd() / ".claude" / "hooks-config.json",
        Path.home() / ".claude" / "hooks-config.json",
    ]:
        if candidate.exists():
            try:
                overrides = json.loads(candidate.read_text())
                config.update(overrides.get("style_check", {}))
            except (json.JSONDecodeError, OSError):
                pass
            break
    return config


def check_python(filepath: str, config: dict) -> list[str]:
    """Check Python-specific style rules."""
    issues = []
    lines = Path(filepath).read_text().splitlines()

    # File length
    if len(lines) > config["max_file_lines"]:
        issues.append(
            f"File has {len(lines)} lines (max {config['max_file_lines']}). "
            "Consider splitting into smaller modules."
        )

    # Function/method length and nesting
    func_start = None
    func_name = None
    func_indent = 0

    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()

        # Line length
        if len(stripped) > config["max_line_length"]:
            issues.append(f"Line {i}: {len(stripped)} chars (max {config['max_line_length']})")

        # Track function definitions
        match = re.match(r'^(\s*)(async\s+)?def\s+(\w+)', line)
        if match:
            # Check previous function length
            if func_start is not None:
                length = i - func_start
                if length > config["max_function_lines"]:
                    issues.append(
                        f"Function '{func_name}' is {length} lines "
                        f"(max {config['max_function_lines']}). Consider refactoring."
                    )
            func_indent = len(match.group(1))
            func_name = match.group(3)
            func_start = i

            # Naming convention check
            if config["check_naming"] and not re.match(r'^[a-z_][a-z0-9_]*$', func_name):
                if func_name != "__init__" and not func_name.startswith("_"):
                    issues.append(
                        f"Line {i}: Function '{func_name}' should use snake_case."
                    )

        # Nesting depth check
        if stripped and not stripped.startswith("#"):
            indent = len(line) - len(line.lstrip())
            depth = indent // 4
            if depth > config["max_nesting_depth"]:
                issues.append(
                    f"Line {i}: Nesting depth {depth} exceeds max {config['max_nesting_depth']}. "
                    "Consider extracting to a helper function."
                )

    # Check last function
    if func_start is not None:
        length = len(lines) - func_start + 1
        if length > config["max_function_lines"]:
            issues.append(
                f"Function '{func_name}' is {length} lines "
                f"(max {config['max_function_lines']}). Consider refactoring."
            )

    return issues


def check_javascript(filepath: str, config: dict) -> list[str]:
    """Check JavaScript/TypeScript style rules."""
    issues = []
    lines = Path(filepath).read_text().splitlines()

    if len(lines) > config["max_file_lines"]:
        issues.append(
            f"File has {len(lines)} lines (max {config['max_file_lines']}). "
            "Consider splitting into smaller modules."
        )

    func_start = None
    func_name = None

    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()

        if len(stripped) > config["max_line_length"]:
            issues.append(f"Line {i}: {len(stripped)} chars (max {config['max_line_length']})")

        # Track function definitions
        match = re.match(
            r'^\s*(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()',
            line
        )
        if match:
            name = match.group(1) or match.group(2)
            if func_start is not None:
                length = i - func_start
                if length > config["max_function_lines"]:
                    issues.append(
                        f"Function '{func_name}' is {length} lines "
                        f"(max {config['max_function_lines']})."
                    )
            func_name = name
            func_start = i

        # Nesting depth
        if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
            indent = len(line) - len(line.lstrip())
            depth = indent // 2  # JS typically uses 2-space indent
            if depth > config["max_nesting_depth"]:
                issues.append(
                    f"Line {i}: Nesting depth {depth} exceeds max {config['max_nesting_depth']}."
                )

    return issues


def main():
    hook_input = json.loads(sys.stdin.read())
    file_path = hook_input.get("tool_input", {}).get("file_path", "")

    if not file_path or not Path(file_path).exists():
        sys.exit(0)

    config = load_config()
    ext = Path(file_path).suffix

    issues = []
    if ext == ".py":
        issues = check_python(file_path, config)
    elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        issues = check_javascript(file_path, config)
    else:
        sys.exit(0)

    if issues:
        context = f"Style issues in {Path(file_path).name}:\n" + "\n".join(f"- {i}" for i in issues[:10])
        if len(issues) > 10:
            context += f"\n... and {len(issues) - 10} more issues"

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
        json.dump(output, sys.stdout)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
