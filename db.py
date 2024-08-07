import json
import pandas as pd

class ActionItemDatabase:
    def __init__(self, file_path='action_items.json'):
        self.file_path = file_path
        self.action_items = self.load_items()

    def load_items(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            return {pd.Timestamp(k): v for k, v in data.items()}
        except FileNotFoundError:
            return {}

    def save_items(self):
        serializable_items = {str(k): v for k, v in self.action_items.items()}
        with open(self.file_path, 'w') as f:
            json.dump(serializable_items, f, indent=2)

    def add_item(self, thread_id, channel, description, due_days=1):
        created = pd.Timestamp.now()
        due = created + pd.Timedelta(days=due_days)
        thread_ts = pd.Timestamp(thread_id)
        if thread_ts not in self.action_items:
            self.action_items[thread_ts] = []
        self.action_items[thread_ts].append({
            'channel': channel,
            'description': description,
            'created': created.isoformat(),
            'due': due.isoformat(),
            'status': 'open'
        })
        self.save_items()

    def get_items(self, thread_id):
        thread_ts = pd.Timestamp(thread_id)
        return self.action_items.get(thread_ts, [])

    def update_item_status(self, thread_id, description, status):
        thread_ts = pd.Timestamp(thread_id)
        if thread_ts in self.action_items:
            for item in self.action_items[thread_ts]:
                if item['description'] == description:
                    item['status'] = status
                    self.save_items()
                    return True
        return False

    def get_all_open_thread_ids(self):
        return [str(thread_id) for thread_id, items in self.action_items.items() 
                if any(item['status'] == 'open' for item in items)]