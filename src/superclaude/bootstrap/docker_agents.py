"""
Docker Agent Orchestration

Generates Docker infrastructure for running parallel Claude agents
with filesystem isolation. Each agent gets its own container with
a local clone, and pushes to a shared bare git repo when done.

Architecture (from Anthropic's C compiler project):
  - A bare git repo at /upstream serves as the coordination point
  - Each agent container clones /upstream → /workspace
  - Agents work independently in their own filesystem
  - When done, agents push from /workspace → /upstream
  - A CI container can run tests on the merged result

Multi-repo support:
  - Each agent can be assigned to a specific repository
  - Supports frontend/backend/microservice project structures
  - Agents can own entire repos or specific directories within one
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Dockerfile Template ────────────────────────────────────────────────

DOCKERFILE_AGENT = """\
# Claude Code Agent Container
# Each agent gets an isolated filesystem with its own git clone.
#
# Build: docker build -t claude-agent -f Dockerfile.agent .
# The entrypoint script handles clone → work → push.

FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    jq \\
    build-essential \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Node.js (for MCP servers and npx-based tools)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Python + UV (for Python projects)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Git config for the agent
RUN git config --global user.name "claude-agent" \\
    && git config --global user.email "agent@localhost" \\
    && git config --global init.defaultBranch main

# Working directories
RUN mkdir -p /upstream /workspace /output

# Entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
"""

# ── Entrypoint Script ──────────────────────────────────────────────────

ENTRYPOINT_SCRIPT = """\
#!/bin/bash
# Agent container entrypoint
#
# Environment variables:
#   AGENT_NAME     - Unique name for this agent (e.g., "frontend-agent")
#   AGENT_TASK     - Task description for the agent
#   AGENT_BRANCH   - Branch name to work on (default: agent/$AGENT_NAME)
#   REPO_URL       - URL or path to clone from (default: /upstream)
#   ANTHROPIC_API_KEY - Required for Claude Code
#   AGENT_MODE     - "claude" (run Claude Code) or "shell" (interactive bash)
#
# Lifecycle:
#   1. Clone repo from /upstream (or REPO_URL)
#   2. Create agent branch
#   3. Run Claude Code with the task (or drop to shell)
#   4. Push results back to /upstream

set -euo pipefail

AGENT_NAME="${AGENT_NAME:-agent-$(hostname)}"
AGENT_BRANCH="${AGENT_BRANCH:-agent/$AGENT_NAME}"
REPO_URL="${REPO_URL:-/upstream}"
AGENT_MODE="${AGENT_MODE:-claude}"

echo "=== Agent: $AGENT_NAME ==="
echo "  Branch: $AGENT_BRANCH"
echo "  Repo: $REPO_URL"
echo "  Mode: $AGENT_MODE"
echo ""

# ── Step 1: Clone ─────────────────────────────────────────────────────
if [ -d "/upstream/.git" ] || [ -f "/upstream/HEAD" ]; then
    echo "Cloning from /upstream..."
    git clone /upstream /workspace 2>/dev/null || {
        # If /workspace already has content, pull instead
        cd /workspace
        git pull origin main 2>/dev/null || true
    }
elif [ -n "$REPO_URL" ] && [ "$REPO_URL" != "/upstream" ]; then
    echo "Cloning from $REPO_URL..."
    git clone "$REPO_URL" /workspace 2>/dev/null || {
        cd /workspace
        git pull origin main 2>/dev/null || true
    }
else
    echo "No repo found at /upstream and no REPO_URL set."
    echo "Starting with empty workspace."
    cd /workspace
    git init
fi

cd /workspace

# ── Step 2: Create agent branch ──────────────────────────────────────
git checkout -b "$AGENT_BRANCH" 2>/dev/null || git checkout "$AGENT_BRANCH"
echo "On branch: $(git branch --show-current)"

# ── Step 3: Run the task ─────────────────────────────────────────────
if [ "$AGENT_MODE" = "claude" ]; then
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "ERROR: ANTHROPIC_API_KEY not set. Cannot run Claude Code."
        exit 1
    fi

    if [ -z "${AGENT_TASK:-}" ]; then
        echo "ERROR: AGENT_TASK not set. Nothing to do."
        exit 1
    fi

    echo ""
    echo "Running Claude Code with task:"
    echo "  $AGENT_TASK"
    echo ""

    # Run Claude Code in non-interactive mode
    claude --dangerously-skip-permissions --print "$AGENT_TASK"

