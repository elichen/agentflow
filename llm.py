import os
from typing import Dict, List, Any
import anthropic

class LLMInteractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-5-sonnet-20240620"

    def generate_thread_response(self, thread: Dict[str, Any], guideline_prompt: str) -> str:
        # Prepare the conversation history
        conversation = self._format_thread(thread)
        
        # Prepare the full prompt
        full_prompt = f"{conversation}\n\n{guideline_prompt}\n\nAssistant:"

        try:
            # Generate the response
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": full_prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""

    def _format_thread(self, thread: Dict[str, Any]) -> str:
        formatted_messages = []
        for message in thread['messages']:
            user_type = "Human" if not message['is_bot'] else "AI"
            formatted_messages.append(f"{user_type}: {message['text']}")
        return "\n".join(formatted_messages)

# Usage example:
# llm_interactor = LLMInteractor()
# thread = {...}  # Thread object from organize_threads()
# guideline_prompt = "Please provide a helpful and concise response to the conversation above."
# response = llm_interactor.generate_thread_response(thread, guideline_prompt)
# print(response)