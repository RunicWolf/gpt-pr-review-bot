from typing import List, Dict
from openai import OpenAI
from app.settings import settings


class LLMClient:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete_json(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
        )
        return resp.choices[0].message.content.strip()

    def review_patches_json(self, patches: List[Dict], system: str, user: str) -> Dict:
        txt = self.complete_json(system, user)
        return {"text": txt}
