"""
Agent Teams Configuration

Configures Claude Code's experimental agent teams feature with
specialized agent roles derived from project analysis.

The key idea (from Anthropic's C compiler project): each agent has a
distinct SPECIALIZATION, not just a file/repo assignment. Roles like
"deduplicator", "performance optimizer", "code quality critic" produce
better results than generic "frontend agent" / "backend agent".

Roles are selected based on what the project analysis reveals:
- Python project with pytest → test coverage agent, type safety agent
- JS/TS project → bundle size agent, accessibility agent
- Any project with linters → code quality critic using those linters
- Any project with Docker → infrastructure agent

Based on:
- Official docs: https://code.claude.com/docs/en/agent-teams
- C compiler project: https://www.anthropic.com/engineering/building-c-compiler
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Specialist Role Definitions ────────────────────────────────────────
# Each role has:
#   - A spawn prompt describing the agent's specialization
#   - Conditions under which the role is relevant (detected from analysis)
#   - Whether it's always-on or project-dependent

SPECIALIST_ROLES: Dict[str, Dict[str, Any]] = {
    "deduplicator": {
        "title": "Code Deduplicator",
        "spawn_prompt": (
            "You are the deduplication specialist. Your job is to find and coalesce "
            "duplicate or near-duplicate code across the codebase. Search for functions "
            "that do similar things with slight variations, copy-pasted logic, and "
            "repeated patterns that should be abstracted. When you find duplicates, "
            "extract them into shared utilities or base classes. Run the test suite "
            "after each change to ensure nothing breaks."
        ),
        "when": "always",
        "category": "quality",
    },
    "quality-critic": {
        "title": "Code Quality Critic",
        "spawn_prompt": (
            "You are the code quality critic. Review the codebase from the perspective "
            "of an experienced {language} developer. Focus on: naming clarity, single "
            "responsibility, unnecessary complexity, dead code, inconsistent patterns, "
            "and violations of the project's own conventions (see CLAUDE.md). Make "
            "structural improvements. {linter_instruction}"
        ),
        "when": "always",
        "category": "quality",
    },
    "test-coverage": {
        "title": "Test Coverage Agent",
        "spawn_prompt": (
            "You are the test coverage specialist. Your job is to find untested code "
            "paths and write tests for them. Use '{test_command}' to run the suite. "
            "Focus on: uncovered branches, edge cases, error paths, and integration "
            "points. Write tests that follow the patterns in the existing test suite "
            "at {test_dir}/. Prioritize tests that would have caught real bugs."
        ),
        "when": "has_tests",
        "category": "quality",
    },
    "performance": {
        "title": "Performance Optimizer",
        "spawn_prompt": (
            "You are the performance specialist. Profile and optimize the codebase "
            "for speed and resource efficiency. Look for: unnecessary allocations, "
            "N+1 query patterns, missing caching opportunities, expensive operations "
            "in hot paths, and algorithmic improvements. Benchmark before and after "
            "each change. Don't micro-optimize — focus on changes with measurable impact."
        ),
        "when": "always",
        "category": "performance",
    },
    "security-auditor": {
        "title": "Security Auditor",
        "spawn_prompt": (
            "You are the security auditor. Scan the codebase for vulnerabilities: "
            "injection risks (SQL, command, XSS), authentication/authorization flaws, "
            "hardcoded secrets, insecure dependencies, missing input validation, "
            "and OWASP Top 10 issues. For each finding, implement the fix and "
            "write a test that verifies the vulnerability is closed."
        ),
        "when": "always",
        "category": "security",
    },
    "documentation": {
        "title": "Documentation Writer",
        "spawn_prompt": (
            "You are the documentation specialist. Find undocumented or poorly "
            "documented public APIs, modules, and complex logic. Write clear "
            "docstrings, update README sections, and add inline comments only "
            "where the logic is non-obvious. Follow the existing documentation "
            "style in the project. Don't over-document trivial code."
        ),
        "when": "always",
        "category": "docs",
    },
    "type-safety": {
        "title": "Type Safety Agent",
        "spawn_prompt": (
            "You are the type safety specialist. Add or fix type annotations "
            "throughout the codebase. Use '{type_checker}' to find type errors. "
            "Focus on: missing return types, Any types that should be specific, "
            "incorrect generics, and union types that can be narrowed. Run the "
            "type checker after each change to ensure you're making progress."
        ),
        "when": "has_type_checker",
        "category": "quality",
    },
    "dependency-updater": {
        "title": "Dependency Updater",
        "spawn_prompt": (
            "You are the dependency management specialist. Audit all project "
            "dependencies for: outdated versions with security patches, unused "
            "dependencies that can be removed, dependencies that can be consolidated, "
            "and license compliance. Update one dependency at a time and run the "
            "test suite after each update to catch breakage immediately."
        ),
        "when": "always",
        "category": "maintenance",
    },
    "api-consistency": {
        "title": "API Consistency Agent",
        "spawn_prompt": (
            "You are the API consistency specialist. Review all API endpoints, "
            "function signatures, and public interfaces for consistency: naming "
            "conventions, error response formats, parameter ordering, HTTP methods, "
            "status codes, and documentation. Make interfaces consistent without "
            "breaking existing callers."
        ),
        "when": "has_api",
        "category": "quality",
    },
}

# ── Team Slash Commands ────────────────────────────────────────────────

TEAM_COMMANDS: Dict[str, Dict[str, str]] = {
    "team-sync": {
        "filename": "team-sync.md",
        "description": "Sync API contracts between frontend and backend in monorepo",
        "content": """\
