"""
MCP Configuration Manager

Manages MCP server configuration for Claude Code.
Merges new servers into existing mcp.json or settings without overwriting.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── MCP Server Definitions ─────────────────────────────────────────────
# Servers referenced in the bootstrap spec.

MCP_SERVER_DEFS: Dict[str, Dict[str, Any]] = {
    "atlassian": {
        "description": "Jira and Confluence integration",
        "command": "npx",
        "args": ["-y", "@anthropic/atlassian-mcp"],
        "env_vars": ["ATLASSIAN_API_TOKEN", "ATLASSIAN_EMAIL", "ATLASSIAN_URL"],
        "notes": "Requires Atlassian API token. Get from https://id.atlassian.com/manage-profile/security/api-tokens",
    },
    "sequential-thinking": {
        "description": "Multi-step problem solving and systematic analysis",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "env_vars": [],
    },
    "grepai": {
        "description": "Semantic code search using vector embeddings (local, privacy-first)",
        "command": "grepai",
        "args": ["mcp"],
        "env_vars": [],
        "notes": "Install: go install github.com/yoanbernabeu/grepai@latest. Uses Ollama for embeddings.",
    },
    "sonarqube": {
        "description": "Code quality and security analysis",
        "command": "npx",
        "args": ["-y", "@anthropic/sonarqube-mcp"],
        "env_vars": ["SONARQUBE_TOKEN", "SONARQUBE_URL"],
        "notes": "Requires SonarQube instance and API token.",
    },
    "sentry": {
        "description": "Error monitoring and production issue tracking",
        "command": "npx",
        "args": ["-y", "@sentry/mcp-server"],
        "env_vars": ["SENTRY_AUTH_TOKEN"],
        "notes": "Requires Sentry auth token. Get from https://sentry.io/settings/auth-tokens/",
    },
    "docker": {
        "description": "Docker container management and operations",
        "command": "docker",
        "args": [
            "run", "-i", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "mcp/docker",
        ],
        "env_vars": [],
    },
}


class McpConfigManager:
    """Manages MCP server configuration."""

    def __init__(self, project_dir: Optional[str] = None, scope: str = "project"):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.home_dir = Path.home()
        self.scope = scope

    @property
    def config_path(self) -> Path:
        """Path to the MCP configuration file."""
        if self.scope == "user":
            return self.home_dir / ".claude" / "mcp.json"
        return self.project_dir / ".claude" / "mcp.json"

    def list_available(self) -> List[Dict[str, Any]]:
        """List all available MCP server definitions."""
        result = []
        installed = self._get_installed_servers()
        for name, config in MCP_SERVER_DEFS.items():
            result.append({
                "name": name,
                "description": config["description"],
                "installed": name in installed,
                "env_vars": config.get("env_vars", []),
                "notes": config.get("notes", ""),
            })
        return result

    def generate_config(
        self,
        server_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate MCP configuration JSON for the specified servers.

        Returns a dict suitable for writing to mcp.json.
        """
        if server_names is None:
            server_names = list(MCP_SERVER_DEFS.keys())

        servers = {}
        for name in server_names:
            defn = MCP_SERVER_DEFS.get(name)
            if not defn:
                continue

            entry: Dict[str, Any] = {
                "command": defn["command"],
                "args": defn["args"],
            }

            # Add environment variable references
            if defn.get("env_vars"):
                entry["env"] = {}
                for var in defn["env_vars"]:
                    # Reference env vars — user fills in values
                    entry["env"][var] = f"${{{var}}}"

            servers[name] = entry

        return {"mcpServers": servers}

    def install(
        self,
        server_names: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Install MCP servers by merging into mcp.json.

        Never overwrites existing server entries.
        """
        new_config = self.generate_config(server_names)
        new_servers = new_config.get("mcpServers", {})

        if dry_run:
            lines = [f"Would merge {len(new_servers)} MCP server(s) into {self.config_path}:", ""]
            for name, cfg in new_servers.items():
                lines.append(f"  {name}: {cfg['command']} {' '.join(cfg['args'][:3])}")
                defn = MCP_SERVER_DEFS.get(name, {})
                if defn.get("env_vars"):
                    lines.append(f"    Requires: {', '.join(defn['env_vars'])}")
            return True, "\n".join(lines)

        # Load existing config
        existing = self._load_config()
        existing_servers = existing.get("mcpServers", {})

        # Merge: only add servers that don't already exist
        added = []
        skipped = []
        for name, cfg in new_servers.items():
            if name in existing_servers:
                skipped.append(name)
            else:
                existing_servers[name] = cfg
                added.append(name)

        existing["mcpServers"] = existing_servers
        self._save_config(existing)

        parts = []
        if added:
            parts.append(f"Added: {', '.join(added)}")
        if skipped:
            parts.append(f"Already configured: {', '.join(skipped)}")
        parts.append(f"Config: {self.config_path}")

        # Report env vars that need to be set
        needed_vars = set()
        for name in added:
            defn = MCP_SERVER_DEFS.get(name, {})
            for var in defn.get("env_vars", []):
                if not os.environ.get(var):
                    needed_vars.add(var)

        if needed_vars:
            parts.append(f"\nEnvironment variables to configure: {', '.join(sorted(needed_vars))}")

        return True, "\n".join(parts)

    def check_env_vars(self) -> Dict[str, bool]:
        """Check which required environment variables are set."""
        result = {}
        for defn in MCP_SERVER_DEFS.values():
            for var in defn.get("env_vars", []):
                result[var] = bool(os.environ.get(var))
        return result

    # ── Private ────────────────────────────────────────────────────────

    def _get_installed_servers(self) -> set:
        config = self._load_config()
        return set(config.get("mcpServers", {}).keys())

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_config(self, config: Dict[str, Any]):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2) + "\n")
