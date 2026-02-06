"""
SuperClaude Bootstrap Module

Environment analysis, hook generation, CLAUDE.md generation,
MCP configuration, slash command scaffolding, local LLM integration,
and agent teams configuration.
"""

from .agent_teams import AgentTeamsConfigurator
from .analyzer import EnvironmentAnalyzer
from .claude_md import ClaudeMdGenerator
from .commands import CommandScaffolder
from .hooks import HookInstaller
from .local_llm import LocalLlmManager
from .mcp_config import McpConfigManager

__all__ = [
    "AgentTeamsConfigurator",
    "ClaudeMdGenerator",
    "CommandScaffolder",
    "EnvironmentAnalyzer",
    "HookInstaller",
    "LocalLlmManager",
    "McpConfigManager",
]
