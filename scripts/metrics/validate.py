#!/usr/bin/env python3
"""
Validation Script - Generate validation data and report for claude-cognitive.

This script runs the context router against representative prompts
to measure actual token savings and keyword effectiveness.

Usage:
  python3 -m scripts.metrics.validate [project_dir]
  python3 -m scripts.metrics.validate --report-only
"""

import json
import os
import sys
import subprocess
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics.store import MetricsStore
from metrics.analyzer import MetricsAnalyzer
from metrics.reporter import MetricsReporter


def run_validation(project_dir: str = ".") -> Dict:
    """
    Run validation by testing the context router against sample prompts.

    Returns a validation result dictionary.
    """
    router_script = Path.home() / ".claude" / "scripts" / "context-router-v2.py"
    if not router_script.exists():
        # Try local path
        router_script = Path(project_dir) / "scripts" / "context-router-v2.py"

    if not router_script.exists():
        return {"error": "Cannot find context-router-v2.py", "status": "FAIL"}

    # Sample prompts that test different activation patterns
    test_prompts = [
        # Generic prompts (should match based on project keywords)
        "How does the main module work?",
        "Show me the project architecture",
        "What are the API endpoints?",
        "How do I run the tests?",
        "Explain the database schema",
        "What does the authentication system do?",
        "How is the deployment configured?",
        "Walk me through the build process",
        # Technical terms
        "Where is the configuration file?",
        "What dependencies does this project have?",
        # Intentionally vague (may not match)
        "Hello",
        "Can you help me?",
        "What should I work on next?",
    ]

    results = []
    for prompt in test_prompts:
        result = _test_prompt(router_script, prompt)
        results.append(result)

    # Aggregate
    total = len(results)
    activated = sum(1 for r in results if r.get("has_activation"))
    failed = sum(1 for r in results if r.get("status") == "FAIL")

    # Calculate totals
    total_injected = sum(r.get("output_chars", 0) for r in results)
    all_managed = results[0].get("total_managed_files", 0) if results else 0

    validation = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "router_script": str(router_script),
        "total_prompts": total,
        "prompts_with_activation": activated,
        "activation_rate": round(activated / total * 100, 1) if total else 0,
        "prompts_failed": failed,
        "total_managed_files": all_managed,
        "total_chars_injected": total_injected,
        "results": results,
        "status": "PASS" if activated > 0 and failed == 0 else "WARN" if failed == 0 else "FAIL",
    }

    return validation


def _test_prompt(router_script: Path, prompt: str) -> Dict:
    """Run a single prompt through the context router in validation mode."""
    try:
        result = subprocess.run(
            ["python3", str(router_script), "--validate", prompt],
            capture_output=True, text=True, timeout=10,
            cwd=str(router_script.parent.parent.parent),  # Project root
        )

        if result.returncode != 0 and not result.stdout.strip():
            return {
                "prompt": prompt,
                "status": "FAIL",
                "error": result.stderr.strip()[:200],
            }

        try:
            data = json.loads(result.stdout)
            data["prompt"] = prompt
            return data
        except json.JSONDecodeError:
            return {
                "prompt": prompt,
                "status": "FAIL",
                "error": f"Invalid JSON output: {result.stdout[:100]}",
            }

    except subprocess.TimeoutExpired:
        return {"prompt": prompt, "status": "FAIL", "error": "Timeout"}
    except Exception as e:
        return {"prompt": prompt, "status": "FAIL", "error": str(e)}


