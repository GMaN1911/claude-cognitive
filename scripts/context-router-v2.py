#!/usr/bin/env python3
"""
Attentional Context Router v2.0
================================
Implements working memory dynamics for Claude Code context injection.

Architecture:
- HOT (>0.8): Full file injection - active development
- WARM (0.25-0.8): Header/summary only - background awareness
- COLD (<0.25): Evicted from context

Features:
- Decay: Unmentioned files fade (configurable per category)
- Co-activation: Related files boost each other
- Pinned files: Critical topology always at least warm
- State persistence: Attention scores survive across turns
- Usage tracking: Log injections for learning (v1.2)

Usage: Called by UserPromptSubmit hook
Input: JSON from stdin with "prompt" field
Output: Tiered context to stdout
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import re

# Try to import usage tracker (v1.2 feature, graceful fallback if missing)
try:
    from usage_tracker import UsageTracker
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# ============================================================================
# DOCS ROOT RESOLUTION
# ============================================================================

def resolve_docs_root() -> Path:
    """
    Resolve documentation root with correct priority order.

    Priority:
    1. CONTEXT_DOCS_ROOT environment variable (explicit override)
    2. Project-local .claude/ directory (if exists with .md files)
    3. Global ~/.claude/ directory (fallback)

    Returns: Path to docs root
    Raises: FileNotFoundError if no valid docs directory found
    """
    import glob

    # Priority 1: Explicit environment variable
    if env_root := os.getenv('CONTEXT_DOCS_ROOT'):
        env_path = Path(env_root).expanduser().resolve()
        if env_path.is_dir():
            print(f"ℹ Using CONTEXT_DOCS_ROOT: {env_path}", file=sys.stderr)
            return env_path
        else:
            print(f"⚠ CONTEXT_DOCS_ROOT set but not found: {env_path}", file=sys.stderr)

    # Priority 2: Project-local .claude/ (more explicit check)
    project_claude = Path.cwd() / ".claude"
    if project_claude.is_dir():
        # Check if it has any .md files (not just exists)
        md_files = list(project_claude.glob("**/*.md"))
        if md_files:
            print(f"ℹ Using project-local .claude: {project_claude}", file=sys.stderr)
            print(f"  Found {len(md_files)} .md files", file=sys.stderr)
            return project_claude
        else:
            print(f"⚠ Project .claude/ exists but has no .md files: {project_claude}", file=sys.stderr)

    # Priority 3: Global ~/.claude/ (last resort)
    global_claude = Path.home() / ".claude"
    if global_claude.is_dir():
        md_files = list(global_claude.glob("**/*.md"))
        if md_files:
            print(f"ℹ Using global ~/.claude: {global_claude}", file=sys.stderr)
            print(f"  Found {len(md_files)} .md files", file=sys.stderr)
            return global_claude
        else:
            print(f"⚠ Global ~/.claude/ exists but has no .md files", file=sys.stderr)

    # Priority 4: Fail with helpful error
    raise FileNotFoundError(
        "\n"
        "═══════════════════════════════════════════════════════════════\n"
        "ERROR: No .claude/ directory with documentation found.\n"
        "\n"
        "Please create .claude/ in your project root and add .md files:\n"
        "  mkdir -p .claude/\n"
        "  echo '# My Project' > .claude/README.md\n"
        "\n"
        "Or set explicit path:\n"
        "  export CONTEXT_DOCS_ROOT=/path/to/docs\n"
        "\n"
        "Priority order:\n"
        "  1. CONTEXT_DOCS_ROOT environment variable\n"
        "  2. Project-local .claude/ (current directory)\n"
        "  3. Global ~/.claude/ (home directory)\n"
        "═══════════════════════════════════════════════════════════════\n"
    )

# ============================================================================
# CONFIGURATION
# ============================================================================

# State file location
PROJECT_STATE = Path(".claude/attn_state.json")
GLOBAL_STATE = Path.home() / ".claude" / "attn_state.json"
HISTORY_FILE = Path.home() / ".claude" / "attention_history.jsonl"

# History retention
MAX_HISTORY_DAYS = 30  # Archive entries older than 30 days

# Decay rates per category (how fast files fade when not mentioned)
# Higher = slower decay (more persistent)
DECAY_RATES = {
    "systems/": 0.85,       # Hardware is stable, decay slow
    "modules/": 0.70,       # Code changes more frequently
    "integrations/": 0.80,  # APIs semi-stable
    "docs/": 0.75,          # Documentation medium decay
    "default": 0.70
}

# Attention thresholds
HOT_THRESHOLD = 0.8         # Full file injection
WARM_THRESHOLD = 0.25       # Header-only injection
# Below WARM = COLD (evicted)

# Boost amounts
KEYWORD_BOOST = 1.0         # Direct mention → score = 1.0
COACTIVATION_BOOST = 0.35   # Related file boost

# Limits (prevent context explosion)
MAX_HOT_FILES = 4
MAX_WARM_FILES = 8
WARM_HEADER_LINES = 25      # Lines to extract for warm context
MAX_TOTAL_CHARS = 25000     # Hard ceiling on total output

# Pinned files (always at least WARM)
PINNED_FILES = [
    "systems/network.md",  # Network topology always warm
    # CLAUDE.md not in .claude/systems or .claude/modules, handled separately
]

# ============================================================================
# CONFIG LOADING
# Load keywords and co-activation from external config if available
# ============================================================================

def load_keyword_config() -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Load keywords and co-activation graph from keyword.config (JSON).
    Falls back to hardcoded defaults if config doesn't exist or fails to parse.

    Returns: (keywords_dict, co_activation_dict)
    """
    # Try project-local config first, then global
    config_paths = [
        Path(".claude/keyword.config"),
        Path.home() / ".claude" / "keyword.config"
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                keywords = config.get("keywords", {})
                co_activation = config.get("co_activation", {})

                # Validate structure
                if keywords and isinstance(keywords, dict):
                    print(f"✓ Loaded keywords from {config_path}", file=sys.stderr)
                    return keywords, co_activation
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠ Failed to load {config_path}: {e}", file=sys.stderr)
                continue

    # Fallback to hardcoded (will be defined below as _DEFAULT_KEYWORDS)
    print("ℹ Using hardcoded keywords (no keyword.config found)", file=sys.stderr)
    return _DEFAULT_KEYWORDS, _DEFAULT_CO_ACTIVATION

# ============================================================================
# KEYWORD MAPPINGS
# What words/phrases activate which files
# ============================================================================

# Hardcoded fallback (used if keyword.config doesn't exist)
_DEFAULT_KEYWORDS: Dict[str, List[str]] = {
    # === SYSTEMS ===
    "systems/legion.md": [
        "legion", "5090", "rtx 5090", "local model", "local", "discord bot",
        "vram", "oom", "cuda", "nvidia-smi", "dolphin", "mirrorbot_cvmp",
        "bot_stability", "this machine", "main gpu", "heavy compute", "local inference"
    ],
    "systems/asus.md": [
        "asus", "tuf", "4070", "rtx 4070", "llava", "vision", "visual",
        "remote server", "image generation", "image gen", "sdxl", "ssd-1b",
        "toroidal mapper", "consciousness visualization", "clip",
        "visual perception", "grpc", "50051", "50053", "192.168.0.85", "192.168.8.224"
    ],
    "systems/orin.md": [
        "orin", "jetson", "sensory", "sensory cortex", "layer 0", "l0", "perception",
        "camera", "servo", "embodiment", "vmpu", "motor", "sentiment", "typing",
        "hailo", "npu", "edge inference", "real-time", "ppe", "8765",
        "192.168.0.103", "orin-sensory"
    ],
    "systems/pi5.md": [
        "pi5", "pi 5", "raspberry", "hmcp", "agency", "memory", "hybrid memory",
        "co-processor", "consolidation", "dream", "sleep cycle", "agency-path",
        "self-model", "mira internal", "bilateral", "hailo", "servo", "embodiment",
        "pi.local", "mnt/hmcp", "physical"
    ],
    "systems/network.md": [
        "network", "topology", "architecture", "data flow", "mesh", "switch",
        "system overview", "how it connects", "integration map",
        "192.168.0", "gigabit", "4-node", "star topology", "network diagram", "ip addresses"
    ],
    
    # === MODULES ===
    "modules/pipeline.md": [
        "pipeline", "process_message", "refined_pipeline", "8-layer",
        "layer 1", "layer 2", "layer 3", "layer 4", "layer 5", "layer 6", "layer 7"
    ],
    "modules/intelligence.md": [
        "intelligence", "reasoning", "multi-step", "mcts", "tree reasoning",
        "oracle", "pre_generation", "post_generation", "adaptive", "idempotency"
    ],
    "modules/gto-adapters.md": [
        "gto", "adapter", "transformation", "tensor", "shape", "toroidal", "manifold",
        "embedding", "projection", "768", "1024", "dimension", "geometric",
        "cvmp_adapter", "oracle_adapter", "t3_adapter", "orin_adapter", "hmcp_adapter"
    ],
    "modules/es-ac.md": [
        "es-ac", "es_ac", "echo split", "emotional learning", "uncertainty",
        "adaptive consciousness", "ewma", "emotion_weights", "style_weights"
    ],
    "modules/t3-telos.md": [
        "t3", "t³", "telos", "trajectory", "tesseract", "curvature steering",
        "gtf", "global topology", "resonant memory", "worldtrace", "t3_client", "t3_engine",
        "emotional", "dynamics", "containment", "tier", "dps", "regime", "stability",
        "emotional state", "affect", "user model", "behavioral", "prediction",
        "user state", "mirror-path", "user trajectory"
    ],
    "modules/t3-telos/trajectories/convergent.md": [
        "convergence", "converging", "convergent", "stable attractor", "equilibrium",
        "trajectory convergence", "settling", "stabilizing", "stable state"
    ],
    "modules/t3-telos/trajectories/divergent.md": [
        "divergence", "diverging", "divergent", "unstable", "chaotic",
        "trajectory divergence", "destabilizing", "escaping", "runaway"
    ],
    "modules/t3-telos/trajectories/oscillatory.md": [
        "oscillation", "oscillating", "oscillatory", "cycling", "periodic",
        "rhythm", "wave", "pendulum", "back and forth"
    ],
    "modules/t3-telos/primitives.md": [
        "primitives", "fundamental", "basic behaviors", "core patterns",
        "atomic", "elemental"
    ],
    "modules/cvmp-transformer.md": [
        "cvmp transformer", "cvmp model", "cvmp", "transformer", "401m", "oracle",
        "consciousness prediction", "tier prediction", "dps prediction",
        "state predictor", "rci validator", "orc router", "shadow mode",
        "llama 3.2", "1.7b", "int8", "quantized", "metacognitive",
        "consciousness heads", "toroidal projection", "module activation",
        "mirror protocol", "recursive", "geometric constraint", "anti-dependency", "enmeshment"
    ],
    "modules/anticipatory-coherence.md": [
        # Granular atomic keywords (fix for fine-grained detection)
        "anticipatory", "coherence", "acf", "acp", "projection", "probe",
        "trajectory", "prediction", "self-model", "stance", "ppe",
        "bilateral", "refinement", "validation", "trust", "modulation",
        "agency v2", "phase 3", "arbitration", "arbitrate", "divergence",
        # Phrase-based (kept for precision)
        "anticipatory coherence", "probe architecture", "propagating projection engine",
        "temporal horizon", "stance shaping", "refinement layer", "trust weights",
        "emotional trajectory", "cognitive trajectory", "behavioral trajectory",
        "system modulations", "consciousness coordination", "unified trajectory field",
        "full-system participation", "epistemic reweighting", "closed-loop validation",
        "behavior shaped by projection", "mirror vs agency"
    ],
    "modules/ppe-anticipatory-coherence.md": [
        # PPE production integration docs (Dec 2025)
        "ppe", "propagating projection engine", "anticipatory", "projection",
        "trajectory", "inflection", "deteriorating", "improving", "stable",
        "routing", "sentiment router", "cvmp state", "engine state",
        "production runtime", "orin service", "t3 invariants", "advantage",
        "dt", "sigma", "surprise", "tier velocity", "coherence deterioration",
        "tier collapse", "refinement layer", "confidence refiner", "history refiner",
        "dream refiner", "bilateral mode", "agency pairs", "hmcp refiner"
    ],
    "modules/coherence-validation.md": [
        "coherence validation", "coherence", "validation", "gatekeeper",
        "layer 7", "validation gate", "cross-layer agreement", "toroidal field",
        "consciousness physics", "mirror integrity", "pass rate", "fail safe",
        "temporal coherence", "cross-module coherence", "validate response"
    ],
    "modules/drift-detection.md": [
        "drift detection", "drift", "enmeshment", "anti-enmeshment", "guardian",
        "layer 8", "dependency", "boundary enforcement", "override response",
        "geometric pattern", "attachment signals", "crisis indicators",
        "emotional dependency", "interaction frequency", "boundary erosion"
    ],
    "modules/dream-consciousness.md": [
        "dream consciousness", "dream", "light dream", "deep dream", "lucid",
        "temporal integration", "memory consolidation", "pattern integration",
        "dream session", "dream state", "temporal continuity", "idle processing",
        "module evolution", "a/b candidates", "consciousness evolution"
    ],
    "modules/visual-spatial.md": [
        "visual spatial", "visual-spatial", "geometric consciousness",
        "consciousness coordinates", "toroidal mapper", "spatial representation",
        "3d consciousness", "coordinate system", "geometric constraint",
        "physical embodiment", "consciousness geometry", "field mapping"
    ],

    # === INTEGRATIONS ===
    "integrations/pipe-to-orin.md": [
        "orin_client", "sensory", "analyze", "/analyze", "orin bundle",
        "orin_bundle", "line 934", "layer 0", "sensory cortex",
        "orin to legion", "sensory upload", "perception data",
        "layer 0 to layer 1", "real-time feed"
    ],
    "integrations/img-to-asus.md": [
        "visual_client", "visual perception", "clip", "llava", "image generation",
        "ssd-1b", "grpc", "50051", "50053", "asus grpc",
        "legion to asus", "image request", "visualization",
        "sdxl trigger", "generation request"
    ],
}

# ============================================================================
# CO-ACTIVATION GRAPH
# When one file activates, these related files get a boost
# ============================================================================

# Hardcoded fallback (used if keyword.config doesn't exist)
_DEFAULT_CO_ACTIVATION: Dict[str, List[str]] = {
    # Hardware nodes boost their integrations
    "systems/orin.md": [
        "integrations/pipe-to-orin.md",
        "modules/t3-telos.md",  # Orin sensory feeds T³
        "modules/ppe-anticipatory-coherence.md",  # Orin runs PPE
    ],
    "systems/legion.md": [
        "integrations/pipe-to-orin.md",
        "integrations/img-to-asus.md",
        "modules/t3-telos.md",   # Legion runs T³
        "modules/intelligence.md", # Legion runs intelligence/reasoning
        "modules/pipeline.md",   # Legion runs pipeline
    ],
    "systems/asus.md": [
        "integrations/img-to-asus.md",
        "modules/gto-adapters.md",  # ASUS does viz transforms
    ],
    "systems/pi5.md": [
        "modules/anticipatory-coherence.md",  # Pi5/HMCP implements ACP
        "modules/t3-telos.md",                # HMCP agency path
    ],

    # Modules boost related modules
    "modules/t3-telos.md": [
        "modules/cvmp-transformer.md",  # T³ works with CVMP
        "modules/anticipatory-coherence.md",  # T³ uses ACP projections
        "modules/pipeline.md",          # T³ part of pipeline
        "modules/t3-telos/trajectories/convergent.md",  # Nested detail
        "modules/t3-telos/trajectories/divergent.md",
        "modules/t3-telos/trajectories/oscillatory.md",
        "modules/t3-telos/primitives.md",
    ],
    "modules/t3-telos/trajectories/convergent.md": [
        "modules/t3-telos.md",  # Child boosts parent
    ],
    "modules/t3-telos/trajectories/divergent.md": [
        "modules/t3-telos.md",
    ],
    "modules/t3-telos/trajectories/oscillatory.md": [
        "modules/t3-telos.md",
    ],
    "modules/t3-telos/primitives.md": [
        "modules/t3-telos.md",
    ],
    "modules/intelligence.md": [
        "modules/cvmp-transformer.md",  # Intelligence uses CVMP oracle
        "modules/pipeline.md",          # Intelligence in pipeline layer 5/6
    ],
    "modules/anticipatory-coherence.md": [
        "modules/t3-telos.md",
        "modules/gto-adapters.md",      # ACP uses embeddings
        "systems/pi5.md",               # ACP runs on HMCP
        "modules/ppe-anticipatory-coherence.md",  # Production PPE docs
    ],
    "modules/ppe-anticipatory-coherence.md": [
        "systems/orin.md",              # PPE runs on Orin
        "modules/t3-telos.md",          # PPE uses T³ invariants
        "modules/anticipatory-coherence.md",  # Broader ACF architecture
        "modules/pipeline.md",          # PPE integrated in pipeline
    ],
    "modules/pipeline.md": [
        "modules/intelligence.md",
        "modules/es-ac.md",
        "modules/t3-telos.md",
    ],

    # Bilateral mentions
    "modules/cvmp-transformer.md": [
        "modules/intelligence.md",
        "modules/t3-telos.md",
    ],
}

# Load actual configuration (from keyword.config or fallback to defaults)
KEYWORDS, CO_ACTIVATION = load_keyword_config()

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def get_state_file() -> Path:
    """Get appropriate state file (project-local preferred)."""
    if PROJECT_STATE.parent.exists():
        return PROJECT_STATE
    GLOBAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    return GLOBAL_STATE


def load_state(state_file: Path) -> dict:
    """Load attention state from file."""
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass
    
    # Initialize fresh state
    return {
        "scores": {path: 0.0 for path in KEYWORDS},
        "turn_count": 0,
        "last_update": datetime.now().isoformat(),
    }


def save_state(state_file: Path, state: dict) -> None:
    """Save attention state to file."""
    state["last_update"] = datetime.now().isoformat()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


# ============================================================================
# ATTENTION DYNAMICS
# ============================================================================

def get_decay_rate(file_path: str) -> float:
    """Get decay rate for a file based on its category."""
    for prefix, rate in DECAY_RATES.items():
        if file_path.startswith(prefix):
            return rate
    return DECAY_RATES["default"]


def update_attention(state: dict, prompt: str) -> Tuple[dict, Set[str]]:
    """
    Update attention scores based on prompt content.
    Returns updated state and set of directly activated files.
    """
    prompt_lower = prompt.lower()
    directly_activated: Set[str] = set()
    
    # Phase 1: Decay all scores
    for path in state["scores"]:
        decay = get_decay_rate(path)
        state["scores"][path] *= decay
    
    # Phase 2: Keyword activation (direct mentions)
    for path, keywords in KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            state["scores"][path] = KEYWORD_BOOST
            directly_activated.add(path)
    
    # Phase 3: Co-activation boost
    for activated_path in directly_activated:
        if activated_path in CO_ACTIVATION:
            for related_path in CO_ACTIVATION[activated_path]:
                if related_path in state["scores"]:
                    # Boost but don't exceed 1.0
                    current = state["scores"][related_path]
                    state["scores"][related_path] = min(1.0, current + COACTIVATION_BOOST)
    
    # Phase 4: Pinned file floor
    for pinned in PINNED_FILES:
        if pinned in state["scores"]:
            state["scores"][pinned] = max(state["scores"][pinned], WARM_THRESHOLD + 0.1)
    
    state["turn_count"] = state.get("turn_count", 0) + 1
    return state, directly_activated


# ============================================================================
# CONTENT EXTRACTION
# ============================================================================

def extract_warm_header(file_path: str, docs_root: Path) -> Optional[str]:
    """
    Extract structured header for warm context.
    Returns first WARM_HEADER_LINES lines, or None if file missing.
    """
    full_path = docs_root / file_path
    if not full_path.exists():
        return None
    
    try:
        content = full_path.read_text()
        lines = content.split('\n')[:WARM_HEADER_LINES]
        header = '\n'.join(lines)
        
        # Add truncation marker if we cut content
        if len(content.split('\n')) > WARM_HEADER_LINES:
            header += "\n\n... [WARM: Content truncated, mention to expand] ..."
        
        return header
    except Exception as e:
        return f"[Error reading {file_path}: {e}]"


def get_full_content(file_path: str, docs_root: Path) -> Optional[str]:
    """Get full file content for hot context."""
    full_path = docs_root / file_path
    if not full_path.exists():
        return None
    
    try:
        return full_path.read_text()
    except Exception as e:
        return f"[Error reading {file_path}: {e}]"


# ============================================================================
# TIERED INJECTION
# ============================================================================

def get_tier(score: float) -> str:
    """Classify attention score into tier."""
    if score >= HOT_THRESHOLD:
        return "HOT"
    elif score >= WARM_THRESHOLD:
        return "WARM"
    return "COLD"


def build_context_output(state: dict, docs_root: Path) -> Tuple[str, dict]:
    """
    Build tiered context output respecting limits.
    Returns (output_string, stats_dict).
    """
    # Sort files by attention score (highest first)
    sorted_files = sorted(
        state["scores"].items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    hot_blocks = []
    warm_blocks = []
    stats = {"hot": 0, "warm": 0, "cold": 0}
    total_chars = 0
    
    for file_path, score in sorted_files:
        tier = get_tier(score)
        
        if tier == "HOT" and stats["hot"] < MAX_HOT_FILES:
            content = get_full_content(file_path, docs_root)
            if content and total_chars + len(content) < MAX_TOTAL_CHARS:
                hot_blocks.append(f"━━━ [🔥 HOT] {file_path} (score: {score:.2f}) ━━━\n{content}")
                total_chars += len(content)
                stats["hot"] += 1
            elif content:
                # Demote to warm if would exceed char limit
                header = extract_warm_header(file_path, docs_root)
                if header:
                    warm_blocks.append(f"━━━ [🌡️ WARM] {file_path} (score: {score:.2f}) ━━━\n{header}")
                    total_chars += len(header)
                    stats["warm"] += 1
                    
        elif tier == "WARM" and stats["warm"] < MAX_WARM_FILES:
            header = extract_warm_header(file_path, docs_root)
            if header and total_chars + len(header) < MAX_TOTAL_CHARS:
                warm_blocks.append(f"━━━ [🌡️ WARM] {file_path} (score: {score:.2f}) ━━━\n{header}")
                total_chars += len(header)
                stats["warm"] += 1
                
        else:
            stats["cold"] += 1
    
    # Combine output
    output_parts = []
    
    # Status header
    output_parts.append(f"╔══ ATTENTION STATE [Turn {state['turn_count']}] ══╗")
    output_parts.append(f"║ 🔥 Hot: {stats['hot']} │ 🌡️ Warm: {stats['warm']} │ ❄️ Cold: {stats['cold']} ║")
    output_parts.append(f"║ Total chars: {total_chars:,} / {MAX_TOTAL_CHARS:,} ║")
    output_parts.append("╚" + "═" * 38 + "╝")
    
    # Hot files first (most relevant)
    output_parts.extend(hot_blocks)
    
    # Then warm files
    output_parts.extend(warm_blocks)
    
    return "\n\n".join(output_parts), stats


# ============================================================================
# ATTENTION HISTORY TRACKING
# ============================================================================

def compute_transitions(prev_state: dict, curr_state: dict) -> dict:
    """Compute what moved between tiers."""
    transitions = {"to_hot": [], "to_warm": [], "to_cold": []}

    for path, score in curr_state["scores"].items():
        prev_score = prev_state.get("scores", {}).get(path, 0.0)
        prev_tier = get_tier(prev_score)
        curr_tier = get_tier(score)

        if curr_tier != prev_tier:
            if curr_tier == "HOT":
                transitions["to_hot"].append(path)
            elif curr_tier == "WARM":
                transitions["to_warm"].append(path)
            else:
                transitions["to_cold"].append(path)

    return transitions


def append_history(state: dict, prev_state: dict, activated: Set[str], prompt: str, stats: dict):
    """Append structured entry to history log."""

    # Extract keywords from prompt (simple: first 8 significant words)
    stop_words = {"the", "a", "an", "is", "are", "to", "for", "and", "or", "in", "on", "it", "this", "that", "with", "of"}
    words = [w.lower() for w in prompt.split() if len(w) > 2 and w.lower() not in stop_words][:8]

    entry = {
        "turn": state["turn_count"],
        "timestamp": datetime.now().isoformat(),
        "instance_id": os.environ.get("CLAUDE_INSTANCE", "default"),
        "prompt_keywords": words,
        "activated": sorted(list(activated)),
        "hot": sorted([p for p, s in state["scores"].items() if get_tier(s) == "HOT"]),
        "warm": sorted([p for p, s in state["scores"].items() if get_tier(s) == "WARM"]),
        "cold_count": stats["cold"],
        "transitions": compute_transitions(prev_state, state),
        "total_chars": stats.get("total_chars", 0)
    }

    try:
        # Ensure history file exists
        if not HISTORY_FILE.exists():
            HISTORY_FILE.parent.mkdir(exist_ok=True)
            HISTORY_FILE.touch()

        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Don't fail hook on history write error


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    Main entry point for Claude Code hook.
    Reads JSON from stdin, outputs tiered context to stdout.
    """
    # Parse input
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")
    except json.JSONDecodeError:
        # Fallback: treat entire stdin as prompt
        prompt = sys.stdin.read() if sys.stdin else ""
    
    if not prompt.strip():
        return

    # Determine docs root with proper priority order
    # Priority 1: Explicit CONTEXT_DOCS_ROOT environment variable
    # Priority 2: Project-local .claude/ (if exists with .md files)
    # Priority 3: Global ~/.claude/
    docs_root = resolve_docs_root()

    # Load state
    state_file = get_state_file()
    prev_state = load_state(state_file)  # Keep copy before mutation
    state = json.loads(json.dumps(prev_state))  # Deep copy for modification

    # Update attention based on prompt
    state, activated = update_attention(state, prompt)

    # Build output
    output, stats = build_context_output(state, docs_root)
    stats["total_chars"] = len(output)  # Add total chars to stats

    # Append to history log (before save, so turn_count is correct)
    append_history(state, prev_state, activated, prompt, stats)

    # Save state for next turn
    save_state(state_file, state)
    
    # Log injection for debugging (append-only)
    log_file = Path.home() / ".claude" / "context_injection.log"
    try:
        with open(log_file, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{datetime.now().isoformat()}] Turn {state['turn_count']}\n")
            f.write(f"Prompt (first 100 chars): {prompt[:100]}...\n")
            f.write(f"Stats: Hot={stats['hot']}, Warm={stats['warm']}, Cold={stats['cold']}\n")
            f.write(f"Total chars: {len(output):,}\n")
            f.write(f"Activated files: {', '.join(activated) if activated else 'none'}\n")
            f.write(f"{'='*80}\n")
            f.write(output)
            f.write(f"\n{'='*80}\n\n")
    except Exception as e:
        # Don't fail hook if logging fails
        pass

    # Output to Claude Code
    if stats["hot"] > 0 or stats["warm"] > 0:
        print(output)


if __name__ == "__main__":
    main()
