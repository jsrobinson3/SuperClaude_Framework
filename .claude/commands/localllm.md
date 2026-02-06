Use the local LLM for bulk processing tasks that don't need Claude-level intelligence.
Route these to Ollama (localhost:11434) via the local-llm script. Task: $ARGUMENTS

Available operations:
- **docs**: Generate documentation for undocumented files
- **stubs**: Generate test stubs from interfaces/types
- **patterns**: Extract patterns for CLAUDE.md updates
- **summarize**: Generate file summaries for onboarding

Steps:
1. Check if Ollama is running: `ollama list`
2. Select the appropriate model for the task
3. Process files using the local LLM
4. Review and refine the output
5. Apply results to the codebase
