# Migration Guide: keywords.json → Hologram v2.0

**Upgrading from:** v1.x (manual keywords.json)
**Upgrading to:** v2.0 (hologram auto-discovery)
**Estimated time:** 15 minutes
**Difficulty:** Easy
**Rollback:** Simple (keep keywords.json as backup)

---

## Overview

v2.0 introduces **hologram-cognitive**, a graph-based context routing system that automatically discovers relationships between documentation files. This eliminates the need for manual `keywords.json` configuration.

**Key benefits:**
- 20x more relationships discovered
- 0% error rate (no broken references)
- Zero ongoing maintenance
- Works immediately on any .claude/ directory

---

## Prerequisites

### 1. Check Current Version
```bash
# If you have a VERSION file:
cat VERSION

# Or check your keywords.json:
ls -la .claude/keywords.json
```

If you have `keywords.json`, you're on v1.x and can upgrade.

### 2. Backup Current Configuration
```bash
# Backup your keywords.json (optional - it still works in v2.0)
cp .claude/keywords.json .claude/keywords.json.backup
```

---

## Installation Steps

### Step 1: Get hologram-cognitive

Hologram is currently a local package (not on PyPI yet). Two options:

#### Option A: Clone Alongside claude-cognitive (Recommended)
```bash
cd ~/
git clone https://github.com/GMaN1911/hologram-cognitive.git
# Or download the hologram-cognitive-v0.1.0 release
```

Your directory structure:
```
~/
├── claude-cognitive/          # Your current project
│   └── .claude/
└── hologram-cognitive/        # New package
    ├── hologram/
    └── pyproject.toml
```

#### Option B: Add to sys.path in Hooks
No installation needed - just reference the path in your hooks (see Step 3).

### Step 2: Update Your Project to v2.0

```bash
cd ~/claude-cognitive  # Your project directory
git fetch
git checkout v2.0
```

Or manually update files:
- Replace `README.md` with v2.0 version
- Add new `docs/` directory
- Update `.claude/` configuration (optional)

### Step 3: Configure Hologram Integration

#### Option A: Automatic (Hooks)
Create `.claude/hologram_hook.py`:

```python
#!/usr/bin/env python3
"""
Hologram context injection hook.
Runs before Claude generates responses.
"""

import sys
from pathlib import Path

# Add hologram to path (adjust path if needed)
hologram_path = Path.home() / "hologram-cognitive/hologram"
sys.path.insert(0, str(hologram_path))

from hologram import HologramRouter

def main():
    # Read user query from stdin
    user_query = sys.stdin.read().strip()
    if not user_query:
        return

    try:
        # Create router from .claude/ directory
        claude_dir = Path(__file__).parent
        router = HologramRouter.from_directory(str(claude_dir))

        # Process query and get injection text
        record = router.process_query(user_query)
        injection = router.get_injection_text()

        # Output to Claude
        print(injection)

    except Exception as e:
        # Don't break Claude if hologram fails
        print(f"[Hologram error: {e}]", file=sys.stderr)

if __name__ == "__main__":
    main()
```

Make it executable:
```bash
chmod +x .claude/hologram_hook.py
```

