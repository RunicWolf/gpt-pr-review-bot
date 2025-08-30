PYTHON_SEC_RULES = [
    "Avoid exec/eval on untrusted input.",
    "Check for hardcoded secrets (API keys, passwords).",
    "Flag use of subprocess with shell=True.",
]

JS_STYLE_RULES = [
    "Discourage use of var; prefer let/const.",
    "Prefer strict equality === instead of ==",
    "Flag direct DOM manipulation in React components.",
]


def get_rulepack(langs):
    rules = []
    if "Python" in langs:
        rules.extend(PYTHON_SEC_RULES)
    if "JavaScript" in langs or "TypeScript" in langs:
        rules.extend(JS_STYLE_RULES)
    return rules
