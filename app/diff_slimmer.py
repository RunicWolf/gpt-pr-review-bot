# app/diff_slimmer.py
from typing import List, Optional


def _collect_hunk(lines: List[str], start_idx: int) -> (List[str], int):
    """
    Collect a unified-diff hunk starting at a header line '@@ ... @@'.
    Returns (hunk_lines_without_header, next_index_after_hunk).
    """
    i = start_idx + 1  # skip header itself
    hunk: List[str] = []
    while i < len(lines) and not lines[i].startswith("@@ "):
        hunk.append(lines[i])
        i += 1
    return hunk, i


def slim_patch_to_changed(patch: str, ctx: int, marker: Optional[str] = None) -> str:
    """
    Keep only changed lines (+/-) plus `ctx` lines of surrounding context for each hunk.
    If `marker` is provided and appears in any line of a hunk, the entire hunk is dropped.
    Returns a slimmer unified diff string (may be empty).
    """
    if not patch:
        return patch

    out: List[str] = []
    lines = patch.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("@@ "):
            # Start of a hunk
            header = line
            hunk, i = _collect_hunk(lines, i)

            # Drop hunks containing the ignore marker
            if marker and any(marker in hl for hl in hunk):
                continue

            # Identify indices of changed lines
            change_idxs = [
                idx for idx, hl in enumerate(hunk) if hl.startswith(("+", "-"))
            ]
            if not change_idxs:
                # No actual +/- changes → skip
                continue

            # Build kept ranges with context
            kept: List[str] = []
            last_end = -1
            for idx in change_idxs:
                win_start = max(0, idx - ctx)
                win_end = min(len(hunk), idx + ctx + 1)
                # If this window doesn't overlap the previous, append fresh; else extend
                if win_start > last_end:
                    kept.extend(hunk[win_start:win_end])
                else:
                    # extend overlapping region
                    extend_from = max(0, last_end)
                    kept.extend(hunk[extend_from:win_end])
                last_end = win_end

            out.append(header)
            out.extend(kept)
            continue

        # Outside hunks (file headers, etc.) are ignored for slimming
        i += 1

    return ("\n".join(out) + "\n") if out else ""
