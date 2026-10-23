#!/usr/bin/env python3
"""
Metrics Analyzer - Statistical analysis of claude-cognitive metrics.

Processes raw events from the MetricsStore into actionable insights:
- Token savings analysis (per-turn, per-session, aggregate)
- Keyword effectiveness scoring
- Attention dynamics patterns
- Trend detection over time
- Coverage gap identification

All analysis functions return structured dicts with a to_dict() pattern
for easy JSON serialization (future GUI/API compatibility).
"""

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics.store import MetricsStore


# ============================================================================
# DATA CLASSES
# ============================================================================

class AnalysisResult:
    """Base class for analysis results with JSON serialization."""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, AnalysisResult):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    v.to_dict() if isinstance(v, AnalysisResult) else v
                    for v in value
                ]
            elif isinstance(value, date):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class TokenSavingsAnalysis(AnalysisResult):
    """Token savings and context efficiency statistics."""

    def __init__(self):
        self.total_turns: int = 0
        self.total_tokens_injected: int = 0
        self.total_tokens_available: int = 0
        self.total_tokens_saved: int = 0
        self.total_baseline_tokens: int = 0
        self.total_context_added: int = 0
        # Practical per-turn metrics
        self.avg_baseline_per_turn: float = 0.0
        self.avg_context_added_per_turn: float = 0.0
        self.avg_total_with_cognitive: float = 0.0
        self.avg_dump_everything: float = 0.0
        self.context_efficiency_pct: float = 0.0
        # Distribution stats (kept for backward compat)
        self.avg_savings_pct: float = 0.0
        self.median_savings_pct: float = 0.0
        self.min_savings_pct: float = 0.0
        self.max_savings_pct: float = 0.0
        self.p25_savings_pct: float = 0.0
        self.p75_savings_pct: float = 0.0
        self.turns_with_zero_injection: int = 0
        self.turns_with_activation: int = 0


class KeywordAnalysis(AnalysisResult):
    """Keyword effectiveness analysis."""

    def __init__(self):
        self.total_unique_keywords_matched: int = 0
        self.keyword_hit_counts: Dict[str, int] = {}
        self.top_keywords: List[Tuple[str, int]] = []
        self.never_matched: List[str] = []
        self.turns_with_no_match: int = 0
        self.avg_keywords_per_turn: float = 0.0
        self.keyword_hit_rate: float = 0.0


class AttentionAnalysis(AnalysisResult):
    """Attention dynamics analysis."""

    def __init__(self):
        self.avg_hot_files: float = 0.0
        self.avg_warm_files: float = 0.0
        self.avg_cold_files: float = 0.0
        self.max_hot_files: int = 0
        self.most_frequently_hot: List[Tuple[str, int]] = []
        self.selectivity_ratio: float = 0.0  # hot+warm / total


class SessionAnalysis(AnalysisResult):
    """Per-session analysis."""

    def __init__(self):
        self.session_id: str = ""
        self.instance_id: str = ""
        self.turn_count: int = 0
        self.duration_seconds: int = 0
        self.total_tokens_injected: int = 0
        self.total_tokens_saved: int = 0
        self.avg_savings_pct: float = 0.0
        self.keyword_hit_rate: float = 0.0


class TrendAnalysis(AnalysisResult):
    """Trend analysis over time."""

    def __init__(self):
        self.period_start: Optional[date] = None
        self.period_end: Optional[date] = None
        self.daily_savings: List[Dict] = []  # [{date, avg_savings_pct, turns}]
        self.savings_trend: str = "stable"  # improving, declining, stable
        self.savings_slope: float = 0.0


class TransitionAnalysis(AnalysisResult):
    """Attention transition analysis."""

    def __init__(self):
        self.total_transitions: int = 0
        self.to_hot_count: int = 0
        self.to_warm_count: int = 0
        self.to_cold_count: int = 0
        self.most_promoted: List[Tuple[str, int]] = []
        self.most_volatile: List[Tuple[str, int]] = []
        self.avg_transitions_per_turn: float = 0.0


