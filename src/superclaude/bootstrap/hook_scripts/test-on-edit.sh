#!/bin/bash
# PostToolUse hook (async): Run related tests after file changes
# Runs in the background so Claude can keep working.
#
# Matcher: Write|Edit
# Event: PostToolUse
# Async: true

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"
BASENAME=$(basename "$FILE_PATH" ".$EXT")
DIR=$(dirname "$FILE_PATH")

run_related_tests() {
  local test_result=""
  local exit_code=0

  case "$EXT" in
    py)
      # Find related test file
      local test_file=""
      for candidate in \
        "${DIR}/test_${BASENAME}.py" \
        "${DIR}/tests/test_${BASENAME}.py" \
        "tests/test_${BASENAME}.py" \
        "tests/unit/test_${BASENAME}.py" \
        "tests/integration/test_${BASENAME}.py"; do
        if [[ -f "$candidate" ]]; then
          test_file="$candidate"
          break
        fi
      done

      if [[ -n "$test_file" ]]; then
        if command -v uv &>/dev/null; then
          test_result=$(uv run pytest "$test_file" -x --tb=short 2>&1) || exit_code=$?
        else
          test_result=$(python -m pytest "$test_file" -x --tb=short 2>&1) || exit_code=$?
        fi
      fi
      ;;
    js|jsx|ts|tsx)
      local test_file=""
      for candidate in \
        "${DIR}/${BASENAME}.test.${EXT}" \
        "${DIR}/${BASENAME}.spec.${EXT}" \
        "${DIR}/__tests__/${BASENAME}.test.${EXT}" \
        "tests/${BASENAME}.test.${EXT}"; do
        if [[ -f "$candidate" ]]; then
          test_file="$candidate"
          break
        fi
      done

      if [[ -n "$test_file" ]]; then
        if command -v npx &>/dev/null; then
          # Try vitest first, then jest
          if [[ -f "vitest.config.ts" || -f "vitest.config.js" ]]; then
            test_result=$(npx vitest run "$test_file" 2>&1) || exit_code=$?
          else
            test_result=$(npx jest "$test_file" --no-coverage 2>&1) || exit_code=$?
          fi
        fi
      fi
      ;;
    *)
      exit 0
      ;;
  esac

  if [[ -n "$test_result" ]]; then
    if [[ $exit_code -eq 0 ]]; then
      echo "{\"systemMessage\": \"Tests passed for ${BASENAME}\"}"
    else
      # Truncate long output to avoid overwhelming context
      local truncated=$(echo "$test_result" | tail -30)
      jq -n --arg result "$truncated" --arg file "$BASENAME" \
        '{"systemMessage": ("Tests FAILED for " + $file + ":\n" + $result)}'
    fi
  fi
}

run_related_tests
