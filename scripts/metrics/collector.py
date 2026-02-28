#!/usr/bin/env python3
"""
Metrics Collector - Hook handler for capturing per-turn metrics.

Designed to run as a lightweight hook alongside context-router-v2.py.
Captures injection metrics, keyword effectiveness, and attention dynamics.

Hook integration:
  - UserPromptSubmit (post-router): Captures injection stats
  - Stop: Captures session-level summary
  - SessionStart: Initializes session tracking

Can also be invoked standalone for testing:
  python -m scripts.metrics.collector --test
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

# Ensure metrics package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics.store import MetricsStore

# Attention thresholds — must match context-router-v2.py values
HOT_THRESHOLD = 0.8
WARM_THRESHOLD = 0.25


# ============================================================================
# SESSION STATE
# ============================================================================

# Session-level state file (ephemeral, lives for one session)
# Include session ID in filename to prevent race conditions between concurrent sessions
def _get_session_state_file() -> Path:
    if env_path := os.getenv("COGNITIVE_SESSION_STATE"):
        return Path(env_path)
    session_id = os.getenv("CLAUDE_SESSION_ID", "default")
    return Path.home() / ".claude" / f"cognitive_session_state_{session_id}.json"


def _load_session_state() -> Dict:
    """Load current session state."""
    state_file = _get_session_state_file()
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "session_id": os.getenv("CLAUDE_SESSION_ID", f"s_{int(time.time())}"),
        "instance_id": os.getenv("CLAUDE_INSTANCE", "default"),
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "turn_count": 0,
        "total_tokens_injected": 0,
        "total_tokens_available": 0,
        "total_tokens_saved": 0,
        "keyword_hits": 0,
        "keyword_misses": 0,
        "hot_file_total": 0,
        "warm_file_total": 0,
    }


def _save_session_state(state: Dict) -> None:
    """Persist session state."""
    state_file = _get_session_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


# ============================================================================
# ATTENTION STATE READING
# ============================================================================

def _read_attention_state() -> Optional[Dict]:
    """Read current attention state from context router's state file."""
    paths = [
        Path.cwd() / ".claude" / "attn_state.json",
        Path.home() / ".claude" / "attn_state.json",
    ]
    for path in paths:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
    return None


def _read_keywords_config() -> Optional[Dict]:
    """Read keywords.json for total doc size estimation."""
    paths = [
        Path.cwd() / ".claude" / "keywords.json",
        Path.home() / ".claude" / "keywords.json",
    ]
    for path in paths:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
    return None


def _read_last_transitions() -> Dict:
    """Read the most recent attention transitions from attention_history.jsonl."""
    # Check project-local first, then global
    history_file = Path(".claude/attention_history.jsonl")
    if not history_file.exists():
        history_file = Path.home() / ".claude" / "attention_history.jsonl"
    if not history_file.exists():
        return {"to_hot": [], "to_warm": [], "to_cold": []}

    try:
        # Read only the last 4096 bytes for efficiency
        size = history_file.stat().st_size
        with open(history_file, "rb") as f:
            if size > 4096:
                f.seek(size - 4096)
            raw = f.read().decode("utf-8", errors="ignore")

        # Find the last complete JSON line
        lines = raw.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                return entry.get("transitions", {"to_hot": [], "to_warm": [], "to_cold": []})
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return {"to_hot": [], "to_warm": [], "to_cold": []}


def _read_last_pool_event() -> Optional[Dict]:
    """Read the most recent pool entry from instance_state.jsonl."""
    # Check project-local first, then global
    pool_file = Path(".claude/pool/instance_state.jsonl")
    if not pool_file.exists():
        pool_file = Path.home() / ".claude" / "pool" / "instance_state.jsonl"
    if not pool_file.exists():
        return None

    try:
        size = pool_file.stat().st_size
        with open(pool_file, "rb") as f:
            if size > 4096:
                f.seek(size - 4096)
            raw = f.read().decode("utf-8", errors="ignore")

        lines = raw.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return None


