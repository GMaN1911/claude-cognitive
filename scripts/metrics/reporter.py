#!/usr/bin/env python3
"""
Metrics Reporter - Generate markdown reports from analysis results.

Produces human-readable reports from MetricsAnalyzer output.
Reports are designed to be useful both within Claude Code sessions
and as standalone documents (e.g., for PRs or documentation).
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics.store import MetricsStore
from metrics.analyzer import MetricsAnalyzer


class MetricsReporter:
    """Generate markdown reports from metrics analysis."""

    def __init__(
        self,
        analyzer: Optional[MetricsAnalyzer] = None,
        store: Optional[MetricsStore] = None,
    ):
        self.store = store or MetricsStore()
        self.analyzer = analyzer or MetricsAnalyzer(self.store)

    def generate_session_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> str:
        """Generate a concise report for the current/recent session."""
        analysis = self.analyzer.full_analysis(start_date, end_date)
        savings = analysis["token_savings"]
        keywords = analysis["keywords"]
        attention = analysis["attention"]

        lines = [
            "## Claude-Cognitive Metrics Summary",
            "",
        ]

        if savings.get("total_turns", 0) == 0:
            lines.append("*No metrics data collected yet.*")
            lines.append("")
            lines.append("Run some prompts with claude-cognitive hooks active to start collecting data.")
            return "\n".join(lines)

        # Context efficiency section
        lines.extend([
            "### Context Efficiency",
            "",
            f"| Scenario | Avg Tokens/Turn |",
            f"|----------|----------------|",
            f"| Without cognitive (CLAUDE.md only) | {savings.get('avg_baseline_per_turn', 0):,} |",
            f"| **With cognitive** (baseline + targeted) | **{savings.get('avg_total_with_cognitive', 0):,}** |",
            f"| Dump everything (all docs) | {savings.get('avg_dump_everything', 0):,} |",
            "",
            f"- Targeted context added: **+{savings.get('avg_context_added_per_turn', 0):,} tokens/turn**",
            f"- Context selectivity: {savings.get('context_efficiency_pct', 0):.1f}% of all docs injected",
            f"- Turns with activation: {savings['turns_with_activation']} / {savings['total_turns']}",
            "",
        ])

        # Keyword effectiveness
        lines.extend([
            "### Keyword Effectiveness",
            "",
            f"- Hit rate: **{keywords['keyword_hit_rate']:.1f}%**",
            f"- Avg keywords per turn: {keywords['avg_keywords_per_turn']:.1f}",
            f"- Turns with no match: {keywords['turns_with_no_match']}",
        ])

        top = keywords.get("top_keywords", [])
        if top:
            lines.append("")
            lines.append("**Top keywords:**")
            for kw, count in top[:5]:
                lines.append(f"- `{kw}` ({count}x)")

        never = keywords.get("never_matched", [])
        if never:
            lines.append("")
            lines.append(f"**Never matched ({len(never)} keywords):** Consider removing or refining these.")

        lines.append("")

        # Attention dynamics
        lines.extend([
            "### Attention Dynamics",
            "",
            f"- Avg HOT files/turn: {attention['avg_hot_files']:.1f}",
            f"- Avg WARM files/turn: {attention['avg_warm_files']:.1f}",
            f"- Selectivity: {attention['selectivity_ratio']:.1%} of files are active",
            "",
        ])

        return "\n".join(lines)

    def generate_full_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        title: str = "Claude-Cognitive Metrics Report",
    ) -> str:
        """Generate a comprehensive report suitable for documentation."""
        if start_date is None:
            dates = self.store.available_dates()
            start_date = dates[0] if dates else date.today()
        if end_date is None:
            end_date = date.today()

        analysis = self.analyzer.full_analysis(start_date, end_date)

        lines = [
            f"# {title}",
            "",
            f"**Period:** {start_date.isoformat()} to {end_date.isoformat()}",
            f"**Generated:** {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            "",
            "---",
            "",
        ]

        # Executive summary
        savings = analysis["token_savings"]
        keywords = analysis["keywords"]
        attention = analysis["attention"]
        coverage = analysis["coverage"]
        trends = analysis["trends"]

        lines.extend([
            "## Executive Summary",
            "",
        ])

        if savings.get("total_turns", 0) == 0:
            lines.append("No metrics data available for this period.")
            return "\n".join(lines)

        baseline = savings.get('avg_baseline_per_turn', 0)
        with_cognitive = savings.get('avg_total_with_cognitive', 0)
        added = savings.get('avg_context_added_per_turn', 0)
        dump_all = savings.get('avg_dump_everything', 0)

        lines.extend([
            f"Over **{savings['total_turns']} turns**, claude-cognitive's attention-based context routing:",
            "",
            f"- Adds **+{added:,} targeted tokens/turn** beyond the {baseline:,}-token baseline",
            f"- Injects only **{savings.get('context_efficiency_pct', 0):.1f}%** of available docs ({with_cognitive:,} vs {dump_all:,} tokens)",
            f"- **{keywords['keyword_hit_rate']:.1f}% keyword hit rate** across {keywords['total_unique_keywords_matched']} unique keywords",
            f"- **{attention['selectivity_ratio']:.1%} selectivity** — {attention['avg_hot_files']:.1f} HOT + {attention['avg_warm_files']:.1f} WARM files per turn",
            f"- **{coverage['coverage_pct']:.0f}% documentation coverage** ({coverage['files_ever_activated']}/{coverage['total_managed_files']} files activated)",
            "",
            "---",
            "",
        ])

        # Context efficiency detail
        lines.extend([
            "## Context Efficiency",
            "",
            "### Per-Turn Comparison",
            "",
            "| Scenario | Avg Tokens/Turn |",
            "|----------|----------------|",
            f"| Without cognitive (CLAUDE.md only) | {baseline:,} |",
            f"| **With cognitive** (baseline + targeted) | **{with_cognitive:,}** |",
            f"| Dump everything (all docs) | {dump_all:,} |",
            "",
            f"Cognitive adds **+{added:,} targeted tokens** per turn while avoiding "
            f"the {dump_all:,}-token cost of injecting everything.",
            "",
            "### Totals",
            "",
            f"- Total tokens injected: {savings['total_tokens_injected']:,}",
            f"- Total baseline tokens (CLAUDE.md): {savings.get('total_baseline_tokens', 0):,}",
            f"- Total targeted context added: {savings.get('total_context_added', 0):,}",
            f"- Total docs available: {savings['total_tokens_available']:,}",
            f"- Context selectivity: {savings.get('context_efficiency_pct', 0):.1f}%",
        ])
        if savings['total_turns'] > 0:
            lines.append(
                f"- Turns with zero injection: {savings['turns_with_zero_injection']} "
                f"({savings['turns_with_zero_injection'] / savings['total_turns'] * 100:.1f}%)"
            )
        lines.append("")

        # Trends
        if trends.get("daily_savings"):
            lines.extend([
                "### Trends",
                "",
                f"Savings trend: **{trends['savings_trend']}** (slope: {trends['savings_slope']:+.1f}%)",
                "",
                "| Date | Avg Savings | Turns |",
                "|------|-------------|-------|",
            ])
            for d in trends["daily_savings"][-14:]:  # Last 14 days
                lines.append(
                    f"| {d['date']} | {d['avg_savings_pct']:.1f}% | {d['turns']} |"
                )
            lines.extend(["", ""])

        # Keyword analysis
        lines.extend([
            "---",
            "",
            "## Keyword Effectiveness",
            "",
            f"- Hit rate: **{keywords['keyword_hit_rate']:.1f}%**",
            f"- Average keywords matched per turn: {keywords['avg_keywords_per_turn']:.2f}",
            f"- Turns with no keyword match: {keywords['turns_with_no_match']}",
            "",
        ])

        top = keywords.get("top_keywords", [])
        if top:
            lines.extend([
                "### Most Effective Keywords",
                "",
                "| Keyword | Matches |",
                "|---------|---------|",
            ])
            for kw, count in top[:15]:
                lines.append(f"| `{kw}` | {count} |")
            lines.extend(["", ""])

        never = keywords.get("never_matched", [])
        if never:
            lines.extend([
                "### Ineffective Keywords (never matched)",
                "",
                "These keywords are configured but never appeared in any prompt. "
                "Consider removing or replacing them:",
                "",
            ])
            for kw in never[:20]:
                lines.append(f"- `{kw}`")
            if len(never) > 20:
                lines.append(f"- *...and {len(never) - 20} more*")
            lines.extend(["", ""])

        # Attention dynamics
        lines.extend([
            "---",
            "",
            "## Attention Dynamics",
            "",
            "| Tier | Avg Files/Turn | Interpretation |",
            "|------|----------------|----------------|",
            f"| HOT | {attention['avg_hot_files']:.2f} | Full content injected |",
            f"| WARM | {attention['avg_warm_files']:.2f} | Headers only |",
            f"| COLD | {attention['avg_cold_files']:.2f} | Excluded from context |",
            "",
        ])

        most_hot = attention.get("most_frequently_hot", [])
        if most_hot:
            lines.extend([
                "### Most Frequently HOT Files",
                "",
                "| File | HOT Count |",
                "|------|-----------|",
            ])
            for f, count in most_hot:
                lines.append(f"| `{f}` | {count} |")
            lines.extend(["", ""])

        # Transitions
        transitions = analysis.get("transitions", {})
        if transitions.get("total_transitions", 0) > 0:
            lines.extend([
                "---",
                "",
                "## Attention Transitions",
                "",
                f"- Total transitions: {transitions['total_transitions']}",
                f"- To HOT: {transitions['to_hot_count']}",
                f"- To WARM: {transitions['to_warm_count']}",
                f"- To COLD: {transitions['to_cold_count']}",
                f"- Avg transitions/turn: {transitions['avg_transitions_per_turn']:.2f}",
                "",
            ])
            promoted = transitions.get("most_promoted", [])
            if promoted:
                lines.extend([
                    "### Most Frequently Promoted Files",
                    "",
                    "| File | Promotions |",
                    "|------|------------|",
                ])
                for f, count in promoted[:10]:
                    lines.append(f"| `{f}` | {count} |")
                lines.extend(["", ""])

        # Pool coordination
        pool = analysis.get("pool", {})
        if pool.get("total_pool_events", 0) > 0:
            lines.extend([
                "---",
                "",
                "## Pool Coordination",
                "",
                f"- Total pool events: {pool['total_pool_events']}",
                f"- Events/session: {pool['coordination_frequency']:.2f}",
                "",
            ])
            actions = pool.get("action_distribution", {})
            if actions:
                lines.extend([
                    "### Action Distribution",
                    "",
                    "| Action | Count |",
                    "|--------|-------|",
                ])
                for action, count in sorted(actions.items()):
                    lines.append(f"| {action} | {count} |")
                lines.extend(["", ""])

        # Setup analysis
        setup = analysis.get("setup", {})
        if setup.get("total_setups", 0) > 0:
            lines.extend([
                "---",
                "",
                "## Setup Performance",
                "",
                f"- Total setups: {setup['total_setups']}",
                f"- Average duration: {setup['avg_duration_seconds']:.1f}s",
                f"- Success rate: {100 - setup['failure_rate']:.1f}%",
                "",
            ])

        # Coverage
        lines.extend([
            "---",
            "",
            "## Documentation Coverage",
            "",
            f"- Managed files: {coverage['total_managed_files']}",
            f"- Files ever activated: {coverage['files_ever_activated']}",
            f"- Coverage: **{coverage['coverage_pct']:.1f}%**",
            "",
        ])

        never_activated = coverage.get("never_activated", [])
        if never_activated:
            lines.extend([
                "### Files Never Activated",
                "",
                "These documentation files were never loaded into context:",
                "",
            ])
            for f in never_activated:
                lines.append(f"- `{f}`")
            lines.extend(["", ""])

        # Sessions
        sessions = analysis.get("sessions", [])
        if sessions:
            lines.extend([
                "---",
                "",
                "## Session Summary",
                "",
                "| Session | Instance | Turns | Duration | Selectivity | KW Hit Rate |",
                "|---------|----------|-------|----------|-------------|-------------|",
            ])
            for s in sessions[-10:]:  # Last 10 sessions
                duration = _format_duration(s.get("duration_seconds", 0))
                selectivity = s.get("avg_context_efficiency_pct",
                                    100 - s.get("avg_savings_pct", 0))
                lines.append(
                    f"| {s['session_id'][:8]} | {s['instance_id']} | "
                    f"{s['turn_count']} | {duration} | "
                    f"{selectivity:.1f}% | {s['keyword_hit_rate']:.1f}% |"
                )
            lines.extend(["", ""])

        # Recommendations
        lines.extend(self._generate_recommendations(analysis))

        # Footer
        lines.extend([
            "---",
            "",
            "*Report generated by claude-cognitive metrics framework*",
        ])

        return "\n".join(lines)

    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations from analysis."""
        lines = [
            "---",
            "",
            "## Recommendations",
            "",
        ]

        savings = analysis["token_savings"]
        keywords = analysis["keywords"]
        coverage = analysis["coverage"]

        recommendations = []

        # Check keyword hit rate
        if keywords.get("keyword_hit_rate", 100) < 50:
            recommendations.append(
                "**Low keyword hit rate** ({:.1f}%): Many prompts don't match any "
                "keywords. Review your `keywords.json` and add terms that match "
                "your actual development vocabulary.".format(keywords["keyword_hit_rate"])
            )

        # Check never-matched keywords
        never = keywords.get("never_matched", [])
        if len(never) > 5:
            recommendations.append(
                f"**{len(never)} keywords never matched**: Remove or replace "
                f"ineffective keywords to reduce noise. Top candidates: "
                f"{', '.join(f'`{k}`' for k in never[:5])}"
            )

        # Check coverage
        if coverage.get("coverage_pct", 100) < 50:
            recommendations.append(
                "**Low documentation coverage** ({:.0f}%): Most documentation "
                "files are never activated. Either add better keywords for "
                "uncovered files, or remove documentation that isn't useful.".format(
                    coverage["coverage_pct"]
                )
            )

        # Check zero-injection turns
        total = savings.get("total_turns", 1)
        zero = savings.get("turns_with_zero_injection", 0)
        if total > 0 and zero / total > 0.3:
            recommendations.append(
                f"**{zero / total * 100:.0f}% of turns had zero injection**: "
                f"The context router is not providing value on many turns. "
                f"Broaden keyword coverage or add co-activation rules."
            )

        # Check context efficiency (high % means injecting too much)
        efficiency = savings.get("context_efficiency_pct", 0)
        if efficiency > 70:
            recommendations.append(
                "**Low selectivity** ({:.1f}% of docs injected): The system is "
                "injecting most of the available documentation. Consider adding "
                "more granular documentation files or tightening keyword "
                "specificity.".format(efficiency)
            )

        if not recommendations:
            recommendations.append(
                "System is performing well. Continue monitoring for changes "
                "in effectiveness as the project evolves."
            )

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
            lines.append("")

        return lines

    def generate_comparison_report(
        self,
        baseline_events: List[Dict],
        active_events: List[Dict],
    ) -> str:
        """
        Generate a before/after comparison report.

        Args:
            baseline_events: Events without claude-cognitive
            active_events: Events with claude-cognitive active
        """
        lines = [
            "# Claude-Cognitive Impact Comparison",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            "",
            "---",
            "",
            "## Comparison: Without vs. With Context Routing",
            "",
            "| Metric | Without | With | Improvement |",
            "|--------|---------|------|-------------|",
        ]

        # Calculate baseline stats
        baseline_tokens = sum(e.get("tokens_available", 0) for e in baseline_events)
        baseline_turns = len(baseline_events)

        # Calculate active stats
        active_injected = sum(e.get("tokens_injected", 0) for e in active_events)
        active_available = sum(e.get("tokens_available", 0) for e in active_events)
        active_saved = sum(e.get("tokens_saved", 0) for e in active_events)
        active_turns = len(active_events)

        avg_baseline = baseline_tokens / baseline_turns if baseline_turns else 0
        avg_active = active_injected / active_turns if active_turns else 0
        savings_pct = (1 - avg_active / avg_baseline) * 100 if avg_baseline else 0

        lines.extend([
            f"| Turns | {baseline_turns} | {active_turns} | - |",
            f"| Avg tokens/turn | {avg_baseline:,.0f} | {avg_active:,.0f} | **{savings_pct:.1f}% reduction** |",
            f"| Total tokens saved | - | {active_saved:,} | - |",
            "",
        ])

        return "\n".join(lines)


def _format_duration(seconds: int) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate metrics reports")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--type", choices=["session", "full"], default="session",
        help="Report type"
    )
    parser.add_argument("--save", action="store_true", help="Save to reports directory")
    parser.add_argument("--name", type=str, help="Report filename (without .md)")

    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None

    reporter = MetricsReporter()

    if args.type == "full":
        report = reporter.generate_full_report(start, end)
    else:
        report = reporter.generate_session_report(start, end)

    print(report)

    if args.save:
        name = args.name or f"report-{date.today().isoformat()}"
        path = reporter.store.save_report(name, report)
        print(f"\nSaved to: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