elif [ "$AGENT_MODE" = "shell" ]; then
    echo "Dropping to interactive shell..."
    exec /bin/bash
else
    echo "Unknown AGENT_MODE: $AGENT_MODE"
    exit 1
fi

# ── Step 4: Push results ─────────────────────────────────────────────
echo ""
echo "=== Pushing results ==="
git add -A
git diff --cached --quiet || {
    git commit -m "agent($AGENT_NAME): completed task"
    git push origin "$AGENT_BRANCH" 2>/dev/null || {
        # If pushing to /upstream (bare repo)
        git push /upstream "$AGENT_BRANCH" 2>/dev/null || {
            echo "WARNING: Could not push to upstream. Results are in /workspace."
        }
    }
}

echo ""
echo "=== Agent $AGENT_NAME finished ==="
"""

# ── Docker Compose Template ───────────────────────────────────────────

COMPOSE_TEMPLATE = """\
# Docker Compose for parallel Claude agents
# Generated by superclaude bootstrap --docker-agents
#
# Usage:
#   docker compose up --build         # Start all agents
#   docker compose up frontend-agent  # Start one agent
#   docker compose logs -f            # Watch all agents
#   docker compose down               # Stop all agents
#
# The 'upstream' volume is a bare git repo shared by all agents.
# Each agent clones it, works on its own branch, and pushes back.

x-agent-common: &agent-common
  build:
    context: .
    dockerfile: Dockerfile.agent
  environment:
    - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
    - AGENT_MODE=${{AGENT_MODE:-claude}}
  volumes:
    - upstream:/upstream
  restart: "no"

services:
  # Initialize the bare git repo from the host project
  init-upstream:
    image: alpine/git:latest
    volumes:
      - upstream:/upstream
      - ${{HOST_PROJECT_DIR:-./../..}}:/source:ro
    entrypoint: /bin/sh
    command: >
      -c "
        if [ ! -f /upstream/HEAD ]; then
          echo 'Initializing bare repo...'
          git init --bare /upstream
          cd /source
          git push /upstream HEAD:main 2>/dev/null || {{
            cd /tmp
            git clone /source work
            cd work
            git push /upstream HEAD:main
          }}
          echo 'Upstream initialized.'
        else
          echo 'Upstream already initialized.'
        fi
      "

{agent_services}

  # CI runner: merges agent branches and runs tests
  ci-runner:
    <<: *agent-common
    container_name: ci-runner
    depends_on: [{agent_depends}]
    environment:
      - AGENT_NAME=ci-runner
      - AGENT_MODE=shell
      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
    entrypoint: /bin/sh
    command: >
      -c "
        echo '=== CI Runner ==='
        git clone /upstream /workspace
        cd /workspace
{merge_commands}
        echo ''
        echo '=== Running tests ==='
        # Auto-detect and run tests
        if [ -f pyproject.toml ]; then
          uv run pytest --tb=short -q 2>&1 || true
        elif [ -f package.json ]; then
          npm install && npm test 2>&1 || true
        elif [ -f go.mod ]; then
          go test ./... 2>&1 || true
        elif [ -f Cargo.toml ]; then
          cargo test 2>&1 || true
        fi
        echo '=== CI Complete ==='
      "

volumes:
  upstream:
    driver: local
"""

# ── Agent Service Template ─────────────────────────────────────────────

AGENT_SERVICE_TEMPLATE = """\
  {name}:
    <<: *agent-common
    container_name: {name}
    depends_on:
      init-upstream:
        condition: service_completed_successfully
    environment:
      - AGENT_NAME={name}
      - AGENT_TASK={task}
      - AGENT_BRANCH=agent/{name}
      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
      - AGENT_MODE=${{AGENT_MODE:-claude}}
