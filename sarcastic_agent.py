# sarcastic_meme_agent.py

from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
from agent_interface import AgentInterface
from llm_interface import LLMInterface
from db import ActionDatabase

class SarcasticAgent(AgentInterface):
    def __init__(self, llm: LLMInterface, action_db: ActionDatabase, slack_interactor):
        self.llm = llm
        self.action_db = action_db
        self.slack_interactor = slack_interactor
        self.current_thread = None
        self.sarcasm_cooldown = {}
        self.cooldown_period = pd.Timedelta(hours=1)
        self.username = "Sarcastic Agent"

    def read_thread(self, thread: Dict[str, Any]) -> None:
        self.current_thread = thread

    def decide_action(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not self.current_thread or not self._should_respond():
            return False, None, None

        emotion = self._analyze_thread_for_emotion()

        if emotion:
            return True, {"type": "immediate", "action": "sarcasm", "content": self._generate_sarcastic_response(emotion)}, None

        return False, None, None

    def execute_immediate_action(self, action: Dict[str, Any]) -> str:
        response = action['content']
        self.slack_interactor.post_thread_reply(self.current_thread, response, username=self.username)
        self._update_sarcasm_cooldown(self.current_thread['thread_ts'])
        return f"Executed {action['action']} action: {response[:30]}..."

    def schedule_delayed_action(self, action: Dict[str, Any]) -> None:
        # This agent doesn't schedule delayed actions
        pass

    def _analyze_thread_for_emotion(self) -> str:
        prompt = f"""
        Analyze the following conversation and determine the prevalent emotion or sentiment.
        Respond with a single word describing the emotion (e.g., happy, sad, excited, angry, etc.).

        Conversation:
        {self._format_thread_messages()}

        Prevalent emotion:
        """
        print(f"XXX prompt XXX\n{prompt}")
        return self.llm.generate_response(prompt).strip().lower()

    def _generate_sarcastic_response(self, emotion: str) -> str:
        prompt = f"""
        Generate a sarcastic response to the following conversation.
        The prevalent emotion in the conversation is: {emotion}
        Your response should express the opposite sentiment in a witty, but not offensive way.
        Keep the response brief and relevant to the conversation topic.

        Conversation:
        {self._format_thread_messages()}

        Sarcastic response:
        """
#         print(f"XXX prompt: {prompt}")
        return self.llm.generate_response(prompt)

    def _should_respond(self) -> bool:
        # Check if the last message is a direct action or request
        last_message = self.current_thread['messages'][-1]['text'].lower()
        if "agentflow" in last_message and any(word in last_message for word in ["can you", "could you", "please"]):
            return False

        # Check meme cooldown
        thread_id = self.current_thread['thread_ts']
        if thread_id in self.sarcasm_cooldown:
            if pd.Timestamp.now() - self.sarcasm_cooldown[thread_id] < self.cooldown_period:
                return False

        return True

    def _update_sarcasm_cooldown(self, thread_id: str) -> None:
        self.sarcasm_cooldown[thread_id] = pd.Timestamp.now()