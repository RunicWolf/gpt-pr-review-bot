import os
import yaml
from typing import Dict, Any

DEFAULT_CONFIG_PATHS = [".gpt-pr-bot.yml", ".gpt-pr-bot.yaml"]

def load_repo_config(base_dir: str = ".") -> Dict[str, Any]:
    for path in DEFAULT_CONFIG_PATHS:
        full = os.path.join(base_dir, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    return {}
    return {}
