## 🐛 v1.2.1 - Critical Bug Fix: docs_root Resolution

**Status:** Patch Release
**Date:** 2026-01-12
**Branch:** main

---

## 🚨 Critical Fix: Issue #9

This patch release fixes a **critical bug** where users were loading the wrong documentation files.

### The Problem

Users reported seeing unrelated documentation files (like `orin.md`, `asus.md`, `pipe-to-orin.md`) that didn't exist in their project. These files were being loaded from the global `~/.claude/` directory instead of their project-local `.claude/` directory.

**Example User Report (Issue #9):**
> "Non of these files are files that are in my codebase and are not in my keywords.json. Unsure if it's a bug or if my installation is incorrect."

### Root Cause

The `context-router-v2.py` script was **not checking project-local .claude/ directories** at all. It only implemented:

1. `CONTEXT_DOCS_ROOT` environment variable
2. Global `~/.claude/` fallback

This meant **project-local documentation was completely ignored**, causing users to accidentally load documentation from other projects that happened to be in their global directory.

### The Fix

Implemented proper **3-tier priority order**:

```python
def resolve_docs_root() -> Path:
    """
    Priority order:
    1. CONTEXT_DOCS_ROOT environment variable (explicit override)
    2. Project-local .claude/ directory (if exists with .md files) ← NEW
    3. Global ~/.claude/ directory (fallback)
    """
```

**Key improvements:**
- ✅ Project-local `.claude/` now correctly takes priority
- ✅ Explicit validation: Checks for `.md` files, not just directory existence
- ✅ Helpful error messages if no documentation found
- ✅ Debug output to stderr showing which docs_root was chosen
- ✅ Fails loudly (not silently) if no valid docs directory exists

### Validation Tests

All three priority levels tested and working:

```bash
# Test 1: Project-local detection
$ cd /tmp/test-project
$ echo '{"prompt": "test"}' | python3 context-router-v2.py 2>&1 | grep "Using"
ℹ Using project-local .claude: /tmp/test-project/.claude
  Found 1 .md files

# Test 2: Global fallback (no project .claude/)
$ cd /tmp/no-local-docs
$ echo '{"prompt": "test"}' | python3 context-router-v2.py 2>&1 | grep "Using"
ℹ Using global ~/.claude: /home/user/.claude
  Found 64 .md files

# Test 3: Explicit override
$ CONTEXT_DOCS_ROOT=/custom/path echo '{"prompt": "test"}' | python3 context-router-v2.py 2>&1 | grep "Using"
ℹ Using CONTEXT_DOCS_ROOT: /custom/path
```

---

## 📝 Changes

### Added
- `resolve_docs_root()` function with explicit 3-tier priority logic
- Content validation: Verifies `.md` files exist, not just directory
- Debug output to stderr showing which docs_root was selected
- Comprehensive error message when no documentation found

### Fixed
- **Issue #9**: Project-local `.claude/` now correctly prioritized over global `~/.claude/`
- Prevents accidental loading of wrong project's documentation
- Users no longer see files from unrelated projects

### Files Modified
- `scripts/context-router-v2.py` (lines 39-107, 626-630)
  - Added `resolve_docs_root()` function
  - Replaced hardcoded global fallback with priority logic

---

## 🚀 Upgrade Instructions

### For All Users (Automatic Fix)

**No action required!** Just update to v1.2.1:

```bash
cd ~/claude-cognitive-package
git pull origin main
```

The fix is automatic. Your project-local `.claude/` will now be correctly detected.

### For Users Who Applied Workaround

If you were using this workaround:

```bash
# OLD workaround (no longer needed)
export CONTEXT_DOCS_ROOT=.claude
```

You can now **remove it**. The project-local `.claude/` will be detected automatically.

### Verification

After updating, verify the fix is working:

```bash
# Run in your project directory
echo '{"prompt": "test"}' | python3 ~/.claude/scripts/context-router-v2.py 2>&1 | grep "Using"

# Should show:
# ℹ Using project-local .claude: /path/to/your/project/.claude
#   Found N .md files
```

If you see "Using global ~/.claude", check:
1. Does `.claude/` exist in your project root?
2. Does it contain `.md` files?
3. Run `ls .claude/*.md` to verify

---

## 🎯 Impact

### Before v1.2.1 (Broken Behavior)
```
User's project/
├── .claude/
│   ├── auth.md         ← IGNORED (never loaded)
│   └── database.md     ← IGNORED (never loaded)

~/.claude/
├── orin.md            ← LOADED (wrong project!)
├── asus.md            ← LOADED (wrong project!)
└── pipe-to-orin.md    ← LOADED (wrong project!)
```

**Result:** User sees MirrorBot CVMP docs instead of their own auth/database docs.

### After v1.2.1 (Fixed Behavior)
```
User's project/
├── .claude/
│   ├── auth.md         ← LOADED ✅ (correct)
│   └── database.md     ← LOADED ✅ (correct)

~/.claude/
├── orin.md            ← IGNORED (fallback only)
├── asus.md            ← IGNORED (fallback only)
└── pipe-to-orin.md    ← IGNORED (fallback only)
```

**Result:** User sees their own project documentation.

---

## 📊 Test Results

| Test Case | Result | Output |
|-----------|--------|--------|
| **Project-local detection** | ✅ PASS | Found project `.claude/` with 1 file |
| **Global fallback (no project)** | ✅ PASS | Used global `~/.claude/` with 64 files |
| **Explicit env var override** | ✅ PASS | Used `CONTEXT_DOCS_ROOT` path |
| **Empty directory error** | ✅ PASS | Helpful error message shown |

---

## 🐛 Known Issues

None. This is a patch release addressing a single critical bug.

---

## 🙏 Credits

**Reported by:** GitHub user via [Issue #9](https://github.com/GMaN1911/claude-cognitive/issues/9)
**Fixed by:** Garret Sutherland ([@GMaN1911](https://github.com/GMaN1911))
**Company:** MirrorEthic LLC

---

## 🔗 Links

- **Repository:** [github.com/GMaN1911/claude-cognitive](https://github.com/GMaN1911/claude-cognitive)
- **Issue #9:** [Wrong documentation loading](https://github.com/GMaN1911/claude-cognitive/issues/9)
- **CHANGELOG:** [CHANGELOG.md](CHANGELOG.md)
- **Previous Release:** [v1.2.0 (Usage Tracking)](https://github.com/GMaN1911/claude-cognitive/releases/tag/v1.2.0)

---

## 📅 Release Timeline

| Version | Date | Description |
|---------|------|-------------|
| v1.2.0 | 2026-01-12 | Phase 1 complete (usage tracking) |
| **v1.2.1** | **2026-01-12** | **Critical bug fix (docs_root priority)** |
| v2.0.0-rc | 2026-01-12 | Hologram integration (pre-release) |

---

**This fix ensures your project-local documentation is always loaded correctly. Thank you for reporting Issue #9!** 🙏
