# claude_llm.py

import os
import anthropic
from llm_interface import LLMInterface

class ClaudeLLM(LLMInterface):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"

    def generate_response(self, prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""