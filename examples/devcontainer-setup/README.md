# DevContainer Setup Example

This example shows how to use claude-cognitive inside a VS Code DevContainer or Docker container.

## What's Included

- `.devcontainer/devcontainer.json` - VS Code DevContainer configuration
- `.devcontainer/Dockerfile` - Container image definition
- `.devcontainer/setup-claude-cognitive.sh` - Automatic setup script
- `.devcontainer/health-check.sh` - Validation script

## Quick Start with VS Code

### 1. Copy to Your Project

```bash
# Copy the entire .devcontainer directory to your project root
cp -r .devcontainer /path/to/your/project/
```

### 2. Open in VS Code

```bash
cd /path/to/your/project
code .
```

### 3. Reopen in Container

- Command Palette (`Cmd+Shift+P` or `Ctrl+Shift+P`)
- Select: "Dev Containers: Reopen in Container"
- Wait for build and setup to complete

### 4. Start Using

```bash
# Inside the container terminal
claude
```

You should see the ATTENTION STATE header indicating claude-cognitive is working!

## Quick Start with Docker CLI

### 1. Build Image

```bash
docker build -t my-project-claude -f .devcontainer/Dockerfile .
```

### 2. Run Container

```bash
docker run -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/home/node/.claude" \
  -e CLAUDE_INSTANCE="${CLAUDE_INSTANCE:-docker}" \
  --workdir /workspace \
  my-project-claude bash
```

### 3. Setup (First Time)

```bash
# Inside container
bash .devcontainer/setup-claude-cognitive.sh
bash .devcontainer/health-check.sh
```

### 4. Start Using

```bash
claude
```

## Multi-Container Setup with Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend-dev:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - .:/workspace
      - ~/.claude:/home/node/.claude
    environment:
      - CLAUDE_INSTANCE=backend
    working_dir: /workspace
    stdin_open: true
    tty: true
    command: bash

  frontend-dev:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - .:/workspace
      - ~/.claude:/home/node/.claude
    environment:
      - CLAUDE_INSTANCE=frontend
    working_dir: /workspace
    stdin_open: true
    tty: true
    command: bash
```

**Usage:**
```bash
# Start containers
docker-compose up -d

# Work in backend container
docker-compose exec backend-dev bash
claude

# In another terminal, work in frontend container
docker-compose exec frontend-dev bash
claude

# Pool coordination works automatically between containers!
```

## What Gets Set Up

The setup script automatically:

1. ✅ Clones claude-cognitive to `~/.claude-cognitive`
2. ✅ Installs scripts to `~/.claude/scripts/`
3. ✅ Configures Claude Code hooks in `~/.claude/settings.json`
4. ✅ Creates project `.claude/` directory structure
5. ✅ Copies documentation templates
6. ✅ Validates the setup

## Customization

### Set Instance ID

**In devcontainer.json:**
```json
{
  "remoteEnv": {
    "CLAUDE_INSTANCE": "my-instance-name"
  }
}
```

**Or set on host machine:**
```bash
export CLAUDE_INSTANCE=A
# Then reopen in container
```

### Modify Dockerfile

Add project-specific dependencies:

```dockerfile
# Install project dependencies
RUN apt-get update && apt-get install -y \
    your-tool \
    another-tool \
    && rm -rf /var/lib/apt/lists/*
```

### Skip Health Check

If you don't want the health check to run automatically:

```json
{
  "postCreateCommand": "bash .devcontainer/setup-claude-cognitive.sh"
}
```

## Troubleshooting

### "Scripts not found"

The setup script should run automatically. If not:

```bash
bash .devcontainer/setup-claude-cognitive.sh
```

### "No ATTENTION STATE header"

Check that hooks are configured:

```bash
cat ~/.claude/settings.json | jq '.hooks'
```

Should show context-router and pool scripts.

### "Permission denied"

Make scripts executable:

```bash
chmod +x ~/.claude/scripts/*.py
```

### "Pool not working"

Ensure `~/.claude` is mounted:

```bash
ls -la ~/.claude/pool/
```

Should exist and be writable.

## Next Steps

1. **Edit `.claude/CLAUDE.md`** - Add your project information
2. **Document systems** - Create files in `.claude/systems/`
3. **Document modules** - Create files in `.claude/modules/`
4. **Customize keywords** - Edit `~/.claude/scripts/context-router-v2.py`
5. **Read the full guide** - [docker-devcontainer-setup.md](../../docs/guides/docker-devcontainer-setup.md)

## Architecture

```
Container Environment
├── /workspace/              # Your project (mounted from host)
│   └── .claude/             # Project-specific docs (commit to git)
│       ├── CLAUDE.md
│       ├── systems/
│       ├── modules/
│       └── integrations/
│
└── /home/node/
    ├── .claude/             # User config (mounted from host ~/.claude)
    │   ├── settings.json    # Claude Code settings + hooks
    │   ├── scripts/         # claude-cognitive scripts
    │   ├── pool/            # Multi-instance coordination
    │   └── attn_state.json  # Attention scores (runtime state)
    │
    └── .claude-cognitive/   # Source repository
        ├── scripts/         # Original scripts
        └── templates/       # Documentation templates
```

## Features

✅ **Automatic setup** - postCreateCommand handles everything
✅ **Persistent state** - Volume mounts preserve ~/.claude/
✅ **Multi-container** - Pool coordination across containers
✅ **VS Code integrated** - Works seamlessly with Dev Containers
✅ **CLI friendly** - Also works with plain Docker
✅ **Validated** - Health check ensures correct setup

## Resources

- [Full Docker Guide](../../docs/guides/docker-devcontainer-setup.md)
- [Getting Started](../../docs/guides/getting-started.md)
- [Main README](../../README.md)
- [Customization Guide](../../CUSTOMIZATION.md)

## Support

Questions or issues? 
- [GitHub Issues](https://github.com/GMaN1911/claude-cognitive/issues)
- [GitHub Discussions](https://github.com/GMaN1911/claude-cognitive/discussions)
