# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🐍 Python Environment Rules

**CRITICAL**: This project uses **UV** for all Python operations. Never use `python -m`, `pip install`, or `python script.py` directly.

### Required Commands

```bash
# All Python operations must use UV
uv run pytest                    # Run tests
uv run pytest tests/pm_agent/   # Run specific tests
uv pip install package           # Install dependencies
uv run python script.py          # Execute scripts
```

## 📂 Project Structure

**Current v4.2.0 Architecture**: Python package with slash commands

```
# Claude Code Configuration (v4.2.0)
.claude/
├── settings.json        # User settings
└── commands/            # Slash commands (installed via `superclaude install`)
    ├── pm.md
    ├── research.md
    └── index-repo.md

# Python Package
src/superclaude/         # Pytest plugin + CLI tools
├── pytest_plugin.py     # Auto-loaded pytest integration
├── pm_agent/            # confidence.py, self_check.py, reflexion.py
├── execution/           # parallel.py, reflection.py, self_correction.py
└── cli/                 # main.py, doctor.py, install_skill.py

# Project Files
tests/                   # Python test suite
docs/                    # Documentation
scripts/                 # Analysis tools (workflow metrics, A/B testing)
PLANNING.md              # Architecture, absolute rules
TASK.md                  # Current tasks
KNOWLEDGE.md             # Accumulated insights
```

## 🔧 Development Workflow

### Essential Commands

```bash
# Setup
make dev              # Install in editable mode with dev dependencies
make verify           # Verify installation (package, plugin, health)

# Testing
make test             # Run full test suite
uv run pytest tests/pm_agent/ -v              # Run specific directory
uv run pytest tests/test_file.py -v           # Run specific file
uv run pytest -m confidence_check             # Run by marker
uv run pytest --cov=superclaude               # With coverage

# Code Quality
make lint             # Run ruff linter
make format           # Format code with ruff
make doctor           # Health check diagnostics

# MCP Servers
superclaude mcp                              # Interactive install (gateway default)
superclaude mcp --list                       # List available servers
superclaude mcp --servers airis-mcp-gateway  # Install AIRIS Gateway (recommended)
superclaude mcp --servers tavily context7    # Install individual servers

# Plugin Packaging
make build-plugin            # Build plugin artefacts into dist/
make sync-plugin-repo        # Sync artefacts into ../SuperClaude_Plugin

# Maintenance
make clean            # Remove build artifacts
```

## 📦 Core Architecture

### Pytest Plugin (Auto-loaded)

Registered via `pyproject.toml` entry point, automatically available after installation.

**Fixtures**: `confidence_checker`, `self_check_protocol`, `reflexion_pattern`, `token_budget`, `pm_context`

**Auto-markers**:
- Tests in `/unit/` → `@pytest.mark.unit`
- Tests in `/integration/` → `@pytest.mark.integration`

**Custom markers**: `@pytest.mark.confidence_check`, `@pytest.mark.self_check`, `@pytest.mark.reflexion`

### PM Agent - Three Core Patterns

**1. ConfidenceChecker** (src/superclaude/pm_agent/confidence.py)
- Pre-execution confidence assessment: ≥90% required, 70-89% present alternatives, <70% ask questions
- Prevents wrong-direction work, ROI: 25-250x token savings

**2. SelfCheckProtocol** (src/superclaude/pm_agent/self_check.py)
- Post-implementation evidence-based validation
- No speculation - verify with tests/docs

**3. ReflexionPattern** (src/superclaude/pm_agent/reflexion.py)
- Error learning and prevention
- Cross-session pattern matching

### Parallel Execution

**Wave → Checkpoint → Wave pattern** (src/superclaude/execution/parallel.py):
- 3.5x faster than sequential execution
- Automatic dependency analysis
- Example: [Read files in parallel] → Analyze → [Edit files in parallel]

### Slash Commands (v4.2.0)

- Install via: `pipx install superclaude && superclaude install`
- Commands installed to: `~/.claude/commands/`
- Available: `/pm`, `/research`, `/index-repo`, and 27 others