Create an agent team to ensure API contracts are synchronized across subprojects.

Arguments: $ARGUMENTS (e.g., "OMS-Frontend OMS-Backend" or "all")

## Purpose

In monorepos with multiple frontends/backends, API changes in one subproject must be
reflected in consuming subprojects. This command coordinates the sync.

## Instructions

1. **Identify API surfaces**:
   - Backend: OpenAPI/Swagger specs, GraphQL schemas, REST endpoints, gRPC protos
   - Frontend: API client code, TypeScript interfaces, request/response types

2. **Spawn specialist pairs**:
   - Backend api-consistency agent: owns the API definition
   - Frontend api-consistency agent: owns the client implementation
   - Agents communicate via mailbox to agree on contract changes

3. **Detect drift**:
   - Compare backend API spec to frontend types
   - Flag mismatches: missing fields, type differences, removed endpoints
   - Check for breaking changes vs. backwards-compatible additions

4. **Coordinate updates**:
   - For breaking changes: update backend + all consuming frontends atomically
   - For additions: update backend first, then frontends opt-in
   - Generate TypeScript types from OpenAPI/GraphQL automatically if possible

5. **Validation**:
   - Run integration tests that call real backend from frontend
   - Check for runtime type errors
   - Verify all consumers are updated

## Example Workflow

Backend agent: "I'm adding a new `domain.status` field to the API"
Frontend agent: "Acknowledged, updating TypeScript interfaces and UI to display status"
Backend agent: "Deployed, here's the updated OpenAPI spec"
Frontend agent: "Generated types, tests passing, deploying frontend"

## Output

Present a sync report:
- API changes detected
- Affected subprojects
- Changes made to each subproject
- Test results
- Breaking changes (if any)
""",
    },
    "team-review": {
        "filename": "team-review.md",
        "description": "Parallel code review with specialized reviewers",
        "content": """\
Create an agent team to review the current changes. Target: $ARGUMENTS

Read .claude/teams.json for the configured specialist roles in this project.

Spawn reviewer teammates using these roles from teams.json:
- **security-auditor**: auth, injection, OWASP top 10
- **quality-critic**: patterns, naming, complexity, conventions from CLAUDE.md
- **performance**: N+1 queries, allocations, algorithmic complexity

Use each role's spawn_prompt from teams.json when creating the teammate.

Instructions:
1. Each reviewer works from git diff of the current branch vs the base branch
2. Reviewers challenge each other's findings — verify or dispute
3. Synthesize into a single review with severity ratings:
   - CRITICAL: must fix before merge
   - WARNING: should fix, acceptable to defer
   - INFO: suggestion for improvement
4. Present consolidated review with file paths and line numbers
""",
    },
    "team-debug": {
        "filename": "team-debug.md",
        "description": "Debug with competing hypotheses in parallel",
        "content": """\
Create an agent team to investigate a bug with competing hypotheses. Bug: $ARGUMENTS

Spawn 3-5 investigator teammates. Each pursues a DIFFERENT theory about the root cause.
Teammates should actively try to DISPROVE each other's theories — this adversarial
approach prevents anchoring on the first plausible explanation.

