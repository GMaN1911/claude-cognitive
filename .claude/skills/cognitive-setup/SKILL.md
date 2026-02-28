---
name: cognitive-setup
description: Interactive setup wizard for claude-cognitive. Analyzes your project, generates keyword mappings, creates documentation stubs, installs hooks, and validates everything works. Turns a 3-hour manual setup into a 5-minute guided workflow.
argument-hint: [init|update|validate]
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Task
---

# Claude-Cognitive Setup Wizard

You are an interactive setup assistant for the claude-cognitive context routing system. Your job is to analyze the user's project and configure claude-cognitive with minimal manual effort.

## Arguments

- **init** (default): Full initial setup for a new project
- **update**: Re-analyze the project and update existing configuration
- **validate**: Just validate that the current setup works

## Overview

Claude-cognitive enhances Claude Code by dynamically routing only relevant documentation into context based on keyword matching and attention decay. Instead of loading everything, it loads only what's relevant to the current prompt.

The system requires:
1. Documentation files in `.claude/modules/`, `.claude/systems/`, `.claude/integrations/`
2. A `keywords.json` mapping keywords to those documentation files
3. Hook scripts installed and configured in Claude Code settings

## Setup Workflow

### Metrics Instrumentation

At each phase boundary, record timing metrics so setup performance can be analyzed. Only call the metrics collector if it exists at `~/.claude/scripts/metrics/collector.py` — skip silently if not yet installed (Phase 0 will install it).

```bash
# At the start of setup (after Phase 0)
python3 ~/.claude/scripts/metrics/collector.py setup-start init

# After each phase completes
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase environment_check --number 1 --success true
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase analysis --number 2 --success true
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase keywords --number 3 --success true
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase documentation --number 4 --success true
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase hooks --number 5 --success true
python3 ~/.claude/scripts/metrics/collector.py setup-phase --phase validation --number 6 --success true

# At the end of setup
python3 ~/.claude/scripts/metrics/collector.py setup-complete --mode init --status success
```

If any phase fails, record `--success false` and `--status failure` on the complete event.

### Phase 0: Script & Hook Installation

This phase ensures the claude-cognitive runtime is installed before doing anything else. It runs automatically and handles the entire infrastructure setup.

1. **Check if scripts are already installed:**
   ```bash
   test -f ~/.claude/scripts/context-router-v2.py && echo "installed" || echo "missing"
   ```

2. **If scripts are missing, locate the claude-cognitive repository.** Search in order:
   - The current working directory (check for `scripts/context-router-v2.py`)
   - `~/.claude-cognitive/`
   - `~/claude-cognitive/`
   - Any directory found via: `find ~ -maxdepth 3 -name "context-router-v2.py" -path "*/scripts/*" 2>/dev/null | head -1`

3. **If the repo is not found anywhere, clone it:**
   ```bash
   git clone https://github.com/GMaN1911/claude-cognitive.git ~/.claude-cognitive
   ```

4. **Install scripts** from the located repo (let `REPO` be the repo path):
   ```bash
   mkdir -p ~/.claude/scripts/metrics
   cp "$REPO/scripts/context-router-v2.py" ~/.claude/scripts/
   cp "$REPO/scripts/pool-loader.py" ~/.claude/scripts/
   cp "$REPO/scripts/pool-extractor.py" ~/.claude/scripts/
   cp "$REPO/scripts/pool-auto-update.py" ~/.claude/scripts/
   cp "$REPO/scripts/pool-query.py" ~/.claude/scripts/
   cp "$REPO/scripts/metrics/"*.py ~/.claude/scripts/metrics/
   chmod +x ~/.claude/scripts/*.py
   ```

5. **Check if hooks are configured** in `~/.claude/settings.json`:
   ```bash
   grep -q "context-router" ~/.claude/settings.json 2>/dev/null && echo "configured" || echo "missing"
   ```

6. **If hooks are missing, configure them.** Read the existing `~/.claude/settings.json` (or create it), and non-destructively merge the required hooks. The hooks to add:

   - **UserPromptSubmit**: `context-router-v2.py`, `pool-auto-update.py`, `metrics/collector.py prompt`
   - **SessionStart**: `pool-loader.py`, `metrics/collector.py session-start`
   - **Stop**: `pool-extractor.py`, `metrics/collector.py session-end`

   **IMPORTANT**: Show the user the proposed settings.json changes and ask for confirmation before writing. Back up the existing file first:
   ```bash
   cp ~/.claude/settings.json ~/.claude/settings.json.backup 2>/dev/null || true
   ```

7. **Report what was installed** and note that the user will need to restart their Claude Code session for hooks to take effect (hooks are loaded at session start).

**If everything is already installed**, skip this phase and report: "Scripts and hooks already installed — skipping to environment check."

### Phase 1: Environment Check

1. Verify Python 3.8+ is available
2. Check if `.claude/` directory already exists in the current project
3. Check if hooks are already configured in `~/.claude/settings.json` (should be, after Phase 0)
4. Detect project characteristics:
   - Language(s) used (check file extensions, package files)
   - Framework(s) (check for package.json, requirements.txt, Cargo.toml, etc.)
   - Project structure (monorepo vs single project)
   - Entry points and key files
