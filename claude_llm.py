# claude_llm.py

from config import CONFIG
import anthropic
from llm_interface import LLMInterface

class ClaudeLLM(LLMInterface):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=CONFIG['anthropic']['api_key'])
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
            print(f"XXX ClaudeLLM prompt:\n{prompt}\nresponse:\n{response}")
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""