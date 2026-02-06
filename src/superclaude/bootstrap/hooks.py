"""
Hook Installer

Installs Claude Code hooks for code quality enforcement.
Copies hook scripts to .claude/hooks/ and merges hook config into settings.json.
Non-destructive: always merges with existing configuration.
"""

import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Hook Registry ──────────────────────────────────────────────────────
# Each entry defines a hook script and its Claude Code settings config.

HOOK_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "lint-on-edit",
        "script": "lint-on-edit.sh",
        "description": "Auto-lint files after Write/Edit operations",
        "event": "PostToolUse",
        "matcher": "Write|Edit",
        "async": False,
        "timeout": 30,
        "category": "quality",
    },
    {
        "id": "test-on-edit",
        "script": "test-on-edit.sh",
        "description": "Run related tests after file changes (background)",
        "event": "PostToolUse",
        "matcher": "Write|Edit",
        "async": True,
        "timeout": 120,
        "category": "quality",
    },
    {
        "id": "block-dangerous",
        "script": "block-dangerous.sh",
        "description": "Block destructive commands (rm -rf, force push, etc.)",
        "event": "PreToolUse",
        "matcher": "Bash",
        "async": False,
        "timeout": 5,
        "category": "safety",
    },
    {
        "id": "style-check",
        "script": "style-check.py",
        "description": "Enforce code style (function length, nesting, naming)",
        "event": "PostToolUse",
        "matcher": "Write|Edit",
        "async": False,
        "timeout": 15,
        "category": "quality",
    },
    {
        "id": "stop-verify",
        "script": "stop-verify.sh",
        "description": "Verify tests pass before Claude finishes",
        "event": "Stop",
        "matcher": "",
        "async": False,
        "timeout": 120,
        "category": "quality",
    },
    {
        "id": "convention-guard",
        "script": "convention-guard.py",
        "description": "Guard project conventions on new file creation",
        "event": "PreToolUse",
        "matcher": "Write",
        "async": False,
        "timeout": 10,
        "category": "quality",
    },
]

# Predefined profiles for quick setup
HOOK_PROFILES = {
    "minimal": {
        "description": "Safety essentials only",
        "hooks": ["block-dangerous"],
    },
    "standard": {
        "description": "Safety + lint + convention checking",
        "hooks": ["block-dangerous", "lint-on-edit", "style-check", "convention-guard"],
    },
    "full": {
        "description": "All hooks including test verification",
        "hooks": [h["id"] for h in HOOK_REGISTRY],
    },
}


