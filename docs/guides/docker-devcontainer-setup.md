# Docker & DevContainer Setup

> **Goal:** Use claude-cognitive inside Docker containers and VS Code DevContainers

This guide explains how to set up and use claude-cognitive when running Claude Code inside a Docker container or VS Code DevContainer environment.

---

## Overview

Claude Code can run inside containers for:
- **Isolation**: Sandboxed execution environment
- **Consistency**: Same environment across team members
- **Security**: Network restrictions and resource limits
- **Platform support**: Works on Windows, macOS, and Linux

**claude-cognitive works seamlessly inside containers** with a few setup considerations.

---

## Quick Start: DevContainer Setup

### Prerequisites

- Docker Desktop or Podman installed
- VS Code with Dev Containers extension (for VS Code integration)
- OR: Dev Containers CLI (`npm install -g @devcontainers/cli`)

### Option A: Using VS Code DevContainer

#### 1. Clone Your Project with DevContainer Config

```bash
git clone https://github.com/your-org/your-project.git
cd your-project
```

#### 2. Add claude-cognitive to DevContainer

Create or edit `.devcontainer/devcontainer.json`:

```json
{
  "name": "Your Project with claude-cognitive",
  "build": {
    "dockerfile": "Dockerfile"
  },
  "features": {
    "ghcr.io/devcontainers/features/node:1": {},
    "ghcr.io/anthropics/devcontainer-features/claude-code:1": {}
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "anthropic.claude-code"
      ]
    }
  },
  "postCreateCommand": "bash .devcontainer/setup-claude-cognitive.sh",
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/node/.claude,type=bind,consistency=cached"
  ],
  "remoteEnv": {
    "CLAUDE_INSTANCE": "${localEnv:CLAUDE_INSTANCE:default}"
  }
}
```

#### 3. Create Setup Script

Create `.devcontainer/setup-claude-cognitive.sh`:

```bash
#!/bin/bash
set -e

echo "Setting up claude-cognitive..."

# Clone claude-cognitive if not already present
if [ ! -d "$HOME/.claude-cognitive" ]; then
    git clone https://github.com/GMaN1911/claude-cognitive.git "$HOME/.claude-cognitive"
fi

# Create directories
mkdir -p "$HOME/.claude/scripts"
mkdir -p "$HOME/.claude/pool"

# Copy scripts
cp -r "$HOME/.claude-cognitive/scripts/"*.py "$HOME/.claude/scripts/"
chmod +x "$HOME/.claude/scripts/"*.py

# Configure hooks
python3 << 'PYTHON'
import json
from pathlib import Path

settings_file = Path.home() / ".claude/settings.json"

# Load existing or create new
if settings_file.exists():
    with open(settings_file) as f:
        settings = json.load(f)
else:
    settings = {}

# Ensure hooks structure exists
if "hooks" not in settings:
    settings["hooks"] = {}

# Add hooks
settings["hooks"]["UserPromptSubmit"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"}
    ]
}]

settings["hooks"]["SessionStart"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"}
    ]
}]

settings["hooks"]["Stop"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"}
    ]
}]

# Write back
settings_file.parent.mkdir(parents=True, exist_ok=True)
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("✓ Hooks configured successfully")
PYTHON

# Initialize project .claude directory
mkdir -p /workspaces/"$(basename $(pwd))"/.claude/{systems,modules,integrations,pool}

# Copy templates if they don't exist
if [ ! -f /workspaces/"$(basename $(pwd))"/.claude/CLAUDE.md ]; then
    cp -r "$HOME/.claude-cognitive/templates/"* /workspaces/"$(basename $(pwd))"/.claude/
fi

echo "✓ claude-cognitive setup complete!"
echo "  - Scripts installed to ~/.claude/scripts/"
echo "  - Hooks configured in ~/.claude/settings.json"
echo "  - Project templates copied to .claude/"
echo ""
echo "Next steps:"
echo "  1. Edit .claude/CLAUDE.md with your project info"
echo "  2. Set CLAUDE_INSTANCE environment variable (optional)"
echo "  3. Start Claude Code: claude"
```

Make it executable:
```bash
chmod +x .devcontainer/setup-claude-cognitive.sh
```

#### 4. Open in Container

In VS Code:
- Open Command Palette (`Cmd+Shift+P` or `Ctrl+Shift+P`)
- Run: "Dev Containers: Reopen in Container"

The container will build and automatically set up claude-cognitive!

