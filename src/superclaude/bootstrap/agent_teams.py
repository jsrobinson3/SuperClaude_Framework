"""
Agent Teams Configuration

Configures Claude Code's experimental agent teams feature.
Enables the feature flag, installs team-oriented slash commands,
and adds agent team patterns to CLAUDE.md.

Based on patterns from:
- Official docs: https://code.claude.com/docs/en/agent-teams
- C compiler project: 16 parallel agents building 100K lines
  (https://www.anthropic.com/engineering/building-c-compiler)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Agent Team Slash Commands ──────────────────────────────────────────

TEAM_COMMANDS: Dict[str, Dict[str, str]] = {
    "team-review": {
        "filename": "team-review.md",
        "description": "Parallel code review with specialized reviewers",
        "content": """\
Create an agent team to review the current changes. Target: $ARGUMENTS

Spawn three reviewer teammates, each with a distinct lens:
- **Security reviewer**: Focus on auth, input validation, injection risks, secret handling, OWASP top 10.
- **Quality reviewer**: Focus on code patterns, maintainability, naming, SOLID principles, test coverage.
- **Performance reviewer**: Focus on N+1 queries, memory leaks, unnecessary allocations, algorithmic complexity.

Instructions for the team:
1. Each reviewer works from git diff of the current branch vs the base branch
2. Reviewers should challenge each other's findings — if one flags something, others should verify or dispute
3. After all reviewers finish, synthesize into a single review summary with severity ratings:
   - CRITICAL: must fix before merge
   - WARNING: should fix, acceptable to defer
   - INFO: suggestion for improvement
4. Present the consolidated review with file paths and line numbers
""",
    },
    "team-debug": {
        "filename": "team-debug.md",
        "description": "Debug with competing hypotheses in parallel",
        "content": """\
Create an agent team to investigate a bug with competing hypotheses. Bug: $ARGUMENTS

Spawn 3-5 investigator teammates, each pursuing a different hypothesis:
- Have each teammate form an independent theory about the root cause
- Teammates should actively try to DISPROVE each other's theories
- This adversarial approach prevents anchoring on the first plausible explanation

Instructions for the team:
1. Lead breaks down the symptom into possible cause categories (data, logic, timing, config, dependency)
2. Each teammate investigates one category independently
3. Teammates share evidence and challenge each other's findings
4. The theory that survives disproval attempts is most likely the real root cause
5. Once consensus emerges, one teammate implements the fix while another writes the test
6. Present: root cause, evidence, fix, and test coverage
""",
    },
    "team-build": {
        "filename": "team-build.md",
        "description": "Parallel feature implementation with owned modules",
        "content": """\
Create an agent team to build a feature in parallel. Feature: $ARGUMENTS

Use the C-compiler pattern: decompose into independent modules, each owned by one teammate.

Instructions for the team:
1. Lead uses Sequential Thinking to decompose the feature into independent units:
   - Each unit should touch DIFFERENT files (avoid merge conflicts)
   - Identify interfaces/contracts between units upfront
   - Create a task list with 5-6 tasks per teammate
2. Spawn teammates, each owning a distinct layer:
   - Data models / types / schemas
   - Business logic / service layer
   - API routes / controllers
   - Tests (unit + integration)
   - Documentation / migration scripts (if needed)
3. Require plan approval before teammates start implementing
4. Each teammate follows the patterns in CLAUDE.md
5. After implementation, run the full test suite to catch integration issues
6. If tests break, assign failing tests to individual teammates (trivially parallel)
7. Present: files created, test results, integration status
""",
    },
    "team-research": {
        "filename": "team-research.md",
        "description": "Parallel research from multiple angles",
        "content": """\
Create an agent team to research a topic from multiple angles. Topic: $ARGUMENTS

Spawn teammates with different research perspectives:
- **Advocate**: find evidence supporting this approach, best practices, success stories
- **Critic**: find evidence against, failure modes, risks, alternatives
- **Practitioner**: find real-world implementations, code examples, libraries
- **Architect**: evaluate system design implications, scalability, maintainability

Instructions for the team:
1. Each teammate researches independently using available tools
2. Teammates share findings and debate trade-offs
3. Synthesize into a decision document:
   - Recommendation with confidence level
   - Pros/cons matrix
   - Risk assessment
   - Suggested implementation approach
   - Links to sources and references
""",
    },
    "team-refactor": {
        "filename": "team-refactor.md",
        "description": "Safe parallel refactoring with file ownership",
        "content": """\
Create an agent team to refactor code safely in parallel. Target: $ARGUMENTS

Key principle: each teammate OWNS a set of files. No two teammates edit the same file.

Instructions for the team:
1. Lead analyzes the refactoring scope and creates a file ownership map
2. Spawn teammates, each assigned specific files/modules:
   - Assign 5-6 tasks per teammate for steady progress
   - Include "update tests" as a task for each module owner
3. Require plan approval — reject plans that modify files owned by another teammate
4. Each teammate:
   - Refactors their owned files
   - Updates corresponding tests
   - Runs tests on their module