> **Note**: TypeScript plugin system planned for v5.0 ([#419](https://github.com/SuperClaude-Org/SuperClaude_Framework/issues/419))

## 🧪 Testing with PM Agent

### Example Test with Markers

```python
@pytest.mark.confidence_check
def test_feature(confidence_checker):
    """Pre-execution confidence check - skips if < 70%"""
    context = {"test_name": "test_feature", "has_official_docs": True}
    assert confidence_checker.assess(context) >= 0.7

@pytest.mark.self_check
def test_implementation(self_check_protocol):
    """Post-implementation validation with evidence"""
    implementation = {"code": "...", "tests": [...]}
    passed, issues = self_check_protocol.validate(implementation)
    assert passed, f"Validation failed: {issues}"

@pytest.mark.reflexion
def test_error_learning(reflexion_pattern):
    """If test fails, reflexion records for future prevention"""
    pass

@pytest.mark.complexity("medium")  # simple: 200, medium: 1000, complex: 2500
def test_with_budget(token_budget):
    """Token budget allocation"""
    assert token_budget.limit == 1000
```

## 🌿 Git Workflow

**Branch structure**: `master` (production) ← `integration` (testing) ← `feature/*`, `fix/*`, `docs/*`

**Standard workflow**:
1. Create branch from `integration`: `git checkout -b feature/your-feature`
2. Develop with tests: `uv run pytest`
3. Commit: `git commit -m "feat: description"` (conventional commits)
4. Merge to `integration` → validate → merge to `master`

**Current branch**: See git status in session start output

### Parallel Development with Git Worktrees

**CRITICAL**: When running multiple Claude Code sessions in parallel, use `git worktree` to avoid conflicts.

```bash
# Create worktree for integration branch
cd ~/github/SuperClaude_Framework
git worktree add ../SuperClaude_Framework-integration integration

# Create worktree for feature branch
git worktree add ../SuperClaude_Framework-feature feature/pm-agent
```

**Benefits**:
- Run Claude Code sessions on different branches simultaneously
- No branch switching conflicts
- Independent working directories
- Parallel development without state corruption

**Usage**:
- Session A: Open `~/github/SuperClaude_Framework/` (current branch)
- Session B: Open `~/github/SuperClaude_Framework-integration/` (integration)
- Session C: Open `~/github/SuperClaude_Framework-feature/` (feature branch)

**Cleanup**:
```bash
git worktree remove ../SuperClaude_Framework-integration
```

## 📝 Key Documentation Files

**PLANNING.md** - Architecture, design principles, absolute rules
**TASK.md** - Current tasks and priorities
**KNOWLEDGE.md** - Accumulated insights and troubleshooting

Additional docs in `docs/user-guide/`, `docs/developer-guide/`, `docs/reference/`

## 💡 Core Development Principles

### 1. Evidence-Based Development
**Never guess** - verify with official docs (Context7 MCP, WebFetch, WebSearch) before implementation.

### 2. Confidence-First Implementation
Check confidence BEFORE starting: ≥90% proceed, 70-89% present alternatives, <70% ask questions.

### 3. Parallel-First Execution
Use **Wave → Checkpoint → Wave** pattern (3.5x faster). Example: `[Read files in parallel]` → Analyze → `[Edit files in parallel]`

### 4. Token Efficiency
- Simple (typo): 200 tokens
- Medium (bug fix): 1,000 tokens
- Complex (feature): 2,500 tokens
- Confidence check ROI: spend 100-200 to save 5,000-50,000

## 🔧 MCP Server Integration

**Recommended**: Use **airis-mcp-gateway** for unified MCP management.

```bash
superclaude mcp  # Interactive install, gateway is default (requires Docker)
```

**Gateway Benefits**: 60+ tools, 98% token reduction, single SSE endpoint, Web UI

**High Priority Servers** (included in gateway):
- **Tavily**: Web search (Deep Research)
- **Context7**: Official documentation (prevent hallucination)
- **Sequential**: Token-efficient reasoning (30-50% reduction)
- **Serena**: Session persistence
- **Mindbase**: Cross-session learning

**Optional**: Playwright (browser automation), Magic (UI components), Chrome DevTools (performance)

**Usage**: TypeScript plugins and Python pytest plugin can call MCP servers. Always prefer MCP tools over speculation for documentation/research.

## 🚀 Development & Installation

### Current Installation Method (v4.2.0)

**Standard Installation**:
```bash
# Option 1: pipx (recommended)
pipx install superclaude
superclaude install

# Option 2: Direct from repo
git clone https://github.com/SuperClaude-Org/SuperClaude_Framework.git
cd SuperClaude_Framework
./install.sh
```

**Development Mode**:
```bash
# Install in editable mode
make dev

# Run tests
make test

# Verify installation
make verify
```

### Plugin System (v5.0 - Not Yet Available)

The TypeScript plugin system (`.claude-plugin/`, marketplace) is planned for v5.0.
See `docs/plugin-reorg.md` for details.

## 📊 Package Information

**Package name**: `superclaude`
**Version**: 4.2.0
**Python**: >=3.10
**Build system**: hatchling (PEP 517)

**Entry points**:
- CLI: `superclaude` command
- Pytest plugin: Auto-loaded as `superclaude`

**Dependencies**:
- pytest>=7.0.0
- click>=8.0.0
- rich>=13.0.0

---

<!-- BEGIN: superclaude bootstrap additions -->

# SuperClaude_Framework

Generated by superclaude bootstrap on 2026-02-06

## Project Overview

- **Languages**: python, javascript
- **Frameworks**: pytest, click, hatchling
- **Package managers**: uv
- **Repository**: http://local_proxy@127.0.0.1:48982/git/jsrobinson3/SuperClaude_Framework

## Directory Structure

```
.claude/
  hooks/
  skills/
    confidence-check/
.github/
  workflows/
docs/
  Development/
    tasks/
  Templates/
  agents/
  architecture/
  developer-guide/
  getting-started/
  mcp/
  memory/
  mistakes/
  reference/
  research/
  sessions/
  testing/
  troubleshooting/
  user-guide/
  user-guide-jp/
  user-guide-kr/
  user-guide-zh/
plugins/
  superclaude/
    agents/
    commands/
    core/
    examples/
    hooks/
    mcp/
      configs/
    modes/
    scripts/
    skills/
      confidence-check/
scripts/
... and 23 more directories
```

## Development Workflow

### Python (UV)

**CRITICAL**: This project uses UV. Never use `pip` or `python` directly.

```bash
uv run pytest              # Run tests
uv pip install <pkg>       # Install packages
uv run python <script>     # Run scripts
```

### Makefile Targets

```bash
make install
make test
make test-plugin
make doctor
make verify
make lint
make format
make clean
make PLUGIN_DIST
make build-plugin
make sync-plugin-repo
make translate
make help
make uninstall-legacy
```

### Package Scripts

```bash
npm run postinstall
npm run update
npm run lint
npm run test
```

## Testing

- **Framework**: pytest
- **Test directory**: tests
- **Config**: pyproject.toml

## Code Quality

- **ruff**
- **black**
- **mypy**


<!-- END: superclaude bootstrap additions -->
