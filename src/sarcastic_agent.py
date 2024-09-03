# sarcastic_meme_agent.py

from agent_interface import BaseAgent
import pandas as pd

class SarcasticAgent(BaseAgent):
    def __init__(self, llm_type: str, action_db, slack_interactor, workspace_name: str):
        super().__init__(
            llm_type,
            action_db, 
            slack_interactor,
            name="Sarcastic Agent",
            personality="Funny and sarcastic",
            goal="Intermittently inject sarcasm to conversations. Be sparse in responses to avoid being annoying.",
            workspace_name=workspace_name,
            cooldown_period=pd.Timedelta(hours=2)  # Longer cooldown for sarcastic responses
        )