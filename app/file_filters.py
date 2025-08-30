from fnmatch import fnmatch
from typing import List
import os

def _basename(path: str) -> str:
    return os.path.basename(path or "")

def _strip_leading_glob_dirs(pat: str) -> str:
    # turn "**/foo/*.lock" -> "foo/*.lock"; "**/*.lock" -> "*.lock"
    while pat.startswith("**/"):
        pat = pat[3:]
    while pat.startswith("./"):
        pat = pat[2:]
    return pat

def matches_any(path: str, patterns: List[str]) -> bool:
    """
    A robust matcher:
    - Try pattern against full path
    - Try pattern with an implied '**/' prefix (covers users writing 'foo/*.py')
    - Try against basename
    - Try against basename with leading '**/' removed
    """
    if not patterns:
        return False

    base = _basename(path)

    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue

        # 1) direct path match
        if fnmatch(path, pat):
            return True

        # 2) implied "**/" (helpful when user writes "foo/*.py" and file is "src/foo/x.py")
        implied = f"**/{pat}" if not pat.startswith("**/") else pat
        if fnmatch(path, implied):
            return True

        # 3) basename match
        if fnmatch(base, pat):
            return True

        # 4) basename match with stripped "**/"
        pat_stripped = _strip_leading_glob_dirs(pat)
        if fnmatch(base, pat_stripped):
            return True

    return False

def should_include(path: str, includes: List[str], excludes: List[str]) -> bool:
    if includes:
        if not matches_any(path, includes):
            return False
    if excludes and matches_any(path, excludes):
        return False
    return True
