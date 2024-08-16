# db.py

import json
import pandas as pd
from typing import List, Dict, Any, Tuple

class ActionDatabase:
    def __init__(self, file_path='actions.json'):
        self.file_path = file_path
        self.actions = self.load_actions()

    def load_actions(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            return {str(k): v for k, v in data.items()}
        except FileNotFoundError:
            return {}

    def save_actions(self):
        serializable_actions = {str(k): v for k, v in self.actions.items()}
        with open(self.file_path, 'w') as f:
            json.dump(serializable_actions, f, indent=2, default=str)

    def add_action(self, thread_id: str, channel: str, description: str, execution_time: pd.Timestamp):
        action = {
            "channel": channel,
            "description": description,
            "execution_time": execution_time.isoformat()
        }
        thread_id_str = str(thread_id)
        if thread_id_str not in self.actions:
            self.actions[thread_id_str] = []
        
        # Enforce one delayed action per thread constraint
        if len(self.actions[thread_id_str]) > 0:
            # Replace the existing action
            self.actions[thread_id_str] = [action]
        else:
            self.actions[thread_id_str].append(action)
        
        self.save_actions()
        print(f"Debug - Added action due at: {execution_time}")

    def get_actions(self, thread_id: str) -> List[Dict[str, Any]]:
        return self.actions.get(str(thread_id), [])

    def remove_action(self, thread_id: str, description: str):
        thread_id_str = str(thread_id)
        if thread_id_str in self.actions:
            self.actions[thread_id_str] = [action for action in self.actions[thread_id_str] if action['description'] != description]
            if not self.actions[thread_id_str]:
                del self.actions[thread_id_str]
            self.save_actions()
            return True
        return False

    def get_due_actions(self, current_time: pd.Timestamp) -> List[Tuple[str, Dict[str, Any]]]:
        due_actions = []
        for thread_id, actions in self.actions.items():
            for action in actions:
                if pd.Timestamp(action['execution_time']) <= current_time:
                    due_actions.append((thread_id, action))
        return due_actions

    def get_all_thread_ids(self) -> List[str]:
        return list(self.actions.keys())

    def get_actions_by_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        all_actions = []
        for thread_id, actions in self.actions.items():
            for action in actions:
                action_copy = action.copy()
                action_copy['thread_id'] = thread_id
                all_actions.append(action_copy)
        return all_actions