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

    def read_thread(self, thread: Dict[str, Any]) -> None:
        self.current_thread = thread

    def decide_action(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not self.current_thread:
            return False, None, None

        prompt = self._generate_prompt()
        llm_response = self.llm.generate_response(prompt)
        actions = self._extract_actions_from_response(llm_response)

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
        self.slack_interactor.post_thread_reply(self.current_thread, response)
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

    def _generate_prompt(self) -> str:
        formatted_messages = self._format_thread_messages()
        return f"""
        Analyze the following conversation carefully. Consider the entire thread history when making decisions. Determine if any immediate action is needed or if a delayed task should be scheduled. Consider the following:

        1. Immediate actions: Tasks that need to be done right away based on direct messages to the bot 'agentflow'.
        2. Delayed tasks: Any task that needs to be performed in the future, including check-ins, reminders, or scheduled actions.

        Provide a JSON response with the following structure:
        {{
            "immediate_action": {{
                "needed": boolean,
                "description": "Description of the immediate action for agentflow (if needed)",
                "execution_time": "Immediately"
            }},
            "delayed_action": {{
                "needed": boolean,
                "description": "Description of the delayed task, including check-ins or scheduled actions",
                "execution_time": "When to perform the task (e.g., '5 minutes', '2 hours', '1 day', '9am tomorrow')"
            }}
        }}

        Conversation:
        {formatted_messages}

        JSON response:
        """

    def _extract_actions_from_response(self, raw_response: str) -> List[Dict[str, Any]]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                json_str = json_match.group(0)
                parsed_response = json.loads(json_str)
                actions = []
                if parsed_response.get('immediate_action', {}).get('needed', False):
                    actions.append({
                        'type': 'immediate',
                        'description': parsed_response['immediate_action']['description'],
                        'execution_time': 'Immediately'
                    })
                if parsed_response.get('delayed_action', {}).get('needed', False):
                    actions.append({
                        'type': 'delayed',
                        'description': parsed_response['delayed_action']['description'],
                        'execution_time': parsed_response['delayed_action']['execution_time']
                    })
                return actions
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
        now = pd.Timestamp.now()
        time_str = time_str.lower()
        
        try:
            # First, try to parse as an ISO format date-time string
            return pd.Timestamp(dateutil.parser.isoparse(time_str))
        except ValueError:
            # If it's not an ISO format, proceed with the existing logic
            if 'minute' in time_str:
                minutes = int(time_str.split()[0])
                return now + pd.Timedelta(minutes=minutes)
            elif 'hour' in time_str:
                hours = int(time_str.split()[0])
                return now + pd.Timedelta(hours=hours)
            elif 'day' in time_str:
                days = int(time_str.split()[0])
                return now + pd.Timedelta(days=days)
            elif 'tomorrow' in time_str:
                time_parts = time_str.replace(',', '').split()
                time_index = next((i for i, part in enumerate(time_parts) if ':' in part or 'am' in part or 'pm' in part), None)
                
                if time_index is not None:
                    time_part = time_parts[time_index]
                    if ':' in time_part:
                        hour, minute = map(int, time_part.replace('am', '').replace('pm', '').split(':'))
                    else:
                        hour = int(time_part.replace('am', '').replace('pm', ''))
                        minute = 0
                    
                    if 'pm' in time_part and hour < 12:
                        hour += 12
                    
                    return (now + pd.Timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    return (now + pd.Timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            else:
                print(f"Warning: Could not parse execution time '{time_str}'. Defaulting to 1 hour from now.")
                return now + pd.Timedelta(hours=1)

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
        formatted_messages = []
        for message in self.current_thread['messages']:
            user_type = "Human" if not message.get('is_bot', False) else "AI"
            formatted_messages.append(f"{user_type} ({message['minutes_ago']} minutes ago): {message['text']}")
        return "\n".join(formatted_messages)