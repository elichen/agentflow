# agent_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
from llm_interface import LLMInterface
from db import ActionDatabase
import pandas as pd
import json
import re

class BaseAgent(ABC):
    def __init__(self, llm: LLMInterface, action_db: ActionDatabase, slack_interactor, name: str, personality: str, goal: str, cooldown_period: pd.Timedelta = pd.Timedelta(hours=1)):
        self.llm = llm
        self.action_db = action_db
        self.slack_interactor = slack_interactor
        self.current_thread = None
        self.name = name
        self.personality = personality
        self.goal = goal
        self.cooldown = {}
        self.cooldown_period = cooldown_period

    def get_name(self) -> str:
        return self.name

    def read_thread(self, thread: Dict[str, Any]) -> None:
        self.current_thread = thread

    def decide_action(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not self.current_thread or not self._should_respond():
            return False, None, None

        prompt = self._generate_prompt()
        llm_response = self.llm.generate_response(prompt)
        
        if self._is_rejection_response(llm_response):
            return False, None, None

        actions = self._extract_actions_from_response(llm_response)

        immediate_action = next((action for action in actions if action['type'] == 'immediate'), None)
        delayed_action = next((action for action in actions if action['type'] == 'delayed'), None)

        return bool(immediate_action or delayed_action), immediate_action, delayed_action

    def execute_immediate_action(self, action: Dict[str, Any]) -> str:
        self.slack_interactor.post_thread_reply(self.current_thread, action['response'], username=self.name)
        self._update_cooldown(self.current_thread['thread_ts'])
        return f"Executed immediate action: {action['description']}"

    def schedule_delayed_action(self, action: Dict[str, Any]) -> None:
        thread_id = self.current_thread['thread_ts']
        channel = self.current_thread['channel']
        execution_time = self._parse_execution_time(action['execution_time'])
        self.action_db.add_action(thread_id, channel, action['description'], execution_time)

    def _should_respond(self) -> bool:
        thread_id = self.current_thread['thread_ts']
        
        # Always respond if the agent's name is mentioned
        last_message = self.current_thread['messages'][-1]['text'].lower()
        if self.name.lower() in last_message:
            return True
        
        # Check cooldown
        if thread_id in self.cooldown:
            if pd.Timestamp.now() - self.cooldown[thread_id] < self.cooldown_period:
                return False
        
        return True

    def _update_cooldown(self, thread_id: str) -> None:
        self.cooldown[thread_id] = pd.Timestamp.now()

    def _generate_prompt(self, due_task_description: Optional[str] = None) -> str:
        formatted_messages = self._format_thread_messages()
        due_task_prompt = f"\nDue task to execute: {due_task_description}" if due_task_description else ""
        return f"""
        You are an AI agent with the following characteristics:
        Personality: {self.personality}
        Goal: {self.goal}
        Username: {self.name}{due_task_prompt}

        Analyze the following conversation carefully. Consider the entire thread history when making decisions. Determine if any immediate action is needed or if a delayed task should be scheduled. Consider the following:

        1. Immediate actions: Tasks that need to be done right away based on the conversation context.
        2. Delayed tasks: Any task that needs to be performed in the future, including check-ins, reminders, or scheduled actions.

        For immediate actions, generate a response that is:
        - Brief and to the point
        - In a conversational tone
        - Without a formal letter structure or signature
        - Including an emoji or two if appropriate
        - Directly addressing the action without unnecessary formalities

        Provide a JSON response with the following structure:
        {{
            "immediate_action": {{
                "needed": boolean,
                "description": "Description of the immediate action (if needed)",
                "response": "The generated response for the immediate action",
                "execution_time": "Immediately"
            }},
            "delayed_action": {{
                "needed": boolean,
                "description": "Description of the delayed task, including check-ins or scheduled actions",
                "execution_time": "When to perform the task (use only these formats: '5 minutes', '2 hours', '1 day', '9am tomorrow', or 'daily at 9am')"
            }}
        }}

        If you feel that responding would be inappropriate or goes against your personality or goals, set both "needed" fields to false.

        Conversation:
        {formatted_messages}

        JSON response:
        """

    def _is_rejection_response(self, response: str) -> bool:
        rejection_phrases = [
            "I apologize",
            "I'm sorry",
            "I don't feel comfortable",
            "I cannot",
            "I will not"
        ]
        return any(phrase.lower() in response.lower() for phrase in rejection_phrases)

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
                        'response': parsed_response['immediate_action']['response'],
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

    def _parse_execution_time(self, time_str: str) -> pd.Timestamp:
        now = pd.Timestamp.now()
        time_str = time_str.lower()
        
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
        elif 'daily' in time_str:
            time_parts = time_str.split()
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
                
                next_occurrence = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_occurrence <= now:
                    next_occurrence += pd.Timedelta(days=1)
                return next_occurrence
            else:
                return now.replace(hour=9, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
        else:
            raise ValueError(f"Unable to parse execution time: {time_str}")

    def _format_thread_messages(self) -> str:
        if not self.current_thread:
            return ""
        formatted_messages = []
        for message in self.current_thread['messages']:
            user_type = "Bot" if message.get('is_bot', False) else "Human"
            username = message['username'] if message.get('is_bot', False) else message['user']
            formatted_messages.append(f"{user_type} {username} ({message['minutes_ago']} minutes ago): {message['text']}")
        return "\n".join(formatted_messages)