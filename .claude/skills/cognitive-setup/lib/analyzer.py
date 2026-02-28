#!/usr/bin/env python3
"""
Project Analyzer - Automated project structure analysis for claude-cognitive setup.

Scans a project directory to identify modules, systems, integrations, and
generates keyword suggestions. Called by the /cognitive-setup skill.

Usage:
  python3 analyzer.py [project_dir]     # Full analysis, JSON output
  python3 analyzer.py --keywords-only   # Just generate keyword suggestions
  python3 analyzer.py --summary         # Human-readable summary
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ============================================================================
# PROJECT DETECTION
# ============================================================================

# File patterns that indicate project characteristics
LANGUAGE_INDICATORS = {
    "python": ["*.py", "requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
    "javascript": ["*.js", "*.jsx", "package.json", "*.mjs"],
    "typescript": ["*.ts", "*.tsx", "tsconfig.json"],
    "rust": ["*.rs", "Cargo.toml"],
    "go": ["*.go", "go.mod", "go.sum"],
    "java": ["*.java", "pom.xml", "build.gradle"],
    "ruby": ["*.rb", "Gemfile"],
    "php": ["*.php", "composer.json"],
    "c_cpp": ["*.c", "*.cpp", "*.h", "*.hpp", "CMakeLists.txt", "Makefile"],
    "swift": ["*.swift", "Package.swift"],
    "kotlin": ["*.kt", "*.kts"],
}

FRAMEWORK_INDICATORS = {
    "react": ["package.json:react", "*.jsx", "*.tsx"],
    "next": ["next.config.*", "package.json:next"],
    "vue": ["package.json:vue", "*.vue"],
    "django": ["manage.py", "*/settings.py", "requirements.txt:django"],
    "flask": ["requirements.txt:flask", "app.py"],
    "fastapi": ["requirements.txt:fastapi"],
    "express": ["package.json:express"],
    "spring": ["pom.xml:spring", "build.gradle:spring"],
    "rails": ["Gemfile:rails", "config/routes.rb"],
    "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
}

SYSTEM_INDICATORS = {
    "ci_cd": [".github/workflows/*", ".gitlab-ci.yml", "Jenkinsfile", ".circleci/*"],
    "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"],
    "database": ["*.sql", "migrations/*", "alembic/*", "prisma/*", "drizzle/*"],
    "deployment": ["deploy.sh", "Procfile", "vercel.json", "netlify.toml", "*.tf"],
    "monitoring": ["prometheus.*", "grafana/*", "*.dashboard.json"],
}

INTEGRATION_INDICATORS = {
    "rest_api": ["**/api/**", "**/routes/**", "**/endpoints/**"],
    "graphql": ["*.graphql", "schema.graphql"],
    "grpc": ["*.proto"],
    "websocket": ["**/ws/**", "**/websocket/**"],
    "message_queue": ["**/queue/**", "**/mq/**", "**/kafka/**", "**/rabbitmq/**"],
}

# Directories to skip during analysis
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", ".next", ".nuxt", "target", ".cache",
    ".pytest_cache", ".mypy_cache", "coverage", ".claude", ".idea",
    ".vscode", "vendor", "tmp", "temp", "logs",
}

# Files to skip
SKIP_FILES = {
    ".DS_Store", "Thumbs.db", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock",
}


# ============================================================================
# ANALYSIS
# ============================================================================

def analyze_project(project_dir: str = ".") -> Dict:
    """
    Perform full project analysis.

    Returns a structured dictionary with:
    - project_info: name, languages, frameworks, structure type
    - modules: list of identified code modules
    - systems: list of identified systems/infrastructure
    - integrations: list of identified integration points
    - keywords: suggested keyword mappings
    - co_activation: suggested co-activation rules
    - pinned: suggested pinned files
    """
    root = Path(project_dir).resolve()

    result = {
        "project_info": _detect_project_info(root),
        "file_tree": _build_file_tree(root),
        "modules": [],
        "systems": [],
        "integrations": [],
        "keywords": {},
        "co_activation": {},
        "pinned": [],
    }

    # Identify components
    result["modules"] = _identify_modules(root, result["file_tree"])
    result["systems"] = _identify_systems(root)
    result["integrations"] = _identify_integrations(root, result["file_tree"])

    # Generate keywords for each component
    all_components = result["modules"] + result["systems"] + result["integrations"]
    for comp in all_components:
        doc_path = comp["doc_path"]
        result["keywords"][doc_path] = comp.get("suggested_keywords", [])

    # Generate co-activation rules
    result["co_activation"] = _generate_co_activation(all_components)

    # Suggest pinned files
    result["pinned"] = _suggest_pinned(all_components)

    return result


def _detect_project_info(root: Path) -> Dict:
    """Detect project name, languages, frameworks, and structure."""
    info = {
        "name": root.name,
        "root": str(root),
        "languages": [],
        "frameworks": [],
        "structure": "single",  # single, monorepo, workspace
    }

    # Detect languages
    extensions = defaultdict(int)
    for f in _walk_files(root, max_depth=5):
        ext = f.suffix.lower()
        if ext:
            extensions[ext] += 1

    for lang, indicators in LANGUAGE_INDICATORS.items():
        for indicator in indicators:
            if indicator.startswith("*."):
                ext = indicator[1:]  # e.g., ".py"
                if extensions.get(ext, 0) > 0:
                    if lang not in info["languages"]:
                        info["languages"].append(lang)
                    break
            else:
                if list(root.glob(indicator)):
                    if lang not in info["languages"]:
                        info["languages"].append(lang)
                    break

    # Detect frameworks (simplified — check key files)
    for framework, indicators in FRAMEWORK_INDICATORS.items():
        for indicator in indicators:
            if ":" in indicator:
                file_part, content_part = indicator.split(":", 1)
                matches = list(root.glob(file_part))
                for match in matches:
                    try:
                        if content_part.lower() in match.read_text().lower():
                            if framework not in info["frameworks"]:
                                info["frameworks"].append(framework)
                            break
                    except (UnicodeDecodeError, OSError):
                        pass
            else:
                if list(root.glob(indicator)):
                    if framework not in info["frameworks"]:
                        info["frameworks"].append(framework)
                    break

    # Detect monorepo patterns
    if (root / "lerna.json").exists() or (root / "pnpm-workspace.yaml").exists():
        info["structure"] = "monorepo"
    elif (root / "packages").is_dir() or (root / "apps").is_dir():
        info["structure"] = "workspace"

    return info


def _build_file_tree(root: Path, max_depth: int = 4) -> List[str]:
    """Build a filtered file tree for analysis."""
    files = []
    for f in _walk_files(root, max_depth=max_depth):
        try:
            rel = str(f.relative_to(root))
            files.append(rel)
        except ValueError:
            pass
    return sorted(files)


def _walk_files(root: Path, max_depth: int = 5, current_depth: int = 0):
    """Walk files respecting skip lists and max depth."""
    if current_depth > max_depth:
        return

    try:
        entries = sorted(root.iterdir())
    except PermissionError:
        return

    for entry in entries:
        if entry.name in SKIP_FILES:
            continue
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            yield from _walk_files(entry, max_depth, current_depth + 1)
        elif entry.is_file():
            yield entry


def _identify_modules(root: Path, file_tree: List[str]) -> List[Dict]:
    """Identify code modules from the file tree."""
    modules = []

    # Group files by top-level directory
    dir_files = defaultdict(list)
    for f in file_tree:
        parts = f.split("/")
        if len(parts) >= 2:
            top_dir = parts[0]
            if top_dir not in SKIP_DIRS and not top_dir.startswith("."):
                dir_files[top_dir].append(f)

    # Also look for important single files at root
    root_code_files = [f for f in file_tree
                       if "/" not in f and _is_code_file(f)]

    # Create modules from significant directories
    for dir_name, files in dir_files.items():
        code_files = [f for f in files if _is_code_file(f)]
        if len(code_files) < 1:
            continue

        # Generate keywords from file contents
        keywords = _extract_keywords_from_dir(root, dir_name, code_files[:20])

        doc_name = _sanitize_doc_name(dir_name)
        modules.append({
            "name": dir_name,
            "type": "module",
            "doc_path": f"modules/{doc_name}.md",
            "source_files": code_files[:20],
            "file_count": len(code_files),
            "suggested_keywords": keywords,
            "description": f"Code module: {dir_name}/",
        })

    # Create module for significant root-level files
    if len(root_code_files) >= 2:
        keywords = []
        for f in root_code_files[:10]:
            keywords.extend(_extract_keywords_from_file(root / f))
        modules.append({
            "name": "core",
            "type": "module",
            "doc_path": "modules/core.md",
            "source_files": root_code_files[:10],
            "file_count": len(root_code_files),
            "suggested_keywords": _dedupe_keywords(keywords),
            "description": "Core root-level source files",
        })

    return modules


def _identify_systems(root: Path) -> List[Dict]:
    """Identify systems/infrastructure."""
    systems = []

    for sys_type, patterns in SYSTEM_INDICATORS.items():
        found_files = []
        for pattern in patterns:
            found_files.extend(str(f.relative_to(root)) for f in root.glob(pattern) if f.is_file())

        if found_files:
            doc_name = _sanitize_doc_name(sys_type)
            keywords = [sys_type.replace("_", " ")]
            # Add specific keywords based on system type
            if sys_type == "docker":
                keywords.extend(["docker", "container", "image", "compose", "dockerfile"])
            elif sys_type == "ci_cd":
                keywords.extend(["ci", "cd", "pipeline", "workflow", "github actions", "deploy"])
            elif sys_type == "database":
                keywords.extend(["database", "db", "migration", "schema", "sql", "query"])
            elif sys_type == "deployment":
                keywords.extend(["deploy", "deployment", "hosting", "infrastructure"])

            systems.append({
                "name": sys_type,
                "type": "system",
                "doc_path": f"systems/{doc_name}.md",
                "source_files": found_files[:10],
                "file_count": len(found_files),
                "suggested_keywords": _dedupe_keywords(keywords),
                "description": f"System: {sys_type.replace('_', ' ')}",
            })

    # Always suggest a development system doc
    systems.append({
        "name": "development",
        "type": "system",
        "doc_path": "systems/development.md",
        "source_files": [],
        "file_count": 0,
        "suggested_keywords": ["development", "dev", "local", "localhost", "setup", "install"],
        "description": "Local development environment",
    })

    return systems


def _identify_integrations(root: Path, file_tree: List[str]) -> List[Dict]:
    """Identify integration points."""
    integrations = []

    for int_type, patterns in INTEGRATION_INDICATORS.items():
        found_files = []
        for pattern in patterns:
            found_files.extend(str(f.relative_to(root)) for f in root.glob(pattern) if f.is_file())

        if found_files:
            doc_name = _sanitize_doc_name(int_type)
            keywords = [int_type.replace("_", " ")]
            if int_type == "rest_api":
                keywords.extend(["api", "endpoint", "route", "rest", "http", "request", "response"])
            elif int_type == "graphql":
                keywords.extend(["graphql", "query", "mutation", "schema", "resolver"])
            elif int_type == "grpc":
                keywords.extend(["grpc", "protobuf", "proto", "rpc", "service"])
            elif int_type == "websocket":
                keywords.extend(["websocket", "ws", "socket", "realtime", "real-time"])

            integrations.append({
                "name": int_type,
                "type": "integration",
                "doc_path": f"integrations/{doc_name}.md",
                "source_files": found_files[:10],
                "file_count": len(found_files),
                "suggested_keywords": _dedupe_keywords(keywords),
                "description": f"Integration: {int_type.replace('_', ' ')}",
            })

    return integrations


def _generate_co_activation(components: List[Dict]) -> Dict[str, List[str]]:
    """Generate co-activation rules based on file proximity and shared keywords."""
    co_activation = {}

    # Create keyword → component index
    keyword_to_components = defaultdict(list)
    for comp in components:
        for kw in comp.get("suggested_keywords", []):
            keyword_to_components[kw.lower()].append(comp["doc_path"])

    # Components that share keywords should co-activate
    for comp in components:
        related = set()
        for kw in comp.get("suggested_keywords", []):
            for other_path in keyword_to_components.get(kw.lower(), []):
                if other_path != comp["doc_path"]:
                    related.add(other_path)

        # Co-activate systems with modules that share keyword overlap
        if comp["type"] == "system":
            comp_kws = set(kw.lower() for kw in comp.get("suggested_keywords", []))
            for other in components:
                if other["type"] == "module" and other["doc_path"] != comp["doc_path"]:
                    other_kws = set(kw.lower() for kw in other.get("suggested_keywords", []))
                    if comp_kws & other_kws:
                        related.add(other["doc_path"])

        if related:
            co_activation[comp["doc_path"]] = sorted(list(related))[:5]

    return co_activation


def _suggest_pinned(components: List[Dict]) -> List[str]:
    """Suggest files that should always be at least WARM."""
    pinned = []
    for comp in components:
        if comp["type"] == "system" and comp["name"] == "development":
            pinned.append(comp["doc_path"])
    return pinned


# ============================================================================
# KEYWORD EXTRACTION
# ============================================================================

def _extract_keywords_from_dir(root: Path, dir_name: str, files: List[str]) -> List[str]:
    """Extract keywords from a directory of source files."""
    keywords = [dir_name.lower()]

    # Add keywords from filenames
    for f in files[:10]:
        name = Path(f).stem.lower()
        # Split on common separators
        parts = re.split(r'[-_.]', name)
        keywords.extend(p for p in parts if len(p) > 2)

    # Sample keywords from file contents
    for f in files[:5]:
        full_path = root / f
        keywords.extend(_extract_keywords_from_file(full_path))

    return _dedupe_keywords(keywords)


def _extract_keywords_from_file(file_path: Path) -> List[str]:
    """Extract keywords from a single source file."""
    keywords = []

    try:
        content = file_path.read_text(errors="ignore")
    except (OSError, UnicodeDecodeError):
        return keywords

    # Limit to first 200 lines
    lines = content.split("\n")[:200]
    content = "\n".join(lines)

    # Extract class names
    class_names = re.findall(r'class\s+(\w+)', content)
    keywords.extend(n.lower() for n in class_names)

    # Extract function/method names (top-level or with self)
    func_names = re.findall(r'(?:def|function|func|fn)\s+(\w+)', content)
    keywords.extend(n.lower() for n in func_names if len(n) > 3 and n != "self")

    # Extract import names
    import_names = re.findall(r'(?:import|from|require|use)\s+["\']?(\w+)', content)
    keywords.extend(n.lower() for n in import_names if len(n) > 2)

    # Extract constants (UPPER_CASE names)
    constants = re.findall(r'\b([A-Z][A-Z_]{2,})\b', content)
    keywords.extend(c.lower() for c in constants[:10])

    return keywords[:30]


def _dedupe_keywords(keywords: List[str]) -> List[str]:
    """Remove duplicate and low-value keywords."""
    # Common words to exclude
    stop_words = {
        "the", "and", "for", "from", "import", "self", "none", "true", "false",
        "return", "class", "def", "function", "var", "let", "const", "this",
        "new", "null", "undefined", "print", "main", "init", "test", "get",
        "set", "has", "str", "int", "bool", "list", "dict", "type", "name",
        "value", "key", "data", "error", "result", "path", "file",
    }

    seen = set()
    unique = []
    for kw in keywords:
        kw = kw.strip().lower()
        if kw and kw not in seen and kw not in stop_words and len(kw) > 2:
            seen.add(kw)
            unique.append(kw)

    return unique[:25]  # Cap at 25 keywords per file


def _is_code_file(filename: str) -> bool:
    """Check if a filename is a code file."""
    code_extensions = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
        ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".swift", ".kt",
        ".scala", ".lua", ".sh", ".bash", ".zsh", ".r", ".jl",
    }
    return Path(filename).suffix.lower() in code_extensions


def _sanitize_doc_name(name: str) -> str:
    """Convert a name to a safe documentation filename."""
    return re.sub(r'[^a-z0-9-]', '-', name.lower()).strip('-')


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze project for claude-cognitive setup")
    parser.add_argument("project_dir", nargs="?", default=".",
                        help="Project directory to analyze")
    parser.add_argument("--keywords-only", action="store_true",
                        help="Output only keyword suggestions")
    parser.add_argument("--summary", action="store_true",
                        help="Output human-readable summary")

    args = parser.parse_args()
    result = analyze_project(args.project_dir)

    if args.keywords_only:
        output = {
            "keywords": result["keywords"],
            "co_activation": result["co_activation"],
            "pinned": result["pinned"],
        }
        print(json.dumps(output, indent=2))
    elif args.summary:
        _print_summary(result)
    else:
        print(json.dumps(result, indent=2, default=str))


def _print_summary(result: Dict):
    """Print a human-readable summary."""
    info = result["project_info"]
    print(f"Project: {info['name']}")
    print(f"Languages: {', '.join(info['languages']) or 'unknown'}")
    print(f"Frameworks: {', '.join(info['frameworks']) or 'none detected'}")
    print(f"Structure: {info['structure']}")
    print()

    print(f"Modules ({len(result['modules'])}):")
    for m in result["modules"]:
        print(f"  {m['doc_path']} — {m['file_count']} files, {len(m['suggested_keywords'])} keywords")

    print(f"\nSystems ({len(result['systems'])}):")
    for s in result["systems"]:
        print(f"  {s['doc_path']} — {s['description']}")

    print(f"\nIntegrations ({len(result['integrations'])}):")
    for i in result["integrations"]:
        print(f"  {i['doc_path']} — {i['description']}")

    total_keywords = sum(len(kws) for kws in result["keywords"].values())
    print(f"\nTotal keyword mappings: {total_keywords}")
    print(f"Co-activation rules: {len(result['co_activation'])}")
    print(f"Pinned files: {len(result['pinned'])}")


if __name__ == "__main__":
    main()
