import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta
import pandas as pd

from slack import SlackInteractor
from claude_llm import ClaudeLLM
from project_manager_agent import ProjectManagerAgent
from db import ActionDatabase
from runner import process_threads, execute_due_actions

class SlackBotSanityTests(unittest.TestCase):

    def setUp(self):
        self.slack_interactor = MagicMock(spec=SlackInteractor)
        self.llm = MagicMock(spec=ClaudeLLM)
        self.action_db = ActionDatabase('test_actions.json')
        self.agent = ProjectManagerAgent(self.llm, self.action_db, self.slack_interactor)

    def tearDown(self):
        # Clean up the test database
        import os
        if os.path.exists('test_actions.json'):
            os.remove('test_actions.json')

    def test_action_scheduling(self):
        # Simulate scheduling an action
        thread_id = "2024-08-12 22:43:44.565398932"
        thread = {
            "channel": "agentflow",
            "thread_ts": thread_id,
            "messages": [
                {
                    "text": "Schedule a joke for tomorrow",
                    "user": "U123456",
                    "ts": thread_id,
                    "minutes_ago": 5
                }
            ]
        }
        
        self.llm.generate_response.return_value = json.dumps({
            "delayed_action": {
                "needed": True,
                "description": "Delayed task: Tell a joke to the human",
                "execution_time": "2024-08-17T09:00:00"
            }
        })

        self.agent.read_thread(thread)
        _, _, delayed_action = self.agent.decide_action()
        self.agent.schedule_delayed_action(delayed_action)

        # Verify the action was scheduled correctly
        actions = self.action_db.get_actions(thread_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['description'], "Delayed task: Tell a joke to the human")
        self.assertEqual(actions[0]['channel'], "agentflow")
        self.assertEqual(pd.Timestamp(actions[0]['execution_time']), pd.Timestamp("2024-08-17T09:00:00"))

    def test_due_action_execution(self):
        # Schedule an action that's due
        thread_id = "2024-08-12 22:43:44.565398932"
        due_time = datetime.now() + timedelta(seconds=1)
        self.action_db.add_action(thread_id, "agentflow", "Delayed task: Tell a joke to the human", pd.Timestamp(due_time))

        # Wait for the action to become due
        import time
        time.sleep(2)

        # Mock fetch_thread to return a valid thread
        self.slack_interactor.fetch_thread.return_value = {
            "channel": "agentflow",
            "thread_ts": thread_id,
            "messages": [{"text": "Previous message"}]
        }

        # Simulate executing the due action
        execute_due_actions(self.agent)

        # Verify the action was removed after execution
        actions = self.action_db.get_actions(thread_id)
        self.assertEqual(len(actions), 0)
        self.slack_interactor.post_thread_reply.assert_called_once()

    def test_thread_processing(self):
        # Simulate a thread with a new message
        thread = {
            "channel": "agentflow",
            "thread_ts": "2024-08-12 22:43:44.565398932",
            "messages": [
                {
                    "text": "Hello, can you schedule a joke for tomorrow?",
                    "user": "U123456",
                    "ts": "2024-08-12 22:43:44.565398932",
                    "minutes_ago": 5
                }
            ]
        }

        # Mock the LLM response to schedule a delayed action
        self.llm.generate_response.return_value = json.dumps({
            "delayed_action": {
                "needed": True,
                "description": "Delayed task: Tell a joke to the human",
                "execution_time": "2024-08-13T09:00:00"
            }
        })

        # Process the thread
        results = process_threads(self.agent, [thread])

        # Verify that a delayed action was scheduled
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]['new_actions']), 1)
        self.assertTrue("Scheduled: Delayed task: Tell a joke to the human" in results[0]['new_actions'][0])

    def test_one_delayed_action_per_thread(self):
        thread_id = "2024-08-12 22:43:44.565398932"
        
        # Schedule first action
        self.action_db.add_action(thread_id, "agentflow", "Delayed task: Tell a joke to the human", pd.Timestamp("2024-08-17T09:00:00"))
        
        # Try to schedule a second action for the same thread
        self.action_db.add_action(thread_id, "agentflow", "Delayed task: Remind about the meeting", pd.Timestamp("2024-08-18T10:00:00"))

        # Verify that only one action is scheduled
        actions = self.action_db.get_actions(thread_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['description'], "Delayed task: Remind about the meeting")

    def test_delayed_action_with_timestamp(self):
        thread_id = pd.Timestamp.now().isoformat()
        thread = {
            "channel": "agentflow",
            "thread_ts": thread_id,
            "messages": [
                {
                    "text": "Everyone, what do you want to eat for lunch?",
                    "user": "U123456",
                    "ts": thread_id,
                    "minutes_ago": 0
                }
            ]
        }
        
        self.llm.generate_response.return_value = json.dumps({
            "delayed_action": {
                "needed": True,
                "description": "Remind about lunch decision",
                "execution_time": "1 hour"
            }
        })

        self.agent.read_thread(thread)
        _, _, delayed_action = self.agent.decide_action()
        
        # This should not raise a TypeError
        self.agent.schedule_delayed_action(delayed_action)

        # Verify the action was scheduled correctly
        actions = self.action_db.get_actions(thread_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['description'], "Remind about lunch decision")
        self.assertEqual(actions[0]['channel'], "agentflow")

        # Verify that the action can be saved and loaded without errors
        self.action_db.save_actions()
        loaded_actions = self.action_db.load_actions()
        self.assertIn(thread_id, loaded_actions)
        
if __name__ == '__main__':
    unittest.main()