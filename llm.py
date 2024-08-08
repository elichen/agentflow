import os
import json
import re
from typing import Dict, List, Any, Tuple
import anthropic
from db import ActionDatabase
import pandas as pd

class LLMInteractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"
        self.action_db = ActionDatabase()

    def process_thread(self, thread: Dict[str, Any], return_raw_response: bool = False) -> Dict[str, Any]:
        conversation = self._format_thread(thread)
        thread_id = thread['thread_ts']
        channel = thread['channel']
        raw_response = self._get_llm_response(self._generate_action_prompt(conversation))
        
        actions = self._extract_actions_from_response(raw_response)
        new_actions = self._process_actions(thread_id, channel, actions)

        result = {
            'new_actions': new_actions,
        }

        if return_raw_response:
            return result, raw_response
        else:
            return result

    def _generate_action_prompt(self, conversation: str) -> str:
        return f"""
        Analyze the following conversation and provide a JSON response with the following structure:
        {{
            "action": {{
                "description": "Brief description of the single most important action to take",
                "execution_time": "Time to execute the action (e.g., '5 minutes', '1 hour', '1 day')"
            }}
        }}
        Include only one action that is the most critical or time-sensitive based on the conversation.
        If no action is needed, return an empty object for "action".
        Provide only the JSON response without any additional text or explanation.
        Conversation:
        {conversation}
        JSON response:
        """

    def _extract_actions_from_response(self, raw_response: str) -> List[Dict[str, str]]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                json_str = json_match.group(0)
                parsed_response = json.loads(json_str)
                action = parsed_response.get('action')
                return [action] if action else []
            else:
                raise ValueError("No JSON found in the response")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON: {e}")
            print(f"Raw response:\n{raw_response}")
            return []

    def _process_actions(self, thread_id: str, channel: str, actions: List[Dict[str, str]]) -> List[str]:
        new_actions = []
        for action in actions:
            description = action['description']
            execution_time = self._parse_execution_time(action['execution_time'])
            self.action_db.add_action(thread_id, channel, description, execution_time)
            new_actions.append(f"{description} (Execute at: {execution_time})")
        
        print(f"Debug - Total new actions identified: {len(new_actions)}")
        return new_actions

    def _parse_execution_time(self, time_str: str) -> pd.Timestamp:
        now = pd.Timestamp.now()
        if 'minute' in time_str:
            minutes = int(time_str.split()[0])
            return now + pd.Timedelta(minutes=minutes)
        elif 'hour' in time_str:
            hours = int(time_str.split()[0])
            return now + pd.Timedelta(hours=hours)
        elif 'day' in time_str:
            days = int(time_str.split()[0])
            return now + pd.Timedelta(days=days)
        else:
            # Default to 1 hour if parsing fails
            print(f"Warning: Could not parse execution time '{time_str}'. Defaulting to 1 hour.")
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