"""

# ── Multi-Repo Compose Addition ───────────────────────────────────────

MULTI_REPO_INIT_TEMPLATE = """\
  init-{repo_name}:
    image: alpine/git:latest
    volumes:
      - {repo_name}-upstream:/upstream
      - {host_path}:/source:ro
    entrypoint: /bin/sh
    command: >
      -c "
        if [ ! -f /upstream/HEAD ]; then
          git init --bare /upstream
          cd /source && git push /upstream HEAD:main 2>/dev/null || {{
            cd /tmp && git clone /source work && cd work && git push /upstream HEAD:main
          }}
        fi
      "
"""

MULTI_REPO_AGENT_TEMPLATE = """\
  {name}:
    <<: *agent-common
    container_name: {name}
    depends_on:
      init-{repo_name}:
        condition: service_completed_successfully
    environment:
      - AGENT_NAME={name}
      - AGENT_TASK={task}
      - AGENT_BRANCH=agent/{name}
      - REPO_URL=/upstream
      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
      - AGENT_MODE=${{AGENT_MODE:-claude}}
    volumes:
      - {repo_name}-upstream:/upstream
"""


class DockerAgentOrchestrator:
    """Generates Docker infrastructure for parallel Claude agents."""

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.docker_dir = self.project_dir / ".claude" / "docker-agents"

    def generate_single_repo(
        self,
        agents: List[Dict[str, str]],
    ) -> Dict[str, str]:
        """
        Generate Docker files for parallel agents on a single repo.

        Args:
            agents: List of {"name": "...", "task": "..."}

        Returns:
            Dict mapping filename → content
        """
        # Generate agent service blocks
        agent_services = ""
        agent_names = []
        merge_commands = ""

        for agent in agents:
            name = agent["name"]
            task = agent["task"].replace('"', '\\"')
            agent_names.append(name)
            agent_services += AGENT_SERVICE_TEMPLATE.format(name=name, task=task)
            merge_commands += (
                f"        git merge origin/agent/{name} --no-edit 2>/dev/null || "
                f"echo 'Conflict merging {name} - manual resolution needed'\n"
            )

        agent_depends = ", ".join(agent_names)

        compose = COMPOSE_TEMPLATE.format(
            agent_services=agent_services,
            agent_depends=agent_depends,
            merge_commands=merge_commands,
        )

        return {
            "docker-compose.yml": compose,
            "Dockerfile.agent": DOCKERFILE_AGENT,
            "entrypoint.sh": ENTRYPOINT_SCRIPT,
        }

    def generate_multi_repo(
        self,
        repos: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Generate Docker files for parallel agents across multiple repos.

        Args:
            repos: List of {
                "name": "frontend",
                "path": "../frontend",
                "agents": [{"name": "...", "task": "..."}]
            }

        Returns:
            Dict mapping filename → content
        """
        init_services = ""
        agent_services = ""
        all_agent_names = []
        volumes = ["  upstream:\n    driver: local"]
        merge_commands = ""

        for repo in repos:
            repo_name = repo["name"]
            host_path = repo.get("path", f"../../{repo_name}")

            # Init service for this repo
            init_services += MULTI_REPO_INIT_TEMPLATE.format(
                repo_name=repo_name,
                host_path=host_path,
            )

            volumes.append(f"  {repo_name}-upstream:\n    driver: local")

            for agent in repo.get("agents", []):
                name = agent["name"]
                task = agent["task"].replace('"', '\\"')
                all_agent_names.append(name)

                agent_services += MULTI_REPO_AGENT_TEMPLATE.format(
                    name=name,
                    repo_name=repo_name,
                    task=task,
                )

        # Build a simpler compose for multi-repo (no single CI runner)
        compose = f"""\
# Docker Compose for multi-repo parallel Claude agents
# Generated by superclaude bootstrap --docker-agents

x-agent-common: &agent-common
  build:
    context: .
    dockerfile: Dockerfile.agent
  environment:
    - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
    - AGENT_MODE=${{AGENT_MODE:-claude}}
  restart: "no"

services:
{init_services}
{agent_services}

volumes:
"""
        for v in volumes:
            compose += v + "\n"

        return {
            "docker-compose.yml": compose,
            "Dockerfile.agent": DOCKERFILE_AGENT,
            "entrypoint.sh": ENTRYPOINT_SCRIPT,
        }

    def generate_example_configs(self) -> Dict[str, List[Dict[str, str]]]:
        """Generate example agent configurations for common project types."""
        return {
            "single_repo": [
                {"name": "feature-agent", "task": "Implement the feature described in the TODO"},
                {"name": "test-agent", "task": "Write comprehensive tests for recent changes"},
                {"name": "review-agent", "task": "Review all code for security and quality issues"},
            ],
            "fullstack": [
                {
                    "name": "frontend",
                    "path": "../frontend",
                    "agents": [
                        {"name": "ui-agent", "task": "Implement the UI components"},
                        {"name": "frontend-test-agent", "task": "Write frontend tests"},
                    ],
                },
                {
                    "name": "backend",
                    "path": "../backend",
                    "agents": [
                        {"name": "api-agent", "task": "Implement the API endpoints"},
                        {"name": "backend-test-agent", "task": "Write API tests"},
                    ],
                },
            ],
            "microservices": [
                {
                    "name": "auth-service",
                    "path": "../auth-service",
                    "agents": [
                        {"name": "auth-agent", "task": "Implement auth feature"},
                    ],
                },
                {
                    "name": "api-gateway",
                    "path": "../api-gateway",
                    "agents": [
                        {"name": "gateway-agent", "task": "Update gateway routing"},
                    ],
                },
                {
                    "name": "frontend",
                    "path": "../frontend",
                    "agents": [
                        {"name": "frontend-agent", "task": "Implement UI for the feature"},
                    ],
                },
            ],
        }

    def install(
        self,
        agents: Optional[List[Dict[str, str]]] = None,
        repos: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Generate Docker agent infrastructure.

        If repos is provided, generates multi-repo config.
        Otherwise, generates single-repo config with the given agents.
        """
        if repos:
            files = self.generate_multi_repo(repos)
            mode = "multi-repo"
        else:
            if agents is None:
                agents = self.generate_example_configs()["single_repo"]
            files = self.generate_single_repo(agents)
            mode = "single-repo"

        if dry_run:
            lines = [
                f"Would create {len(files)} files in {self.docker_dir}:",
                f"  Mode: {mode}",
            ]
            for name in files:
                lines.append(f"  {name}")
            if repos:
                for repo in repos:
                    agent_count = len(repo.get("agents", []))
                    lines.append(f"  Repo '{repo['name']}': {agent_count} agent(s)")
            else:
                lines.append(f"  Agents: {len(agents)}")
            lines.extend([
                "",
                "Usage after generation:",
                "  cd .claude/docker-agents",
                "  export ANTHROPIC_API_KEY=your-key",
                "  docker compose up --build",
            ])
            return True, "\n".join(lines)

        self.docker_dir.mkdir(parents=True, exist_ok=True)

        for name, content in files.items():
            path = self.docker_dir / name
            path.write_text(content)
            # Make scripts executable
            if name.endswith(".sh"):
                path.chmod(path.stat().st_mode | 0o755)

        # Write a .env.example
        env_example = self.docker_dir / ".env.example"
        env_example.write_text(
            "# Copy to .env and fill in your values\n"
            "ANTHROPIC_API_KEY=sk-ant-...\n"
            "AGENT_MODE=claude  # or 'shell' for interactive\n"
            "HOST_PROJECT_DIR=../../  # path to your project root\n"
        )

        agent_count = sum(len(r.get("agents", [])) for r in repos) if repos else len(agents)

        lines = [
            f"Created Docker agent infrastructure in {self.docker_dir}",
            f"  Mode: {mode}",
            f"  Agents: {agent_count}",
            f"  Files: {', '.join(files.keys())}",
            "",
            "Usage:",
            f"  cd {self.docker_dir}",
            "  cp .env.example .env   # Add your ANTHROPIC_API_KEY",
            "  docker compose up --build",
            "",
            "How it works:",
            "  1. init-upstream: creates a bare git repo from your project",
            "  2. Each agent clones the bare repo to its own /workspace",
            "  3. Agents work on separate branches (agent/<name>)",
            "  4. When done, agents push back to the bare repo",
            "  5. ci-runner merges all branches and runs tests",
            "",
            "Customization:",
            "  Edit docker-compose.yml to change agent tasks",
            "  Set AGENT_MODE=shell for interactive debugging",
            "  Add more agents by copying a service block",
        ]

        return True, "\n".join(lines)
