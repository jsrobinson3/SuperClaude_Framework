#!/bin/bash
# PostToolUse hook: Auto-lint files after Write|Edit
# Runs the project's linter on changed files and reports issues to Claude.
#
# Matcher: Write|Edit
# Event: PostToolUse

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path
if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"
ISSUES=""

case "$EXT" in
  py)
    # Python: try ruff first, fall back to flake8
    if command -v ruff &>/dev/null; then
      ISSUES=$(ruff check --no-fix --output-format=text "$FILE_PATH" 2>&1) || true
    elif command -v flake8 &>/dev/null; then
      ISSUES=$(flake8 "$FILE_PATH" 2>&1) || true
    fi
    ;;
  js|jsx|ts|tsx|mjs|cjs)
    # JavaScript/TypeScript: try eslint, then biome
    if command -v eslint &>/dev/null; then
      ISSUES=$(eslint --no-fix --format compact "$FILE_PATH" 2>&1) || true
    elif command -v biome &>/dev/null; then
      ISSUES=$(biome check --no-errors-on-unmatched "$FILE_PATH" 2>&1) || true
    fi
    ;;
  go)
    if command -v golangci-lint &>/dev/null; then
      ISSUES=$(golangci-lint run "$FILE_PATH" 2>&1) || true
    fi
    ;;
  rs)
    if command -v clippy-driver &>/dev/null; then
      ISSUES=$(cargo clippy -- -W clippy::all 2>&1) || true
    fi
    ;;
  *)
    # Unsupported file type — skip silently
    exit 0
    ;;
esac

if [[ -n "$ISSUES" && "$ISSUES" != *"All checks passed"* && "$ISSUES" != *"0 errors"* ]]; then
  # Report lint issues as context for Claude to fix
  jq -n --arg issues "$ISSUES" --arg file "$FILE_PATH" '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "additionalContext": ("Lint issues found in " + $file + ":\n" + $issues + "\nPlease fix these issues.")
    }
  }'
else
  exit 0
fi
