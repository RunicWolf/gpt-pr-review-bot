from fnmatch import fnmatch
from typing import List

def matches_any(path: str, patterns: List[str]) -> bool:
    for pat in patterns or []:
        if fnmatch(path, pat):
            return True
        # also try with leading "**/" if the user left it out
        if not pat.startswith("**/") and fnmatch(path, f"**/{pat}"):
            return True
    return False

def should_include(path: str, includes: List[str], excludes: List[str]) -> bool:
    if includes:
        if not matches_any(path, includes):
            return False
    if excludes and matches_any(path, excludes):
        return False
    return True
