"""
SuperClaude Bootstrap Module

Environment analysis, hook generation, CLAUDE.md generation,
MCP configuration, slash command scaffolding, and local LLM integration.
"""

from .analyzer import EnvironmentAnalyzer
from .hooks import HookInstaller

__all__ = [
    "EnvironmentAnalyzer",
    "HookInstaller",
]
