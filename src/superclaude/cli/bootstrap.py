"""
Bootstrap CLI Subcommand

Orchestrates the full Claude Code environment setup:
  superclaude bootstrap             # Interactive full setup
  superclaude bootstrap --analyze   # Environment analysis only
  superclaude bootstrap --hooks     # Install hooks only
  superclaude bootstrap --mcp       # Configure MCP servers only
  superclaude bootstrap --commands  # Install slash commands only
  superclaude bootstrap --llm       # Set up local LLM only
  superclaude bootstrap --claude-md # Generate CLAUDE.md files only
  superclaude bootstrap --teams     # Configure agent teams only
"""

import os
import sys

import click

from superclaude.bootstrap.agent_teams import AgentTeamsConfigurator
from superclaude.bootstrap.analyzer import EnvironmentAnalyzer
from superclaude.bootstrap.claude_md import ClaudeMdGenerator
from superclaude.bootstrap.commands import CommandScaffolder
from superclaude.bootstrap.hooks import HOOK_PROFILES, HookInstaller
from superclaude.bootstrap.local_llm import LocalLlmManager
from superclaude.bootstrap.mcp_config import McpConfigManager


@click.command()
@click.option("--analyze", is_flag=True, help="Run environment analysis only")
@click.option("--hooks", is_flag=True, help="Install code quality hooks only")
@click.option(
    "--hooks-profile",
    type=click.Choice(["minimal", "standard", "full"]),
    default=None,
    help="Hook profile to install (default: interactive selection)",
)
@click.option("--mcp", is_flag=True, help="Configure MCP servers only")
@click.option(
    "--mcp-servers",
    multiple=True,
    help="Specific MCP servers to configure",
)
@click.option("--commands", is_flag=True, help="Install slash commands only")
@click.option("--llm", is_flag=True, help="Set up local LLM integration only")
@click.option("--claude-md", is_flag=True, help="Generate CLAUDE.md files only")
@click.option("--teams", is_flag=True, help="Configure agent teams only")
@click.option(
    "--teammate-mode",
    type=click.Choice(["auto", "in-process", "tmux"]),
    default="auto",
    help="Agent teams display mode (default: auto)",
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user", "local"]),
    default="project",
    help="Installation scope for hooks and MCP config",
)
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it")
@click.option("--vram", type=int, default=None, help="Override VRAM detection (MB)")
@click.option("--developer", default=None, help="Developer name for global CLAUDE.md")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--monorepo", is_flag=True, help="Bootstrap all subprojects independently")
def bootstrap(
    analyze,
    hooks,
    hooks_profile,
    mcp,
    mcp_servers,
    commands,
    llm,
    claude_md,
    teams,
    teammate_mode,
    scope,
    dry_run,
    vram,
    developer,
    yes,
    monorepo,
):
    """
    Bootstrap a Claude Code development environment.

    Sets up hooks, MCP servers, slash commands, CLAUDE.md files,
    and local LLM integration for maximum productivity.

    Run without flags for interactive full setup, or use flags
    to set up individual components.

    Examples:
        superclaude bootstrap                          # Full interactive setup
        superclaude bootstrap --analyze                # Just analyze the environment
        superclaude bootstrap --hooks --hooks-profile standard  # Install standard hooks
        superclaude bootstrap --mcp --mcp-servers docker --mcp-servers sentry
        superclaude bootstrap --llm --vram 8192        # Set up for 8GB VRAM
        superclaude bootstrap --teams                  # Set up agent teams with specialized roles
        superclaude bootstrap --dry-run                # Preview everything
    """
    # If no specific flag, run everything
    run_all = not any([analyze, hooks, mcp, commands, llm, claude_md, teams])

    project_dir = os.getcwd()
    report = None  # Will be populated by analysis step

    if dry_run:
        click.echo("=== DRY RUN MODE ===\n")

    # ── Step 1: Environment Analysis ─────────────────────────────────
    if run_all or analyze:
        click.echo("== Environment Analysis ==\n")
        analyzer = EnvironmentAnalyzer(project_dir)
        report = analyzer.analyze()

        click.echo(analyzer.summary())
        click.echo()

        if analyze and not run_all:
            return

        # Auto-detect monorepo mode
        if not monorepo and report["is_monorepo"] and not yes and not dry_run:
            click.echo(f"Detected {len(report['subprojects'])} subproject(s).")
            if click.confirm("Bootstrap each subproject independently?", default=True):
                monorepo = True
            click.echo()

        if not yes and not dry_run:
            if not click.confirm("Proceed with bootstrap?", default=True):
                click.echo("Aborted.")
                return

        click.echo()

    # ── Step 2: Hooks ────────────────────────────────────────────────
    if run_all or hooks:
        click.echo("== Code Quality Hooks ==\n")
        installer = HookInstaller(project_dir, scope=scope)

        if hooks_profile is None and not dry_run and not yes:
            click.echo("Hook profiles available:")
            for name, info in HOOK_PROFILES.items():
                hook_list = ", ".join(info["hooks"])
                click.echo(f"  {name:12} {info['description']}")
                click.echo(f"               Hooks: {hook_list}")
            click.echo()
            hooks_profile = click.prompt(
                "Select profile",
                type=click.Choice(["minimal", "standard", "full"]),
                default="standard",
            )
        elif hooks_profile is None:
            hooks_profile = "standard"

        success, msg = installer.install_profile(hooks_profile, dry_run=dry_run)
        _show_result(success, msg)
        click.echo()

    # ── Step 3: MCP Servers ──────────────────────────────────────────
    if run_all or mcp:
        click.echo("== MCP Server Configuration ==\n")
        mcp_mgr = McpConfigManager(project_dir, scope=scope)

        server_list = list(mcp_servers) if mcp_servers else None

        if server_list is None and not dry_run and not yes:
            click.echo("Available MCP servers:")
            for srv in mcp_mgr.list_available():
                status = "installed" if srv["installed"] else "not configured"
                click.echo(f"  {srv['name']:25} {srv['description']} [{status}]")
                if srv["env_vars"]:
                    click.echo(f"    Requires: {', '.join(srv['env_vars'])}")
            click.echo()

            if click.confirm("Install all available MCP servers?", default=True):
                server_list = None  # None = all
            else:
                raw = click.prompt(
                    "Enter server names (comma-separated)",
                    default="sequential-thinking,docker",
                )
                server_list = [s.strip() for s in raw.split(",")]

        success, msg = mcp_mgr.install(server_list, dry_run=dry_run)
        _show_result(success, msg)
        click.echo()

    # ── Step 4: CLAUDE.md ────────────────────────────────────────────
    if run_all or claude_md:
        click.echo("== CLAUDE.md Generation ==\n")
        analyzer = EnvironmentAnalyzer(project_dir)
        report = analyzer.analyze()
        generator = ClaudeMdGenerator(project_dir)

        # Global
        if developer is None and not dry_run and not yes:
            developer = click.prompt("Developer name", default="")
        developer = developer or ""

        # Determine MCP server names for global config
        mcp_mgr = McpConfigManager(project_dir, scope=scope)
        installed_mcp = [s["name"] for s in mcp_mgr.list_available() if s["installed"]]
        if not installed_mcp:
            installed_mcp = list(mcp_servers) if mcp_servers else []

        global_content = generator.generate_global(
            report, developer_name=developer, mcp_servers=installed_mcp
        )
        result = generator.write_global(global_content, merge=True, dry_run=dry_run)
        click.echo(f"  Global: {result}")

        # Project-level
        project_content = generator.generate_project(report)
        result = generator.write_project(project_content, merge=True, dry_run=dry_run)
        click.echo(f"  Project: {result}")
        click.echo()

    # ── Step 5: Slash Commands ───────────────────────────────────────
    if run_all or commands:
        click.echo("== Slash Commands ==\n")
        scaffolder = CommandScaffolder(project_dir)

        success, msg = scaffolder.install(dry_run=dry_run)
        _show_result(success, msg)
        click.echo()

    # ── Step 6: Agent Teams ──────────────────────────────────────────
    if run_all or teams:
        click.echo("== Agent Teams ==\n")

        # Run analysis if we don't have it yet
        if not (run_all or analyze):
            analyzer = EnvironmentAnalyzer(project_dir)
            report = analyzer.analyze()

        teams_cfg = AgentTeamsConfigurator(project_dir, scope=scope)

        success, msg = teams_cfg.install(
            analysis=report,
            teammate_mode=teammate_mode,
            dry_run=dry_run,
        )
        _show_result(success, msg)
        click.echo()

    # ── Step 7: Local LLM ────────────────────────────────────────────
    if run_all or llm:
        click.echo("== Local LLM Integration ==\n")
        llm_mgr = LocalLlmManager(project_dir)

        # Hardware detection
        hw = llm_mgr.detect_hardware()
        effective_vram = vram or hw.get("vram_mb") or 0

        if effective_vram > 0:
            rec = llm_mgr.recommend_models(effective_vram)
            click.echo(f"  VRAM: {effective_vram}MB ({rec['tier']})")
            click.echo(f"  Primary model: {rec['primary_code_model']}")
            click.echo("  Recommended models:")
            for m in rec["models"]:
                click.echo(f"    {m['name']:45} {m['purpose']}")
        else:
            click.echo("  No GPU detected. Script will use CPU-compatible defaults.")

        click.echo()
        success, msg = llm_mgr.install(vram_mb=effective_vram, dry_run=dry_run)
        _show_result(success, msg)
        click.echo()

    # ── Step 8: Monorepo Subproject Bootstrap ────────────────────────
    if monorepo and (run_all or any([hooks, teams, commands])):
        click.echo("== Monorepo Subproject Bootstrap ==\n")

        # Get subprojects from analysis
        if 'report' not in locals():
            analyzer = EnvironmentAnalyzer(project_dir)
            report = analyzer.analyze()

        subprojects = report.get("subprojects", [])
        if not subprojects:
            click.echo("No subprojects detected. Skipping monorepo bootstrap.")
            click.echo()
        else:
            click.echo(f"Bootstrapping {len(subprojects)} subproject(s)...\n")

            for sp in subprojects:
                sp_path = os.path.join(project_dir, sp["path"])
                click.echo(f"  → {sp['path']}")

                if dry_run:
                    click.echo(f"    Would bootstrap: hooks, teams, commands")
                    continue

                # Create mini-report for this subproject
                sp_report = {
                    "project_dir": sp_path,
                    "languages": [{"name": "javascript", "primary": True}] if sp["package_manager"] else [],
                    "package_managers": [{"name": sp["package_manager"]}] if sp["package_manager"] else [],
                    "linters": [{"name": l} for l in sp["linters"]],
                    "frameworks": [{"name": f} for f in sp["frameworks"]],
                    "test_frameworks": [],
                }

                # Bootstrap this subproject (hooks + teams + commands only)
                if run_all or hooks:
                    installer = HookInstaller(sp_path, scope="project")
                    profile = hooks_profile or "standard"
                    success, msg = installer.install_profile(profile, dry_run=False)
                    if not success:
                        click.echo(f"    Warning: {msg}")

                if run_all or teams:
                    teams_cfg = AgentTeamsConfigurator(sp_path, scope="project")
                    success, msg = teams_cfg.install(
                        analysis=sp_report,
                        teammate_mode=teammate_mode,
                        dry_run=False,
                    )
                    if not success:
                        click.echo(f"    Warning: {msg}")

                if run_all or commands:
                    scaffolder = CommandScaffolder(sp_path)
                    success, msg = scaffolder.install(dry_run=False)
                    if not success:
                        click.echo(f"    Warning: {msg}")

                click.echo(f"    ✓ Bootstrapped {sp['path']}")

            click.echo()

    # ── Summary ──────────────────────────────────────────────────────
    if run_all:
        click.echo("== Bootstrap Complete ==\n")
        click.echo("What was set up:")
        click.echo("  - Code quality hooks (in .claude/settings.json)")
        click.echo("  - Hook scripts (in .claude/hooks/)")
        click.echo("  - MCP server configuration (in .claude/mcp.json)")
        click.echo("  - Slash commands (in .claude/commands/)")
        click.echo("  - Agent teams with specialized roles (in .claude/teams.json)")
        click.echo("  - CLAUDE.md (global and project-level)")
        click.echo("  - Local LLM helper (in .claude/scripts/)")
        if monorepo:
            click.echo(f"  - Per-subproject .claude/ directories ({len(report.get('subprojects', []))} subprojects)")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Review .claude/ directory contents")
        click.echo("  2. Set required environment variables for MCP servers")
        click.echo("  3. If using Ollama: .claude/scripts/local-llm.sh setup")
        click.echo("  4. Start a new Claude Code session to activate hooks")
        if monorepo:
            click.echo("  5. Try: /team-build OMS-Frontend OMS-Backend feature: YOUR_FEATURE")
            click.echo("  6. Try: /team-sync OMS-Frontend OMS-Backend (API contract sync)")
        else:
            click.echo("  5. Try: /team-build, /team-review, /team-debug")


def _show_result(success: bool, message: str):
    """Display a result with appropriate formatting."""
    prefix = "OK" if success else "FAIL"
    for line in message.split("\n"):
        click.echo(f"  {line}")