5. After all teammates finish, run the full test suite
6. If integration tests fail, the lead assigns cross-module fixes
7. Present: what changed, test results, before/after metrics
""",
    },
}

# ── Agent Teams Settings ───────────────────────────────────────────────

AGENT_TEAMS_SETTINGS = {
    "env": {
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    },
    "teammateMode": "auto",
}


class AgentTeamsConfigurator:
    """Configures Claude Code agent teams support."""

    def __init__(self, project_dir: Optional[str] = None, scope: str = "project"):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.home_dir = Path.home()
        self.scope = scope

        if scope == "user":
            self.settings_path = self.home_dir / ".claude" / "settings.json"
        elif scope == "local":
            self.settings_path = self.project_dir / ".claude" / "settings.local.json"
        else:
            self.settings_path = self.project_dir / ".claude" / "settings.json"

        self.commands_dir = self.project_dir / ".claude" / "commands"

    def install(
        self,
        enable_feature: bool = True,
        install_commands: bool = True,
        teammate_mode: str = "auto",
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Configure agent teams support.

        - Enables the experimental feature flag in settings.json
        - Installs team-oriented slash commands
        """
        parts = []

        if enable_feature:
            result = self._enable_feature_flag(teammate_mode, dry_run)
            parts.append(result)

        if install_commands:
            result = self._install_commands(dry_run)
            parts.append(result)

        return True, "\n".join(parts)

    def list_commands(self) -> List[Dict[str, str]]:
        """List available agent team commands."""
        result = []
        for name, tmpl in TEAM_COMMANDS.items():
            installed = (self.commands_dir / tmpl["filename"]).exists()
            result.append({
                "name": name,
                "filename": tmpl["filename"],
                "description": tmpl["description"],
                "installed": installed,
            })
        return result

    def generate_claude_md_section(self) -> str:
        """Generate CLAUDE.md section for agent teams best practices."""
        return """\
## Agent Teams — Parallel Work Patterns

This project has agent teams enabled. Use them for tasks where parallel
exploration adds real value. Don't use them for sequential work or when
teammates would need to edit the same files.

### When to Use Agent Teams
- Code review (security + quality + performance reviewers)
- Bug investigation (competing hypotheses)
- New features with independent modules
- Research from multiple angles
- Large refactors with clear file ownership

### When NOT to Use Agent Teams
- Sequential tasks with dependencies between steps
- Same-file edits (use a single session instead)
- Small, focused tasks (overhead > benefit)

### Key Patterns

**File ownership**: Each teammate owns a distinct set of files. No two
teammates should edit the same file — this prevents merge conflicts and
overwrites.

**Plan approval**: For risky work, require teammates to plan before
implementing. Review and approve plans before they start coding.

**Task sizing**: 5-6 tasks per teammate keeps everyone productive.
Too few tasks = idle teammates. Too many = lost context.

**Testing harness** (from the C compiler pattern): When many tests fail,
assign each failing test to a different teammate — trivially parallel.
Use `--fast` sampling (1-10% of tests) during development, full suite
before merging.

### Available Team Commands
- `/team-review` — Parallel code review with specialized reviewers
- `/team-debug` — Debug with competing hypotheses
- `/team-build` — Parallel feature implementation with owned modules
- `/team-research` — Multi-angle research and decision-making
- `/team-refactor` — Safe parallel refactoring with file ownership
"""

    # ── Private ────────────────────────────────────────────────────────

    def _enable_feature_flag(self, teammate_mode: str, dry_run: bool) -> str:
        """Enable agent teams in settings.json."""
        if dry_run:
            return (
                f"Would enable CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in {self.settings_path}\n"
                f"Would set teammateMode to '{teammate_mode}'"
            )

        settings = self._load_settings()

        # Merge env vars
        if "env" not in settings:
            settings["env"] = {}
        settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"

        # Set teammate mode
        settings["teammateMode"] = teammate_mode

        self._save_settings(settings)
        return f"Enabled agent teams in {self.settings_path} (mode: {teammate_mode})"

    def _install_commands(self, dry_run: bool) -> str:
        """Install team slash commands."""
        if dry_run:
            lines = [f"Would install {len(TEAM_COMMANDS)} team command(s):"]
            for name, tmpl in TEAM_COMMANDS.items():
                lines.append(f"  /{name:20} {tmpl['description']}")
            return "\n".join(lines)

        self.commands_dir.mkdir(parents=True, exist_ok=True)

        installed = []
        skipped = []
        for name, tmpl in TEAM_COMMANDS.items():
            path = self.commands_dir / tmpl["filename"]
            if path.exists():
                skipped.append(name)
                continue
            path.write_text(tmpl["content"])
            installed.append(name)

        parts = []
        if installed:
            parts.append(f"Installed team commands: {', '.join(installed)}")
        if skipped:
            parts.append(f"Already exists (skipped): {', '.join(skipped)}")
        return "\n".join(parts)

    def _load_settings(self) -> Dict[str, Any]:
        if self.settings_path.exists():
            try:
                return json.loads(self.settings_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_settings(self, settings: Dict[str, Any]):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(settings, indent=2) + "\n")
