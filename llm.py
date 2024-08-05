import os
from typing import Dict, List, Any
import anthropic
from db import ActionItemDatabase
import pandas as pd

class LLMInteractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-3-opus-20240229"
        self.action_db = ActionItemDatabase()

    def review_and_remind(self, thread: Dict[str, Any]) -> Dict[str, Any]:
        conversation = self._format_thread(thread)
        thread_id = thread['thread_ts']
        channel = thread['channel']

        # Check if the thread has been inactive for more than a day
        last_activity = pd.Timestamp(thread['messages'][-1]['ts'])
        time_since_last_activity = pd.Timestamp.now() - last_activity

        # Check for completed items
        self._check_completed_items(thread_id, conversation)

        # Identify new action items
        new_items = self._identify_new_items(thread_id, channel, conversation)

        # Generate reminders for open items only if thread is inactive for more than a day
        if time_since_last_activity > pd.Timedelta(days=1):
            reminders = self._generate_reminders(thread_id)
        else:
            reminders = "No reminders needed at this time."

        return {
            'new_items': new_items,
            'reminders': reminders,
            'time_since_last_activity': time_since_last_activity
        }

    def _check_completed_items(self, thread_id: str, conversation: str):
        completion_prompt = f"""
        Analyze the following conversation and determine if any previously mentioned tasks or action items have been completed.
        If a task appears to be completed, respond with the task description. If no tasks are completed, respond with "No completed tasks".

        Conversation:
        {conversation}

        Completed tasks (if any):
        """

        response = self._get_llm_response(completion_prompt)
        if response != "No completed tasks":
            for item in response.split('\n'):
                self.action_db.update_item_status(thread_id, item.strip(), 'closed')

    def _identify_new_items(self, thread_id: str, channel: str, conversation: str) -> List[str]:
        identification_prompt = f"""
        Analyze the following conversation and identify any new tasks, action items, or requests that have been made.
        For each new item, provide a brief description. If no new items are found, respond with "No new items".

        Conversation:
        {conversation}

        New action items (if any):
        """

        response = self._get_llm_response(identification_prompt)
        new_items = []
        if response != "No new items":
            for item in response.split('\n'):
                self.action_db.add_item(thread_id, channel, item.strip())
                new_items.append(item.strip())
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