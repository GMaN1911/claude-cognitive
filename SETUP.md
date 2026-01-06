# Claude Cognitive - 15-Minute Setup

**Goal:** Get working memory for Claude Code in 15 minutes or less.

**What you'll have:**
- Context router with attention dynamics
- Pool coordinator for multi-instance work
- Project-local configuration
- Self-monitoring tools

---

## Prerequisites

- Claude Code installed and working
- Basic terminal/command-line familiarity
- A project with 100+ files (or use our examples)

**Time estimate:** 10-15 minutes

**Using Docker or DevContainers?** See [Docker & DevContainer Setup Guide](./docs/guides/docker-devcontainer-setup.md)

---

## Step 1: Install Scripts (3 minutes)

### Clone Repository

```bash
cd ~
git clone https://github.com/GMaN1911/claude-cognitive.git .claude-cognitive
```

### Copy Scripts

```bash
# Create scripts directory if it doesn't exist
mkdir -p ~/.claude/scripts

# Copy all scripts
cp .claude-cognitive/scripts/*.py ~/.claude/scripts/

# Make executable
chmod +x ~/.claude/scripts/*.py
```

### Verify

```bash
ls -lh ~/.claude/scripts/

# Should see:
# context-router-v2.py
# pool-auto-update.py
# pool-loader.py
# pool-extractor.py
# pool-query.py
```

✅ **Checkpoint:** Scripts installed

---

## Step 2: Configure Hooks (2 minutes)

### Option A: Automatic (Recommended)

```bash
# Backup existing settings
cp ~/.claude/settings.json ~/.claude/settings.json.backup

# Add hooks (safe - appends to existing config)
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

# Add UserPromptSubmit hooks
settings["hooks"]["UserPromptSubmit"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"}
    ]
}]

# Add SessionStart hook
settings["hooks"]["SessionStart"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"}
    ]
}]

# Add Stop hook
settings["hooks"]["Stop"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"}
    ]
}]

# Write back
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("✓ Hooks configured successfully")
PYTHON
```

### Option B: Manual

Edit `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"}
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"}
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"}
        ]
      }
    ]
  }
}
```

✅ **Checkpoint:** Hooks configured

---

## Step 3: Set Instance ID (1 minute)

### Add to ~/.bashrc (Persistent)

```bash
echo 'export CLAUDE_INSTANCE=A' >> ~/.bashrc
source ~/.bashrc
```

### Verify

```bash
echo $CLAUDE_INSTANCE
# Should output: A
```

**For multiple terminals:**
```bash
# Terminal 1
export CLAUDE_INSTANCE=A

# Terminal 2
export CLAUDE_INSTANCE=B

# etc.
```

✅ **Checkpoint:** Instance ID set

---

## Step 4: Initialize Your Project (5 minutes)

### Create `.claude/` Directory

```bash
cd /path/to/your/project

# Create structure
mkdir -p .claude/{systems,modules,integrations,pool}
```

### Copy Templates

```bash
# Copy all templates
cp ~/.claude-cognitive/templates/CLAUDE.md .claude/
cp ~/.claude-cognitive/templates/systems/example-system.md .claude/systems/
cp ~/.claude-cognitive/templates/modules/example-module.md .claude/modules/
cp ~/.claude-cognitive/templates/integrations/example-integration.md .claude/integrations/
```

### Customize CLAUDE.md

Edit `.claude/CLAUDE.md`:

1. Replace `[Your Project Name]` with actual name
2. Fill in `[entry_point.py]` with your main file
3. Add your architecture overview
4. List your core components
5. Add any critical environment variables

**Minimum viable customization:**
```markdown
# MyProject

**Project:** Web API for [whatever]
**Status:** Development
**Primary Goal:** [What you're building]

Quick Reference:
- Start: `python app.py`
- Test: `pytest`
```

### Document Key Systems (Optional but Recommended)

If you have distinct systems (e.g., database, API server, workers):

```bash
# Create a file per system
cp .claude/systems/example-system.md .claude/systems/api-server.md
cp .claude/systems/example-system.md .claude/systems/database.md

# Edit each with relevant info
```

✅ **Checkpoint:** Project initialized

---

## Step 5: Test It Works (3 minutes)

### Start Claude Code

```bash
cd /path/to/your/project
claude
```

### Verify Context Router

**First message:**
```
Show me the project structure
```

**Look for:**
```
╔══ ATTENTION STATE [Turn 1] ══╗
║ 🔥 Hot: 0 │ 🌡️ Warm: 0 │ ❄️ Cold: X ║
...
```

This means context router is working!

### Verify Pool Coordinator

**Query pool:**
```bash
python3 ~/.claude/scripts/pool-query.py --since 10m
```

