from typing import List, Optional


def find_addition_lines(patch: str) -> List[int]:
    """
    Heuristic: return a list of candidate line numbers for added lines in the unified diff.
    This is the existing helper used by guess_line_for_hint as a fallback.
    """
    added_line_numbers: List[int] = []
    current_target_line = 0

    for ln in patch.splitlines():
        # Hunk header: @@ -a,b +c,d @@
        if ln.startswith("@@ "):
            # Parse the +c,d portion to reset the "current target line".
            try:
                # naive parse: find the "+c,d" chunk
                plus_index = ln.find("+")
                space_index = ln.find(" ", plus_index)
                plus_slice = (
                    ln[plus_index + 1 : space_index]
                    if space_index != -1
                    else ln[plus_index + 1 :]
                )
                # c or c,d
                c_str = plus_slice.split(",")[0]
                current_target_line = (
                    int(c_str) - 1
                )  # will increment when we see context/added
            except Exception:
                current_target_line = 0
            continue

        # File header "+"
        if ln.startswith("+++"):
            continue
        if ln.startswith("---"):
            continue

        # Added / removed / context
        if ln.startswith("+"):
            current_target_line += 1
            added_line_numbers.append(current_target_line)
        elif ln.startswith("-"):
            # deletion does not advance target line number
            pass
        else:
            # context (' ' or anything else) advances target line
            current_target_line += 1

    return added_line_numbers


# --- NEW: exact-match fast path on added lines --------------------------------
def _first_added_line_containing(patch: str, token: str) -> Optional[int]:
    """
    If `token` appears in any real added line (+, not +++), return that 1-based line
    number within the target hunk (GitHub RIGHT side).
    """
    token = (token or "").strip()
    if not token:
        return None

    current_target_line = 0
    for ln in patch.splitlines():
        if ln.startswith("@@ "):
            try:
                plus_index = ln.find("+")
                space_index = ln.find(" ", plus_index)
                plus_slice = (
                    ln[plus_index + 1 : space_index]
                    if space_index != -1
                    else ln[plus_index + 1 :]
                )
                c_str = plus_slice.split(",")[0]
                current_target_line = int(c_str) - 1
            except Exception:
                current_target_line = 0
            continue

        if ln.startswith("+++") or ln.startswith("---"):
            continue

        if ln.startswith("+") and not ln.startswith("+++"):
            current_target_line += 1
            if token in ln:
                return current_target_line
        elif ln.startswith("-"):
            # deletion
            pass
        else:
            # context
            current_target_line += 1

    return None


# ------------------------------------------------------------------------------


def guess_line_for_hint(patch: str, hint: str) -> Optional[int]:
    """
    Best-effort mapping of an LLM hint (token/substring) to a target line number on the RIGHT side.
    1) Try exact match on added lines.
    2) Fall back to the first added line in the patch (existing behavior).
    """
    # Fast path: exact match on added lines
    hit = _first_added_line_containing(patch, hint)
    if hit is not None:
        return hit

    # Fallback: first added line heuristic
    candidates = find_addition_lines(patch)
    return candidates[0] if candidates else None