def generate_validation_report(validation: Dict) -> str:
    """Generate a markdown validation report."""
    lines = [
        "# Claude-Cognitive Validation Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"**Router:** `{validation.get('router_script', 'unknown')}`",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "This report tests the claude-cognitive context router by running representative",
        "prompts through its `--validate` mode. Each prompt is tested in a dry-run that",
        "does not modify state, measuring whether keywords activate and how much context",
        "would be injected vs. the total available documentation.",
        "",
        "---",
        "",
        "## Results Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total test prompts | {validation['total_prompts']} |",
        f"| Prompts with activation | {validation['prompts_with_activation']} |",
        f"| Activation rate | **{validation['activation_rate']}%** |",
        f"| Failed tests | {validation['prompts_failed']} |",
        f"| Managed files | {validation['total_managed_files']} |",
        f"| Overall status | **{validation['status']}** |",
        "",
    ]

    # Detailed results
    lines.extend([
        "## Detailed Results",
        "",
        "| Prompt | Status | HOT | WARM | COLD | Activated Files |",
        "|--------|--------|-----|------|------|-----------------|",
    ])

    for r in validation.get("results", []):
        prompt = r.get("prompt", "")[:40]
        status = r.get("status", "?")
        hot = r.get("stats", {}).get("hot", 0) if "stats" in r else "—"
        warm = r.get("stats", {}).get("warm", 0) if "stats" in r else "—"
        cold = r.get("stats", {}).get("cold", 0) if "stats" in r else "—"
        activated = ", ".join(r.get("directly_activated", [])[:3]) or "none"
        if len(r.get("directly_activated", [])) > 3:
            activated += f" +{len(r['directly_activated']) - 3} more"

        lines.append(f"| {prompt} | {status} | {hot} | {warm} | {cold} | {activated} |")

    lines.extend(["", ""])

    # Analysis
    lines.extend([
        "## Analysis",
        "",
    ])

    rate = validation["activation_rate"]
    if rate >= 70:
        lines.append(
            f"**Good coverage**: {rate}% of prompts activated at least one file. "
            "The keyword configuration is well-matched to typical developer queries."
        )
    elif rate >= 40:
        lines.append(
            f"**Moderate coverage**: {rate}% of prompts activated files. "
            "Consider adding more keywords for common development terms."
        )
    elif rate > 0:
        lines.append(
            f"**Low coverage**: Only {rate}% of prompts activated files. "
            "The keyword configuration needs significant expansion. "
            "Run `/cognitive-setup update` to regenerate keywords from the codebase."
        )
    else:
        lines.append(
            "**No activation**: The context router did not activate any files for any test prompt. "
            "This indicates the keyword configuration does not match the test prompts. "
            "This is expected if using default/example keywords with a different project."
        )

    lines.extend([
        "",
        "## Token Savings Potential",
        "",
    ])

    # Calculate baseline: total docs size if everything injected
    results = validation.get("results", [])

    # Use actual output_chars from results with activation
    injection_sizes = [r.get("output_chars", 0) for r in results if r.get("has_activation")]

    # Calculate actual total doc size from the managed files
    total_doc_size = 0
    managed_files = validation.get("total_managed_files", 0)
    if results:
        # Use tokens_available from first result that has stats, which represents actual doc size
        for r in results:
            if "stats" in r and r.get("output_chars", 0) > 0:
                # output_chars gives us the actual injection size
                pass
        # Use router's own calculation if available
        first_valid = next((r for r in results if r.get("stats")), None)
        if first_valid:
            total_chars = first_valid.get("stats", {}).get("total_chars", 0)

    # Rough estimate using managed file count
    estimated_total = managed_files * 2000

    if injection_sizes and estimated_total > 0:
        avg_injection = sum(injection_sizes) / len(injection_sizes)
        savings = (1 - avg_injection / estimated_total) * 100

        lines.extend([
            "### Baseline Comparison",
            "",
            "| Scenario | Context Size |",
            "|----------|--------------|",
            f"| **Without routing** (all docs injected) | ~{estimated_total:,.0f} chars ({managed_files} files) |",
            f"| **With routing** (attention-based) | ~{avg_injection:,.0f} chars avg |",
            f"| **Savings** | **~{savings:.0f}%** |",
            "",
            f"- Baseline: {managed_files} managed files x ~2,000 chars avg = ~{estimated_total:,} chars",
            f"- Actual injection: {avg_injection:,.0f} chars average across {len(injection_sizes)} activated prompts",
            f"- Savings: {1 - avg_injection / estimated_total:.1%} reduction in context size",
            "",
            "Note: Actual savings depend on documentation file sizes and usage patterns. "
            "Use `/cognitive-metrics` after real usage for precise measurements.",
        ])
    else:
        lines.extend([
            "Cannot calculate savings — no prompts activated any files.",
            "Run the setup wizard (`/cognitive-setup`) to configure keywords for your project.",
        ])

    lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    # Generate recommendations
    no_activation_prompts = [
        r["prompt"] for r in results
        if not r.get("has_activation") and r.get("status") != "FAIL"
    ]

    if no_activation_prompts:
        lines.extend([
            "### Prompts That Didn't Activate",
            "",
            "These common prompts did not match any keywords. Consider adding keywords for:",
            "",
        ])
        for p in no_activation_prompts[:5]:
            lines.append(f"- \"{p}\"")
        lines.append("")

    lines.extend([
        "### Next Steps",
        "",
        "1. Run `/cognitive-setup init` to generate project-specific keywords",
        "2. Use the system for several sessions to collect real metrics",
        "3. Run `/cognitive-metrics full` to see actual effectiveness data",
        "4. Iterate on `keywords.json` based on metrics recommendations",
        "",
        "---",
        "",
        "*Report generated by claude-cognitive validation framework*",
    ])

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate claude-cognitive setup")
    parser.add_argument("project_dir", nargs="?", default=".",
                        help="Project directory to validate")
    parser.add_argument("--report-only", action="store_true",
                        help="Generate report from existing metrics data only")
    parser.add_argument("--save", action="store_true",
                        help="Save report to file")

    args = parser.parse_args()

    if args.report_only:
        store = MetricsStore()
        analyzer = MetricsAnalyzer(store)
        reporter = MetricsReporter(analyzer, store)
        report = reporter.generate_full_report()
        print(report)
        if args.save:
            path = store.save_report(f"validation-{date.today().isoformat()}", report)
            print(f"\nSaved to: {path}", file=sys.stderr)
    else:
        print("Running validation...", file=sys.stderr)
        validation = run_validation(args.project_dir)
        report = generate_validation_report(validation)
        print(report)

        if args.save:
            store = MetricsStore()
            path = store.save_report(f"validation-{date.today().isoformat()}", report)
            print(f"\nSaved to: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
