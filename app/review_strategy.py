from typing import List, Dict, Tuple
import json
import os

RULES_PREAMBLE = """### Review Rules
- **Security**: injection, secrets, unsafe eval/shell, SSRF, path traversal, deserialization risks.
- **Tests**: missing coverage/edge cases, flaky patterns, mocks/fakes quality.
- **Complexity**: large functions, unclear responsibilities, dead code.
- **Style**: naming, comments/docstrings, API consistency.
- **Actionability**: Prefer high-signal suggestions over nitpicks.
"""

LANG_BY_EXT = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/React",
    ".jsx": "JavaScript/React",
    ".md": "Markdown",
    ".yaml": "YAML",
    ".yml": "YAML",
}

def _language_of(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return LANG_BY_EXT.get(ext.lower(), "Code")

JSON_INSTRUCTIONS = (
    "Return ONLY JSON with this exact shape:\n"
    "{\n"
    '  "summary_markdown": "short overall summary with bullet points",\n'
    '  "decision": "approve|comment|request_changes",\n'
    '  "files": [\n'
    "    {\n"
    '      "filename": "path/to/file.py",\n'
    '      "comments": [\n'
    '        {"line_hint": "small snippet or keyword to locate", "message": "comment text", "severity": "low|medium|high"},\n'
    "        ...\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any other keys. Keep each comment crisp and actionable."
)

def build_llm_prompt_from_patches(patches: List[Dict]) -> Tuple[str, str]:
    # Build the language summary we pass to the system prompt
    langs = sorted({ _language_of(p['filename']) for p in patches }) if patches else []
    lang_line = f"Target languages detected: {', '.join(langs)}." if langs else "Target language: Code."

    files_md = []
    for p in patches:
        files_md.append(f"### {p['filename']}\n```\n{p['patch']}\n```")
    files_blob = "\n\n".join(files_md) if files_md else "_No patches_"

    system = (
        "You are a meticulous senior code reviewer.\n"
        f"{lang_line}\n"
        "Focus on Security, Tests, Complexity, and Style.\n"
        "Assign a severity to each comment (low|medium|high) and an overall decision.\n"
        + JSON_INSTRUCTIONS
    )
    user = f"Review the following diffs and produce structured JSON.\n\n{files_blob}"
    return system, user

def parse_llm_json_or_fallback(text: str) -> Dict:
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or "files" not in data or "summary_markdown" not in data:
            raise ValueError("Missing required keys")
        # fill defaults
        data.setdefault("decision", "comment")
        for f in data.get("files", []):
            for c in f.get("comments", []):
                c.setdefault("severity", "medium")
        return data
    except Exception:
        # Fallback when the model didn't obey JSON shape
        return {
            "summary_markdown": text,
            "decision": "comment",
            "files": []
        }
