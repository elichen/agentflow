# project_manager_agent.py

from agent_interface import BaseAgent
import pandas as pd

class ProjectManagerAgent(BaseAgent):
    def __init__(self, llm, action_db, slack_interactor):
        super().__init__(
            llm, 
            action_db, 
            slack_interactor,
            name="PM Agent",
            personality="Professional and efficient",
            goal="Close the loop on open items, nudging and reminding people when necessary. Strive to not be very chatty, and only chime in efficiently.",
            cooldown_period=pd.Timedelta(minutes=30)  # Adjust as needed
        )