---

### Option B: Using Docker CLI

#### 1. Create Dockerfile

Create `.devcontainer/Dockerfile`:

```dockerfile
FROM node:20

# Install Claude Code
RUN npm install -g @anthropic/claude-code

# Install dependencies for claude-cognitive
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash claude

USER claude
WORKDIR /home/claude

# Clone and setup claude-cognitive
RUN git clone https://github.com/GMaN1911/claude-cognitive.git .claude-cognitive

# Copy scripts
RUN mkdir -p .claude/scripts && \
    cp .claude-cognitive/scripts/*.py .claude/scripts/ && \
    chmod +x .claude/scripts/*.py

# Set up default instance
ENV CLAUDE_INSTANCE=docker

CMD ["/bin/bash"]
```

#### 2. Build and Run

```bash
# Build the image
docker build -t claude-cognitive -f .devcontainer/Dockerfile .

# Run with project mounted
docker run -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/home/claude/.claude" \
  -e CLAUDE_INSTANCE="${CLAUDE_INSTANCE:-docker}" \
  --workdir /workspace \
  claude-cognitive bash

# Inside container, configure hooks (first time only)
python3 /home/claude/.claude-cognitive/scripts/setup-hooks.py

# Initialize project
mkdir -p .claude/{systems,modules,integrations,pool}
cp -r ~/.claude-cognitive/templates/* .claude/

# Start Claude Code
claude
```

---

## Architecture Considerations

### Volume Mounts

**Key directories to mount:**

1. **`~/.claude`** - Settings, attention state, pool data
   - Should persist across container restarts
   - Can be shared across containers for coordination

2. **Project directory** - Your codebase
   - Mount to `/workspace` or similar
   - Where `.claude/` project configuration lives

3. **Optional: `~/.claude-cognitive`** - Source repository
   - For easy updates and template access

### Instance IDs in Containers

Set unique `CLAUDE_INSTANCE` per container:

```bash
# Container 1 - Backend work
docker run -e CLAUDE_INSTANCE=backend ...

# Container 2 - Frontend work  
docker run -e CLAUDE_INSTANCE=frontend ...

# Container 3 - Testing
docker run -e CLAUDE_INSTANCE=test ...
```

**Pool coordination works across containers** as long as they share the `~/.claude/pool/` directory!

---

## End-to-End Workflow

### 1. Initial Setup (One Time)

```bash
# On host machine
cd ~/your-project

# Create devcontainer config
mkdir .devcontainer
# Copy devcontainer.json and Dockerfile from above
```

### 2. Start Container with claude-cognitive

**Using VS Code:**
- Open project in VS Code
- "Reopen in Container"
- Setup runs automatically

**Using CLI:**
```bash
# Build and run
docker run -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/home/claude/.claude" \
  -e CLAUDE_INSTANCE=A \
  claude-cognitive bash
```

### 3. Initialize Project (First Time)

```bash
# Inside container
cd /workspace

# Create structure
mkdir -p .claude/{systems,modules,integrations,pool}

# Copy templates
cp -r ~/.claude-cognitive/templates/* .claude/

# Customize
vim .claude/CLAUDE.md
```

### 4. Start Claude Code

```bash
claude
```

**You should see:**
```
╔══ ATTENTION STATE [Turn 1] ══╗
║ 🔥 Hot: 0 │ 🌡️ Warm: 0 │ ❄️ Cold: X ║
...
```

### 5. Work Normally

- Context router activates files automatically
- Pool coordination works across containers
- Attention history persists in `~/.claude/`

### 6. Coordinate with Other Containers

**Container A:**
```pool
INSTANCE: backend
ACTION: completed
TOPIC: API authentication refactor
SUMMARY: Migrated to JWT tokens. All endpoints updated.
AFFECTS: api/auth.py, api/middleware.py
BLOCKS: Frontend can now implement new auth flow
```

**Container B (frontend)** sees this at session start:
```
### Recent Activity
- [backend] completed: API authentication refactor
```

---

## Multi-Container Team Setup

### Docker Compose Example

```yaml
version: '3.8'

services:
  backend-dev:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - .:/workspace
      - ~/.claude:/home/claude/.claude
    environment:
      - CLAUDE_INSTANCE=backend
    working_dir: /workspace
    stdin_open: true
    tty: true

  frontend-dev:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - .:/workspace
      - ~/.claude:/home/claude/.claude
    environment:
      - CLAUDE_INSTANCE=frontend
    working_dir: /workspace
    stdin_open: true
    tty: true

  test-runner:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - .:/workspace
      - ~/.claude:/home/claude/.claude
    environment:
      - CLAUDE_INSTANCE=test
    working_dir: /workspace
    stdin_open: true
    tty: true
```