class HookInstaller:
    """Installs and manages Claude Code hooks."""

    def __init__(
        self,
        project_dir: Optional[str] = None,
        scope: str = "project",
    ):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.home_dir = Path.home()
        self.scope = scope

        # Where hook scripts get installed
        self.hooks_script_dir = self.project_dir / ".claude" / "hooks"

        # Where settings live
        if scope == "user":
            self.settings_path = self.home_dir / ".claude" / "settings.json"
        elif scope == "local":
            self.settings_path = self.project_dir / ".claude" / "settings.local.json"
        else:
            self.settings_path = self.project_dir / ".claude" / "settings.json"

        # Source directory for hook script templates
        self.source_dir = Path(__file__).parent / "hook_scripts"

    def list_hooks(self) -> List[Dict[str, Any]]:
        """List all available hooks with their installation status."""
        result = []
        installed = self._get_installed_hook_ids()

        for hook in HOOK_REGISTRY:
            result.append({
                **hook,
                "installed": hook["id"] in installed,
            })
        return result

    def list_profiles(self) -> Dict[str, Any]:
        """List available hook profiles."""
        return HOOK_PROFILES

    def install_profile(
        self, profile_name: str, dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Install all hooks in a named profile."""
        if profile_name not in HOOK_PROFILES:
            available = ", ".join(HOOK_PROFILES.keys())
            return False, f"Unknown profile '{profile_name}'. Available: {available}"

        profile = HOOK_PROFILES[profile_name]
        return self.install_hooks(profile["hooks"], dry_run=dry_run)

    def install_hooks(
        self,
        hook_ids: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Install specified hooks (or all if none specified).

        Copies scripts to .claude/hooks/ and merges config into settings.json.
        Never overwrites existing hooks — only adds new ones.
        """
        if hook_ids is None:
            hook_ids = [h["id"] for h in HOOK_REGISTRY]

        # Validate hook IDs
        valid_ids = {h["id"] for h in HOOK_REGISTRY}
        invalid = [hid for hid in hook_ids if hid not in valid_ids]
        if invalid:
            return False, f"Unknown hook(s): {', '.join(invalid)}"

        hooks_to_install = [h for h in HOOK_REGISTRY if h["id"] in hook_ids]

        if dry_run:
            lines = ["Would install the following hooks:", ""]
            for h in hooks_to_install:
                lines.append(f"  {h['id']:20} {h['description']}")
                lines.append(f"    Event: {h['event']}, Matcher: {h['matcher'] or '(all)'}")
                lines.append(f"    Script: .claude/hooks/{h['script']}")
            lines.append(f"\nSettings file: {self.settings_path}")
            return True, "\n".join(lines)

        # Step 1: Copy scripts
        installed_scripts = self._copy_scripts(hooks_to_install)

        # Step 2: Merge into settings
        merged_count = self._merge_settings(hooks_to_install)

        # Step 3: Create hooks-config.json with defaults
        self._create_hooks_config()

        msg_parts = [
            f"Installed {len(installed_scripts)} hook script(s) to {self.hooks_script_dir}",
            f"Merged {merged_count} hook(s) into {self.settings_path}",
        ]

        return True, "\n".join(msg_parts)

    def uninstall_hook(self, hook_id: str) -> Tuple[bool, str]:
        """Remove a hook from settings (does not delete script files)."""
        hook = next((h for h in HOOK_REGISTRY if h["id"] == hook_id), None)
        if not hook:
            return False, f"Unknown hook: {hook_id}"

        settings = self._load_settings()
        hooks_config = settings.get("hooks", {})
        event = hook["event"]

        if event not in hooks_config:
            return False, f"Hook '{hook_id}' is not installed"

        # Find and remove the matching hook entry
        groups = hooks_config[event]
        script_path = f'"$CLAUDE_PROJECT_DIR"/.claude/hooks/{hook["script"]}'
        new_groups = []
        removed = False

        for group in groups:
            new_hooks = []
            for h in group.get("hooks", []):
                if h.get("command", "") != script_path:
                    new_hooks.append(h)
                else:
                    removed = True
            if new_hooks:
                group["hooks"] = new_hooks
                new_groups.append(group)

        if not removed:
            return False, f"Hook '{hook_id}' not found in settings"

        if new_groups:
            hooks_config[event] = new_groups
        else:
            del hooks_config[event]

        settings["hooks"] = hooks_config
        self._save_settings(settings)

        return True, f"Removed hook '{hook_id}' from {self.settings_path}"

    # ── Private Methods ────────────────────────────────────────────────

    def _copy_scripts(self, hooks: List[Dict[str, Any]]) -> List[str]:
        """Copy hook scripts to .claude/hooks/."""
        self.hooks_script_dir.mkdir(parents=True, exist_ok=True)
        installed = []

        for hook in hooks:
            src = self.source_dir / hook["script"]
            dst = self.hooks_script_dir / hook["script"]

            if not src.exists():
                continue

            shutil.copy2(src, dst)
            # Make executable for owner and group only (no world-execute)
            dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP)
            installed.append(hook["script"])

        return installed

    def _merge_settings(self, hooks: List[Dict[str, Any]]) -> int:
        """Merge hook configurations into settings.json without overwriting."""
        settings = self._load_settings()

        if "hooks" not in settings:
            settings["hooks"] = {}

        hooks_config = settings["hooks"]
        merged_count = 0

        for hook in hooks:
            event = hook["event"]
            matcher = hook["matcher"]
            script_path = f'"$CLAUDE_PROJECT_DIR"/.claude/hooks/{hook["script"]}'

            # Check if this exact hook already exists
            if self._hook_exists(hooks_config, event, script_path):
                continue

            # Build hook entry
            hook_entry = {
                "type": "command",
                "command": script_path,
                "timeout": hook.get("timeout", 600),
            }
            if hook.get("async"):
                hook_entry["async"] = True

            # Find or create matcher group for this event
            if event not in hooks_config:
                hooks_config[event] = []

            # Try to find an existing group with the same matcher
            group_found = False
            for group in hooks_config[event]:
                if group.get("matcher", "") == matcher:
                    group["hooks"].append(hook_entry)
                    group_found = True
                    break

            if not group_found:
                new_group = {"hooks": [hook_entry]}
                if matcher:
                    new_group["matcher"] = matcher
                hooks_config[event].append(new_group)

            merged_count += 1

        settings["hooks"] = hooks_config
        self._save_settings(settings)
        return merged_count

    def _hook_exists(
        self, hooks_config: Dict, event: str, script_path: str
    ) -> bool:
        """Check if a hook with this script already exists in config."""
        if event not in hooks_config:
            return False
        for group in hooks_config[event]:
            for h in group.get("hooks", []):
                if h.get("command", "") == script_path:
                    return True
        return False

    def _get_installed_hook_ids(self) -> set:
        """Get set of hook IDs currently in settings."""
        settings = self._load_settings()
        hooks_config = settings.get("hooks", {})
        installed = set()

        for hook in HOOK_REGISTRY:
            script_path = f'"$CLAUDE_PROJECT_DIR"/.claude/hooks/{hook["script"]}'
            if self._hook_exists(hooks_config, hook["event"], script_path):
                installed.add(hook["id"])

        return installed

    def _create_hooks_config(self):
        """Create .claude/hooks-config.json with configurable thresholds."""
        config_path = self.project_dir / ".claude" / "hooks-config.json"
        if config_path.exists():
            return

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "_comment": "Hook configuration for superclaude bootstrap hooks. Adjust thresholds as needed.",
            "style_check": {
                "max_function_lines": 50,
                "max_file_lines": 500,
                "max_line_length": 120,
                "max_nesting_depth": 4,
                "check_naming": True,
            },
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n")

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings.json, returning empty dict if not found."""
        if self.settings_path.exists():
            try:
                return json.loads(self.settings_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_settings(self, settings: Dict[str, Any]):
        """Save settings.json, creating parent dirs if needed."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(settings, indent=2) + "\n")