Instructions:
1. Lead decomposes the symptom into cause categories (data, logic, timing, config, dependency)
2. Each teammate investigates one category independently
3. Teammates share evidence and challenge each other
4. The theory that survives disproval is most likely the real cause
5. Once consensus emerges, one teammate fixes while another writes the test
6. Present: root cause, evidence, fix, test coverage
""",
    },
    "team-build": {
        "filename": "team-build.md",
        "description": "Parallel feature build with specialist roles",
        "content": """\
Create an agent team to build a feature with specialized roles.

Arguments: $ARGUMENTS

## Argument Parsing

Parse the arguments to extract:
1. **Subprojects** (if specified): Look for directory names at the start (e.g., "OMS-Frontend OMS-Backend")
2. **Feature description**: The main task description
3. **Jira ticket** (if specified): Pattern like "Jira: OMS-1234" or "JIRA-1234"

Examples:
- `/team-build OMS-Frontend OMS-Backend feature: add visual syncing of domains Jira: OMS-1234`
- `/team-build feature: improve error handling` (auto-detect affected projects)
- `/team-build OCConnect-Chrome-Extension bug: fix popup not opening`

## Monorepo Auto-Detection

If subprojects are NOT explicitly specified:
1. Check `git diff` to see which directories have changes
2. Or ask the user which subproject(s) to work on
3. List available subprojects from directory structure

## Team Coordination

Read `.claude/teams.json` from the root AND each affected subproject.

For cross-project features:
- Each subproject gets its own team of specialists
- Teams coordinate via shared task list and mailbox
- Example: Frontend team implements UI, Backend team implements API, they sync on contract

Use the C-compiler pattern: decompose into independent work, each owned by one specialist.

Instructions:
1. Lead decomposes the feature into independent implementation tasks
2. For each subproject, assign tasks to specialist roles from that subproject's teams.json
3. Each teammate OWNS distinct files — no two edit the same file (prevents conflicts)
4. Require plan approval before implementation starts
5. After implementation, spawn test-coverage specialists per subproject to verify
6. If tests fail, assign each failure to a different teammate (trivially parallel)
7. Present: files created, test results, integration status

Additional specialist roles to spawn alongside the implementers:
- **deduplicator**: runs after implementation to coalesce any duplicate code
- **quality-critic**: reviews the new code against project conventions
- **api-consistency**: if API changes, ensures contracts match between frontend/backend

## Jira Integration

If a Jira ticket is specified:
- Include ticket number in all commit messages
- Reference ticket in PR description
- Update ticket with progress/blockers
""",
    },
    "team-research": {
        "filename": "team-research.md",
        "description": "Parallel research from multiple angles",
        "content": """\
Create an agent team to research a topic from multiple angles. Topic: $ARGUMENTS

Spawn teammates with different perspectives:
- **Advocate**: evidence supporting this approach, best practices, success stories
- **Critic**: evidence against, failure modes, risks, alternatives
- **Practitioner**: real-world implementations, code examples, libraries
- **Architect**: system design implications, scalability, maintainability

Instructions:
1. Each teammate researches independently
2. Teammates share findings and debate trade-offs
3. Synthesize into a decision document:
   - Recommendation with confidence level
   - Pros/cons matrix
   - Risk assessment
   - Implementation approach
""",
    },
    "team-refactor": {
        "filename": "team-refactor.md",
        "description": "Safe parallel refactoring with specialist roles",
        "content": """\
Create an agent team to refactor code with specialist roles. Target: $ARGUMENTS

Read .claude/teams.json for this project's specialist roles.

Instructions:
1. Lead creates a file ownership map — each teammate owns distinct files
2. Spawn specialists from teams.json:
   - **quality-critic**: owns the structural refactoring
   - **deduplicator**: owns extracting shared code
   - **test-coverage**: owns updating and expanding tests
   - **documentation**: owns updating docs for changed interfaces
