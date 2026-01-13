#!/usr/bin/env python3
"""
Hologram injection hook for claude-cognitive-package (project-local).

This hook runs before Claude generates a response and injects
relevant context based on hologram-cognitive's auto-discovered DAG.
"""

import sys
from pathlib import Path

# Add hologram to path
hologram_path = Path.home() / "hologram-cognitive-v0.1.0/hologram-cognitive"
sys.path.insert(0, str(hologram_path))

from hologram import HologramRouter

def main():
    # Read user's query from stdin
    user_query = sys.stdin.read().strip()

    if not user_query:
        return

    try:
        # Create router from local .claude/ directory
        claude_dir = Path(__file__).parent  # .claude/
        router = HologramRouter.from_directory(
            str(claude_dir),
            instance_id='claude-cognitive-local'
        )

        # Process query (updates pressure, discovers relationships)
        record = router.process_query(user_query)

        # Get injection text
        injection = router.get_injection_text()

        # Output to Claude
        print(injection)

        # Debug info to stderr
        print(f"\n[Hologram v0.1.0: {len(record.activated)} activated, turn {record.turn}]",
              file=sys.stderr)

    except Exception as e:
        # Don't break Claude if hologram fails
        print(f"[Hologram error: {e}]", file=sys.stderr)

if __name__ == "__main__":
    main()
