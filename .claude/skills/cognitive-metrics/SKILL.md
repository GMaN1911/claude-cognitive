---
name: cognitive-metrics
description: Analyze claude-cognitive metrics — token savings, keyword effectiveness, attention dynamics, and coverage. Use this to check if the context routing system is working and how to improve it.
argument-hint: [summary|full|savings|keywords|coverage|trends]
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# Claude-Cognitive Metrics Analysis

You are analyzing the metrics collected by the claude-cognitive context routing system.

## What You Have Access To

The metrics framework stores data in `.claude/cognitive-metrics/`:
- `events/*.jsonl` — Raw per-turn events (context_injection, session_start, session_end)
- `summaries/*.json` — Daily aggregated summaries
- `reports/*.md` — Previously generated reports

## How To Analyze

Use the Python metrics modules located in `scripts/metrics/`:

```bash
# Full analysis (all metrics, text output)
python3 -m scripts.metrics.analyzer --analysis all

# Specific analyses
python3 -m scripts.metrics.analyzer --analysis savings
python3 -m scripts.metrics.analyzer --analysis keywords
python3 -m scripts.metrics.analyzer --analysis attention
python3 -m scripts.metrics.analyzer --analysis coverage
python3 -m scripts.metrics.analyzer --analysis trends

# JSON output (for programmatic use)
python3 -m scripts.metrics.analyzer --analysis all --format json

# Date range
python3 -m scripts.metrics.analyzer --start 2026-02-01 --end 2026-02-28
```

## How To Generate Reports

```bash
# Session summary (concise)
python3 -m scripts.metrics.reporter --type session

# Full comprehensive report
python3 -m scripts.metrics.reporter --type full

# Save report to .claude/cognitive-metrics/reports/
python3 -m scripts.metrics.reporter --type full --save --name my-report
```

## What To Present

Based on the user's argument ($ARGUMENTS):

- **summary** (default): Run session report, present key findings concisely
- **full**: Run full report, present comprehensive analysis with recommendations
- **savings**: Focus on token savings analysis
- **keywords**: Focus on keyword effectiveness and suggestions
- **coverage**: Focus on documentation coverage gaps
- **trends**: Focus on historical trends

Always include:
1. Key numbers (savings %, hit rate, coverage)
2. What's working well
3. What could be improved (actionable recommendations)
4. Specific suggestions (e.g., which keywords to add/remove)

If no data exists yet, explain how to set up data collection (the metrics collector hook).
