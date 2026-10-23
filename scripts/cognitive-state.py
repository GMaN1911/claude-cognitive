#!/usr/bin/env python3
"""Quick attention state viewer. Runs directly in terminal with no context overhead."""

import json
import sys
from pathlib import Path
from datetime import datetime

HOT_THRESHOLD = 0.8
WARM_THRESHOLD = 0.25

def main():
    # Find state file (project-local first)
    for p in [Path(".claude/attn_state.json"), Path.home() / ".claude/attn_state.json"]:
        if p.exists():
            state = json.loads(p.read_text())
            break
    else:
        print("No attention state found.")
        sys.exit(1)

    scores = state.get("scores", {})
    turn = state.get("turn_count", "?")
    updated = state.get("last_update", "?")

    hot  = sorted([(f, s) for f, s in scores.items() if s >= HOT_THRESHOLD], key=lambda x: -x[1])
    warm = sorted([(f, s) for f, s in scores.items() if WARM_THRESHOLD <= s < HOT_THRESHOLD], key=lambda x: -x[1])
    cold_count = sum(1 for s in scores.values() if s < WARM_THRESHOLD)

    print(f"Turn {turn}  |  🔥 {len(hot)} HOT  🌡️ {len(warm)} WARM  ❄️ {cold_count} COLD  |  {updated}")
    for f, s in hot:
        print(f"  🔥 {f} ({s:.2f})")
    for f, s in warm:
        print(f"  🌡️  {f} ({s:.2f})")

    # Show last 3 transitions if history exists
    for hp in [Path(".claude/attention_history.jsonl"), Path.home() / ".claude/attention_history.jsonl"]:
        if hp.exists():
            lines = hp.read_text().strip().split("\n")
            recent = lines[-3:] if len(lines) >= 3 else lines
            changes = []
            for line in recent:
                e = json.loads(line)
                t = e.get("transitions", {})
                parts = []
                for kind in ["to_hot", "to_warm", "to_cold"]:
                    for f in t.get(kind, []):
                        name = f.split("/")[-1].replace(".md", "")
                        parts.append(f"{name}→{kind[3:].upper()}")
                if parts:
                    changes.append(f"  T{e['turn']}: {', '.join(parts)}")
            if changes:
                print("Recent:")
                print("\n".join(changes))
            break

if __name__ == "__main__":
    main()