5. Report findings and ask user to confirm or correct

### Phase 2: Project Analysis

Use the Explore agent or directly scan the project to identify:

1. **Key modules/components**: Major source directories, important classes/functions
2. **Systems/infrastructure**: Docker, CI/CD, database, deployment configs
3. **Integrations**: External APIs, services, webhooks, SDKs
4. **Configuration files**: Environment variables, config files
5. **Entry points**: Main scripts, server files, CLI commands

Build a **project map** that organizes discoveries into the three categories:
- `modules/` — Code systems that change frequently
- `systems/` — Infrastructure that changes slowly
- `integrations/` — Cross-system communication

Present the project map to the user for review before proceeding.

### Phase 3: Keyword Generation

For each identified documentation file, generate keyword mappings:

1. Extract key terms from:
   - File names and directory names
   - Class names, function names, and variable names
   - Import statements and dependency names
   - Comments and docstrings
   - Configuration keys

2. Organize keywords by relevance:
   - **Primary**: Direct identifiers (class names, function names, module names)
   - **Secondary**: Related concepts (what the module does, its domain)
   - **Tertiary**: Common synonyms a developer might use

3. Generate co-activation rules:
   - Files in the same directory or package
   - Files with import relationships
   - Files that share common keywords

4. Suggest pinned files (always warm):
   - Project overview/architecture docs
   - Critical configuration files

5. Write `keywords.json` using **exactly** this format (the context router will not load any other structure):

   ```json
   {
     "keywords": {
       "modules/example.md": ["keyword1", "keyword2", "keyword3"],
       "systems/infra.md": ["deploy", "docker", "ci"]
     },
     "co_activation": {
       "modules/example.md": ["modules/related.md"],
       "systems/infra.md": ["integrations/deploy-pipeline.md"]
     },
     "pinned": ["systems/development.md"]
   }
   ```

   - **`keywords`**: a flat dict mapping each doc file path (relative to `.claude/`) to a list of keyword strings
   - **`co_activation`**: a flat dict mapping each doc file path to a list of other doc file paths that should be boosted when the key file activates
   - **`pinned`**: a flat list of doc file paths that should always remain at least WARM

   Do NOT nest keywords inside file objects. Do NOT add extra metadata fields. The router reads only these three top-level keys.

Present the generated `keywords.json` for user review before writing it.

### Phase 4: Documentation Generation

For each file in the project map, generate a documentation stub:

1. Use the fractal documentation format:
   - Structured header (under 25 lines) with: purpose, entry point, status, key functions, architecture
   - `<!-- WARM CONTEXT ENDS -->` marker separating header from details
   - Detailed content below the marker

2. Pre-fill content by reading the actual source files:
   - Extract function signatures and docstrings
   - Identify key classes and their purposes
   - Note dependencies and integration points
   - Include common operations and error handling

3. Write files to `.claude/modules/`, `.claude/systems/`, `.claude/integrations/`

4. Create or update `.claude/CLAUDE.md` with:
   - Project overview
   - Architecture summary
   - Documentation structure reference
   - Quick reference commands

### Phase 5: Hook & Script Verification

Scripts and hooks were installed in Phase 0. This phase verifies and updates them if needed.

1. **Verify scripts are current** — compare installed scripts against the repo source (if available). If the repo has newer versions, offer to update:
   ```bash
   diff -q "$REPO/scripts/context-router-v2.py" ~/.claude/scripts/context-router-v2.py 2>/dev/null
   ```

2. **Verify hooks are properly configured** — check that `~/.claude/settings.json` contains all required hooks:
   - `UserPromptSubmit`: context-router-v2.py, pool-auto-update.py, metrics/collector.py
   - `SessionStart`: pool-loader.py, metrics/collector.py
   - `Stop`: pool-extractor.py, metrics/collector.py

3. **Verify hooks JSON is syntactically valid:**
   ```bash
   python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))" && echo "valid" || echo "invalid"
   ```

4. If any hooks are missing, merge them (same approach as Phase 0 — show changes, ask for confirmation, back up first).

### Phase 6: Validation

1. Run the context router in validation mode with project-relevant prompts:
   ```bash
   python3 ~/.claude/scripts/context-router-v2.py --validate "a prompt about [key project concept]"
   ```

2. Verify:
   - At least one file activates for each test prompt
   - Documentation files are found and readable
   - Keywords.json is valid JSON
   - Hooks configuration is valid

3. Report results:
   - PASS: Everything working
   - WARN: Working but with suggestions for improvement
   - FAIL: Specific issues with fix instructions

4. Suggest next steps:
   - Start a new Claude Code session to see the hooks in action
   - Use `/cognitive-status` to check health
   - Use `/cognitive-metrics` after some usage to see effectiveness

## Key Principles

- **Ask before writing**: Always present generated content for user review before writing files
- **Idempotent**: Can be re-run safely to update configuration
- **Non-destructive**: Never overwrite existing files without asking; merge where possible
- **Progressive**: Each phase builds on the previous; user can stop at any point
- **Honest**: If analysis quality is low, say so and suggest manual refinement