Register in `.claude/hooks.json` (or create if doesn't exist):
```json
{
  "pre_response": [
    "python3 .claude/hologram_hook.py"
  ]
}
```

#### Option B: Manual (Script Usage)
```python
import sys
from pathlib import Path

# Add hologram to path
sys.path.insert(0, str(Path.home() / "hologram-cognitive/hologram"))

from hologram import HologramRouter

# Create router
router = HologramRouter.from_directory('.claude/')

# Process query
record = router.process_query("your query here")

# Get injection text
injection = router.get_injection_text()
print(injection)
```

### Step 4: Test the Integration

```bash
# Test hologram discovery
cd ~/claude-cognitive
echo "usage tracking implementation" | python3 .claude/hologram_hook.py
```

**Expected output:**
```
ATTENTION STATE [Turn 1]
Instance: default
🔥 HOT: 2 | 🌡️ WARM: 3 | ❄️ COLD: 0

🔥 CRITICAL ### modules/usage-tracker.md
Coordinate: (45, 47), Priority: 1.83
...
```

If you see this, hologram is working!

---

## Migration Strategies

### Strategy 1: Parallel Running (Recommended)
Keep both systems running during transition:

```json
{
  "pre_response": [
    "python3 .claude/hologram_hook.py",
    "python3 .claude/keywords_hook.py"  // Your old system
  ]
}
```

**Benefits:**
- Compare output quality
- Safe fallback if hologram has issues
- Gradual transition

**After 1-2 weeks:**
- Remove keywords_hook.py from hooks.json
- Archive keywords.json

### Strategy 2: Clean Break
Remove keywords.json and rely entirely on hologram:

```bash
# Backup old config
mv .claude/keywords.json .claude/keywords.json.archived

# Use only hologram
# (already configured in Step 3)
```

**Benefits:**
- Clean slate
- Full hologram capabilities
- No confusion

**Risks:**
- No fallback if issues arise
- Recommended only after testing

### Strategy 3: Hybrid Approach
Use hologram for discovery, but pin critical files via config:

```python
# In hologram_hook.py, add pinned files:
router = HologramRouter.from_directory(str(claude_dir))

# Manually activate critical files that must always appear
router.activate_files(['CLAUDE.md', 'systems/critical-system.md'])

record = router.process_query(user_query)
injection = router.get_injection_text()
```

**Benefits:**
- Auto-discovery for most files
- Manual control for critical files
- Best of both worlds

---

## Mapping keywords.json to Hologram

### Understanding the Difference

**keywords.json (v1.x):**
```json
{
  "co_activation": {
    "systems/orin.md": ["integrations/pipe-to-orin.md"]
  },
  "keywords": {
    "orin": ["systems/orin.md"],
    "visual": ["systems/asus.md"]
  }
}
```

**Hologram (v2.0):**
- No manual configuration needed
- Auto-discovers: orin.md → pipe-to-orin.md via content analysis
- Auto-discovers: "orin" → orin.md via filename matching
- Auto-discovers: "visual" → asus.md via content matching

### Migration Checklist

For each entry in your keywords.json:

- [ ] **Keywords**: Hologram auto-discovers via filename/content matching (no action needed)
- [ ] **Co-activation**: Hologram auto-discovers via 6 discovery strategies (no action needed)
- [ ] **Pinned files**: Use `router.activate_files([...])` for must-have files
- [ ] **Custom relationships**: Hologram likely discovers them; validate with test queries

---

## Validation

### Test Your Migration

Run these test queries and verify correct files appear:

```bash
# Test 1: Keyword matching
echo "usage tracking" | python3 .claude/hologram_hook.py | grep "usage-tracker.md"

# Test 2: Relationship discovery
echo "work on orin sensory" | python3 .claude/hologram_hook.py | grep "pipe-to-orin.md"

# Test 3: Complex query
echo "fix pipeline integration" | python3 .claude/hologram_hook.py | grep "pipeline.md"
```

### Compare Against keywords.json

```bash
# What files would keywords.json activate for "orin"?
grep -A5 '"orin"' .claude/keywords.json

# What files does hologram activate for "orin"?
echo "orin" | python3 .claude/hologram_hook.py | grep "🔥 CRITICAL\|⭐ HIGH"
```

Hologram should activate **at least** the same files, plus more related ones.

---

## Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'hologram'"

**Cause:** Python can't find hologram package

**Fix:**
```python
# Verify path in hologram_hook.py
hologram_path = Path.home() / "hologram-cognitive/hologram"
print(f"Looking for hologram at: {hologram_path}")  # Debug
sys.path.insert(0, str(hologram_path))
```

Check that `hologram_path` actually exists:
```bash
ls ~/hologram-cognitive/hologram/__init__.py
```

### Issue 2: No Files Activated

**Cause:** Hologram didn't find any .md files

**Fix:**
```bash
# Check .claude/ directory has .md files
ls .claude/*.md
ls .claude/**/*.md

# Verify file patterns in router creation
# Default is **/*.md, adjust if needed:
router = HologramRouter.from_directory(
    str(claude_dir),
    file_patterns=['**/*.md', '*.md']  # Add patterns
)
```

### Issue 3: Wrong Files Appearing

**Cause:** Discovery strategies finding unexpected relationships

**Fix:**
```python
# Tune discovery config
from hologram.dag import EdgeDiscoveryConfig

config = EdgeDiscoveryConfig(
    enable_path_matching=True,
    enable_filename_matching=True,
    enable_hyphenated_matching=False,  # Disable if too broad
    enable_import_detection=True,
    enable_markdown_links=True,
    enable_component_matching=False,   # Disable if too broad
)

# Use custom config
router.system.discover_edges(config=config)
```

### Issue 4: Performance Issues

**Cause:** Large codebase, many files

**Fix:**
```bash
# Check discovery time
time echo "test" | python3 .claude/hologram_hook.py

# If >5 seconds on first run: normal (one-time discovery)
# If >2 seconds on subsequent runs: investigate

# Optimize by caching state
# State file created automatically at: .claude/hologram_state.json
```

---

## Advanced Configuration

### Tuning Priority Parameters

If files you want aren't appearing in 🔥 CRITICAL, adjust parameters:

```python
# In hologram_hook.py

# More non-saturating (if lots of ties):
priority, aggregate, hop = router._calculate_injection_priority(
    file, activated, query_hit,
    top_k=5,        # Increase from 3
    hop_lambda=1.0  # Increase from 0.7
)

# Stricter hub governance (if meta-docs dominating):
max_hubs_tier1 = 1  # Decrease from 2 in router.py

# Adjust budget split (if want more headers):
full_content_budget = int(max_total_chars * 0.7)  # Decrease from 0.8
header_budget = int(max_total_chars * 0.3)        # Increase from 0.2
```

See `docs/ARCHITECTURE.md` for parameter details.

### Custom Edge Weights

Override discovered edge weights for critical relationships:

```python
# After router creation
router.system.edge_weights['systems/orin.md']['integrations/pipe-to-orin.md'] = 3.0
# (Default is ~1.0-2.3, higher = stronger relationship)
```

---

## Rollback Plan

If you need to rollback to v1.x:

### Quick Rollback
```bash
# Restore keywords.json
cp .claude/keywords.json.backup .claude/keywords.json

# Remove hologram hook
rm .claude/hologram_hook.py

# Restore hooks.json
# (remove "python3 .claude/hologram_hook.py" line)

# Checkout v1.2.0
git checkout v1.2.0
```

### Keep Both Systems
```json
// .claude/hooks.json
{
  "pre_response": [
    "python3 .claude/keywords_hook.py",  // Old system
    "python3 .claude/hologram_hook.py"   // New system (optional)
  ]
}
```

Claude will receive context from both systems (combined injection).

---

## Success Criteria

After migration, you should see:

- ✅ More files activated than keywords.json
- ✅ Correct files in 🔥 CRITICAL tier
- ✅ Related files discovered automatically
- ✅ No manual maintenance needed
- ✅ <1s performance after initial discovery

If you see these, migration successful! 🎉

---

## Getting Help

**Issues or questions?**
- Open GitHub issue: https://github.com/GMaN1911/claude-cognitive/issues
- Check `docs/ARCHITECTURE.md` for technical details
- Review `docs/VALIDATION_RESULTS.md` for expected behavior

**Report migration blockers:**
- Include your keywords.json (sanitize if needed)
- Include hologram output (first 50 lines)
- Include error messages if any

---

**Next Steps:**
1. Complete migration steps above
2. Test with real queries (1-2 days)
3. Remove keywords.json when confident
4. Tune parameters if needed
5. Enjoy automatic context routing! 🚀
