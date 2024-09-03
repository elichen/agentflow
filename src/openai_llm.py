from config import CONFIG
import openai
from llm_interface import LLMInterface

class OpenAILLM(LLMInterface):
    def __init__(self):
        openai.api_key = CONFIG['openai']['api_key']
        self.model = "gpt-4o"

    def generate_response(self, prompt: str) -> str:
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024
            )
            print(f"OpenAI {self.model} prompt:\n{prompt}\nresponse:\n{response}")
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""