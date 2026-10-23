---
name: cognitive-status
description: Check the health and status of the claude-cognitive context routing system. Diagnoses configuration issues, shows attention state, and validates hooks are working.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# Claude-Cognitive Status Check

You are running a health check on the claude-cognitive context routing system. Follow these steps and report results clearly.

## Step 1: Check Required Files

Check that these files/directories exist. Report each as PASS or FAIL:

1. **Scripts**: Check `~/.claude/scripts/` for:
   - `context-router-v2.py`
   - `pool-loader.py`
   - `pool-extractor.py`
   - `pool-auto-update.py`
   - `metrics/collector.py` (optional, for v1.3 metrics)

2. **Project config**: Check `.claude/` in current directory for:
   - `keywords.json` (required for keyword-based routing)
   - Any `.md` files in `modules/`, `systems/`, `integrations/`
   - `attn_state.json` (auto-generated after first use)

3. **Hook configuration**: Check that `~/.claude/settings.json` contains hooks for `UserPromptSubmit`, `SessionStart`, and `Stop` that reference the cognitive scripts.

## Step 2: Validate Configuration

Run the context router in validation mode with a sample prompt relevant to the project:

```bash
python3 ~/.claude/scripts/context-router-v2.py --validate "sample prompt about the project"
```

Check if status is PASS or WARN.

## Step 3: Check Attention State

If `.claude/attn_state.json` exists, read it and report:
- Number of tracked files
- Turn count
- How many files are HOT, WARM, COLD
- Last update timestamp

## Step 4: Check Metrics (if available)

If `.claude/cognitive-metrics/` exists:
- Count event files
- Show the latest session summary
- Report total turns tracked

## Step 5: Report

Present a clear status report with:
- Overall health: HEALTHY, DEGRADED, or NOT CONFIGURED
- Specific issues found with fix instructions
- Quick actions the user can take to resolve problems

Use this format:
```
## Claude-Cognitive Status: [HEALTHY/DEGRADED/NOT CONFIGURED]

### Files
- [PASS/FAIL] Scripts installed
- [PASS/FAIL] Keywords configured
- [PASS/FAIL] Documentation files present
- [PASS/FAIL] Hooks configured

### Configuration
- Keyword mappings: N files, M total keywords
- Documentation: N modules, N systems, N integrations
- Attention state: N HOT, N WARM, N COLD (turn N)

### Issues
- [list any problems found with fix instructions]
```