def _estimate_baseline_size() -> int:
    """
    Estimate baseline context size WITHOUT claude-cognitive.
    This is just the CLAUDE.md file that Claude Code loads by default.
    """
    for root in [Path.cwd() / ".claude", Path.home() / ".claude"]:
        claude_md = root / "CLAUDE.md"
        if claude_md.exists():
            try:
                return claude_md.stat().st_size
            except OSError:
                pass
    return 0


def _estimate_total_doc_size() -> int:
    """
    Estimate total size of all managed documentation files.
    This represents what would be injected if EVERYTHING were dumped
    into context (the naive alternative to attention-based routing).
    """
    docs_roots = [
        Path.cwd() / ".claude",
        Path.home() / ".claude",
    ]
    total_chars = 0
    seen = set()

    for root in docs_roots:
        if not root.is_dir():
            continue
        for md_file in root.rglob("*.md"):
            # Skip non-documentation files
            rel = str(md_file.relative_to(root))
            if rel.startswith("cognitive-metrics"):
                continue
            if rel in seen:
                continue
            seen.add(rel)
            try:
                total_chars += md_file.stat().st_size
            except OSError:
                continue

    return total_chars


# ============================================================================
# EVENT COLLECTION
# ============================================================================

def collect_injection_event(
    prompt: str,
    router_output: str,
    attn_state: Optional[Dict] = None,
) -> Dict:
    """
    Build a context_injection event from router output.

    Called after context-router-v2.py runs. Parses the router's
    output to extract metrics.
    """
    if attn_state is None:
        attn_state = _read_attention_state() or {}

    scores = attn_state.get("scores", {})

    # Classify files by tier (thresholds match context-router-v2.py)
    hot_threshold = attn_state.get("hot_threshold", HOT_THRESHOLD)
    warm_threshold = attn_state.get("warm_threshold", WARM_THRESHOLD)
    hot_files = [p for p, s in scores.items() if s >= hot_threshold]
    warm_files = [p for p, s in scores.items() if warm_threshold <= s < hot_threshold]
    cold_files = [p for p, s in scores.items() if s < warm_threshold]

    # Calculate token metrics (approximate: 1 token ~ 4 chars)
    tokens_injected = len(router_output) // 4 if router_output else 0
    total_available = _estimate_total_doc_size() // 4
    baseline_tokens = _estimate_baseline_size() // 4
    tokens_saved = max(0, total_available - tokens_injected)
    # Context added by cognitive beyond the CLAUDE.md baseline
    context_added = max(0, tokens_injected - baseline_tokens)

    # Extract matched keywords from prompt
    keywords_config = _read_keywords_config()
    matched_keywords = []
    if keywords_config:
        prompt_lower = prompt.lower()
        for file_path, kw_list in keywords_config.get("keywords", {}).items():
            for kw in kw_list:
                if kw in prompt_lower:
                    matched_keywords.append(kw)

    # Determine if any files activated
    has_activation = len(hot_files) > 0 or len(warm_files) > 0

    session_state = _load_session_state()
    session_state["turn_count"] += 1
    session_state["total_tokens_injected"] += tokens_injected
    session_state["total_tokens_available"] += total_available
    session_state["total_tokens_saved"] += tokens_saved
    session_state["total_baseline_tokens"] = session_state.get("total_baseline_tokens", 0) + baseline_tokens
    session_state["total_context_added"] = session_state.get("total_context_added", 0) + context_added
    session_state["keyword_hits"] += len(matched_keywords)
    session_state["keyword_misses"] += (1 if not matched_keywords and prompt.strip() else 0)
    session_state["hot_file_total"] += len(hot_files)
    session_state["warm_file_total"] += len(warm_files)
    _save_session_state(session_state)

    # Read attention transitions from history log
    transitions = _read_last_transitions()
    transition_count = sum(len(v) for v in transitions.values()) if transitions else 0

    # Context efficiency: how selective is the router vs dumping everything
    context_efficiency_pct = round(
        tokens_injected / total_available * 100, 1
    ) if total_available > 0 else 0

    event = {
        "event": "context_injection",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": session_state["session_id"],
        "instance": session_state["instance_id"],
        "turn": session_state["turn_count"],
        "tokens_injected": tokens_injected,
        "tokens_available": total_available,
        "baseline_tokens": baseline_tokens,
        "context_added": context_added,
        "tokens_saved": tokens_saved,
        "savings_pct": round(tokens_saved / total_available * 100, 1) if total_available > 0 else 0,
        "context_efficiency_pct": context_efficiency_pct,
        "hot_files": len(hot_files),
        "warm_files": len(warm_files),
        "cold_files": len(cold_files),
        "hot_file_names": hot_files[:10],
        "keywords_matched": matched_keywords[:20],
        "keywords_matched_count": len(matched_keywords),
        "has_activation": has_activation,
        "prompt_length": len(prompt),
        "output_length": len(router_output) if router_output else 0,
        "transitions": transitions,
        "transition_count": transition_count,
    }

    return event


