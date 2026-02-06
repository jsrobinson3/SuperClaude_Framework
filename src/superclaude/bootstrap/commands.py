"""
Slash Command Scaffolder

Generates project-specific slash commands for Claude Code.
Commands are installed to .claude/commands/ in the project directory.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Command Templates ──────────────────────────────────────────────────

COMMAND_TEMPLATES: Dict[str, Dict[str, str]] = {
    "skills": {
        "filename": "skills.md",
        "description": "Extract and update codebase patterns in CLAUDE.md",
        "content": """\
Analyze the current codebase and update CLAUDE.md with extracted patterns.

1. Use Sequential Thinking to plan the analysis approach
2. Search the codebase for repeated structural patterns:
   - API/route handler patterns
   - Service/business logic patterns
   - Data model/schema patterns
   - Test file patterns
   - Error handling patterns
   - Configuration patterns
   - Middleware patterns
   - Validation patterns
3. For each pattern, extract:
   - A descriptive name
   - The template structure with placeholders
   - 2-3 real file paths as examples
   - When to use vs when NOT to use
4. Update the "Codebase Skills/Patterns" section of ./CLAUDE.md
5. Present a summary of patterns found and updated
""",
    },
    "newfeature": {
        "filename": "newfeature.md",
        "description": "Scaffold a new feature using established patterns",
        "content": """\
Scaffold a new feature using established codebase patterns. Feature: $ARGUMENTS

1. Use Sequential Thinking to plan the feature implementation
2. Read ./CLAUDE.md for all established patterns and conventions
3. Search the codebase for similar existing features to use as reference
4. Scaffold all required files following the established patterns:
   - Route/controller (if applicable)
   - Service layer
   - Data model/types
   - Tests (unit + integration)
   - Validation
5. Run the project's linter on all generated files
6. Present summary:
   - Files created/modified
   - Pattern sources used
   - Suggested next steps
""",
    },
    "diagnose": {
        "filename": "diagnose.md",
        "description": "Debug and diagnose an issue",
        "content": """\
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
""",
    },
    "review": {
        "filename": "review.md",
        "description": "Review current changes for quality and consistency",
        "content": """\
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
""",
    },
    "standup": {
        "filename": "standup.md",
        "description": "Morning context load for development session",
        "content": """\
Load context for my development session.

1. Check git log for recent commits to understand what changed
2. Check git status for any work in progress
3. Check for any failing tests
4. Present a concise morning briefing:
   - What was last worked on (from git log)
   - Current branch and status
   - Any test failures
   - Suggested priorities for today
""",
    },
    "localllm": {
        "filename": "localllm.md",
        "description": "Offload bulk tasks to local LLM via Ollama",
        "content": """\
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
""",
    },
}


class CommandScaffolder:
    """Scaffolds slash commands into .claude/commands/."""

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.commands_dir = self.project_dir / ".claude" / "commands"

    def list_templates(self) -> List[Dict[str, str]]:
        """List available command templates."""
        result = []
        for name, tmpl in COMMAND_TEMPLATES.items():
            installed = (self.commands_dir / tmpl["filename"]).exists()
            result.append({
                "name": name,
                "filename": tmpl["filename"],
                "description": tmpl["description"],
                "installed": installed,
            })
        return result

    def install(
        self,
        command_names: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Install slash commands to .claude/commands/.

        Does not overwrite existing files.
        """
        if command_names is None:
            command_names = list(COMMAND_TEMPLATES.keys())

        # Validate
        invalid = [n for n in command_names if n not in COMMAND_TEMPLATES]
        if invalid:
            return False, f"Unknown command(s): {', '.join(invalid)}"

        if dry_run:
            lines = [f"Would install {len(command_names)} command(s) to {self.commands_dir}:", ""]
            for name in command_names:
                tmpl = COMMAND_TEMPLATES[name]
                exists = (self.commands_dir / tmpl["filename"]).exists()
                status = " (already exists, skip)" if exists else ""
                lines.append(f"  /{tmpl['filename'].replace('.md',''):20} {tmpl['description']}{status}")
            return True, "\n".join(lines)

        self.commands_dir.mkdir(parents=True, exist_ok=True)

        installed = []
        skipped = []

        for name in command_names:
            tmpl = COMMAND_TEMPLATES[name]
            path = self.commands_dir / tmpl["filename"]

            if path.exists():
                skipped.append(name)
                continue

            path.write_text(tmpl["content"])
            installed.append(name)

        parts = []
        if installed:
            parts.append(f"Installed: {', '.join(installed)}")
        if skipped:
            parts.append(f"Already exists (skipped): {', '.join(skipped)}")
        parts.append(f"Location: {self.commands_dir}")

        return True, "\n".join(parts)

    def install_custom(
        self, name: str, content: str, dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Install a custom slash command."""
        # Reject names with path separators or traversal attempts
        if "/" in name or "\\" in name or ".." in name:
            return False, f"Invalid command name: {name}"

        filename = f"{name}.md"
        path = self.commands_dir / filename

        # Verify resolved path stays within commands_dir
        if not path.resolve().is_relative_to(self.commands_dir.resolve()):
            return False, f"Invalid command name: {name}"

        if dry_run:
            return True, f"Would create {path}"

        self.commands_dir.mkdir(parents=True, exist_ok=True)

        if path.exists():
            return False, f"Command '{name}' already exists at {path}"

        path.write_text(content)
        return True, f"Created {path}"
