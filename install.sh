#!/usr/bin/env bash
set -euo pipefail

# Claude-Cognitive Installer
# Usage: ./install.sh [project-path]
#
# Installs hook scripts, skills, and optionally configures hooks.
# If project-path is provided, skills are also copied to that project.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$HOME/.claude/scripts"
SKILLS_DIR="$HOME/.claude/skills"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Colors (if terminal supports them)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BOLD='' NC=''
fi

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $1"; }
error() { echo -e "${RED}[ERR]${NC} $1"; }
step()  { echo -e "\n${BOLD}$1${NC}"; }

# --- Preflight checks ---
step "1/4  Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    error "Python 3 is required but not found."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    error "Python 3.8+ required, found $PY_VERSION"
    exit 1
fi
info "Python $PY_VERSION"

if [ ! -f "$REPO_DIR/scripts/context-router-v2.py" ]; then
    error "Cannot find scripts/context-router-v2.py — run this from the claude-cognitive repo root."
    exit 1
fi
info "Repository found at $REPO_DIR"

# --- Install scripts ---
step "2/4  Installing hook scripts to $SCRIPTS_DIR..."

mkdir -p "$SCRIPTS_DIR"
mkdir -p "$SCRIPTS_DIR/metrics"

cp "$REPO_DIR/scripts/context-router-v2.py"  "$SCRIPTS_DIR/"
cp "$REPO_DIR/scripts/pool-loader.py"        "$SCRIPTS_DIR/"
cp "$REPO_DIR/scripts/pool-extractor.py"     "$SCRIPTS_DIR/"
cp "$REPO_DIR/scripts/pool-auto-update.py"   "$SCRIPTS_DIR/"
cp "$REPO_DIR/scripts/pool-query.py"         "$SCRIPTS_DIR/"
cp "$REPO_DIR/scripts/usage_tracker.py"      "$SCRIPTS_DIR/"

# Metrics framework
cp "$REPO_DIR/scripts/metrics/__init__.py"   "$SCRIPTS_DIR/metrics/"
cp "$REPO_DIR/scripts/metrics/collector.py"  "$SCRIPTS_DIR/metrics/"
cp "$REPO_DIR/scripts/metrics/store.py"      "$SCRIPTS_DIR/metrics/"
cp "$REPO_DIR/scripts/metrics/analyzer.py"   "$SCRIPTS_DIR/metrics/"
cp "$REPO_DIR/scripts/metrics/reporter.py"   "$SCRIPTS_DIR/metrics/"
cp "$REPO_DIR/scripts/metrics/validate.py"   "$SCRIPTS_DIR/metrics/" 2>/dev/null || true

chmod +x "$SCRIPTS_DIR"/*.py

info "Hook scripts installed ($(ls "$SCRIPTS_DIR"/*.py | wc -l | tr -d ' ') files)"
info "Metrics framework installed ($(ls "$SCRIPTS_DIR/metrics/"*.py | wc -l | tr -d ' ') files)"

# --- Install skills ---
step "3/4  Installing skills..."

mkdir -p "$SKILLS_DIR"

for skill in cognitive-setup cognitive-status cognitive-metrics; do
    SKILL_SRC="$REPO_DIR/.claude/skills/$skill"
    if [ -d "$SKILL_SRC" ]; then
        cp -r "$SKILL_SRC" "$SKILLS_DIR/"
        info "Installed /$(basename "$skill")"
    else
        warn "Skill $skill not found in repo — skipping"
    fi
done

# If a project path was provided, also install skills there
if [ -n "${1:-}" ]; then
    PROJECT_DIR="$1"
    if [ ! -d "$PROJECT_DIR" ]; then
        error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    PROJECT_SKILLS="$PROJECT_DIR/.claude/skills"
    mkdir -p "$PROJECT_SKILLS"
    for skill in cognitive-setup cognitive-status cognitive-metrics; do
        SKILL_SRC="$REPO_DIR/.claude/skills/$skill"
        if [ -d "$SKILL_SRC" ]; then
            cp -r "$SKILL_SRC" "$PROJECT_SKILLS/"
        fi
    done
    info "Skills also installed to $PROJECT_SKILLS"
fi

# --- Configure hooks ---
step "4/4  Configuring Claude Code hooks..."

if [ -f "$SETTINGS_FILE" ]; then
    # Check if hooks are already configured
    if grep -q "context-router" "$SETTINGS_FILE" 2>/dev/null; then
        info "Hooks already configured in settings.json — skipping"
    else
        # Backup and merge
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"
        info "Backed up settings to $SETTINGS_FILE.backup"

        python3 << 'PYEOF'
import json
from pathlib import Path

settings_file = Path.home() / ".claude" / "settings.json"
with open(settings_file) as f:
    settings = json.load(f)

if "hooks" not in settings:
    settings["hooks"] = {}

hooks = settings["hooks"]

# Helper: add hooks to a lifecycle event without duplicating
def merge_hooks(event_name, new_hooks):
    existing = hooks.get(event_name, [])
    if not existing:
        hooks[event_name] = [{"hooks": new_hooks}]
        return
    # Check first hook group for existing commands
    group = existing[0]
    existing_cmds = {h.get("command", "") for h in group.get("hooks", [])}
    for h in new_hooks:
        if h["command"] not in existing_cmds:
            group.setdefault("hooks", []).append(h)

merge_hooks("UserPromptSubmit", [
    {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
    {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"},
    {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py prompt"},
])
merge_hooks("SessionStart", [
    {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"},
    {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-start"},
])
merge_hooks("Stop", [
    {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"},
    {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-end"},
])

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("Hooks merged into settings.json")
PYEOF
        info "Hooks configured"
    fi
else
    # No settings file — create one
    python3 << 'PYEOF'
import json
from pathlib import Path

settings = {
    "hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "python3 ~/.claude/scripts/context-router-v2.py"},
            {"type": "command", "command": "python3 ~/.claude/scripts/pool-auto-update.py"},
            {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py prompt"},
        ]}],
        "SessionStart": [{"hooks": [
            {"type": "command", "command": "python3 ~/.claude/scripts/pool-loader.py"},
            {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-start"},
        ]}],
        "Stop": [{"hooks": [
            {"type": "command", "command": "python3 ~/.claude/scripts/pool-extractor.py"},
            {"type": "command", "command": "python3 ~/.claude/scripts/metrics/collector.py session-end"},
        ]}],
    }
}

settings_file = Path.home() / ".claude" / "settings.json"
settings_file.parent.mkdir(parents=True, exist_ok=True)
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("Created settings.json with hooks")
PYEOF
    info "Settings file created with hooks"
fi

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Open Claude Code in your project:  cd /path/to/project && claude"
echo "  2. Run the setup wizard:              /cognitive-setup init"
echo "  3. Check system health:               /cognitive-status"
echo ""
echo "The setup wizard will analyze your project, generate keywords,"
echo "create documentation stubs, and validate everything works."
