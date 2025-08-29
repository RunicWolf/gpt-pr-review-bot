from typing import List, Dict
from openai import OpenAI

class LLMClient:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def review_patches(self, patches: List[Dict]) -> str:
        """
        patches: list of {"filename": str, "patch": str (unified diff chunk)}
        Returns a markdown review string.
        """
        # Build a compact, structured prompt:
        files_md = []
        for p in patches:
            fname = p.get("filename", "unknown")
            patch = p.get("patch", "")[:8000]  # ensure extra safety on per-file slice
            files_md.append(f"### {fname}\n```\n{patch}\n```")
        files_blob = "\n\n".join(files_md) or "_No patches_"

        system = (
            "You are a meticulous senior code reviewer. "
            "Give actionable, concise feedback: correctness, security, complexity, style, tests, edge cases. "
            "Use bullet points. If everything looks good, say so and suggest 1-2 small improvements."
        )

        user = (
            "Please review the following PR diff. "
            "Prefer high-signal comments over nitpicks. "
            "If you reference lines, quote a tiny snippet."
            f"\n\n{files_blob}"
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
