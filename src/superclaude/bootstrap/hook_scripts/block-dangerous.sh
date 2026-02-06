#!/bin/bash
# PreToolUse hook: Block destructive and dangerous commands
# Prevents accidental rm -rf, force pushes, database drops, etc.
#
# Matcher: Bash
# Event: PreToolUse

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

deny_with_reason() {
  jq -n --arg reason "$1" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": $reason
    }
  }'
  exit 0
}

# Block rm -rf on sensitive paths
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+)*(\/|~|\$HOME|\.\.)'; then
  deny_with_reason "Blocked: recursive force-delete on sensitive path. Be more specific about what to delete."
fi

# Block force push
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*(-f|--force)'; then
  deny_with_reason "Blocked: force push can destroy remote history. Use --force-with-lease if you must overwrite."
fi

# Block git reset --hard without specific ref
if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard\s*$'; then
  deny_with_reason "Blocked: 'git reset --hard' without a ref discards all uncommitted work. Specify a commit hash."
fi

# Block git clean -f on root
if echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
  deny_with_reason "Blocked: 'git clean -f' permanently deletes untracked files. Use 'git clean -n' to preview first."
fi

# Block database drops
if echo "$COMMAND" | grep -qiE '(drop\s+(database|table|schema)|truncate\s+table)'; then
  deny_with_reason "Blocked: destructive database operation. Confirm intent with the developer first."
fi

# Block overwriting .env files
if echo "$COMMAND" | grep -qE '(>|tee)\s+\.env'; then
  deny_with_reason "Blocked: overwriting .env file could destroy secrets. Use append (>>) or edit specific values."
fi

# Block killing all processes
if echo "$COMMAND" | grep -qE '(killall|pkill\s+-9|kill\s+-9\s+-1)'; then
  deny_with_reason "Blocked: mass process kill. Target specific PIDs instead."
fi

# Block chmod/chown on sensitive paths
if echo "$COMMAND" | grep -qE '(chmod|chown)\s+.*(-R|--recursive)\s+(/|/etc|/usr|/var)'; then
  deny_with_reason "Blocked: recursive permission change on system directory."
fi

# Warn (but allow via ask) for potentially risky commands
warn_and_ask() {
  jq -n --arg reason "$1" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "ask",
      "permissionDecisionReason": $reason
    }
  }'
  exit 0
}

# Flag pip install (should use uv in this project)
if echo "$COMMAND" | grep -qE '^pip\s+install|^python\s+-m\s+pip'; then
  warn_and_ask "This project uses UV for package management. Consider using 'uv pip install' instead."
fi

# Flag direct python execution (should use uv run)
if echo "$COMMAND" | grep -qE '^python\s+((?!-c).)+\.py'; then
  warn_and_ask "This project uses UV. Consider using 'uv run python script.py' instead."
fi

# All clear
exit 0