def collect_session_start_event() -> Dict:
    """Build a session_start event."""
    state = _load_session_state()
    return {
        "event": "session_start",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "total_docs": _estimate_total_doc_size() // 4,
    }


def collect_session_end_event() -> Dict:
    """Build a session_end event with session-level summary."""
    state = _load_session_state()
    duration = 0
    if state.get("started_at"):
        try:
            start = datetime.fromisoformat(state["started_at"].rstrip("Z"))
            duration = (datetime.now(timezone.utc) - start).total_seconds()
        except (ValueError, TypeError):
            pass

    turns = state.get("turn_count", 0)

    total_available = max(state.get("total_tokens_available", 1), 1)
    total_baseline = state.get("total_baseline_tokens", 0)
    total_context_added = state.get("total_context_added", 0)

    return {
        "event": "session_end",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "turn_count": turns,
        "duration_seconds": round(duration),
        "total_tokens_injected": state.get("total_tokens_injected", 0),
        "total_tokens_saved": state.get("total_tokens_saved", 0),
        "total_baseline_tokens": total_baseline,
        "total_context_added": total_context_added,
        "avg_tokens_injected": round(state.get("total_tokens_injected", 0) / turns) if turns else 0,
        "avg_tokens_saved": round(state.get("total_tokens_saved", 0) / turns) if turns else 0,
        "avg_baseline_per_turn": round(total_baseline / turns) if turns else 0,
        "avg_context_added_per_turn": round(total_context_added / turns) if turns else 0,
        "avg_savings_pct": round(
            state.get("total_tokens_saved", 0) / total_available * 100, 1
        ),
        "avg_context_efficiency_pct": round(
            state.get("total_tokens_injected", 0) / total_available * 100, 1
        ),
        "keyword_hits": state.get("keyword_hits", 0),
        "keyword_misses": state.get("keyword_misses", 0),
        "keyword_hit_rate": round(
            state.get("keyword_hits", 0) /
            max(state.get("keyword_hits", 0) + state.get("keyword_misses", 0), 1) * 100, 1
        ),
    }


def collect_pool_event() -> Optional[Dict]:
    """Build a pool_event from the most recent pool entry."""
    pool_entry = _read_last_pool_event()
    if not pool_entry:
        return None

    state = _load_session_state()
    return {
        "event": "pool_event",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "source_instance": pool_entry.get("instance", "unknown"),
        "action": pool_entry.get("action", "unknown"),
        "topic": pool_entry.get("topic", ""),
        "affects": pool_entry.get("affects", ""),
        "blocks": pool_entry.get("blocks", ""),
    }


def collect_setup_start_event(mode: str = "init") -> Dict:
    """Build a setup_start event to begin timing setup."""
    state = _load_session_state()
    return {
        "event": "setup_start",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "mode": mode,
    }


