#!/bin/bash

echo ""
echo "Checking claude-cognitive setup..."
echo "=================================="

checks_passed=0
checks_total=0

# Check 1: Scripts installed
checks_total=$((checks_total + 1))
if [ -d "$HOME/.claude/scripts" ] && [ -f "$HOME/.claude/scripts/context-router-v2.py" ]; then
    echo "✓ Scripts installed in ~/.claude/scripts/"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Scripts not found in ~/.claude/scripts/"
fi

# Check 2: Hooks configured
checks_total=$((checks_total + 1))
if [ -f "$HOME/.claude/settings.json" ] && grep -q "context-router" "$HOME/.claude/settings.json"; then
    echo "✓ Hooks configured in ~/.claude/settings.json"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Hooks not configured in ~/.claude/settings.json"
fi

# Check 3: Project .claude exists
checks_total=$((checks_total + 1))
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
if [ -d "$WORKSPACE_DIR/.claude" ] && [ -f "$WORKSPACE_DIR/.claude/CLAUDE.md" ]; then
    echo "✓ Project .claude directory initialized"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Project .claude not found in $WORKSPACE_DIR/"
fi

# Check 4: Instance ID set
checks_total=$((checks_total + 1))
if [ -n "$CLAUDE_INSTANCE" ]; then
    echo "✓ CLAUDE_INSTANCE set to: $CLAUDE_INSTANCE"
    checks_passed=$((checks_passed + 1))
else
    echo "⚠ CLAUDE_INSTANCE not set (will use 'default')"
    checks_passed=$((checks_passed + 1))  # Not a critical failure
fi

# Check 5: Python available
checks_total=$((checks_total + 1))
if command -v python3 &> /dev/null; then
    echo "✓ Python 3 available: $(python3 --version)"
    checks_passed=$((checks_passed + 1))
else
    echo "✗ Python 3 not found"
fi

echo ""
echo "=================================="
echo "Passed $checks_passed/$checks_total checks"
echo ""

if [ $checks_passed -eq $checks_total ]; then
    echo "✓ claude-cognitive is ready to use!"
    echo ""
    echo "Start Claude Code with: claude"
    echo ""
    exit 0
else
    echo "⚠ Some checks failed. Review the setup."
    echo ""
    echo "For troubleshooting, see:"
    echo "  https://github.com/GMaN1911/claude-cognitive/blob/main/docs/guides/docker-devcontainer-setup.md"
    echo ""
    exit 1
fi
