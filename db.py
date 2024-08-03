import json
from datetime import datetime, timedelta

class ActionItemDatabase:
    def __init__(self, file_path='action_items.json'):
        self.file_path = file_path
        self.action_items = self.load_items()

    def load_items(self):
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_items(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.action_items, f, indent=2)

    def add_item(self, thread_id, channel, description, due_days=1):
        created = datetime.now().isoformat()
        due = (datetime.now() + timedelta(days=due_days)).isoformat()
        if thread_id not in self.action_items:
            self.action_items[thread_id] = []
        self.action_items[thread_id].append({
            'channel': channel,
            'description': description,
            'created': created,
            'due': due,
            'status': 'open'
        })
        self.save_items()

    def get_items(self, thread_id):
        return self.action_items.get(thread_id, [])

    def update_item_status(self, thread_id, description, status):
        if thread_id in self.action_items:
            for item in self.action_items[thread_id]:
                if item['description'] == description:
                    item['status'] = status
                    self.save_items()
                    return True
        return False

    def get_all_open_thread_ids(self):
        return [thread_id for thread_id, items in self.action_items.items() 
                if any(item['status'] == 'open' for item in items)]
