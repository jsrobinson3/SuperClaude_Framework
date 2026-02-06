Diagnose and fix an issue. Issue: $ARGUMENTS

1. Use Sequential Thinking to break down the problem
2. Search for all code paths related to the issue
3. If Docker containers are involved, check container logs
4. Identify the root cause and plan the fix
5. Implement the fix following codebase patterns from CLAUDE.md
6. Write or update tests to cover the failure case
7. Run the linter on changed files
8. Present:
   - Root cause analysis
   - What was changed and why
   - Test coverage for the fix
