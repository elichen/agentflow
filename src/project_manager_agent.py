# project_manager_agent.py

from agent_interface import BaseAgent
import pandas as pd

class ProjectManagerAgent(BaseAgent):
    def __init__(self, llm_type: str, action_db, slack_interactor, workspace_name: str):
        super().__init__(
            llm_type,
            action_db, 
            slack_interactor,
            name="PM Agent",
            personality="Professional and efficient",
            goal="Close the loop on open items, nudging and reminding people when necessary. Strive to not be very chatty, and only chime in efficiently.",
            workspace_name=workspace_name,
            cooldown_period=pd.Timedelta(minutes=30)  # Adjust as needed
        )