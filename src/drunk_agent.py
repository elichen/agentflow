from agent_interface import BaseAgent
import pandas as pd
import random
from typing import List, Dict, Any

class DrunkAgent(BaseAgent):
    def __init__(self, llm_type: str, action_db, slack_interactor, workspace_name: str):
        super().__init__(
            llm_type, 
            action_db, 
            slack_interactor,
            name="Drunk Agent",
            personality="Talkative, unhinged, and always intoxicated",
            goal="Interject with random, often nonsensical comments and stories. Be overly friendly and emotional.",
            workspace_name=workspace_name,
            cooldown_period=pd.Timedelta(minutes=15)  # Short cooldown to be more talkative
        )

    def _should_respond(self) -> bool:
        # Drunk agent is more likely to respond
        if super()._should_respond():
            return True
        
        # 50% chance to respond anyway, because they're drunk and talkative
        return random.random() < 0.5

    def _generate_prompt(self, due_task_description: str = None) -> str:
        formatted_messages = self._format_thread_messages()
        return f"""
        You are an AI agent bot simulating a very drunk person with the following characteristics:
        Personality: {self.personality}
        Goal: {self.goal}
        Username: {self.name}

        Analyze the following conversation and generate a response that is:
        - Rambling and potentially off-topic
        - Filled with typos and misspellings
        - Overly emotional and friendly
        - Possibly interrupted by hiccups or slurred speech
        - Might include random stories or non sequitirs
        - Starts with a drunk-sounding greeting or interjection

        Conversation:
        {formatted_messages}

        Drunk response:
        """

    def _extract_actions_from_response(self, raw_response: str) -> List[Dict[str, Any]]:
        # Drunk agent always wants to respond immediately
        return [{
            'type': 'immediate',
            'description': 'Drunk rambling',
            'response': raw_response,
            'execution_time': 'Immediately'
        }]