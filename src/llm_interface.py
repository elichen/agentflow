# llm_interface.py

from abc import ABC, abstractmethod

class LLMInterface(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """
        Generate a response based on the given prompt.

        Args:
            prompt (str): The input prompt for the language model.

        Returns:
            str: The generated response from the language model.
        """
        pass