from typing import List, Dict, Tuple
import json

RULES_PREAMBLE = """### Review Rules
- **Security**: injection, secrets, unsafe eval/shell, unpinned deps, SSRF, path traversal.
- **Tests**: missing tests, lack of edge cases, flaky patterns.
- **Complexity**: dead code, large functions, unclear responsibilities.
- **Style**: naming, comments, docstrings, API consistency.
"""

JSON_INSTRUCTIONS = (
    "Return ONLY JSON with this exact shape:\n"
    "{\n"
    '  "summary_markdown": "short overall summary with bullet points",\n'
    '  "files": [\n'
    "    {\n"
    '      "filename": "path/to/file.py",\n'
    '      "comments": [\n'
    '        {"line_hint": "small snippet or keyword to locate", "message": "comment text"},\n'
    "        ...\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any other keys. Keep each comment crisp and actionable."
)

def build_llm_prompt_from_patches(patches: List[Dict]) -> Tuple[str, str]:
    # files_md for context
    files_md = []
    for p in patches:
        files_md.append(f"### {p['filename']}\n```\n{p['patch']}\n```")
    files_blob = "\n\n".join(files_md) if files_md else "_No patches_"

    system = (
        "You are a meticulous senior code reviewer. "
        "Focus on Security, Tests, Complexity, and Style. "
        "Prefer high-signal comments over nitpicks. "
        "When unsure, ask for clarification.\n\n"
        + JSON_INSTRUCTIONS
    )
    user = f"Review the following diffs and produce structured JSON.\n\n{files_blob}"
    return system, user

def parse_llm_json_or_fallback(text: str) -> Dict:
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or "files" not in data or "summary_markdown" not in data:
            raise ValueError("Missing required keys")
        return data
    except Exception:
        # Fallback to a single-file, single-comment structure using raw text
        return {
            "summary_markdown": text,
            "files": []
        }
