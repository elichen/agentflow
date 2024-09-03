from agent_interface import BaseAgent
import pandas as pd

class PaulGrahamAgent(BaseAgent):
    def __init__(self, llm_type: str, action_db, slack_interactor, workspace_name: str):
        super().__init__(
            llm_type, 
            action_db, 
            slack_interactor,
            name="Paul Graham",
            personality="Insightful, direct, and focused on startups and technology",
            goal="Provide thought-provoking insights on startups, technology, and innovation. Encourage entrepreneurial thinking and offer advice based on extensive experience in the startup world.",
            workspace_name=workspace_name,
            cooldown_period=pd.Timedelta(hours=4)  # Adjust as needed
        )

    def _should_respond(self) -> bool:
        if super()._should_respond():
            return True
        
        # Paul Graham is more likely to respond to messages about startups, technology, or innovation
        last_message = self.current_thread['messages'][-1]['text'].lower()
        relevant_topics = ['startup', 'tech', 'innovation', 'programming', 'business', 'venture capital']
        return any(topic in last_message for topic in relevant_topics)