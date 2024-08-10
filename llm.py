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
        Analyze the following conversation carefully. Consider the entire thread history when making decisions. Determine if any immediate action is needed or if a check-in should be scheduled. Consider the following:

        1. Immediate actions: Tasks that need to be done right away based on direct messages to the bot 'agentflow'.
        2. Check-ins: For requests or tasks assigned to specific team members or broadly to the team that haven't been fully addressed or resolved.

        Provide a JSON response with the following structure:
        {{
            "immediate_action": {{
                "needed": boolean,
                "description": "Description of the immediate action for agentflow (if needed)",
                "execution_time": "Time to execute the action (e.g., '5 minutes', '1 hour')"
            }},
            "check_in": {{
                "needed": boolean,
                "description": "Description of what to check or follow up on",
                "execution_time": "When to perform the check-in (e.g., '2 hours', '1 day')"
            }}
        }}

        Guidelines:
        1. Consider the entire conversation history when making decisions.
        2. Immediate actions are only for direct requests to 'agentflow'.
        3. For team tasks or requests, suggest a check-in only if the matter hasn't been fully resolved or addressed.
        4. Choose appropriate check-in times based on the urgency and context of the conversation.
        5. If no action or check-in is needed (e.g., the matter has been resolved), set both 'needed' fields to false.

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
                        'execution_time': parsed_response['immediate_action']['execution_time']
                    })
                if parsed_response.get('check_in', {}).get('needed', False):
                    actions.append({
                        'type': 'check_in',
                        'description': parsed_response['check_in']['description'],
                        'execution_time': parsed_response['check_in']['execution_time']
                    })
                return actions
            else:
                raise ValueError("No JSON found in the response")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON: {e}")
            print(f"Raw response:\n{raw_response}")
            return []

    def _process_actions(self, thread_id: str, channel: str, actions: List[Dict[str, Any]]) -> List[str]:
        new_actions = []
        for action in actions:
            execution_time = self._parse_execution_time(action['execution_time'])
            action_description = f"{action['type'].capitalize()}: {action['description']}"
            self.action_db.add_action(thread_id, channel, action_description, execution_time)
            new_actions.append(f"{action_description} (Execute at: {execution_time})")
        
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