3. Require plan approval — reject plans that modify files owned by another teammate
4. After all finish, run the full test suite
5. Present: what changed, before/after metrics, test results
""",
    },
}


class AgentTeamsConfigurator:
    """Configures Claude Code agent teams with project-aware specialist roles."""

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
        self.teams_config_path = self.project_dir / ".claude" / "teams.json"

    def install(
        self,
        analysis: Optional[Dict[str, Any]] = None,
        teammate_mode: str = "auto",
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Configure agent teams.

        1. Enables the experimental feature flag
        2. Selects specialist roles based on project analysis
        3. Writes teams.json with role definitions and spawn prompts
        4. Installs team slash commands
        """
        parts = []

        # Enable feature flag
        parts.append(self._enable_feature_flag(teammate_mode, dry_run))

        # Select and configure roles
        roles = self._select_roles(analysis)
        parts.append(self._write_teams_config(roles, dry_run))

        # Install commands
        parts.append(self._install_commands(dry_run))

        return True, "\n".join(parts)

    def _select_roles(self, analysis: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Select specialist roles relevant to this project."""
        selected = []

        # Build context for template substitution
        context = self._build_context(analysis)

        for role_id, role_def in SPECIALIST_ROLES.items():
            condition = role_def["when"]

            if condition == "always":
                pass  # Always include
            elif condition == "has_tests" and not context.get("test_command"):
                continue
            elif condition == "has_type_checker" and not context.get("type_checker"):
                continue
            elif condition == "has_api" and not context.get("has_api"):
                continue

            # Format spawn prompt with project-specific context
            prompt = role_def["spawn_prompt"].format(**context)

            selected.append({
                "id": role_id,
                "title": role_def["title"],
                "spawn_prompt": prompt,
                "category": role_def["category"],
            })

        return selected

    def _build_context(self, analysis: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Build template context from project analysis."""
        ctx: Dict[str, str] = {
            "language": "the project's primary language",
            "linter_instruction": "",
            "test_command": "",
            "test_dir": "tests",
            "type_checker": "",
            "has_api": "",
        }

        if not analysis:
            return ctx

        # Language
        langs = analysis.get("languages", [])
        primary = next((lang["name"] for lang in langs if lang.get("primary")), None)
        if primary:
            ctx["language"] = primary

        # Linters
        linters = [lint["name"] for lint in analysis.get("linters", [])]
        if linters:
            ctx["linter_instruction"] = (
                f"Use {', '.join(linters)} to validate your changes."
            )

        # Type checker
        if "mypy" in linters:
            ctx["type_checker"] = "mypy"
        elif "pyright" in linters:
            ctx["type_checker"] = "pyright"

        # Test framework
        test_fws = analysis.get("test_frameworks", [])
        if test_fws:
            tf = test_fws[0]
            if tf["name"] == "pytest":
                pkg_mgrs = [p["name"] for p in analysis.get("package_managers", [])]
                if "uv" in pkg_mgrs:
                    ctx["test_command"] = "uv run pytest"
                else:
                    ctx["test_command"] = "pytest"
            elif tf["name"] in ("jest", "vitest"):
                ctx["test_command"] = f"npx {tf['name']}"
            else:
                ctx["test_command"] = tf["name"]

            if tf.get("test_dirs"):
                ctx["test_dir"] = tf["test_dirs"][0]

        # API detection (check for frameworks that imply API routes)
        frameworks = [f["name"] for f in analysis.get("frameworks", [])]
        api_frameworks = {"fastapi", "flask", "django", "Express", "NestJS", "Next.js"}
        if any(f in api_frameworks for f in frameworks):
            ctx["has_api"] = "true"

        return ctx

    def _write_teams_config(
        self, roles: List[Dict[str, Any]], dry_run: bool
    ) -> str:
        """Write teams.json with selected specialist roles."""
        config = {
            "_comment": (
                "Agent team specialist roles for this project. "
                "Generated by superclaude bootstrap. "
                "Edit spawn_prompt to customize each role's behavior."
            ),
            "roles": {r["id"]: r for r in roles},
        }

        if dry_run:
            lines = [f"Would write {len(roles)} specialist role(s) to {self.teams_config_path}:"]
            for r in roles:
                lines.append(f"  {r['title']:30} [{r['category']}]")
            return "\n".join(lines)

        self.teams_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.teams_config_path.write_text(json.dumps(config, indent=2) + "\n")
        return f"Wrote {len(roles)} specialist roles to {self.teams_config_path}"

    def _enable_feature_flag(self, teammate_mode: str, dry_run: bool) -> str:
        """Enable agent teams in settings.json."""
        if dry_run:
            return (
                f"Would enable CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in {self.settings_path}\n"
                f"Would set teammateMode to '{teammate_mode}'"
            )

        settings = self._load_settings()
        if "env" not in settings:
            settings["env"] = {}
        settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
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

    # ── Settings I/O ───────────────────────────────────────────────────

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