**Usage:**
```bash
# Start all containers
docker-compose up -d

# Attach to backend container
docker-compose exec backend-dev bash
claude

# In another terminal, attach to frontend container
docker-compose exec frontend-dev bash
claude

# Pool coordination works automatically!
```

---

## Security Considerations

### Network Restrictions

Anthropic's devcontainer includes firewall rules that restrict network access. claude-cognitive scripts only need:

- **Local filesystem access** - Already available
- **No external network** - Scripts are pure Python

If using Anthropic's devcontainer with `init-firewall.sh`:
```bash
# claude-cognitive scripts work without modification
# They only read/write local files in ~/.claude/ and .claude/
```

### API Key Storage

- Claude Code stores API keys in `~/.claude/` by default
- **Mount as volume** to persist across container rebuilds
- **Don't commit** `.claude/` to version control
- Use `.gitignore`:
  ```
  .claude/settings.json
  .claude/attn_state.json
  .claude/pool/
  .claude/*.log
  ```

### Permission Skipping

Anthropic's devcontainer supports `--dangerously-skip-permissions` for automation:
```bash
# In container startup script
claude --dangerously-skip-permissions
```

**Use with caution** - only in trusted, isolated environments.

---

## Persistence Strategy

### What to Persist

**✅ Mount as volumes:**
- `~/.claude/` - Settings, state, pool data
- Project `.claude/` - Documentation (commit to git)

**✅ Commit to git:**
- `.claude/CLAUDE.md` - Project context
- `.claude/systems/*.md` - System docs
- `.claude/modules/*.md` - Module docs
- `.devcontainer/` - Container config

**❌ Don't commit:**
- `~/.claude/settings.json` - Contains API keys
- `.claude/attn_state.json` - Runtime state
- `.claude/pool/` - Coordination logs
- `~/.claude/attention_history.jsonl` - History logs

---

## Troubleshooting

### "No ATTENTION STATE header in container"

**Check:**
```bash
# 1. Verify scripts exist
ls -lh ~/.claude/scripts/

# 2. Test manually
echo '{"prompt":"test"}' | python3 ~/.claude/scripts/context-router-v2.py

# 3. Check hooks
cat ~/.claude/settings.json | jq '.hooks'

# 4. Verify Python available
python3 --version
```

### "Pool not working across containers"

**Check:**
```bash
# 1. Verify shared mount
ls -lh ~/.claude/pool/

# 2. Check instance ID differs
echo $CLAUDE_INSTANCE

# 3. Test pool query
python3 ~/.claude/scripts/pool-query.py --since 1h

# 4. Verify permissions
ls -l ~/.claude/pool/instance_state.jsonl
```

### "Scripts not executable in container"

```bash
# Fix permissions
chmod +x ~/.claude/scripts/*.py

# Or run with python3 explicitly
python3 ~/.claude/scripts/context-router-v2.py
```

### "Volume mount not persisting"

**Check Docker volume:**
```bash
# On host
docker volume ls
docker volume inspect <volume-name>

# Ensure using bind mount, not named volume
docker run -v "$HOME/.claude:/home/claude/.claude" ...
#          ^^^^^^^^^^^^^^^^ absolute path required
```

---

## Best Practices

### 1. One Container Per Task Area

```bash
# Instead of one container doing everything
CLAUDE_INSTANCE=A

# Use task-specific containers
CLAUDE_INSTANCE=backend    # Container for API work
CLAUDE_INSTANCE=frontend   # Container for UI work  
CLAUDE_INSTANCE=database   # Container for schema work
CLAUDE_INSTANCE=deploy     # Container for ops work
```

### 2. Shared Documentation, Separate State

- **Commit** `.claude/CLAUDE.md` and docs to git
- **Mount** `~/.claude/` as volume for state
- **Set** unique `CLAUDE_INSTANCE` per container

### 3. Use postCreateCommand

```json
{
  "postCreateCommand": "bash .devcontainer/setup-claude-cognitive.sh"
}
```

This ensures claude-cognitive is configured automatically on container creation.

### 4. Health Check Script

Create `.devcontainer/health-check.sh`:

