"""
Environment Analyzer

Detects project language, framework, package manager, test framework,
directory structure, existing Claude Code configuration, and code patterns.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class EnvironmentAnalyzer:
    """Analyzes a project directory to detect its development environment."""

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / ".claude"
        self.project_claude_dir = self.project_dir / ".claude"

    def analyze(self) -> Dict[str, Any]:
        """Run full environment analysis. Returns a structured report."""
        return {
            "project_dir": str(self.project_dir),
            "existing_config": self._detect_existing_config(),
            "languages": self._detect_languages(),
            "frameworks": self._detect_frameworks(),
            "package_managers": self._detect_package_managers(),
            "test_frameworks": self._detect_test_frameworks(),
            "linters": self._detect_linters(),
            "build_tools": self._detect_build_tools(),
            "docker": self._detect_docker(),
            "git": self._detect_git(),
            "directory_structure": self._map_directory_structure(),
            "scripts": self._detect_scripts(),
            "hardware": self._detect_hardware(),
        }

    # ── Existing Config Detection ──────────────────────────────────────

    def _detect_existing_config(self) -> Dict[str, Any]:
        """Check what Claude Code configuration already exists."""
        config = {
            "global_claude_md": None,
            "project_claude_md": None,
            "global_settings": None,
            "project_settings": None,
            "project_settings_local": None,
            "global_mcp": None,
            "project_mcp": None,
            "existing_hooks": [],
            "existing_commands": [],
        }

        # Global CLAUDE.md
        global_md = self.claude_dir / "CLAUDE.md"
        if global_md.exists():
            config["global_claude_md"] = str(global_md)

        # Project CLAUDE.md
        project_md = self.project_dir / "CLAUDE.md"
        if project_md.exists():
            config["project_claude_md"] = str(project_md)

        # Settings files
        for name, key in [
            (self.claude_dir / "settings.json", "global_settings"),
            (self.project_claude_dir / "settings.json", "project_settings"),
            (self.project_claude_dir / "settings.local.json", "project_settings_local"),
        ]:
            if name.exists():
                try:
                    config[key] = json.loads(name.read_text())
                except (json.JSONDecodeError, OSError):
                    config[key] = {"_error": "could not parse"}

        # MCP configs
        for name, key in [
            (self.claude_dir / "mcp.json", "global_mcp"),
            (self.project_claude_dir / "mcp.json", "project_mcp"),
        ]:
            if name.exists():
                try:
                    config[key] = json.loads(name.read_text())
                except (json.JSONDecodeError, OSError):
                    config[key] = {"_error": "could not parse"}

        # Existing hooks (from settings files)
        for settings_key in ["global_settings", "project_settings"]:
            settings = config.get(settings_key)
            if isinstance(settings, dict) and "hooks" in settings:
                for event, groups in settings["hooks"].items():
                    if isinstance(groups, list):
                        for group in groups:
                            config["existing_hooks"].append({
                                "event": event,
                                "source": settings_key,
                                "matcher": group.get("matcher", "*"),
                            })

        # Existing commands
        commands_dir = self.claude_dir / "commands"
        if commands_dir.exists():
            for item in commands_dir.rglob("*.md"):
                config["existing_commands"].append(str(item.relative_to(commands_dir)))

        return config

    # ── Language Detection ─────────────────────────────────────────────

    def _detect_languages(self) -> List[Dict[str, Any]]:
        """Detect programming languages used in the project."""
        languages = []
        indicators = {
            "python": {
                "files": ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "requirements.txt"],
                "globs": ["**/*.py"],
            },
            "typescript": {
                "files": ["tsconfig.json", "tsconfig.build.json"],
                "globs": ["**/*.ts", "**/*.tsx"],
            },
            "javascript": {
                "files": ["package.json", "jsconfig.json"],
                "globs": ["**/*.js", "**/*.jsx", "**/*.mjs"],
            },
            "go": {
                "files": ["go.mod", "go.sum"],
                "globs": ["**/*.go"],
            },
            "rust": {
                "files": ["Cargo.toml", "Cargo.lock"],
                "globs": ["**/*.rs"],
            },
            "java": {
                "files": ["pom.xml", "build.gradle", "build.gradle.kts"],
                "globs": ["**/*.java"],
            },
            "ruby": {
                "files": ["Gemfile", "Rakefile"],
                "globs": ["**/*.rb"],
            },
        }

        for lang, checks in indicators.items():
            found_files = [f for f in checks["files"] if (self.project_dir / f).exists()]
            if found_files:
                languages.append({"name": lang, "config_files": found_files, "primary": False})

        # Mark the most likely primary language
        if languages:
            # Heuristic: language with the most config files is primary
            languages.sort(key=lambda x: len(x["config_files"]), reverse=True)
            languages[0]["primary"] = True

        return languages

    # ── Framework Detection ────────────────────────────────────────────

    def _detect_frameworks(self) -> List[Dict[str, str]]:
        """Detect frameworks from config files."""
        frameworks = []

        # Python frameworks
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            py_frameworks = {
                "django": "django",
                "flask": "flask",
                "fastapi": "fastapi",
                "pytest": "pytest",
                "click": "click",
                "hatchling": "hatchling",
            }
            for key, name in py_frameworks.items():
                if key in content.lower():
                    frameworks.append({"name": name, "language": "python"})

        # JS/TS frameworks
        pkg_json = self.project_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                all_deps = {
                    **pkg.get("dependencies", {}),
                    **pkg.get("devDependencies", {}),
                }
                js_frameworks = {
                    "react": "React",
                    "next": "Next.js",
                    "vue": "Vue",
                    "nuxt": "Nuxt",
                    "express": "Express",
                    "nestjs": "NestJS",
                    "svelte": "Svelte",
                    "angular": "Angular",
                }
                for key, name in js_frameworks.items():
                    if any(key in dep.lower() for dep in all_deps):
                        frameworks.append({"name": name, "language": "javascript/typescript"})
            except (json.JSONDecodeError, OSError):
                pass

        return frameworks

    # ── Package Manager Detection ──────────────────────────────────────

    def _detect_package_managers(self) -> List[Dict[str, str]]:
        """Detect package managers in use."""
        managers = []
        checks = [
            ("uv", "uv.lock", "python"),
            ("poetry", "poetry.lock", "python"),
            ("pip", "requirements.txt", "python"),
            ("pipenv", "Pipfile.lock", "python"),
            ("npm", "package-lock.json", "javascript"),
            ("yarn", "yarn.lock", "javascript"),
            ("pnpm", "pnpm-lock.yaml", "javascript"),
            ("bun", "bun.lockb", "javascript"),
            ("cargo", "Cargo.lock", "rust"),
            ("go modules", "go.sum", "go"),
        ]

        for name, lockfile, lang in checks:
            if (self.project_dir / lockfile).exists():
                managers.append({"name": name, "lockfile": lockfile, "language": lang})

        # Special case: detect UV from pyproject.toml tool.uv section
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists() and "[tool.uv]" in pyproject.read_text():
            if not any(m["name"] == "uv" for m in managers):
                managers.append({"name": "uv", "lockfile": "pyproject.toml", "language": "python"})

        return managers

    # ── Test Framework Detection ───────────────────────────────────────

    def _detect_test_frameworks(self) -> List[Dict[str, Any]]:
        """Detect test frameworks and their configuration."""
        frameworks = []

        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[tool.pytest" in content:
                cfg = {"name": "pytest", "language": "python", "config": "pyproject.toml"}
                # Extract test paths
                if "testpaths" in content:
                    cfg["test_dirs"] = ["tests"]
                frameworks.append(cfg)

        pkg_json = self.project_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "jest" in all_deps:
                    frameworks.append({"name": "jest", "language": "javascript"})
                if "vitest" in all_deps:
                    frameworks.append({"name": "vitest", "language": "javascript"})
                if "mocha" in all_deps:
                    frameworks.append({"name": "mocha", "language": "javascript"})
            except (json.JSONDecodeError, OSError):
                pass

        # Check for test directories
        test_dirs = ["tests", "test", "__tests__", "spec"]
        for d in test_dirs:
            if (self.project_dir / d).is_dir():
                if not any(f.get("test_dirs") for f in frameworks):
                    for f in frameworks:
                        f["test_dirs"] = [d]

        return frameworks

    # ── Linter Detection ───────────────────────────────────────────────

    def _detect_linters(self) -> List[Dict[str, str]]:
        """Detect linters and formatters."""
        linters = []
        checks = [
            ("ruff", [".ruff.toml", "ruff.toml"], "pyproject.toml", "[tool.ruff]"),
            ("black", [], "pyproject.toml", "[tool.black]"),
            ("eslint", [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs"], None, None),
            ("prettier", [".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yml"], None, None),
            ("mypy", ["mypy.ini", ".mypy.ini"], "pyproject.toml", "[tool.mypy]"),
            ("biome", ["biome.json", "biome.jsonc"], None, None),
        ]

        pyproject_content = ""
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            pyproject_content = pyproject.read_text()

        for name, config_files, toml_file, toml_section in checks:
            found = any((self.project_dir / f).exists() for f in config_files)
            if not found and toml_section and toml_section in pyproject_content:
                found = True
            if found:
                linters.append({"name": name})

        return linters

    # ── Build Tool Detection ───────────────────────────────────────────

    def _detect_build_tools(self) -> List[Dict[str, str]]:
        """Detect build systems."""
        tools = []
        checks = [
            ("make", ["Makefile", "makefile", "GNUmakefile"]),
            ("just", ["justfile", "Justfile"]),
            ("cmake", ["CMakeLists.txt"]),
            ("webpack", ["webpack.config.js", "webpack.config.ts"]),
            ("vite", ["vite.config.js", "vite.config.ts"]),
            ("turbo", ["turbo.json"]),
        ]

        for name, files in checks:
            if any((self.project_dir / f).exists() for f in files):
                tools.append({"name": name})

        return tools

    # ── Docker Detection ───────────────────────────────────────────────

    def _detect_docker(self) -> Dict[str, Any]:
        """Detect Docker configuration."""
        result = {"available": False, "compose_file": None, "dockerfile": None, "services": []}

        for name in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
            path = self.project_dir / name
            if path.exists():
                result["compose_file"] = name
                # Basic service detection from file content
                content = path.read_text()
                if "services:" in content:
                    in_services = False
                    for line in content.split("\n"):
                        if line.strip() == "services:":
                            in_services = True
                            continue
                        if in_services and line and not line.startswith(" " * 4) and line.strip().endswith(":"):
                            if not line.startswith("#"):
                                result["services"].append(line.strip().rstrip(":"))
                        elif in_services and line and not line.startswith(" "):
                            in_services = False
                break

        for name in ["Dockerfile", "dockerfile", "Containerfile"]:
            if (self.project_dir / name).exists():
                result["dockerfile"] = name
                break

        # Check if Docker daemon is available
        try:
            proc = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=5,
            )
            result["available"] = proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            result["available"] = False

        return result

    # ── Git Detection ──────────────────────────────────────────────────

    def _detect_git(self) -> Dict[str, Any]:
        """Detect git configuration."""
        result = {"is_repo": False, "branch": None, "remote": None}

        if not (self.project_dir / ".git").exists():
            return result

        result["is_repo"] = True

        try:
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=5,
                cwd=str(self.project_dir),
            )
            if branch.returncode == 0:
                result["branch"] = branch.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
                cwd=str(self.project_dir),
            )
            if remote.returncode == 0:
                result["remote"] = remote.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return result

    # ── Directory Structure ────────────────────────────────────────────

    def _map_directory_structure(self, max_depth: int = 3) -> List[str]:
        """Map the project's directory structure to a specified depth."""
        dirs = []
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv",
                ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
                "dist", "build", ".egg-info", ".eggs"}

        def _walk(path: Path, depth: int, prefix: str = ""):
            if depth > max_depth:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            except PermissionError:
                return

            for entry in entries:
                if entry.name in skip or entry.name.endswith(".egg-info"):
                    continue
                if entry.is_dir():
                    dirs.append(f"{prefix}{entry.name}/")
                    _walk(entry, depth + 1, prefix + "  ")

        _walk(self.project_dir, 0)
        return dirs

    # ── Script Detection ───────────────────────────────────────────────

    def _detect_scripts(self) -> Dict[str, List[str]]:
        """Detect available run scripts from Makefile, package.json, etc."""
        scripts = {"makefile": [], "package_json": [], "pyproject": []}

        # Makefile targets
        makefile = self.project_dir / "Makefile"
        if makefile.exists():
            for line in makefile.read_text().split("\n"):
                if line and not line.startswith("\t") and not line.startswith("#") and ":" in line:
                    target = line.split(":")[0].strip()
                    if target and not target.startswith("."):
                        scripts["makefile"].append(target)

        # package.json scripts
        pkg_json = self.project_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                scripts["package_json"] = list(pkg.get("scripts", {}).keys())
            except (json.JSONDecodeError, OSError):
                pass

        # pyproject.toml scripts
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[project.scripts]" in content:
                in_scripts = False
                for line in content.split("\n"):
                    if "[project.scripts]" in line:
                        in_scripts = True
                        continue
                    if in_scripts and line.startswith("["):
                        break
                    if in_scripts and "=" in line:
                        scripts["pyproject"].append(line.split("=")[0].strip())

        return scripts

    # ── Hardware Detection ─────────────────────────────────────────────

    def _detect_hardware(self) -> Dict[str, Any]:
        """Detect available hardware for local LLM support."""
        hw = {"cpu": None, "gpu": None, "vram_mb": None, "ollama_available": False, "ollama_models": []}

        # CPU info
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        hw["cpu"] = line.split(":")[1].strip()
                        break
        except (OSError, IndexError):
            pass

        # GPU detection via nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                hw["gpu"] = parts[0].strip()
                if len(parts) > 1:
                    try:
                        hw["vram_mb"] = int(parts[1].strip())
                    except ValueError:
                        pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Ollama detection
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                hw["ollama_available"] = True
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:  # Skip header line
                    hw["ollama_models"] = [
                        line.split()[0] for line in lines[1:] if line.strip()
                    ]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return hw

    # ── Summary ────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Generate a human-readable summary of the analysis."""
        data = self.analyze()
        lines = [f"Project: {data['project_dir']}", ""]

        # Languages
        langs = [l["name"] + (" (primary)" if l.get("primary") else "") for l in data["languages"]]
        lines.append(f"Languages: {', '.join(langs) if langs else 'none detected'}")

        # Frameworks
        fws = [f["name"] for f in data["frameworks"]]
        lines.append(f"Frameworks: {', '.join(fws) if fws else 'none detected'}")

        # Package managers
        pms = [p["name"] for p in data["package_managers"]]
        lines.append(f"Package managers: {', '.join(pms) if pms else 'none detected'}")

        # Test frameworks
        tfs = [t["name"] for t in data["test_frameworks"]]
        lines.append(f"Test frameworks: {', '.join(tfs) if tfs else 'none detected'}")

        # Linters
        lints = [l["name"] for l in data["linters"]]
        lines.append(f"Linters: {', '.join(lints) if lints else 'none detected'}")

        # Existing config
        cfg = data["existing_config"]
        lines.append("")
        lines.append("Existing Claude Code config:")
        lines.append(f"  Global CLAUDE.md: {'exists' if cfg['global_claude_md'] else 'not found'}")
        lines.append(f"  Project CLAUDE.md: {'exists' if cfg['project_claude_md'] else 'not found'}")
        lines.append(f"  Hooks configured: {len(cfg['existing_hooks'])}")
        lines.append(f"  Commands installed: {len(cfg['existing_commands'])}")

        # Hardware
        hw = data["hardware"]
        lines.append("")
        lines.append("Hardware:")
        if hw["cpu"]:
            lines.append(f"  CPU: {hw['cpu']}")
        if hw["gpu"]:
            vram = f" ({hw['vram_mb']}MB VRAM)" if hw["vram_mb"] else ""
            lines.append(f"  GPU: {hw['gpu']}{vram}")
        lines.append(f"  Ollama: {'available' if hw['ollama_available'] else 'not found'}")
        if hw["ollama_models"]:
            lines.append(f"  Models: {', '.join(hw['ollama_models'])}")

        return "\n".join(lines)
