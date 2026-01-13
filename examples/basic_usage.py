#!/usr/bin/env python3
"""
Basic hologram usage example.

Shows how to:
1. Create a router from .claude/ directory
2. Process a query
3. Get injection text
"""

import sys
from pathlib import Path

# Add hologram to path
hologram_path = Path.home() / "hologram-cognitive/hologram"
sys.path.insert(0, str(hologram_path))

from hologram import HologramRouter


def main():
    print("=" * 70)
    print("BASIC HOLOGRAM USAGE")
    print("=" * 70)
    print()

    # Step 1: Create router from .claude/ directory
    print("1. Creating router from .claude/ directory...")
    router = HologramRouter.from_directory('.claude/')
    print(f"   ✓ Loaded {len(router.system.files)} files")
    print(f"   ✓ Discovered {sum(len(edges) for edges in router.system.adjacency.values())} edges")
    print()

    # Step 2: Process a query
    query = "work on authentication"
    print(f"2. Processing query: '{query}'")
    record = router.process_query(query)
    print(f"   ✓ Activated {len(record.activated)} files")
    print(f"   ✓ Turn {record.turn}")
    print()

    # Step 3: Get injection text
    print("3. Getting injection text...")
    injection = router.get_injection_text()
    print(f"   ✓ Generated {len(injection):,} characters")
    print()

    # Display injection (first 500 chars)
    print("=" * 70)
    print("INJECTION OUTPUT (first 500 chars)")
    print("=" * 70)
    print(injection[:500])
    print("...")
    print()

    # Show state
    print("=" * 70)
    print("SYSTEM STATE")
    print("=" * 70)
    context = router.get_context_dict()
    print(f"Hot files: {len(context['hot'])}")
    print(f"Warm files: {len(context['warm'])}")
    print(f"Cold count: {context['cold_count']}")
    print()

    # Show activated files
    print("Activated files:")
    for path in record.activated[:10]:
        print(f"  - {path}")
    if len(record.activated) > 10:
        print(f"  ... and {len(record.activated) - 10} more")
    print()

    print("✓ Basic usage complete!")


if __name__ == "__main__":
    main()
