# Docker & DevContainer Quick Reference

Quick reference for using claude-cognitive in Docker/DevContainer environments.

## TL;DR

```bash
# Copy example config to your project
cp -r examples/devcontainer-setup/.devcontainer /path/to/your/project/

# Open in VS Code
code /path/to/your/project

# Reopen in Container (Cmd+Shift+P > "Reopen in Container")

# Setup runs automatically, then:
claude
```

## Key Concepts

### Volume Mounts

Mount `~/.claude` for persistence:
```json
"mounts": [
  "source=${localEnv:HOME}/.claude,target=/home/node/.claude,type=bind"
]
```

### Instance IDs

Set per container for coordination:
```json
"remoteEnv": {
  "CLAUDE_INSTANCE": "${localEnv:CLAUDE_INSTANCE:docker}"
}
```

### Automatic Setup

Use `postCreateCommand`:
```json
"postCreateCommand": "bash .devcontainer/setup-claude-cognitive.sh"
```

## What Gets Mounted

| Path | Purpose | Commit to Git? |
|------|---------|----------------|
| `~/.claude/` | Settings, state, pool | ❌ No |
| `.claude/` | Project docs | ✅ Yes |
| `.devcontainer/` | Container config | ✅ Yes |

## Multi-Container Coordination

Each container needs unique `CLAUDE_INSTANCE`:

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - CLAUDE_INSTANCE=backend
  frontend:
    environment:
      - CLAUDE_INSTANCE=frontend
```

Pool coordination works automatically via shared `~/.claude/pool/`!

## Common Issues

### No ATTENTION STATE header
```bash
# Check hooks
cat ~/.claude/settings.json | jq '.hooks'

# Test router
echo '{"prompt":"test"}' | python3 ~/.claude/scripts/context-router-v2.py
```

### Pool not working
```bash
# Verify mount
ls -la ~/.claude/pool/

# Check instance ID
echo $CLAUDE_INSTANCE
```

### Scripts not executable
```bash
chmod +x ~/.claude/scripts/*.py
```

## Files Structure

```
Container:
├── /workspace/              # Your project (mounted)
│   └── .claude/            # Docs (commit)
└── /home/node/
    ├── .claude/            # State (mounted, don't commit)
    │   ├── settings.json
    │   ├── scripts/
    │   └── pool/
    └── .claude-cognitive/  # Source repo
```

## Documentation

- [Full Docker Guide](../../docs/guides/docker-devcontainer-setup.md)
- [Example Setup](../../examples/devcontainer-setup/)
- [Getting Started](../../docs/guides/getting-started.md)

## Examples

### VS Code DevContainer
See: `examples/devcontainer-setup/`

### Plain Docker
```bash
docker run -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/home/node/.claude" \
  -e CLAUDE_INSTANCE=docker \
  my-project-claude bash
```

### Docker Compose
```yaml
version: '3.8'
services:
  dev:
    build: .devcontainer
    volumes:
      - .:/workspace
      - ~/.claude:/home/node/.claude
    environment:
      - CLAUDE_INSTANCE=A
```
