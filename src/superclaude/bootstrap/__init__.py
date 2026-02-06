"""
SuperClaude Bootstrap Module

Environment analysis, hook generation, CLAUDE.md generation,
MCP configuration, slash command scaffolding, local LLM integration,
and agent teams configuration.
"""

from .agent_teams import AgentTeamsConfigurator
from .analyzer import EnvironmentAnalyzer
from .hooks import HookInstaller

__all__ = [
    "AgentTeamsConfigurator",
    "EnvironmentAnalyzer",
    "HookInstaller",
]
