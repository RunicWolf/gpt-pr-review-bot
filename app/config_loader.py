# app/config_loader.py
import os
from typing import Any, Dict, List

import yaml

DEFAULT_CONFIG_PATHS = [".gpt-pr-bot.yml", ".gpt-pr-bot.yaml"]


def load_repo_config(base_dir: str = ".") -> Dict[str, Any]:
    """
    Load repo-level YAML config if present.
    Returns a dict (empty if not found or invalid).
    """
    for path in DEFAULT_CONFIG_PATHS:
        full = os.path.join(base_dir, path)
        if os.path.exists(full):
            try:
                with open(full, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                # Non-fatal: just ignore malformed files
                return {}
    return {}


def load_ignore_file(path: str) -> List[str]:
    """
    Load ignore patterns (one per line) from a file like .gpt-pr-bot-ignore.
    Lines starting with '#' or blank lines are ignored.
    """
    patterns: List[str] = []
    if not path:
        return patterns
    if not os.path.exists(path):
        return patterns

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                patterns.append(s)
    except Exception:
        # Non-fatal: return what we have
        return patterns

    return patterns