def collect_setup_phase_event(
    phase_name: str,
    phase_number: int,
    success: bool,
    details: str = "",
) -> Dict:
    """Build a setup_phase event for per-phase tracking."""
    state = _load_session_state()
    return {
        "event": "setup_phase",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "phase_name": phase_name,
        "phase_number": phase_number,
        "success": success,
        "details": details,
    }


def collect_setup_complete_event(
    mode: str = "init",
    files_created: int = 0,
    keywords_generated: int = 0,
    status: str = "success",
) -> Dict:
    """Build a setup_complete event with total duration."""
    state = _load_session_state()

    # Calculate duration from the most recent setup_start event
    store = MetricsStore()
    duration = 0
    try:
        events = store.read_events_list(event_type="setup_start")
        if events:
            last_start = events[-1]
            start_ts = datetime.fromisoformat(last_start["ts"].rstrip("Z"))
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            duration = round((now - start_ts).total_seconds())
    except Exception:
        pass

    return {
        "event": "setup_complete",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": state["session_id"],
        "instance": state["instance_id"],
        "mode": mode,
        "files_created": files_created,
        "keywords_generated": keywords_generated,
        "status": status,
        "duration_seconds": duration,
    }


# ============================================================================
# HOOK ENTRY POINTS
# ============================================================================

def handle_user_prompt_submit():
    """
    Hook handler for UserPromptSubmit.

    Reads the attention state AFTER context-router-v2.py has run,
    captures metrics, and appends to the event store.

    Designed to run as a second hook in the UserPromptSubmit chain,
    after context-router-v2.py.
    """
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")
    except (json.JSONDecodeError, EOFError):
        return

    if not prompt.strip():
        return

    # Read the attention state that context-router-v2.py just wrote
    attn_state = _read_attention_state()

    # Read the context router's output from its log
    # (The router writes to context_injection.log before us)
    router_output = _read_last_router_output()

    event = collect_injection_event(prompt, router_output, attn_state)

    store = MetricsStore()
    store.append(event)


def handle_session_start():
    """Hook handler for SessionStart. Initializes session tracking."""
    # Reset session state for new session
    state = {
        "session_id": os.getenv("CLAUDE_SESSION_ID", f"s_{int(time.time())}"),
        "instance_id": os.getenv("CLAUDE_INSTANCE", "default"),
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "turn_count": 0,
        "total_tokens_injected": 0,
        "total_tokens_available": 0,
        "total_tokens_saved": 0,
        "keyword_hits": 0,
        "keyword_misses": 0,
        "hot_file_total": 0,
        "warm_file_total": 0,
    }
    _save_session_state(state)

    event = collect_session_start_event()
    store = MetricsStore()
    store.append(event)


def handle_session_end():
    """Hook handler for Stop/SessionEnd. Records session summary."""
    event = collect_session_end_event()
    store = MetricsStore()
    store.append(event)


