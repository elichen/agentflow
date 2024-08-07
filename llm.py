import os
import json
from typing import Dict, List, Any, Tuple
import anthropic
from db import ActionItemDatabase
import pandas as pd

class LLMInteractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"
        self.action_db = ActionItemDatabase()

    def review_and_remind(self, thread: Dict[str, Any], return_raw_response: bool = False) -> Dict[str, Any]:
        conversation = self._format_thread(thread)
        thread_id = thread['thread_ts']
        channel = thread['channel']
        last_activity = pd.Timestamp(thread['messages'][-1]['ts'])
        time_since_last_activity = pd.Timestamp.now() - last_activity
        raw_response = self._get_llm_response(self._generate_review_prompt(conversation))
        try:
            parsed_response = json.loads(raw_response)
        except json.JSONDecodeError:
            print(f"Error: Unable to parse LLM response as JSON. Raw response:\n{raw_response}")
            action_items = self._extract_action_items(raw_response)
            completed_tasks = self._extract_completed_tasks(raw_response)
            parsed_response = {"action_items": action_items, "completed_tasks": completed_tasks}
        self._check_completed_items(thread_id, parsed_response.get('completed_tasks', []))
        new_items = self._identify_new_items(thread_id, channel, parsed_response.get('action_items', []))
        if time_since_last_activity > pd.Timedelta(days=1):
            reminders = self._generate_reminders(thread_id)
        else:
            reminders = "No reminders needed at this time."
        result = {
            'new_items': new_items,
            'reminders': reminders,
            'time_since_last_activity': time_since_last_activity
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
            ],
            "completed_tasks": [
                "Description of completed task"
            ]
        }}
        Include in "action_items":
        - Direct requests or assignments
        - Indirect requests or questions that require action
        - Suggestions that imply action
        If no action items are found or no tasks are completed, return empty arrays for the respective fields.
        Conversation:
        {conversation}
        JSON response:
        """

    def _check_completed_items(self, thread_id: str, completed_tasks: List[str]):
        for task in completed_tasks:
            print(f"Debug - Marking as completed: {task}")
            self.action_db.update_item_status(thread_id, task, 'closed')
        print(f"Debug - Total completed items: {len(completed_tasks)}")

    def _identify_new_items(self, thread_id: str, channel: str, action_items: List[Dict[str, str]]) -> List[str]:
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

    def _generate_reminders(self, thread_id: str) -> str:
        open_items = [item for item in self.action_db.get_items(thread_id) if item['status'] == 'open']
        if not open_items:
            return "No reminders needed at this time."
        reminder_prompt = f"""
        Generate a friendly reminder for the following open action items. The reminder should encourage action without being pushy or nagging:
        {', '.join([item['description'] for item in open_items])}
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
            if line.strip().lower().startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")):
                action_items.append({"description": line.strip()[2:], "assignee": "Unassigned"})
        return action_items

    def _extract_completed_tasks(self, raw_response: str) -> List[str]:
        completed_tasks = []
        for line in raw_response.split('\n'):
            if "completed" in line.lower() or "done" in line.lower():
                completed_tasks.append(line.strip())
        return completed_tasks