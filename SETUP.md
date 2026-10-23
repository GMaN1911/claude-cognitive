# Claude Cognitive - Setup Guide

**Goal:** Get working memory for Claude Code in minutes.

**What you'll have:**
- Context router with attention dynamics
- Pool coordinator for multi-instance work
- Project-local configuration
- Self-monitoring tools
- Metrics and analytics (v1.3)

---

## Prerequisites

- Claude Code installed and working
- Python 3.8+
- A project you want to enhance

---

## Option A: One-Command Install (Recommended, ~5 minutes)

The fastest way to get started. One script installs everything, then the setup wizard configures your project.

### 1. Install

```bash
git clone https://github.com/GMaN1911/claude-cognitive.git ~/.claude-cognitive
~/.claude-cognitive/install.sh
```

That's it. The install script:
- Copies hook scripts to `~/.claude/scripts/`
- Installs the metrics framework
- Copies skills (`/cognitive-setup`, `/cognitive-status`, `/cognitive-metrics`)
- Configures Claude Code hooks (non-destructive merge, backs up existing settings)

### 2. Run the Setup Wizard

```bash
cd /path/to/your/project
claude
```

Then in Claude Code:
```
/cognitive-setup init
```

The wizard will:
1. **Analyze your project** — detect languages, frameworks, key modules
2. **Generate keyword mappings** — create `keywords.json` automatically
3. **Create documentation stubs** — generate fractal docs for your codebase
4. **Verify hooks** — confirm Claude Code's hook system is properly configured
5. **Validate everything** — run dry-run tests to confirm it works

Each step is presented for your review before any files are written.

### 3. Verify

```
/cognitive-status
```

This checks that all files are in place, hooks are configured, and the context router is working.

### Alternative: Skip the install script entirely

If you're already in a Claude Code session, the `/cognitive-setup init` wizard can install everything for you. It detects missing scripts and hooks and handles installation automatically — no separate install step needed. Just make sure the skill is available (either from a cloned repo or copied to your project's `.claude/skills/`).

---

## Option B: Manual Setup (~15 minutes)

For those who prefer full control over every step.

### Step 1: Install Scripts (3 minutes)

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
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"},
        {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py prompt"}
    ]
}]

# Add SessionStart hook
settings["hooks"]["SessionStart"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"},
        {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-start"}
    ]
}]

# Add Stop hook
settings["hooks"]["Stop"] = [{
    "hooks": [
        {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"},
        {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-end"}
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
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"},
          {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py prompt"}
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"},
          {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-start"}
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"},
          {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-end"}
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

### Create Keywords Config

Create `.claude/keywords.json` with your project's keywords:

```bash
cp ~/.claude-cognitive/templates/keywords.json.example .claude/keywords.json
```

Edit to match your project's documentation files and relevant keywords:

```json
{
  "keywords": {
    "systems/your-system.md": ["keyword1", "keyword2"],
    "modules/your-module.md": ["module-keyword", "function-name"]
  },
  "co_activation": {
    "modules/your-module.md": ["systems/your-system.md"]
  },
  "pinned": ["systems/your-system.md"]
}
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

### Check Attention State

The context router runs silently in the background (its output goes to Claude's context, not your terminal). To see what it's doing, use:

```
/cognitive-state
```

Or run the standalone script directly:
```bash
python3 ~/.claude/scripts/cognitive-state.py
```

You should see something like:
```
Turn 1  |  🔥 0 HOT  🌡️ 0 WARM  ❄️ 6 COLD  |  2026-02-28T...
```

### Trigger Context Activation

**Mention something relevant to your project:**
```
How does the authentication system work?
```

Then check state again:
```
/cognitive-state
```

HOT/WARM counts should increase for files with matching keywords.

### Verify Pool Coordinator

**Query pool:**
```bash
python3 ~/.claude/scripts/pool-query.py --since 10m
```

Should show recent activity (or empty if no pool blocks yet).

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

- [ ] `/cognitive-state` shows turn count, HOT/WARM/COLD counts
- [ ] HOT count increases when you mention relevant topics
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

### Monitor Effectiveness

Use the metrics system to track how well claude-cognitive is working:

```
/cognitive-metrics summary
```

After a few sessions, run a full analysis:

```
/cognitive-metrics full
```

This shows token savings, keyword effectiveness, and actionable recommendations.

### Learn More

- [README.md](./README.md) - Full documentation
- [docs/concepts/](./docs/concepts/) - Theory and design
- [docs/guides/](./docs/guides/) - How-to guides
- [examples/](./examples/) - Example projects

### Customize

**Context Router:**
- Edit `.claude/keywords.json` to add project-specific keywords, co-activation rules, and pinned files
- Edit `~/.claude/scripts/context-router-v2.py` to adjust decay rates (search for `DECAY_RATES`) or thresholds (search for `HOT_THRESHOLD`)
- Use `python3 ~/.claude/scripts/context-router-v2.py --validate "your prompt"` to test keyword activation

**Pool Coordinator:**
- Edit `~/.claude/scripts/pool-auto-update.py`
- Adjust cooldown (search for `COOLDOWN`)
- Add detection patterns (search for `PATTERN`)

### Diagnose Issues

```
/cognitive-status
```

This checks file presence, hook configuration, attention state, and metrics collection. Reports clear PASS/FAIL/WARN for each component.

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

### "Context Router - Configuration Required"

**Cause:** No `.claude/` directory with documentation files found

**Fix:**
```bash
# Run the setup wizard
/cognitive-setup init

# Or manually create the directory
mkdir -p .claude/{systems,modules,integrations}
# Add at least one .md file and keywords.json
```

### `/cognitive-state` shows "No attention state found"

**Cause:** Context router hasn't run yet, or no `.claude/attn_state.json` exists

**Fix:**
```bash
# Check hook is configured
grep context-router ~/.claude/settings.json

# Validate with a test prompt
python3 ~/.claude/scripts/context-router-v2.py --validate "your project keywords here"

# Send a prompt in Claude Code to trigger the first run, then check again
/cognitive-state
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

✅ `/cognitive-state` shows attention state
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
