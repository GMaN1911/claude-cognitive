#!/usr/bin/env python3
"""
Metrics Store - JSONL-based event storage with daily rotation.

Stores metrics events in append-only JSONL files organized by date.
Generates daily aggregate summaries for efficient querying.

Storage layout:
    .claude/cognitive-metrics/
    ├── events/
    │   └── YYYY-MM-DD.jsonl          # Raw events (one per line)
    ├── summaries/
    │   └── YYYY-MM-DD.json           # Daily aggregated summaries
    └── reports/
        └── *.md                      # Generated analysis reports
"""

import json
import os
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Iterator

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


# ============================================================================
# STORAGE LOCATION RESOLUTION
# ============================================================================

def resolve_metrics_root() -> Path:
    """
    Resolve metrics storage root directory.

    Priority:
    1. COGNITIVE_METRICS_ROOT environment variable
    2. Project-local .claude/cognitive-metrics/
    3. Global ~/.claude/cognitive-metrics/
    """
    if env_root := os.getenv("COGNITIVE_METRICS_ROOT"):
        return Path(env_root).expanduser().resolve()

    project_local = Path.cwd() / ".claude" / "cognitive-metrics"
    if (Path.cwd() / ".claude").is_dir():
        return project_local

    return Path.home() / ".claude" / "cognitive-metrics"


# ============================================================================
# EVENT STORE
# ============================================================================

class MetricsStore:
    """Append-only JSONL event store with daily file rotation."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or resolve_metrics_root()
        self.events_dir = self.root / "events"
        self.summaries_dir = self.root / "summaries"
        self.reports_dir = self.root / "reports"

        # Ensure directories exist
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _event_file(self, day: date) -> Path:
        """Get the event file path for a given date."""
        return self.events_dir / f"{day.isoformat()}.jsonl"

    def _summary_file(self, day: date) -> Path:
        """Get the summary file path for a given date."""
        return self.summaries_dir / f"{day.isoformat()}.json"

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def append(self, event: Dict) -> None:
        """
        Append a single event to today's event file.

        Adds a timestamp if not already present. Uses file locking
        for safe concurrent writes from multiple hook processes.
        """
        if "ts" not in event:
            event["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        today = date.today()
        event_file = self._event_file(today)

        line = json.dumps(event, separators=(",", ":")) + "\n"

        with open(event_file, "a") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)

    def append_batch(self, events: List[Dict]) -> None:
        """Append multiple events atomically."""
        if not events:
            return

        today = date.today()
        event_file = self._event_file(today)

        lines = []
        for event in events:
            if "ts" not in event:
                event["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            lines.append(json.dumps(event, separators=(",", ":")) + "\n")

        with open(event_file, "a") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.writelines(lines)
            finally:
                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Iterator[Dict]:
        """
        Read events within a date range, optionally filtered.

        Args:
            start_date: Inclusive start (default: today)
            end_date: Inclusive end (default: today)
            event_type: Filter by event type (e.g., "context_injection")
            session_id: Filter by session ID
        """
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = date.today()

        current = start_date
        while current <= end_date:
            event_file = self._event_file(current)
            if event_file.exists():
                with open(event_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            if event_type and event.get("event") != event_type:
                                continue
                            if session_id and event.get("session") != session_id:
                                continue
                            yield event
                        except json.JSONDecodeError:
                            continue
            current += timedelta(days=1)

    def read_events_list(self, **kwargs) -> List[Dict]:
        """Read events as a list (convenience wrapper)."""
        return list(self.read_events(**kwargs))

    def count_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Count events in a date range."""
        count = 0
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = date.today()

        current = start_date
        while current <= end_date:
            event_file = self._event_file(current)
            if event_file.exists():
                with open(event_file) as f:
                    count += sum(1 for line in f if line.strip())
            current += timedelta(days=1)
        return count

    def available_dates(self) -> List[date]:
        """List all dates that have event data."""
        dates = []
        for f in sorted(self.events_dir.glob("*.jsonl")):
            try:
                d = date.fromisoformat(f.stem)
                dates.append(d)
            except ValueError:
                continue
        return dates

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def save_summary(self, day: date, summary: Dict) -> None:
        """Save a daily aggregate summary."""
        summary["date"] = day.isoformat()
        summary["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._summary_file(day).write_text(
            json.dumps(summary, indent=2)
        )

    def load_summary(self, day: date) -> Optional[Dict]:
        """Load a daily summary, if it exists."""
        summary_file = self._summary_file(day)
        if summary_file.exists():
            try:
                return json.loads(summary_file.read_text())
            except json.JSONDecodeError:
                return None
        return None

    def load_summaries(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """Load all summaries in a date range."""
        summaries = []
        current = start_date
        while current <= end_date:
            s = self.load_summary(current)
            if s:
                summaries.append(s)
            current += timedelta(days=1)
        return summaries

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def save_report(self, name: str, content: str) -> Path:
        """Save a markdown report. Returns the file path."""
        name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        report_path = self.reports_dir / f"{name}.md"
        report_path.write_text(content)
        return report_path

    def list_reports(self) -> List[Path]:
        """List all saved reports."""
        return sorted(self.reports_dir.glob("*.md"))

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def rotate(self, max_days: int = 90) -> int:
        """
        Remove event files older than max_days.
        Summaries are kept indefinitely (they're small).
        Returns count of removed files.
        """
        cutoff = date.today() - timedelta(days=max_days)
        removed = 0
        for f in self.events_dir.glob("*.jsonl"):
            try:
                file_date = date.fromisoformat(f.stem)
                if file_date < cutoff:
                    f.unlink()
                    removed += 1
            except ValueError:
                continue
        return removed

    def disk_usage(self) -> Dict[str, int]:
        """Report disk usage in bytes by directory."""
        usage = {}
        for name, directory in [
            ("events", self.events_dir),
            ("summaries", self.summaries_dir),
            ("reports", self.reports_dir),
        ]:
            total = sum(
                f.stat().st_size for f in directory.rglob("*") if f.is_file()
            )
            usage[name] = total
        usage["total"] = sum(usage.values())
        return usage
