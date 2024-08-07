import os
import json
import re
from typing import Dict, List, Any, Tuple
import anthropic
from db import ActionItemDatabase
import pandas as pd

class LLMInteractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"
        self.action_db = ActionItemDatabase()

    def process_thread(self, thread: Dict[str, Any], return_raw_response: bool = False) -> Dict[str, Any]:
        conversation = self._format_thread(thread)
        thread_id = thread['thread_ts']
        channel = thread['channel']
        raw_response = self._get_llm_response(self._generate_review_prompt(conversation))
        
        action_items = self._extract_action_items_from_response(raw_response)

        new_items = self._process_action_items(thread_id, channel, action_items)

        result = {
            'new_items': new_items,
        }

        if return_raw_response:
            return result, raw_response
        else:
            return result

    def _generate_review_prompt(self, conversation: str) -> str:
        return f"""
        Analyze the following conversation and provide a JSON response with the following structure:
        {{
            "action_items": [
                {{
                    "description": "Brief description of the action item",
                    "assignee": "Name of the person assigned (if specified), or 'Unassigned'"
                }}
            ]
        }}
        Include in "action_items" only tasks or actions that are not resolved within the conversation.
        If no unresolved action items are found, return an empty array.
        Provide only the JSON response without any additional text or explanation.
        Conversation:
        {conversation}
        JSON response:
        """

    def _extract_action_items_from_response(self, raw_response: str) -> List[Dict[str, str]]:
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                json_str = json_match.group(0)
                parsed_response = json.loads(json_str)
                return parsed_response.get('action_items', [])
            else:
                raise ValueError("No JSON found in the response")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON: {e}")
            print(f"Raw response:\n{raw_response}")
            # Fallback to extracting action items manually
            return self._extract_action_items(raw_response)

    def _process_action_items(self, thread_id: str, channel: str, action_items: List[Dict[str, str]]) -> List[str]:
        existing_items = self.action_db.get_items(thread_id)
        for item in existing_items:
            self.action_db.delete_item(thread_id, item['description'])
        
        new_items = []
        for item in action_items:
            description = item['description']
            assignee = item['assignee']
            action_item = f"{description} (Assignee: {assignee})"
            print(f"Debug - Adding new item: {action_item}")
            self.action_db.add_item(thread_id, channel, action_item)
            new_items.append(action_item)
        
        print(f"Debug - Total new items identified: {len(new_items)}")
        return new_items

    def generate_reminder(self, thread_id: str, item: Dict[str, Any]) -> str:
        reminder_prompt = f"""
        Generate a friendly reminder for the following open action item. The reminder should encourage action without being pushy or nagging:
        {item['description']}
        Reminder:
        """
        return self._get_llm_response(reminder_prompt)

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

    def _extract_action_items(self, raw_response: str) -> List[Dict[str, str]]:
        action_items = []
        for line in raw_response.split('\n'):
            if "description" in line.lower() and "assignee" in line.lower():
                parts = line.split(',')
                if len(parts) >= 2:
                    description = parts[0].split(':')[-1].strip().strip('"')
                    assignee = parts[1].split(':')[-1].strip().strip('"')
                    action_items.append({"description": description, "assignee": assignee})
        return action_items