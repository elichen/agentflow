# project_manager_agent.py

from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import json
import re
from agent_interface import AgentInterface
from llm_interface import LLMInterface
from db import ActionDatabase
import dateutil.parser

class ProjectManagerAgent(AgentInterface):
    def __init__(self, llm: LLMInterface, action_db: ActionDatabase, slack_interactor):
        self.llm = llm
        self.action_db = action_db
        self.slack_interactor = slack_interactor
        self.current_thread = None
        self.username = "PM Agent"

    def read_thread(self, thread: Dict[str, Any]) -> None:
        self.current_thread = thread

    def decide_action(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not self.current_thread or not self._should_respond():
            return False, None, None

        actions = self._generate_actions()

        immediate_action = next((action for action in actions if action['type'] == 'immediate'), None)
        delayed_action = next((action for action in actions if action['type'] == 'delayed'), None)

        if self.identify_open_action_items(self.current_thread):
            check_in_action = self._create_check_in_action()
            if not delayed_action:
                delayed_action = check_in_action
            # If there's already a delayed action, we keep it (one delayed action per thread constraint)

        return bool(immediate_action or delayed_action), immediate_action, delayed_action

    def execute_immediate_action(self, action: Dict[str, Any]) -> str:
        response = self._generate_action_response(action)
        self.slack_interactor.post_thread_reply(self.current_thread, response, username=self.username)
        return f"Executed immediate action: {action['description']}"

    def schedule_delayed_action(self, action: Dict[str, Any]) -> None:
        thread_id = self.current_thread['thread_ts']
        channel = self.current_thread['channel']
        execution_time = self._parse_execution_time(action['execution_time'])
        self.action_db.add_action(thread_id, channel, action['description'], execution_time)

    def identify_open_action_items(self, thread: Dict[str, Any]) -> bool:
        prompt = self._generate_open_items_prompt(thread)
        response = self.llm.generate_response(prompt)
        return 'yes' in response.lower()

    def _should_respond(self) -> bool:
        # Check if the last message is from a bot, AI, or agent
        last_message = self.current_thread['messages'][-1]
        if last_message.get('is_bot', False) or last_message.get('username', '') == self.username:
            return False

        # Check if the last message is a direct action or request
        last_message_text = last_message['text'].lower()
        if "agentflow" not in last_message_text or not any(word in last_message_text for word in ["can you", "could you", "please"]):
            return False

        return True

    def _generate_actions(self) -> List[Dict[str, Any]]:
        prompt = f"""
        Analyze the following conversation and determine if any immediate action is needed or if a delayed task should be scheduled. Consider the entire thread history when making decisions.

        Your username in this thread is "{self.username}". Avoid responding to messages from other bots, AIs, agents, or yourself.

        Guidelines for actions:
        1. Immediate actions: Tasks that need to be done right away based on direct messages to the bot 'agentflow'.
        2. Delayed tasks: Any task that needs to be performed in the future, including check-ins, reminders, or scheduled actions.
        3. Be concise and straightforward in your action descriptions.
        4. Do not include any explanatory text or meta-commentary about the actions.
        5. Focus on actionable items and project management tasks.

        Provide a JSON response with the following structure:
        {{
            "actions": [
                {{
                    "type": "immediate",
                    "description": "Description of the immediate action",
                    "execution_time": "Immediately"
                }},
                {{
                    "type": "delayed",
                    "description": "Description of the delayed task",
                    "execution_time": "When to perform the task (e.g., '5 minutes', '2 hours', '1 day', '9am tomorrow')"
                }}
            ]
        }}

        Conversation:
        {self._format_thread_messages()}

        JSON response:
        """
        llm_response = self.llm.generate_response(prompt)
        return self._extract_actions_from_response(llm_response)

    def _extract_actions_from_response(self, raw_response: str) -> List[Dict[str, Any]]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                json_str = json_match.group(0)
                parsed_response = json.loads(json_str)
                return parsed_response.get('actions', [])
            else:
                raise ValueError("No JSON found in the response")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON: {e}")
            print(f"Raw response:\n{raw_response}")
            return []

    def _create_check_in_action(self) -> Dict[str, Any]:
        return {
            'type': 'delayed',
            'description': 'Check in on thread for open action items',
            'execution_time': '1 day'
        }

    def _generate_action_response(self, action: Dict[str, Any]) -> str:
        prompt = f"""
        Generate a response for the following action in a Slack conversation:
        - Keep it brief and to the point
        - Use a conversational tone
        - Don't use a formal letter structure or signature
        - Include an emoji or two if appropriate
        - Directly address the action without unnecessary formalities

        Action: {action['description']}

        Slack message:
        """
        return self.llm.generate_response(prompt)

    def _parse_execution_time(self, time_str: str) -> pd.Timestamp:
        # (existing _parse_execution_time method remains unchanged)
        pass

    def _generate_open_items_prompt(self, thread: Dict[str, Any]) -> str:
        formatted_messages = self._format_thread_messages()
        return f"""
        Analyze the following conversation and determine if there are any open action items or tasks that haven't been completed.
        Respond with 'Yes' if there are open items, or 'No' if all tasks have been completed or there are no actionable items.

        Conversation:
        {formatted_messages}

        Are there any open action items? (Yes/No):
        """

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