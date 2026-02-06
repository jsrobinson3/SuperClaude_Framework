Review the current changes for quality and consistency. Focus: $ARGUMENTS

1. Identify all modified/staged files (use git diff or git status)
2. Use Sequential Thinking to plan the review approach
3. For each changed file:
   - Check it follows patterns documented in CLAUDE.md
   - Search for consistency with similar files in the codebase
4. Check test coverage for changed code
5. Present review findings:
   - Pattern compliance: pass/fail for each file
   - Missing tests
   - Suggested improvements
   - Overall: ready to merge / needs work