```bash
#!/bin/bash

echo "Checking claude-cognitive setup..."

checks_passed=0
checks_total=0

# Check 1: Scripts installed
checks_total=$((checks_total + 1))
if [ -d "$HOME/.claude/scripts" ] && [ -f "$HOME/.claude/scripts/context-router-v2.py" ]; then
    echo "✓ Scripts installed"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Scripts not found"
fi

# Check 2: Hooks configured
checks_total=$((checks_total + 1))
if [ -f "$HOME/.claude/settings.json" ] && grep -q "context-router" "$HOME/.claude/settings.json"; then
    echo "✓ Hooks configured"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Hooks not configured"
fi

# Check 3: Project .claude exists
checks_total=$((checks_total + 1))
if [ -d ".claude" ] && [ -f ".claude/CLAUDE.md" ]; then
    echo "✓ Project .claude directory exists"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Project .claude not initialized"
fi

# Check 4: Instance ID set
checks_total=$((checks_total + 1))
if [ -n "$CLAUDE_INSTANCE" ]; then
    echo "✓ CLAUDE_INSTANCE set to: $CLAUDE_INSTANCE"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ CLAUDE_INSTANCE not set (will use 'default')"
fi

echo ""
echo "Passed $checks_passed/$checks_total checks"

if [ $checks_passed -eq $checks_total ]; then
    echo "✓ claude-cognitive ready!"
    exit 0
else
    echo "⚠ Some checks failed. Review setup."
    exit 1
fi
```

Run after container starts:
```bash
bash .devcontainer/health-check.sh
```

---

## Example: Complete DevContainer Setup

### Project Structure
```
your-project/
├── .devcontainer/
│   ├── devcontainer.json
│   ├── Dockerfile
│   ├── setup-claude-cognitive.sh
│   └── health-check.sh
├── .claude/
│   ├── CLAUDE.md
│   ├── systems/
│   ├── modules/
│   └── integrations/
├── src/
└── ...
```

### devcontainer.json (Complete)
```json
{
  "name": "Your Project with claude-cognitive",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  },
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "20"
    },
    "ghcr.io/anthropics/devcontainer-features/claude-code:1": {}
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "anthropic.claude-code"
      ],
      "settings": {
        "terminal.integrated.defaultProfile.linux": "bash"
      }
    }
  },
  "postCreateCommand": "bash .devcontainer/setup-claude-cognitive.sh && bash .devcontainer/health-check.sh",
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/node/.claude,type=bind,consistency=cached"
  ],
  "remoteEnv": {
    "CLAUDE_INSTANCE": "${localEnv:CLAUDE_INSTANCE:docker}"
  },
  "runArgs": [
    "--cap-add=NET_ADMIN",
    "--cap-add=NET_RAW"
  ],
  "workspaceFolder": "/workspace",
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspace,type=bind,consistency=cached"
}
```

### Dockerfile (Complete)
```dockerfile
FROM node:20-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    vim \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (if not using devcontainer feature)
# RUN useradd -m -s /bin/bash -u 1000 node

USER node
WORKDIR /home/node

# Set up environment
ENV PATH="/home/node/.local/bin:${PATH}"
ENV CLAUDE_INSTANCE="${CLAUDE_INSTANCE:-docker}"

CMD ["/bin/bash"]
```

---

## Summary

**claude-cognitive works seamlessly in containers** with these key points:

✅ **Mount `~/.claude/` directory** for persistence
✅ **Set unique `CLAUDE_INSTANCE`** per container
✅ **Use `postCreateCommand`** for automatic setup
✅ **Share pool directory** for multi-container coordination
✅ **Commit `.claude/` docs** to version control
✅ **Don't commit state files** or API keys

**Workflow:**
1. Create devcontainer config with claude-cognitive setup
2. Open in container (VS Code) or run with Docker CLI
3. Automatic setup configures scripts and hooks
4. Use Claude Code normally - context router and pool work automatically
5. Pool coordinates across all containers sharing `~/.claude/`

**Next Steps:**
- [Getting Started Guide](./getting-started.md) - Basic concepts
- [Team Setup](./team-setup.md) - Multi-developer patterns
- [CUSTOMIZATION.md](../../CUSTOMIZATION.md) - Keyword tuning

---

**Questions?** Open an [issue](https://github.com/GMaN1911/claude-cognitive/issues) or [discussion](https://github.com/GMaN1911/claude-cognitive/discussions)
