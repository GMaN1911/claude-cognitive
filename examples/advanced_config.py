#!/usr/bin/env python3
"""
Advanced hologram configuration example.

Shows how to:
1. Customize injection settings
2. Tune priority parameters
3. Manually activate files
4. Query DAG structure
"""

import sys
from pathlib import Path

# Add hologram to path
hologram_path = Path.home() / "hologram-cognitive/hologram"
sys.path.insert(0, str(hologram_path))

from hologram import HologramRouter, InjectionConfig


def main():
    print("=" * 70)
    print("ADVANCED HOLOGRAM CONFIGURATION")
    print("=" * 70)
    print()

    # Example 1: Custom injection configuration
    print("1. Custom Injection Configuration")
    print("-" * 70)

    config = InjectionConfig(
        hot_full_content=True,          # Inject full content for HOT files
        warm_header_lines=30,            # More lines for WARM headers (default 25)
        cold_skip=True,                  # Skip COLD files
        max_hot_files=15,                # Allow more HOT files (default 10)
        max_warm_files=20,               # Allow more WARM files (default 15)
        max_total_chars=150000,          # Larger budget (default 100K)
        include_coordinates=True,        # Show file coordinates
        include_tier_markers=True,       # Show tier markers (🔥/🌡️/❄️)
    )

    router = HologramRouter.from_directory('.claude/')
    router.injection_config = config

    print(f"   ✓ Custom config applied")
    print(f"     - Header lines: {config.warm_header_lines}")
    print(f"     - Max budget: {config.max_total_chars:,} chars")
    print()

    # Example 2: Manually activate specific files
    print("2. Manual File Activation")
    print("-" * 70)

    # Pin critical files that should always appear
    router.activate_files(['CLAUDE.md', 'systems/critical-system.md'])
    print("   ✓ Manually activated pinned files")
    print()

    # Example 3: Query DAG structure
    print("3. Query DAG Structure")
    print("-" * 70)

    dag_summary = router.get_dag_summary()
    print(f"   Total nodes: {dag_summary['total_nodes']}")
    print(f"   Total edges: {dag_summary['total_edges']}")
    print(f"   Nodes with outgoing: {dag_summary['nodes_with_outgoing']}")
    print(f"   Nodes with incoming: {dag_summary['nodes_with_incoming']}")
    print(f"   SCCs: {len(dag_summary.get('sccs', []))}")
    print()

    # Example 4: Check bucket distribution
    print("4. System Bucket Distribution")
    print("-" * 70)

    buckets = router.get_bucket_map()
    print(f"   Files distributed across {len(buckets)} buckets")
    for bucket in sorted(buckets.keys())[:5]:
        files = buckets[bucket]
        print(f"   Bucket {bucket}: {len(files)} file(s)")
        for f in files[:2]:
            print(f"     - {f}")
    print(f"   ... and {len(buckets) - 5} more buckets")
    print()

    # Example 5: Process query with custom settings
    print("5. Process Query with Custom Settings")
    print("-" * 70)

    query = "work on authentication"
    record = router.process_query(query)

    print(f"   Query: '{query}'")
    print(f"   Activated: {len(record.activated)} files")
    print(f"   Turn: {record.turn}")
    print()

    injection = router.get_injection_text()
    print(f"   Injection size: {len(injection):,} chars")
    print(f"   Budget used: {len(injection) / config.max_total_chars * 100:.1f}%")
    print()

    # Example 6: Inspect edge weights
    print("6. Edge Weight Inspection")
    print("-" * 70)

    # Show some edge weights
    sample_edges = 0
    for source, targets in list(router.system.edge_weights.items())[:3]:
        print(f"   {source}:")
        for target, weight in list(targets.items())[:3]:
            print(f"     → {target}: weight {weight:.2f}")
        sample_edges += 1

    print()

    # Example 7: Manually override edge weight
    print("7. Manual Edge Weight Override")
    print("-" * 70)

    # Make a relationship stronger
    if 'auth.md' in router.system.files and 'database.md' in router.system.files:
        router.system.edge_weights.setdefault('auth.md', {})['database.md'] = 3.0
        print("   ✓ Increased auth.md → database.md weight to 3.0")
        print("     (Default is ~1.0-2.3, higher = stronger)")
    else:
        print("   (Skipped - example files not present)")
    print()

    print("=" * 70)
    print("✓ Advanced configuration complete!")
    print()
    print("Tips:")
    print("  - Increase max_total_chars for larger budgets")
    print("  - Increase warm_header_lines for more context")
    print("  - Use manual activation for must-have files")
    print("  - Override edge weights for critical relationships")


if __name__ == "__main__":
    main()
