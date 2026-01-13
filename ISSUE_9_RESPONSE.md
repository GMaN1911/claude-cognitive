# Issue #9 Response: Wrong Documentation Loading

**Issue:** User seeing MirrorBot CVMP docs (orin.md, asus.md, etc.) instead of their own project documentation.

## Root Cause

The `context-router-v2.py` script has a **docs_root resolution priority issue**. It's supposed to:

1. Check `CONTEXT_DOCS_ROOT` environment variable
2. Fall back to project-local `.claude/` directory
3. Fall back to global `~/.claude/` directory

**What's happening:** The script is loading from global `~/.claude/` (which has MirrorBot CVMP docs) instead of the user's project-local `.claude/`.

## Immediate Fix for User

**Check your setup:**

```bash
# 1. Verify you have a .claude/ directory in your project
cd /path/to/your/project
ls -la .claude/

# 2. Verify it has documentation files
ls .claude/*.md

# 3. Check if CONTEXT_DOCS_ROOT is set
echo $CONTEXT_DOCS_ROOT

# 4. Run context-router with explicit path
CONTEXT_DOCS_ROOT=/path/to/your/project/.claude python3 ~/.claude/scripts/context-router-v2.py
```

**If `.claude/` doesn't exist:**
```bash
mkdir -p .claude/
# Add your documentation files here
```

**If `.claude/` exists but router still uses global:**

This is the bug - the priority order isn't working correctly.

**Workaround:**
```bash
# Set explicit path in your hooks
export CONTEXT_DOCS_ROOT="$(pwd)/.claude"
```

Or in `.claude/hooks.json`:
```json
{
  "pre_response": [
    "CONTEXT_DOCS_ROOT=.claude python3 ~/.claude/scripts/context-router-v2.py"
  ]
}
```

## Why You're Seeing MirrorBot Files

Those files (orin.md, asus.md, pipe-to-orin.md, etc.) are from **my development environment** where I'm building MirrorBot CVMP. They're in my global `~/.claude/` directory.

**The bug:** Your project is accidentally loading my global documentation instead of your project-local docs.

## The Fix (For v2.0.1 / v1.2.1)

**In `context-router-v2.py`, we need to fix the docs_root resolution:**

```python
def resolve_docs_root() -> str:
    """Resolve docs_root with correct priority order."""

    # Priority 1: Explicit environment variable
    if env_root := os.getenv('CONTEXT_DOCS_ROOT'):
        if os.path.isdir(env_root):
            return env_root

    # Priority 2: Project-local .claude/ (NEW: More explicit check)
    project_claude = os.path.join(os.getcwd(), '.claude')
    if os.path.isdir(project_claude):
        # Check if it has any .md files (not just exists)
        if glob.glob(os.path.join(project_claude, '**', '*.md'), recursive=True):
            return project_claude

    # Priority 3: Global ~/.claude/ (LAST RESORT)
    global_claude = os.path.expanduser('~/.claude')
    if os.path.isdir(global_claude):
        return global_claude

    # Priority 4: Fail with helpful error
    raise FileNotFoundError(
        "No .claude/ directory found. Please create .claude/ in your project "
        "or set CONTEXT_DOCS_ROOT environment variable."
    )
```

**Key changes:**
1. More explicit project-local check (verify .md files exist)
2. Fail loudly if no docs found (instead of silent fallback)
3. Clear error message pointing user to solution

## For v2.0 (Hologram)

**Good news:** Hologram doesn't have this bug because it requires explicit path:

```python
router = HologramRouter.from_directory('.claude/')  # Explicit path required
```

But we should add the same safety check:
```python
@classmethod
def from_directory(cls, docs_root: str, instance_id: str = 'default'):
    """Create router from docs directory."""

    # Expand relative paths relative to CWD
    if not os.path.isabs(docs_root):
        docs_root = os.path.join(os.getcwd(), docs_root)

    if not os.path.isdir(docs_root):
        raise FileNotFoundError(
            f"Documentation directory not found: {docs_root}\n"
            f"Please create this directory and add .md files."
        )

    # Check for .md files
    md_files = glob.glob(os.path.join(docs_root, '**', '*.md'), recursive=True)
    if not md_files:
        raise FileNotFoundError(
            f"No .md files found in: {docs_root}\n"
            f"Please add documentation files to this directory."
        )

    # Continue with normal initialization...
```

## Action Items

### Immediate (v1.2.1 patch)
- [ ] Fix docs_root resolution priority in context-router-v2.py
- [ ] Add explicit validation (check for .md files)
- [ ] Add helpful error messages
- [ ] Add `--verbose` flag to show which docs_root was chosen

### For v2.0
- [ ] Ensure hologram has same safety checks
- [ ] Add `--dry-run` mode to show what would be loaded
- [ ] Document priority order clearly in README
- [ ] Add troubleshooting section for "wrong docs loading"

## Response to User

**Immediate help:**

> Thank you for the excellent bug report! You've found a critical issue in the docs_root resolution.
>
> **What's happening:** You're seeing my MirrorBot CVMP documentation (from my global `~/.claude/`) instead of your project docs. This is a priority order bug in `context-router-v2.py`.
>
> **Immediate fix:**
> 1. Ensure you have `.claude/` in your project directory
> 2. Add `*.md` files to `.claude/`
> 3. Set explicit path: `export CONTEXT_DOCS_ROOT=.claude`
>
> Or in your hooks:
> ```json
> {
>   "pre_response": [
>     "CONTEXT_DOCS_ROOT=.claude python3 ~/.claude/scripts/context-router-v2.py"
>   ]
> }
> ```
>
> **Longer-term fix:** We'll patch this in v1.2.1 to properly prioritize project-local over global, and add validation that fails loudly if no docs are found.
>
> **For v2.0 users:** This issue is already fixed in hologram-cognitive because it requires explicit paths.
>
> Can you verify:
> 1. Do you have a `.claude/` directory in your project?
> 2. Does it contain `.md` files?
> 3. What does `ls .claude/` show?
>
> This will help me understand if it's a missing project setup or a genuine priority bug.

## Testing Plan

**Create test case:**
```bash
# Test 1: Project-local should win
cd /tmp/test-project
mkdir .claude
echo "# Test" > .claude/test.md
CONTEXT_DOCS_ROOT="" python3 context-router-v2.py
# Should load test.md, NOT global docs

# Test 2: Env var should win over everything
CONTEXT_DOCS_ROOT=/different/path python3 context-router-v2.py
# Should load from /different/path

# Test 3: Missing docs should fail loudly
cd /tmp/no-docs-project
python3 context-router-v2.py
# Should fail with helpful error, NOT fallback to global
```

## Documentation Updates

**Add to README.md:**

### Troubleshooting: Wrong Documentation Loading

**Symptom:** You see files like `orin.md`, `asus.md` that aren't in your project.

**Cause:** The router is loading from global `~/.claude/` instead of your project `.claude/`.

**Fix:**
1. Create `.claude/` in your project root
2. Add your documentation `.md` files
3. Set explicit path:
   ```bash
   export CONTEXT_DOCS_ROOT=.claude
   ```

**Verify it's working:**
```bash
# Should show YOUR files, not global ones
python3 ~/.claude/scripts/context-router-v2.py --dry-run
```