Should show recent activity (or empty if no pool blocks yet).

### Trigger Context Activation

**Mention something in your code:**
```
How does the authentication system work?
```

**Next message check:**
```
╔══ ATTENTION STATE [Turn 2] ══╗
║ 🔥 Hot: 1 │ 🌡️ Warm: X │ ❄️ Cold: X ║
```

HOT count should increase!

✅ **Checkpoint:** System working

---

## Step 6: Create First Documentation (3 minutes)

### Document Your Main System

```bash
# If you have a web server:
cp .claude/systems/example-system.md .claude/systems/production-server.md
```

Edit `production-server.md`:

```markdown
# Production Server - Web API

> **Role**: Main API server
> **Host**: `api.yourapp.com`
> **Hardware**: [Cloud provider, instance type]
> **Critical Path**: Yes - All requests go through this

## Quick Health
```bash
curl https://api.yourapp.com/health
```

## Key Processes
- `app.py`: Main FastAPI/Flask/Django server
- Port: 8000
```

### Document Your Main Module

```bash
cp .claude/modules/example-module.md .claude/modules/auth.md
```

Edit with your auth system details.

✅ **Checkpoint:** First docs created

---

## Validation Checklist

### Context Router Working?

- [ ] See "ATTENTION STATE" header in Claude responses
- [ ] HOT count increases when you mention things
- [ ] Files decay when not mentioned (WARM → COLD)

### Pool Coordinator Working?

- [ ] `pool-query.py` runs without errors
- [ ] Instance ID shows correctly (`echo $CLAUDE_INSTANCE`)
- [ ] Can write manual pool blocks (see below)

### Project Setup Complete?

- [ ] `.claude/` directory exists in project
- [ ] `CLAUDE.md` customized with your info
- [ ] At least one system or module documented

---

## Optional: Test Pool Coordination

### Write a Manual Pool Block

In Claude, say:

```pool
INSTANCE: A
ACTION: completed
TOPIC: Setup test
SUMMARY: Tested claude-cognitive installation. Context router and pool coordinator both working.
AFFECTS: .claude/ directory
BLOCKS: Can now use for real development
```

### Query Pool

```bash
python3 ~/.claude/scripts/pool-query.py --since 5m
```

Should see your test entry!

---

## Next Steps

### Learn More

- [README.md](./README.md) - Full documentation
- [docs/concepts/](./docs/concepts/) - Theory and design
- [docs/guides/](./docs/guides/) - How-to guides
- [examples/](./examples/) - Example projects

### Customize

**Context Router:**
- Edit `~/.claude/scripts/context-router-v2.py`
- Adjust decay rates (lines 40-47)
- Add custom keywords (lines 75-178)

**Pool Coordinator:**
- Edit `~/.claude/scripts/pool-auto-update.py`
- Adjust cooldown (line 41)
- Add detection patterns (lines 48-91)

### Advanced Setup

**Multiple Developers:**
- Each dev sets unique `CLAUDE_INSTANCE`
- Pool coordinates automatically
- See [docs/guides/team-setup.md](./docs/guides/team-setup.md)

**Large Codebases (50k+ lines):**
- Create more granular documentation
- Use co-activation for related files
- See [docs/guides/large-codebases.md](./docs/guides/large-codebases.md)

---

## Troubleshooting

### "No ATTENTION STATE header"

**Cause:** Context router not running

**Fix:**
```bash
# Check hook is configured
grep context-router ~/.claude/settings.json

# Test manually
echo '{"prompt":"test"}' | python3 ~/.claude/scripts/context-router-v2.py
```

### "Pool query shows nothing"

**Cause:** No pool entries yet (normal for new setup)

**Fix:**
- Either wait for auto-detection (5min cooldown)
- Or write a manual pool block (see above)

### "Instance ID is '?'"

**Cause:** `$CLAUDE_INSTANCE` not set

**Fix:**
```bash
export CLAUDE_INSTANCE=A
# Or add to ~/.bashrc for persistence
```

### "Permission denied on scripts"

**Cause:** Scripts not executable

**Fix:**
```bash
chmod +x ~/.claude/scripts/*.py
```

---

## Success Criteria

**You're ready when:**

✅ Context router shows attention state
✅ Pool query runs without errors
✅ Instance ID set and visible
✅ `.claude/CLAUDE.md` customized for your project
✅ At least one system or module documented

**Typical setup time:** 10-15 minutes

---

## Get Help

**Issues?** https://github.com/GMaN1911/claude-cognitive/issues

**Questions?** Open a discussion

**Want to contribute?** PRs welcome!

---

**Status:** Setup complete! 🎉

**Next:** Start using Claude Code with persistent memory and multi-instance coordination.
