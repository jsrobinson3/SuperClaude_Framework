#!/bin/bash
# Stop hook: Verify tests pass before Claude finishes
# Blocks Claude from stopping if tests are failing.
#
# Matcher: (none — fires on all stops)
# Event: Stop

set -euo pipefail

INPUT=$(cat)

# Prevent infinite loops: if stop hook is already active, allow stop
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
  exit 0
fi

# Detect project type and run quick test suite
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // "."')
cd "$PROJECT_DIR"

run_tests() {
  local test_output=""
  local exit_code=0

  # Python (pytest)
  if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]]; then
    if [[ -d "tests" ]]; then
      if command -v uv &>/dev/null; then
        test_output=$(uv run pytest tests/ -x --tb=line -q 2>&1) || exit_code=$?
      elif command -v pytest &>/dev/null; then
        test_output=$(pytest tests/ -x --tb=line -q 2>&1) || exit_code=$?
      fi
    fi
  fi

  # JavaScript/TypeScript
  if [[ -f "package.json" ]] && [[ -z "$test_output" ]]; then
    if command -v npm &>/dev/null; then
      # Check if test script exists in package.json
      has_test=$(jq -r '.scripts.test // empty' package.json 2>/dev/null)
      if [[ -n "$has_test" && "$has_test" != "echo \"Error: no test specified\" && exit 1" ]]; then
        test_output=$(npm test 2>&1) || exit_code=$?
      fi
    fi
  fi

  # Go
  if [[ -f "go.mod" ]] && [[ -z "$test_output" ]]; then
    test_output=$(go test ./... -short 2>&1) || exit_code=$?
  fi

  # Rust
  if [[ -f "Cargo.toml" ]] && [[ -z "$test_output" ]]; then
    test_output=$(cargo test 2>&1) || exit_code=$?
  fi

  echo "$exit_code"
  echo "$test_output"
}

# Only run if there are git changes (don't run tests for read-only sessions)
if git rev-parse --git-dir &>/dev/null; then
  if git diff --quiet && git diff --cached --quiet; then
    # No changes — skip test verification
    exit 0
  fi
fi

RESULT=$(run_tests)
EXIT_CODE=$(echo "$RESULT" | head -1)
TEST_OUTPUT=$(echo "$RESULT" | tail -n +2)

if [[ "$EXIT_CODE" != "0" && -n "$TEST_OUTPUT" ]]; then
  # Tests failed — block Claude from stopping
  TRUNCATED=$(echo "$TEST_OUTPUT" | tail -20)
  jq -n --arg reason "Tests are failing. Please fix before finishing:\n$TRUNCATED" '{
    "decision": "block",
    "reason": $reason
  }'
else
  # Tests pass or no tests found — allow stop
  exit 0
fi
