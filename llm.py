import os
import json
import re
from typing import Dict, List, Any, Tuple
import anthropic
from db import ActionDatabase
import pandas as pd

class LLMInteractor:
    def __init__(self, slack_interactor):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"
        self.action_db = ActionDatabase()
        self.slack_interactor = slack_interactor

    def process_thread(self, thread: Dict[str, Any], return_raw_response: bool = False) -> Dict[str, Any]:
        conversation = self._format_thread(thread)
        thread_id = thread['thread_ts']
        channel = thread['channel']
        raw_response = self._get_llm_response(self._generate_action_prompt(conversation))
        
#         print(f"Debug: Raw LLM response:\n{raw_response}")  # Debug output
        
        actions = self._extract_actions_from_response(raw_response)
        
#         print(f"Debug: Extracted actions: {actions}")  # Debug output
        
        immediate_action = next((action for action in actions if action['type'] == 'immediate'), None)
        delayed_action = next((action for action in actions if action['type'] == 'delayed'), None)
        
        executed_actions = []
        new_actions = []

        if immediate_action:
            executed_actions.append(self._execute_immediate_action(thread, immediate_action))
        
        if delayed_action:
            print(f"Debug: Processing delayed action: {delayed_action}")  # Debug output
            execution_time = self._parse_execution_time(delayed_action['execution_time'])
            action_description = f"Delayed task: {delayed_action['description']}"
            self.action_db.add_action(thread_id, channel, action_description, execution_time)
            new_actions.append(f"{action_description} (Execute at: {execution_time})")

        result = {
            'executed_actions': executed_actions,
            'new_actions': new_actions,
        }

        if return_raw_response:
            return result, raw_response
        else:
            return result

    def _execute_immediate_action(self, thread: Dict[str, Any], action: Dict[str, Any]) -> str:
        response = self.generate_action_response(thread['thread_ts'], action)
        self.slack_interactor.post_thread_reply(thread, response)
        return f"Executed immediate action: {action['description']}"

    def _generate_action_prompt(self, conversation: str) -> str:
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

        Guidelines:
        1. Consider the entire conversation history when making decisions.
        2. Immediate actions are only for direct requests to 'agentflow' that need to be done right away.
        3. Use delayed actions for any task that should be performed in the future, including check-ins, reminders, and scheduled tasks.
        4. Choose appropriate execution times for delayed actions based on the context of the conversation.
        5. If no action is needed, set both 'needed' fields to false.

        Provide only the JSON response without any additional text or explanation.

        Conversation:
        {conversation}

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

    def _parse_execution_time(self, time_str: str) -> pd.Timestamp:
        now = pd.Timestamp.now()
        print(f"Debug: Parsing execution time: '{time_str}'")  # Debug output
        
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
            # Handle cases like "9am tomorrow", "tomorrow at 9am", "9:00 tomorrow", etc.
            time_parts = time_str.replace(',', '').split()
            print(f"Debug: Time parts: {time_parts}")  # Debug output
            
            # Find the time within the string
            time_index = next((i for i, part in enumerate(time_parts) if ':' in part or 'am' in part or 'pm' in part), None)
            
            if time_index is not None:
                time_part = time_parts[time_index]
                print(f"Debug: Found time part: {time_part}")  # Debug output
                
                if ':' in time_part:
                    hour, minute = map(int, time_part.replace('am', '').replace('pm', '').split(':'))
                else:
                    hour = int(time_part.replace('am', '').replace('pm', ''))
                    minute = 0
                
                if 'pm' in time_part and hour < 12:
                    hour += 12
                
                return (now + pd.Timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                print(f"Debug: No specific time found, defaulting to 9am")  # Debug output
                return (now + pd.Timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            print(f"Warning: Could not parse execution time '{time_str}'. Defaulting to 1 hour from now.")
            return now + pd.Timedelta(hours=1)

    def generate_action_response(self, thread_id: str, action: Dict[str, Any]) -> str:
        action_prompt = f"""
        Generate a response for the following action in a Slack conversation:
        - Keep it brief and to the point
        - Use a conversational tone
        - Don't use a formal letter structure or signature
        - Include an emoji or two if appropriate
        - Directly address the action without unnecessary formalities

        Action: {action['description']}

        Slack message:
        """
        return self._get_llm_response(action_prompt)

    def _get_llm_response(self, prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""

    def _format_thread(self, thread: Dict[str, Any]) -> str:
        formatted_messages = []
        for message in thread['messages']:
            user_type = "Human" if not message['is_bot'] else "AI"
            formatted_messages.append(f"{user_type} ({message['minutes_ago']} minutes ago): {message['text']}")
        return "\n".join(formatted_messages)