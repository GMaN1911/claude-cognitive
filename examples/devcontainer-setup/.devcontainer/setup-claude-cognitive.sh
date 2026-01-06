#!/bin/bash
set -e

echo "Setting up claude-cognitive in devcontainer..."

# Clone claude-cognitive if not already present
if [ ! -d "$HOME/.claude-cognitive" ]; then
    echo "Cloning claude-cognitive repository..."
    git clone https://github.com/GMaN1911/claude-cognitive.git "$HOME/.claude-cognitive"
else
    echo "claude-cognitive repository already exists"
fi

# Create directories
echo "Creating ~/.claude directories..."
mkdir -p "$HOME/.claude/scripts"
mkdir -p "$HOME/.claude/pool"

# Copy scripts
echo "Installing claude-cognitive scripts..."
cp -r "$HOME/.claude-cognitive/scripts/"*.py "$HOME/.claude/scripts/"
chmod +x "$HOME/.claude/scripts/"*.py

# Configure hooks
echo "Configuring Claude Code hooks..."
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

# Add hooks for claude-cognitive
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

# Initialize project .claude directory if it doesn't exist
if [ ! -d "/workspace/.claude" ]; then
    echo "Initializing project .claude directory..."
    mkdir -p /workspace/.claude/{systems,modules,integrations,pool}
    
    # Copy templates
    cp -r "$HOME/.claude-cognitive/templates/"* /workspace/.claude/
    echo "✓ Templates copied to /workspace/.claude/"
else
    echo "Project .claude directory already exists"
fi

echo ""
echo "✓ claude-cognitive setup complete!"
echo "  - Scripts installed to ~/.claude/scripts/"
echo "  - Hooks configured in ~/.claude/settings.json"
echo "  - Project templates in /workspace/.claude/"
echo ""
echo "Next steps:"
echo "  1. Edit /workspace/.claude/CLAUDE.md with your project info"
echo "  2. Customize system and module documentation"
echo "  3. Start Claude Code: claude"
