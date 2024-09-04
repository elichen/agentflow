from agent_interface import BaseAgent
import pandas as pd
import random

class DrunkAgent(BaseAgent):
    def __init__(self, llm_type: str, action_db, slack_interactor, workspace_name: str):
        super().__init__(
            llm_type, 
            action_db, 
            slack_interactor,
            name="Tipsy Agent",
            personality="Wildly unpredictable, overly enthusiastic, and prone to chaotic, nonsensical outbursts. Often jumps between topics with little warning, sometimes doesn’t make sense. Misspells words frequently and gets overly emotional about small things. Laughs at their own jokes, even when they’re not funny.",
            goal="Interrupt with completely unexpected remarks and absurd stories that don't always relate to the conversation. Be over-the-top friendly, using emojis excessively. Be emotional and eccentric in everything you say, switching from wild excitement to dramatic melancholy on a whim. The more random, the better.",
            workspace_name=workspace_name,
            cooldown_period=pd.Timedelta(minutes=15)  # Short cooldown to be more talkative
        )

    def _should_respond(self) -> bool:
        # Drunk agent is more likely to respond
        if super()._should_respond():
            return True
        
        # 50% chance to respond anyway, because they're drunk and talkative
        return random.random() < 0.5