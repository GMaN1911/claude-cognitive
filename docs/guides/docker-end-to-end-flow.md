# End-to-End Flow: claude-cognitive in Docker Containers

This document provides the complete end-to-end workflow for using claude-cognitive when running Claude Code inside a Docker container, as requested in the GitHub issue.

## Overview

**Question:** What would the end-to-end flow be for claude-cognitive when using Claude Code inside a Docker container?

**Answer:** claude-cognitive works seamlessly inside Docker containers with proper volume mounts and configuration. Below is the complete flow.

---

## Prerequisites

1. **Docker Desktop** (or Podman) installed
2. **VS Code** with Dev Containers extension (optional, for VS Code integration)
3. **Claude Code API key** ready

---

## End-to-End Flow

### Phase 1: Initial Container Setup

#### Step 1: Copy DevContainer Configuration

```bash
# Navigate to your project
cd /path/to/your/project

# Copy the example devcontainer setup
cp -r path/to/claude-cognitive/examples/devcontainer-setup/.devcontainer ./
```

**What this includes:**
- `devcontainer.json` - VS Code DevContainer configuration
- `Dockerfile` - Container image with Python, Node, and dependencies
- `setup-claude-cognitive.sh` - Automatic installation script
- `health-check.sh` - Validation script

#### Step 2: Open in Container

**Option A - VS Code:**
```bash
code /path/to/your/project
# In VS Code: Cmd+Shift+P > "Dev Containers: Reopen in Container"
```

**Option B - Docker CLI:**
```bash
docker build -t my-project-claude -f .devcontainer/Dockerfile .
docker run -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/home/node/.claude" \
  -e CLAUDE_INSTANCE="${CLAUDE_INSTANCE:-docker}" \
  --workdir /workspace \
  my-project-claude bash
```

#### Step 3: Automatic Setup (First Time)

When container starts, `postCreateCommand` automatically:

1. ✅ Clones claude-cognitive to `~/.claude-cognitive`
2. ✅ Creates `~/.claude/scripts/` directory
3. ✅ Copies scripts from repository
4. ✅ Configures Claude Code hooks in `~/.claude/settings.json`:
   - `UserPromptSubmit`: Context router + pool auto-update
   - `SessionStart`: Pool loader
   - `Stop`: Pool extractor
5. ✅ Creates project `.claude/` directory structure
6. ✅ Copies documentation templates
7. ✅ Runs health check to validate setup

**Output you'll see:**
```
Setting up claude-cognitive in devcontainer...
Cloning claude-cognitive repository...
Creating ~/.claude directories...
Installing claude-cognitive scripts...
Configuring Claude Code hooks...
✓ Hooks configured successfully
Initializing project .claude directory...
✓ Templates copied to /workspace/.claude/

✓ claude-cognitive setup complete!

Checking claude-cognitive setup...
==================================
✓ Scripts installed in ~/.claude/scripts/
✓ Hooks configured in ~/.claude/settings.json
✓ Project .claude directory initialized
✓ CLAUDE_INSTANCE set to: docker
✓ Python 3 available: Python 3.9.2
==================================
Passed 5/5 checks

✓ claude-cognitive is ready to use!
```

### Phase 2: Project Configuration

#### Step 4: Customize Project Documentation

```bash
# Inside container
cd /workspace

# Edit main project context
vim .claude/CLAUDE.md
```

**Customize with your project info:**
- Project name and purpose
- Main entry points
- Key commands (start, test, build)
- Critical environment variables

#### Step 5: Document Your Systems

```bash
# Create documentation for your systems
cp .claude/systems/example-system.md .claude/systems/production-server.md
vim .claude/systems/production-server.md
```

**Document:**
- Production servers
- Development environments
- Database systems
- External services

#### Step 6: Document Your Modules

```bash
# Create documentation for your modules
cp .claude/modules/example-module.md .claude/modules/authentication.md
vim .claude/modules/authentication.md
```

**Document:**
- Core application modules
- Shared libraries
- API endpoints
- Business logic components

### Phase 3: Using Claude Code

#### Step 7: Start Claude Code

```bash
# Inside container
claude
```

**On first launch:**
- You'll be prompted for your Anthropic API key
- Key is stored in `~/.claude/` (persisted via volume mount)

#### Step 8: Verify Context Router Working

**Your first prompt:**
```
Show me the project structure
```

**You should see:**
```
╔══ ATTENTION STATE [Turn 1] ══╗
║ 🔥 Hot: 1 │ 🌡️ Warm: 0 │ ❄️ Cold: 3 ║
╚════════════════════════════════════════╝

━━━ [🔥 HOT] .claude/CLAUDE.md (score: 1.00) ━━━
[Full project documentation injected automatically]

[Claude's response about your project structure]
```

