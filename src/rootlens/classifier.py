"""
classifier.py — Error Signal Classifier (Layer 2)

Extracts error type and file references from build logs.
Returns ErrorSignal (NEVER a Decision).
"""
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml

from .models import ErrorSignal, normalize_path

logger = logging.getLogger("rootlens")

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs"

_FILE_RE = re.compile(
    r"(?:^|\s)([\w./\-]+\.\w{1,5})"
    r"(?::(\d+))?",
    re.MULTILINE,
)

# Source code file extensions (to reduce false positives from URLs/config)
_SOURCE_EXTENSIONS = {
    "c", "cc", "cpp", "cxx", "h", "hpp", "hxx",
    "java", "kt", "scala", "py", "rb", "rs", "go",
    "js", "ts", "jsx", "tsx", "swift", "m", "mm",
}


@lru_cache(maxsize=1)
def _load_patterns() -> tuple:
    """Load error patterns from YAML config (thread-safe via lru_cache).

    Supports both grouped format ({base: [...], cpp: [...]}) and
    flat format ({patterns: [...]}) and plain list format.
    Returns tuple for lru_cache hashability.
    """
    config_file = _CONFIG_DIR / "error_patterns.yaml"
    if not config_file.exists():
        logger.warning("Config file not found: %s — classifier degraded", config_file)
        return ()
    try:
        with open(config_file) as f:
            data = yaml.safe_load(f)
        if not data:
            return ()
        # Flatten grouped or keyed formats into a single list
        if isinstance(data, list):
            patterns = data
        elif isinstance(data, dict) and "patterns" in data:
            patterns = data["patterns"]
        elif isinstance(data, dict):
            patterns = []
            for group_patterns in data.values():
                if isinstance(group_patterns, list):
                    patterns.extend(group_patterns)
        else:
            logger.warning("Config file malformed — classifier degraded")
            return ()
        # Pre-compile regexes
        for pat in patterns:
            regex_str = pat.get("regex", "") or pat.get("pattern", "")
            try:
                pat["_compiled"] = re.compile(regex_str, re.MULTILINE | re.IGNORECASE)
            except re.error as e:
                logger.warning("Skipping uncompilable pattern %r: %s", regex_str, e)
                pat["_compiled"] = None
        return tuple(patterns)
    except Exception as e:
        logger.error("Failed to load error patterns: %s", e)
        return ()


def classify(build_log: str) -> Optional[ErrorSignal]:
    """Classify build log into error signal. Returns None if no match."""
    patterns = _load_patterns()
    for entry in patterns:
        compiled = entry.get("_compiled")
        regex = entry.get("regex", "") or entry.get("pattern", "")
        try:
            matched = compiled.search(build_log) if compiled else re.search(
                regex, build_log, re.MULTILINE | re.IGNORECASE
            )
            if matched:
                files = extract_files(build_log)
                return ErrorSignal(
                    error_type=entry.get("type", "UNKNOWN"),
                    matched_pattern=regex,
                    error_files=files,
                )
        except re.error:
            logger.warning("Invalid regex in config: %s", regex)
            continue
    return None


def extract_files(build_log: str) -> List[str]:
    """Extract file paths from build log error context.

    Filters to source code extensions to reduce false positives
    from URLs, config files, and dependency paths.
    """
    matches = _FILE_RE.findall(build_log)
    files = set()
    for match in matches:
        filepath = match[0] if isinstance(match, tuple) else match
        # Filter: must have source code extension
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        if ext not in _SOURCE_EXTENSIONS:
            continue
        # Filter: skip obvious URLs
        if "://" in filepath or "www." in filepath:
            continue
        files.add(normalize_path(filepath))
    return sorted(files)
