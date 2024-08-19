# sarcastic_agent.py

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

        sarcastic_response = self._generate_sarcastic_response()

        if sarcastic_response:
            return True, {"type": "immediate", "action": "sarcasm", "content": sarcastic_response}, None

        return False, None, None

    def execute_immediate_action(self, action: Dict[str, Any]) -> str:
        response = action['content']
        self.slack_interactor.post_thread_reply(self.current_thread, response, username=self.username)
        self._update_sarcasm_cooldown(self.current_thread['thread_ts'])
        return f"Executed {action['action']} action: {response[:30]}..."

    def schedule_delayed_action(self, action: Dict[str, Any]) -> None:
        # This agent doesn't schedule delayed actions
        pass

    def _generate_sarcastic_response(self) -> str:
        prompt = f"""
        Analyze the following conversation and generate a brief, sarcastic response.
        Your username in this thread is "{self.username}". Avoid responding to messages from other bots, AIs, agents, or yourself.

        Guidelines for the sarcastic response:
        1. Be witty and playful, expressing the opposite sentiment of the prevalent emotion in the conversation.
        2. Use light humor and gentle teasing. Think of it as friendly banter among colleagues.
        3. Avoid being mean-spirited, insulting, or targeting individuals directly.
        4. Keep the response brief (1-2 sentences) and relevant to the conversation topic.
        5. Do not include any explanatory text or meta-commentary about the sarcasm.
        6. It's okay to be a bit cheeky or use mild exaggeration for comedic effect.
        7. When in doubt, lean towards being more playful than biting.

        Remember, the goal is to add a touch of humor to the conversation, not to offend or upset anyone.

        Conversation:
        {self._format_thread_messages()}

        Sarcastic response:
        """
        return self.llm.generate_response(prompt).strip()

    def _should_respond(self) -> bool:
        # Check if the last message is from a bot, AI, or agent
        last_message = self.current_thread['messages'][-1]
        if last_message.get('is_bot', False) or last_message.get('username', '') == self.username:
            return False

        # Check if the last message is a direct action or request
        last_message_text = last_message['text'].lower()
        if "agentflow" in last_message_text and any(word in last_message_text for word in ["can you", "could you", "please"]):
            return False

        # Check sarcasm cooldown
        thread_id = self.current_thread['thread_ts']
        if thread_id in self.sarcasm_cooldown:
            if pd.Timestamp.now() - self.sarcasm_cooldown[thread_id] < self.cooldown_period:
                return False

        return True

    def _update_sarcasm_cooldown(self, thread_id: str) -> None:
        self.sarcasm_cooldown[thread_id] = pd.Timestamp.now()

    def _format_thread_messages(self) -> str:
        if not self.current_thread:
            return ""
        formatted_messages = []
        for message in self.current_thread['messages']:
            if message.get('is_bot', False):
                user_type = f"AI {message['username']}"
            else:
                user_type = "Human"
            formatted_messages.append(f"{user_type} ({message['minutes_ago']} minutes ago): {message['text']}")
        return "\n".join(formatted_messages)