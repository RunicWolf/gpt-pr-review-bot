from typing import List, Dict, Optional

def find_addition_lines(patch: str) -> List[int]:
    """
    Parse unified diff chunk and return a list of added line numbers on the RIGHT side.
    We infer the right-side starting line from the @@ header: @@ -a,b +c,d @@
    """
    if not patch:
        return []
    lines = patch.splitlines()
    right_line = 0
    added_lines: List[int] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@"):
            # parse like: @@ -12,5 +34,8 @@
            try:
                header = line.split("@@")[1].strip()  # '-12,5 +34,8'
                parts = header.split()
                plus = [p for p in parts if p.startswith("+")][0]  # '+34,8'
                start = plus[1:].split(",")[0]
                right_line = int(start)
            except Exception:
                right_line = 0
        else:
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(right_line)
                right_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                # deletion only affects left; right stays same
                pass
            else:
                # context line present on both sides
                right_line += 1 if right_line > 0 else 0
        i += 1
    return added_lines

def guess_line_for_hint(patch: str, hint: str) -> Optional[int]:
    """
    Try to find an added line that contains the hint (substring match).
    If not found, return the first added line (so comment still attaches).
    """
    if not patch:
        return None
    lines = patch.splitlines()
    # Compute right-side line numbers for each added line
    added = []
    right_line = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            try:
                header = line.split("@@")[1].strip()
                plus = [p for p in header.split() if p.startswith("+")][0]
                start = plus[1:].split(",")[0]
                right_line = int(start)
            except Exception:
                right_line = 0
        else:
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                added.append((right_line, content))
                right_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                pass
            else:
                right_line += 1 if right_line > 0 else 0

    if not added:
        return None

    if hint:
        for ln, content in added:
            if hint in content:
                return ln

    return added[0][0]  # first added line number