class PoolAnalysis(AnalysisResult):
    """Pool coordination analysis."""

    def __init__(self):
        self.total_pool_events: int = 0
        self.action_distribution: Dict[str, int] = {}
        self.coordination_frequency: float = 0.0
        self.most_active_instances: List[Tuple[str, int]] = []
        self.common_topics: List[Tuple[str, int]] = []


class SetupAnalysis(AnalysisResult):
    """Setup timing analysis."""

    def __init__(self):
        self.total_setups: int = 0
        self.avg_duration_seconds: float = 0.0
        self.phase_breakdown: List[Dict] = []
        self.failure_rate: float = 0.0
        self.success_count: int = 0
        self.failure_count: int = 0


class CoverageAnalysis(AnalysisResult):
    """Documentation coverage gap analysis."""

    def __init__(self):
        self.total_managed_files: int = 0
        self.files_ever_activated: int = 0
        self.coverage_pct: float = 0.0
        self.never_activated: List[str] = []
        self.rarely_activated: List[Tuple[str, int]] = []  # (file, count)
        self.frequently_activated: List[Tuple[str, int]] = []


# ============================================================================
# ANALYZER
# ============================================================================

class MetricsAnalyzer:
    """Analyzes metrics events to produce insights."""

    def __init__(self, store: Optional[MetricsStore] = None):
        self.store = store or MetricsStore()

    def _get_injection_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict]:
        """Get context_injection events in date range."""
        return self.store.read_events_list(
            start_date=start_date,
            end_date=end_date,
            event_type="context_injection",
        )

    @staticmethod
    def _percentile(values: List[float], pct: float) -> float:
        """Calculate percentile from sorted list."""
        if not values:
            return 0.0
        values = sorted(values)
        k = (len(values) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(values):
            return values[-1]
        return values[f] + (k - f) * (values[c] - values[f])

    # ------------------------------------------------------------------
    # Token Savings Analysis
    # ------------------------------------------------------------------

    def analyze_token_savings(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> TokenSavingsAnalysis:
        """Analyze token savings across all turns in the date range."""
        events = self._get_injection_events(start_date, end_date)
        result = TokenSavingsAnalysis()

        if not events:
            return result

        savings_pcts = []
        for e in events:
            result.total_turns += 1
            result.total_tokens_injected += e.get("tokens_injected", 0)
            result.total_tokens_available += e.get("tokens_available", 0)
            result.total_tokens_saved += e.get("tokens_saved", 0)
            result.total_baseline_tokens += e.get("baseline_tokens", 0)
            result.total_context_added += e.get("context_added", 0)

            pct = e.get("savings_pct", 0)
            savings_pcts.append(pct)

            if e.get("tokens_injected", 0) == 0:
                result.turns_with_zero_injection += 1
            if e.get("has_activation", False):
                result.turns_with_activation += 1

        turns = result.total_turns

        # Practical per-turn averages
        result.avg_baseline_per_turn = round(
            result.total_baseline_tokens / turns
        ) if turns else 0
        result.avg_context_added_per_turn = round(
            result.total_context_added / turns
        ) if turns else 0
        result.avg_total_with_cognitive = round(
            result.total_tokens_injected / turns
        ) if turns else 0
        result.avg_dump_everything = round(
            result.total_tokens_available / turns
        ) if turns else 0

        # Context efficiency: what % of all docs does the router actually inject
        if result.total_tokens_available > 0:
            result.context_efficiency_pct = round(
                result.total_tokens_injected / result.total_tokens_available * 100, 1
            )

        # Distribution stats (backward compat)
        result.avg_savings_pct = round(
            sum(savings_pcts) / len(savings_pcts), 1
        )
        result.median_savings_pct = round(
            self._percentile(savings_pcts, 50), 1
        )
        result.min_savings_pct = round(min(savings_pcts), 1)
        result.max_savings_pct = round(max(savings_pcts), 1)
        result.p25_savings_pct = round(
            self._percentile(savings_pcts, 25), 1
        )
        result.p75_savings_pct = round(
            self._percentile(savings_pcts, 75), 1
        )

        return result

    # ------------------------------------------------------------------
    # Keyword Analysis
    # ------------------------------------------------------------------

    def analyze_keywords(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> KeywordAnalysis:
        """Analyze keyword effectiveness."""
        events = self._get_injection_events(start_date, end_date)
        result = KeywordAnalysis()

        if not events:
            return result

        keyword_counts = defaultdict(int)
        turns_with_match = 0
        total_keywords_per_turn = []

        for e in events:
            matched = e.get("keywords_matched", [])
            count = e.get("keywords_matched_count", len(matched))
            total_keywords_per_turn.append(count)

            if count > 0:
                turns_with_match += 1

            for kw in matched:
                keyword_counts[kw] += 1

        result.total_unique_keywords_matched = len(keyword_counts)
        result.keyword_hit_counts = dict(keyword_counts)
        result.top_keywords = sorted(
            keyword_counts.items(), key=lambda x: x[1], reverse=True
        )[:20]
        result.turns_with_no_match = len(events) - turns_with_match
        result.avg_keywords_per_turn = round(
            sum(total_keywords_per_turn) / len(total_keywords_per_turn), 2
        ) if total_keywords_per_turn else 0.0
        result.keyword_hit_rate = round(
            turns_with_match / len(events) * 100, 1
        ) if events else 0.0

        # Find keywords that are configured but never matched
        keywords_config = self._load_all_keywords()
        if keywords_config:
            all_configured = set()
            for kw_list in keywords_config.values():
                all_configured.update(kw_list)
            result.never_matched = sorted(
                all_configured - set(keyword_counts.keys())
            )

        return result

    def _load_all_keywords(self) -> Dict[str, List[str]]:
        """Load all configured keywords."""
        paths = [
            Path.cwd() / ".claude" / "keywords.json",
            Path.home() / ".claude" / "keywords.json",
        ]
        for path in paths:
            if path.exists():
                try:
                    config = json.loads(path.read_text())
                    return config.get("keywords", {})
                except json.JSONDecodeError:
                    continue
        return {}

    # ------------------------------------------------------------------
    # Attention Dynamics
    # ------------------------------------------------------------------

    def analyze_attention(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AttentionAnalysis:
        """Analyze attention state dynamics."""
        events = self._get_injection_events(start_date, end_date)
        result = AttentionAnalysis()

        if not events:
            return result

        hot_counts = []
        warm_counts = []
        cold_counts = []
        hot_file_frequency = defaultdict(int)

        for e in events:
            hot = e.get("hot_files", 0)
            warm = e.get("warm_files", 0)
            cold = e.get("cold_files", 0)
            hot_counts.append(hot)
            warm_counts.append(warm)
            cold_counts.append(cold)

            for f in e.get("hot_file_names", []):
                hot_file_frequency[f] += 1

        result.avg_hot_files = round(
            sum(hot_counts) / len(hot_counts), 2
        )
        result.avg_warm_files = round(
            sum(warm_counts) / len(warm_counts), 2
        )
        result.avg_cold_files = round(
            sum(cold_counts) / len(cold_counts), 2
        )
        result.max_hot_files = max(hot_counts) if hot_counts else 0
        result.most_frequently_hot = sorted(
            hot_file_frequency.items(), key=lambda x: x[1], reverse=True
        )[:10]

        total_files = result.avg_hot_files + result.avg_warm_files + result.avg_cold_files
        if total_files > 0:
            result.selectivity_ratio = round(
                (result.avg_hot_files + result.avg_warm_files) / total_files, 3
            )

        return result

    # ------------------------------------------------------------------
    # Session Analysis
    # ------------------------------------------------------------------

    def analyze_sessions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SessionAnalysis]:
        """Analyze individual sessions."""
        session_events = self.store.read_events_list(
            start_date=start_date,
            end_date=end_date,
            event_type="session_end",
        )

        results = []
        for e in session_events:
            sa = SessionAnalysis()
            sa.session_id = e.get("session", "")
            sa.instance_id = e.get("instance", "")
            sa.turn_count = e.get("turn_count", 0)
            sa.duration_seconds = e.get("duration_seconds", 0)
            sa.total_tokens_injected = e.get("total_tokens_injected", 0)
            sa.total_tokens_saved = e.get("total_tokens_saved", 0)
            sa.avg_savings_pct = e.get("avg_savings_pct", 0)
            sa.keyword_hit_rate = e.get("keyword_hit_rate", 0)
            results.append(sa)

        return results

    # ------------------------------------------------------------------
    # Trend Analysis
    # ------------------------------------------------------------------

    def analyze_trends(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> TrendAnalysis:
        """Analyze savings trends over time."""
        if start_date is None:
            # Default to last 30 days
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        events = self._get_injection_events(start_date, end_date)
        result = TrendAnalysis()
        result.period_start = start_date
        result.period_end = end_date

        if not events:
            return result

        # Group by date
        daily_data = defaultdict(list)
        for e in events:
            try:
                event_date = datetime.fromisoformat(
                    e["ts"].rstrip("Z")
                ).date()
                daily_data[event_date].append(e.get("savings_pct", 0))
            except (KeyError, ValueError):
                continue

        daily_savings = []
        for d in sorted(daily_data.keys()):
            pcts = daily_data[d]
            daily_savings.append({
                "date": d.isoformat(),
                "avg_savings_pct": round(sum(pcts) / len(pcts), 1),
                "turns": len(pcts),
            })
        result.daily_savings = daily_savings

        # Simple linear trend detection
        if len(daily_savings) >= 3:
            recent = [d["avg_savings_pct"] for d in daily_savings[-3:]]
            earlier = [d["avg_savings_pct"] for d in daily_savings[:3]]
            avg_recent = sum(recent) / len(recent)
            avg_earlier = sum(earlier) / len(earlier)
            diff = avg_recent - avg_earlier

            if diff > 5:
                result.savings_trend = "improving"
            elif diff < -5:
                result.savings_trend = "declining"
            else:
                result.savings_trend = "stable"
            result.savings_slope = round(diff, 2)

        return result

    # ------------------------------------------------------------------
    # Transition Analysis
    # ------------------------------------------------------------------

    def analyze_transitions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> TransitionAnalysis:
        """Analyze attention transitions between tiers."""
        events = self._get_injection_events(start_date, end_date)
        result = TransitionAnalysis()

        if not events:
            return result

        promoted_counts = defaultdict(int)  # file -> times promoted to hot/warm
        transition_counts = defaultdict(int)  # file -> total transitions
        turns_with_data = 0

        for e in events:
            transitions = e.get("transitions", {})
            if not transitions:
                continue
            turns_with_data += 1

            to_hot = transitions.get("to_hot", [])
            to_warm = transitions.get("to_warm", [])
            to_cold = transitions.get("to_cold", [])

            result.to_hot_count += len(to_hot)
            result.to_warm_count += len(to_warm)
            result.to_cold_count += len(to_cold)

            for f in to_hot:
                promoted_counts[f] += 1
                transition_counts[f] += 1
            for f in to_warm:
                promoted_counts[f] += 1
                transition_counts[f] += 1
            for f in to_cold:
                transition_counts[f] += 1

        result.total_transitions = result.to_hot_count + result.to_warm_count + result.to_cold_count
        result.avg_transitions_per_turn = round(
            result.total_transitions / turns_with_data, 2
        ) if turns_with_data else 0.0

        result.most_promoted = sorted(
            promoted_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
        result.most_volatile = sorted(
            transition_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return result

    # ------------------------------------------------------------------
    # Pool Analysis
    # ------------------------------------------------------------------

    def analyze_pool(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PoolAnalysis:
        """Analyze pool coordination events."""
        events = self.store.read_events_list(
            start_date=start_date,
            end_date=end_date,
            event_type="pool_event",
        )
        result = PoolAnalysis()

        if not events:
            return result

        result.total_pool_events = len(events)
        action_counts = defaultdict(int)
        instance_counts = defaultdict(int)
        topic_counts = defaultdict(int)

        for e in events:
            action = e.get("action", "unknown")
            action_counts[action] += 1
            instance_counts[e.get("source_instance", "unknown")] += 1
            topic = e.get("topic", "")
            if topic:
                topic_counts[topic] += 1

        result.action_distribution = dict(action_counts)
        result.most_active_instances = sorted(
            instance_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
        result.common_topics = sorted(
            topic_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Coordination frequency: pool events per session
        session_ids = set(e.get("session", "") for e in events)
        result.coordination_frequency = round(
            len(events) / max(len(session_ids), 1), 2
        )

        return result

    # ------------------------------------------------------------------
    # Setup Analysis
    # ------------------------------------------------------------------

    def analyze_setup(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SetupAnalysis:
        """Analyze setup timing and success rates."""
        complete_events = self.store.read_events_list(
            start_date=start_date,
            end_date=end_date,
            event_type="setup_complete",
        )
        phase_events = self.store.read_events_list(
            start_date=start_date,
            end_date=end_date,
            event_type="setup_phase",
        )
        result = SetupAnalysis()

        if not complete_events:
            return result

        result.total_setups = len(complete_events)
        durations = []
        for e in complete_events:
            d = e.get("duration_seconds", 0)
            if d > 0:
                durations.append(d)
            if e.get("status", "success") == "success":
                result.success_count += 1
            else:
                result.failure_count += 1

        result.avg_duration_seconds = round(
            sum(durations) / len(durations), 1
        ) if durations else 0.0
        result.failure_rate = round(
            result.failure_count / result.total_setups * 100, 1
        ) if result.total_setups else 0.0

        # Phase breakdown
        phase_data = defaultdict(lambda: {"count": 0, "success": 0, "fail": 0})
        for e in phase_events:
            name = e.get("phase_name", "unknown")
            phase_data[name]["count"] += 1
            if e.get("success", True):
                phase_data[name]["success"] += 1
            else:
                phase_data[name]["fail"] += 1

        result.phase_breakdown = [
            {"phase": name, **data}
            for name, data in sorted(phase_data.items())
        ]

        return result

    # ------------------------------------------------------------------
    # Coverage Analysis
    # ------------------------------------------------------------------

    def analyze_coverage(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> CoverageAnalysis:
        """Analyze documentation coverage — which files get used."""
        events = self._get_injection_events(start_date, end_date)
        result = CoverageAnalysis()

        # Get all managed files from keywords config
        keywords_config = self._load_all_keywords()
        all_managed = set(keywords_config.keys())
        result.total_managed_files = len(all_managed)

        if not events or not all_managed:
            return result

        # Count activations per file
        activation_counts = defaultdict(int)
        for e in events:
            for f in e.get("hot_file_names", []):
                activation_counts[f] += 1

        activated_files = set(activation_counts.keys())
        result.files_ever_activated = len(activated_files & all_managed)
        result.coverage_pct = round(
            result.files_ever_activated / len(all_managed) * 100, 1
        ) if all_managed else 0.0

        result.never_activated = sorted(all_managed - activated_files)
        result.rarely_activated = sorted(
            [(f, c) for f, c in activation_counts.items()
             if f in all_managed and c <= 2],
            key=lambda x: x[1],
        )
        result.frequently_activated = sorted(
            [(f, c) for f, c in activation_counts.items()
             if f in all_managed and c > 2],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return result

    # ------------------------------------------------------------------
    # Full Analysis
    # ------------------------------------------------------------------

    def full_analysis(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """Run all analyses and return combined results."""
        return {
            "token_savings": self.analyze_token_savings(start_date, end_date).to_dict(),
            "keywords": self.analyze_keywords(start_date, end_date).to_dict(),
            "attention": self.analyze_attention(start_date, end_date).to_dict(),
            "transitions": self.analyze_transitions(start_date, end_date).to_dict(),
            "pool": self.analyze_pool(start_date, end_date).to_dict(),
            "setup": self.analyze_setup(start_date, end_date).to_dict(),
            "sessions": [s.to_dict() for s in self.analyze_sessions(start_date, end_date)],
            "trends": self.analyze_trends(start_date, end_date).to_dict(),
            "coverage": self.analyze_coverage(start_date, end_date).to_dict(),
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI for running analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze claude-cognitive metrics")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--format", choices=["json", "text"], default="text",
        help="Output format"
    )
    parser.add_argument(
        "--analysis", choices=["all", "savings", "keywords", "attention", "transitions",
                               "pool", "setup", "sessions", "trends", "coverage"],
        default="all", help="Which analysis to run"
    )

    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None

    analyzer = MetricsAnalyzer()

    if args.analysis == "all":
        result = analyzer.full_analysis(start, end)
    elif args.analysis == "savings":
        result = analyzer.analyze_token_savings(start, end).to_dict()
    elif args.analysis == "keywords":
        result = analyzer.analyze_keywords(start, end).to_dict()
    elif args.analysis == "attention":
        result = analyzer.analyze_attention(start, end).to_dict()
    elif args.analysis == "sessions":
        result = [s.to_dict() for s in analyzer.analyze_sessions(start, end)]
    elif args.analysis == "trends":
        result = analyzer.analyze_trends(start, end).to_dict()
    elif args.analysis == "transitions":
        result = analyzer.analyze_transitions(start, end).to_dict()
    elif args.analysis == "pool":
        result = analyzer.analyze_pool(start, end).to_dict()
    elif args.analysis == "setup":
        result = analyzer.analyze_setup(start, end).to_dict()
    elif args.analysis == "coverage":
        result = analyzer.analyze_coverage(start, end).to_dict()
    else:
        result = {}

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        _print_text(result, args.analysis)


def _print_text(result: Dict, analysis_type: str):
    """Pretty-print analysis results as text."""
    if analysis_type == "all":
        _print_savings(result.get("token_savings", {}))
        print()
        _print_keywords(result.get("keywords", {}))
        print()
        _print_attention(result.get("attention", {}))
        print()
        _print_transitions(result.get("transitions", {}))
        print()
        _print_pool(result.get("pool", {}))
        print()
        _print_setup(result.get("setup", {}))
        print()
        _print_coverage(result.get("coverage", {}))
    elif analysis_type == "savings":
        _print_savings(result)
    elif analysis_type == "keywords":
        _print_keywords(result)
    elif analysis_type == "attention":
        _print_attention(result)
    elif analysis_type == "transitions":
        _print_transitions(result)
    elif analysis_type == "pool":
        _print_pool(result)
    elif analysis_type == "setup":
        _print_setup(result)
    elif analysis_type == "coverage":
        _print_coverage(result)
    else:
        print(json.dumps(result, indent=2))


def _print_savings(data: Dict):
    print("CONTEXT EFFICIENCY")
    print("=" * 50)
    print(f"  Total turns analyzed:    {data.get('total_turns', 0)}")
    print()
    print("  Per-Turn Context (avg tokens):")
    print(f"    Without cognitive:     {data.get('avg_baseline_per_turn', 0):,} (CLAUDE.md only)")
    print(f"    With cognitive:        {data.get('avg_total_with_cognitive', 0):,} (baseline + targeted)")
    print(f"      Targeted context:    +{data.get('avg_context_added_per_turn', 0):,}")
    print(f"    Dump everything:       {data.get('avg_dump_everything', 0):,} (all docs)")
    print()
    print(f"  Context efficiency:      {data.get('context_efficiency_pct', 0):.1f}% of docs injected per turn")
    print(f"  Turns with activation:   {data.get('turns_with_activation', 0)}")
    print(f"  Turns with zero inject:  {data.get('turns_with_zero_injection', 0)}")


def _print_keywords(data: Dict):
    print("KEYWORD EFFECTIVENESS")
    print("=" * 50)
    print(f"  Unique keywords matched: {data.get('total_unique_keywords_matched', 0)}")
    print(f"  Hit rate:                {data.get('keyword_hit_rate', 0):.1f}%")
    print(f"  Avg keywords/turn:       {data.get('avg_keywords_per_turn', 0):.2f}")
    print(f"  Turns with no match:     {data.get('turns_with_no_match', 0)}")
    top = data.get("top_keywords", [])
    if top:
        print("  Top keywords:")
        for kw, count in top[:10]:
            print(f"    {count:4d}x  {kw}")
    never = data.get("never_matched", [])
    if never:
        print(f"  Never matched ({len(never)}):")
        for kw in never[:10]:
            print(f"    - {kw}")
        if len(never) > 10:
            print(f"    ... and {len(never) - 10} more")


def _print_attention(data: Dict):
    print("ATTENTION DYNAMICS")
    print("=" * 50)
    print(f"  Avg HOT files/turn:      {data.get('avg_hot_files', 0):.2f}")
    print(f"  Avg WARM files/turn:     {data.get('avg_warm_files', 0):.2f}")
    print(f"  Avg COLD files/turn:     {data.get('avg_cold_files', 0):.2f}")
    print(f"  Selectivity ratio:       {data.get('selectivity_ratio', 0):.3f}")
    top = data.get("most_frequently_hot", [])
    if top:
        print("  Most frequently HOT:")
        for f, count in top[:5]:
            print(f"    {count:4d}x  {f}")


def _print_coverage(data: Dict):
    print("COVERAGE ANALYSIS")
    print("=" * 50)
    print(f"  Total managed files:     {data.get('total_managed_files', 0)}")
    print(f"  Files ever activated:    {data.get('files_ever_activated', 0)}")
    print(f"  Coverage:                {data.get('coverage_pct', 0):.1f}%")
    never = data.get("never_activated", [])
    if never:
        print(f"  Never activated ({len(never)}):")
        for f in never[:10]:
            print(f"    - {f}")


def _print_transitions(data: Dict):
    print("ATTENTION TRANSITIONS")
    print("=" * 50)
    print(f"  Total transitions:       {data.get('total_transitions', 0)}")
    print(f"  To HOT:                  {data.get('to_hot_count', 0)}")
    print(f"  To WARM:                 {data.get('to_warm_count', 0)}")
    print(f"  To COLD:                 {data.get('to_cold_count', 0)}")
    print(f"  Avg transitions/turn:    {data.get('avg_transitions_per_turn', 0):.2f}")
    promoted = data.get("most_promoted", [])
    if promoted:
        print("  Most frequently promoted:")
        for f, count in promoted[:5]:
            print(f"    {count:4d}x  {f}")
    volatile = data.get("most_volatile", [])
    if volatile:
        print("  Most volatile:")
        for f, count in volatile[:5]:
            print(f"    {count:4d}x  {f}")


def _print_pool(data: Dict):
    print("POOL COORDINATION")
    print("=" * 50)
    print(f"  Total pool events:       {data.get('total_pool_events', 0)}")
    print(f"  Coordination frequency:  {data.get('coordination_frequency', 0):.2f} events/session")
    actions = data.get("action_distribution", {})
    if actions:
        print("  Action distribution:")
        for action, count in sorted(actions.items()):
            print(f"    {count:4d}x  {action}")
    instances = data.get("most_active_instances", [])
    if instances:
        print("  Most active instances:")
        for inst, count in instances[:5]:
            print(f"    {count:4d}x  {inst}")


def _print_setup(data: Dict):
    print("SETUP ANALYSIS")
    print("=" * 50)
    print(f"  Total setups:            {data.get('total_setups', 0)}")
    print(f"  Avg duration:            {data.get('avg_duration_seconds', 0):.1f}s")
    print(f"  Success:                 {data.get('success_count', 0)}")
    print(f"  Failures:                {data.get('failure_count', 0)}")
    print(f"  Failure rate:            {data.get('failure_rate', 0):.1f}%")
    phases = data.get("phase_breakdown", [])
    if phases:
        print("  Phase breakdown:")
        for p in phases:
            print(f"    {p['phase']}: {p['success']} ok, {p['fail']} fail")


if __name__ == "__main__":
    main()
