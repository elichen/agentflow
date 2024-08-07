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

    def add_item(self, thread_id, channel, description):
        created = pd.Timestamp.now()
        due = created + pd.Timedelta(minutes=1)  # Changed to 1 minute for debugging
        thread_ts = pd.Timestamp(thread_id)
        if thread_ts not in self.action_items:
            self.action_items[thread_ts] = []
        self.action_items[thread_ts].append({
            'channel': channel,
            'description': description,
            'created': created.isoformat(),
            'due': due.isoformat()
        })
        self.save_items()
        print(f"Debug - Added item due at: {due}")  # Added debug print

    def get_items(self, thread_id):
        thread_ts = pd.Timestamp(thread_id)
        return self.action_items.get(thread_ts, [])

    def delete_item(self, thread_id, description):
        thread_ts = pd.Timestamp(thread_id)
        if thread_ts in self.action_items:
            self.action_items[thread_ts] = [item for item in self.action_items[thread_ts] if item['description'] != description]
            if not self.action_items[thread_ts]:
                del self.action_items[thread_ts]
            self.save_items()
            return True
        return False

    def delete_thread_items(self, thread_id):
        thread_ts = pd.Timestamp(thread_id)
        if thread_ts in self.action_items:
            del self.action_items[thread_ts]
            self.save_items()
            return True
        return False

    def get_all_thread_ids(self):
        return [str(thread_id) for thread_id in self.action_items.keys()]

    def get_due_items(self):
        now = pd.Timestamp.now()
        due_items = []
        for thread_id, items in self.action_items.items():
            for item in items:
                if pd.Timestamp(item['due']) <= now:
                    due_items.append((thread_id, item))
        return due_items