**This confirms:**
- ✅ Context router is active
- ✅ Files are being injected automatically
- ✅ Attention system is tracking state

#### Step 9: Watch Attention Dynamics

**Try multiple queries:**

```
Turn 1: "How does authentication work?"
  → .claude/modules/authentication.md: HOT (full content)
  → Related files: WARM (headers)

Turn 2: "What about the database?"
  → .claude/systems/database.md: HOT (newly activated)
  → authentication.md: WARM (decayed)

Turn 3: "Back to authentication"
  → authentication.md: HOT again (reactivated)
```

**Files fade when not mentioned, activate on keywords!**

### Phase 4: Multi-Container Coordination

#### Step 10: Launch Additional Containers (Optional)

**For team or multi-task work:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend-dev:
    build: .devcontainer
    volumes:
      - .:/workspace
      - ~/.claude:/home/node/.claude  # Shared state!
    environment:
      - CLAUDE_INSTANCE=backend       # Unique ID
    stdin_open: true
    tty: true

  frontend-dev:
    build: .devcontainer
    volumes:
      - .:/workspace
      - ~/.claude:/home/node/.claude  # Shared state!
    environment:
      - CLAUDE_INSTANCE=frontend      # Unique ID
    stdin_open: true
    tty: true
```

**Start containers:**
```bash
docker-compose up -d
docker-compose exec backend-dev bash
# In container: claude
```

#### Step 11: Use Pool Coordination

**In backend container:**
```
user: "Fix the authentication bug"

assistant: [works on fix]

assistant: "Fixed! Here's what I did:

```pool
INSTANCE: backend
ACTION: completed
TOPIC: Auth bug - race condition in token refresh
SUMMARY: Added mutex locking to prevent concurrent token refreshes. 
         Updated tests. All passing.
AFFECTS: auth.py, session_handler.py, tests/test_auth.py
BLOCKS: Frontend can now implement new token refresh UI
```

All done!"
```

**In frontend container (new session):**
```
## Session Context
- **Instance**: frontend
- **Pool**: 1 recent (0 own, 1 others)

### Recent Activity
- [backend] completed: Auth bug - race condition in token refresh
```

**Frontend instance now knows what backend did!** No duplicate work.

### Phase 5: Monitoring and Maintenance

#### Step 12: Query Pool Activity

```bash
# Inside any container
python3 ~/.claude/scripts/pool-query.py --since 1h
```

**Output:**
```
╔═══════════════════════════════════════════╗
║            POOL COORDINATOR               ║
║          Last 1 hour of activity          ║
╚═══════════════════════════════════════════╝

[14:23:45] backend | completed
  Topic: Auth bug - race condition in token refresh
  Affects: auth.py, session_handler.py
  Blocks: Frontend can implement new UI

[15:10:22] frontend | started
  Topic: Implementing new token refresh UI
  Dependencies: Waiting for backend auth changes
```

#### Step 13: View Attention History

```bash
# View recent attention patterns
python3 ~/.claude/scripts/history.py --since 2h
```

**Output:**
```
[14:30:15] backend | Turn 23
  Query: fix authentication race condition
  🔥 HOT: authentication.md, session_handler.md
  🌡️  WARM: database.md, api.md
  ⬆️  Promoted to HOT: session_handler.md

[15:15:42] frontend | Turn 8
  Query: implement token refresh UI
  🔥 HOT: authentication.md, components.md
  🌡️  WARM: api.md, styling.md
```

#### Step 14: Get Statistics

```bash
python3 ~/.claude/scripts/history.py --stats --since 7d
```

**Output:**
```
╔══════════════════════════════════════════════════╗
║              ATTENTION STATISTICS                ║
╚══════════════════════════════════════════════════╝

Total turns: 156
Instances: {'backend': 89, 'frontend': 67}

Most frequently HOT:
  45 turns: authentication.md
  32 turns: api.md
  28 turns: database.md