def _read_last_router_output() -> str:
    """
    Read the most recent router output from the injection log.
    Returns the output string, or empty if unavailable.
    """
    # Check project-local first, then global
    log_file = Path(".claude/context_injection.log")
    if not log_file.exists():
        log_file = Path.home() / ".claude" / "context_injection.log"
    if not log_file.exists():
        return ""

    try:
        # Read only the last 4096 bytes for efficiency
        size = log_file.stat().st_size
        with open(log_file, "rb") as f:
            if size > 4096:
                f.seek(size - 4096)
            raw = f.read().decode("utf-8", errors="ignore")

        # Find the last complete entry (between === markers)
        entries = raw.split("=" * 80)
        for entry in reversed(entries):
            entry = entry.strip()
            if entry and "Turn" in entry:
                return entry
        return ""
    except Exception:
        return ""


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    """CLI dispatcher based on hook event or direct invocation."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "--test":
            _run_test()
        elif command == "session-start":
            handle_session_start()
        elif command == "session-end":
            handle_session_end()
        elif command == "prompt":
            handle_user_prompt_submit()
        elif command == "setup-start":
            mode = sys.argv[2] if len(sys.argv) > 2 else "init"
            event = collect_setup_start_event(mode)
            MetricsStore().append(event)
        elif command == "setup-phase":
            # Parse --phase, --number, --success flags
            phase = "unknown"
            number = 0
            success = True
            details = ""
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--phase" and i + 1 < len(sys.argv):
                    phase = sys.argv[i + 1]; i += 2
                elif sys.argv[i] == "--number" and i + 1 < len(sys.argv):
                    number = int(sys.argv[i + 1]); i += 2
                elif sys.argv[i] == "--success" and i + 1 < len(sys.argv):
                    success = sys.argv[i + 1].lower() == "true"; i += 2
                elif sys.argv[i] == "--details" and i + 1 < len(sys.argv):
                    details = sys.argv[i + 1]; i += 2
                else:
                    i += 1
            event = collect_setup_phase_event(phase, number, success, details)
            MetricsStore().append(event)
        elif command == "setup-complete":
            mode = "init"
            status = "success"
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--mode" and i + 1 < len(sys.argv):
                    mode = sys.argv[i + 1]; i += 2
                elif sys.argv[i] == "--status" and i + 1 < len(sys.argv):
                    status = sys.argv[i + 1]; i += 2
                else:
                    i += 1
            event = collect_setup_complete_event(mode=mode, status=status)
            MetricsStore().append(event)
        elif command == "pool-event":
            event = collect_pool_event()
            if event:
                MetricsStore().append(event)
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            print("Usage: collector.py [--test|session-start|session-end|prompt|"
                  "setup-start|setup-phase|setup-complete|pool-event]",
                  file=sys.stderr)
            sys.exit(1)
    else:
        # Default: treat as UserPromptSubmit hook
        handle_user_prompt_submit()


def _run_test():
    """Run a self-test with synthetic data."""
    print("Testing metrics collector...")

    store = MetricsStore()

    # Test session start
    event = collect_session_start_event()
    store.append(event)
    print(f"  session_start event: {json.dumps(event, indent=2)}")

    # Test injection event (includes transitions)
    event = collect_injection_event(
        prompt="How does the API authentication work?",
        router_output="[Test output - 500 chars of context]" * 10,
    )
    store.append(event)
    print(f"  context_injection event: tokens_injected={event['tokens_injected']}, "
          f"baseline={event['baseline_tokens']}, "
          f"context_added={event['context_added']}, "
          f"efficiency={event['context_efficiency_pct']}%, "
          f"transitions={event['transition_count']}")

    # Test setup timing events
    setup_start = collect_setup_start_event("init")
    store.append(setup_start)
    print(f"  setup_start event: mode={setup_start['mode']}")

    setup_phase = collect_setup_phase_event("environment_check", 1, True, "Python 3.11 found")
    store.append(setup_phase)
    print(f"  setup_phase event: {setup_phase['phase_name']} (phase {setup_phase['phase_number']})")

    setup_complete = collect_setup_complete_event("init", files_created=5, keywords_generated=25)
    store.append(setup_complete)
    print(f"  setup_complete event: duration={setup_complete['duration_seconds']}s, "
          f"files={setup_complete['files_created']}, keywords={setup_complete['keywords_generated']}")

    # Test pool event (may return None if no pool data)
    pool_event = collect_pool_event()
    if pool_event:
        store.append(pool_event)
        print(f"  pool_event: action={pool_event['action']}, source={pool_event['source_instance']}")
    else:
        print("  pool_event: skipped (no pool data available)")

    # Test session end
    event = collect_session_end_event()
    store.append(event)
    print(f"  session_end event: turns={event['turn_count']}, "
          f"duration={event['duration_seconds']}s")

    # Verify storage
    events = store.read_events_list()
    print(f"\n  Total events stored today: {len(events)}")
    print("  Test passed!")


if __name__ == "__main__":
    main()