Average context size: 19,230 chars
Token savings: ~72%
```

---

## Key Architecture Points

### Volume Mounts

**Critical mounts for persistence:**

```json
{
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/node/.claude,type=bind"
  ]
}
```

**What's stored:**
- `~/.claude/settings.json` - Claude Code config + hooks
- `~/.claude/scripts/` - claude-cognitive scripts
- `~/.claude/pool/` - Multi-instance coordination
- `~/.claude/attn_state.json` - Attention scores (runtime)
- `~/.claude/attention_history.jsonl` - History log

**What's in project (commit to git):**
- `.claude/CLAUDE.md` - Project context
- `.claude/systems/*.md` - System documentation
- `.claude/modules/*.md` - Module documentation
- `.devcontainer/` - Container configuration

### Instance IDs

**Set unique ID per container:**
```json
{
  "remoteEnv": {
    "CLAUDE_INSTANCE": "${localEnv:CLAUDE_INSTANCE:docker}"
  }
}
```

**Why?**
- Pool coordinator uses this to track which instance did what
- Prevents confusion in multi-container setups
- Enables proper coordination

### Hooks System

**Automatically configured by setup script:**

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
      {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"}
    ],
    "SessionStart": [
      {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"}
    ],
    "Stop": [
      {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"}
    ]
  }
}
```

**What they do:**
- `UserPromptSubmit`: Before each prompt, inject relevant context + detect coordination needs
- `SessionStart`: At session start, load recent pool activity
- `Stop`: At session end, extract any manual pool blocks

---

## Complete Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Copy .devcontainer/ to your project                        │
│  2. Open in container (VS Code or Docker CLI)                  │
│  3. Automatic setup runs (scripts, hooks, templates)           │
│  4. Customize .claude/CLAUDE.md and documentation              │
│  5. Start Claude Code: claude                                   │
│  6. Context router injects relevant docs automatically         │
│  7. Work on your project, files activate/decay dynamically     │
│  8. (Optional) Launch more containers with unique IDs          │
│  9. Pool coordinator shares work across containers             │
│ 10. Query pool/history anytime to see what's happening         │
└─────────────────────────────────────────────────────────────────┘
```

**Result:**
- ✅ 64-95% token savings
- ✅ No hallucinated integrations
- ✅ Zero duplicate work across containers
- ✅ Persistent memory across sessions
- ✅ Automatic context injection
- ✅ Multi-container coordination

---

## Reference Links

### Documentation
- [Full Docker Guide](../docs/guides/docker-devcontainer-setup.md) - Complete reference
- [Quick Reference](./QUICK_REFERENCE.md) - Command cheatsheet
- [Getting Started](../docs/guides/getting-started.md) - Basic concepts
- [Main README](../README.md) - Project overview

### Example Files
- [devcontainer.json](./examples/devcontainer-setup/.devcontainer/devcontainer.json)
- [Dockerfile](./examples/devcontainer-setup/.devcontainer/Dockerfile)
- [setup-claude-cognitive.sh](./examples/devcontainer-setup/.devcontainer/setup-claude-cognitive.sh)
- [health-check.sh](./examples/devcontainer-setup/.devcontainer/health-check.sh)

### Related
- [Anthropic's DevContainer Documentation](https://code.claude.com/docs/en/devcontainer)
- [Anthropic's DevContainer Features](https://github.com/anthropics/devcontainer-features)

---

## Troubleshooting

### Setup Issues

**Problem:** Scripts not installed
```bash
# Manually run setup
bash .devcontainer/setup-claude-cognitive.sh
```

**Problem:** Hooks not configured
```bash
# Check configuration
cat ~/.claude/settings.json | jq '.hooks'

# Should show context-router, pool-auto-update, pool-loader, pool-extractor
```

### Runtime Issues

**Problem:** No ATTENTION STATE header
```bash
# Test router manually
echo '{"prompt":"test"}' | python3 ~/.claude/scripts/context-router-v2.py

# Check for errors
cat ~/.claude/context_injection.log
```

**Problem:** Pool not working
```bash
# Verify mount
ls -la ~/.claude/pool/

# Check instance ID
echo $CLAUDE_INSTANCE

# Test query
python3 ~/.claude/scripts/pool-query.py
```

### Multi-Container Issues

**Problem:** Containers not coordinating
```bash
# Ensure shared mount
docker inspect <container> | grep -A 5 Mounts

# Verify different instance IDs
docker exec container1 bash -c 'echo $CLAUDE_INSTANCE'
docker exec container2 bash -c 'echo $CLAUDE_INSTANCE'
```

---

## Support

- **Issues:** https://github.com/GMaN1911/claude-cognitive/issues
- **Discussions:** https://github.com/GMaN1911/claude-cognitive/discussions
- **Full Documentation:** https://github.com/GMaN1911/claude-cognitive

---

**That's the complete end-to-end flow!** 🎉

The key insight: claude-cognitive works seamlessly in containers with proper volume mounts. The setup is automated, coordination works across containers, and the development experience is identical to host-based usage.
