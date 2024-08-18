# runner.py

import time
import sys
from typing import List, Dict, Any
import pandas as pd
from slack import SlackInteractor
from claude_llm import ClaudeLLM
from project_manager_agent import ProjectManagerAgent
from sarcastic_agent import SarcasticAgent
from db import ActionDatabase

SLEEP_PERIOD = 60  # 1 minute for more frequent checks

def process_threads(project_manager: ProjectManagerAgent, sarcastic_agent: SarcasticAgent, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    
    for thread in threads:
        print(f"\n{'='*50}")
        print(f"Processing thread in channel: {thread['channel']}")
        print(f"Thread timestamp: {thread['thread_ts']}")
        print(f"Last message content:\n{thread['messages'][-1]['text']}")
        
        # Process with ProjectManagerAgent
        project_manager.read_thread(thread)
        action_needed, immediate_action, delayed_action = project_manager.decide_action()
        
        thread_result = {
            'channel': thread['channel'],
            'thread_ts': thread['thread_ts'],
            'executed_actions': [],
            'new_actions': [],
        }
        
        if immediate_action:
            result = project_manager.execute_immediate_action(immediate_action)
            thread_result['executed_actions'].append(result)
            print(f"\nExecuted immediate action: {result}")
        
        if delayed_action:
            project_manager.schedule_delayed_action(delayed_action)
            thread_result['new_actions'].append(f"Scheduled: {delayed_action['description']} (Execute at: {delayed_action['execution_time']})")
            print(f"\nNew action scheduled: {delayed_action['description']}")
        
        sarcastic_agent.read_thread(thread)
        sarcasm_action_needed, sarcasm_immediate_action, _ = sarcastic_agent.decide_action()
        
        if sarcasm_action_needed and sarcasm_immediate_action:
            result = sarcastic_agent.execute_immediate_action(sarcasm_immediate_action)
            thread_result['executed_actions'].append(result)
            print(f"\nExecuted sarcastic action as {sarcastic_agent.username}: {result}")
        
        if not action_needed and not sarcasm_action_needed:
            print("\nNo actions needed.")
        
        results.append(thread_result)
        
        print(f"{'='*50}\n")
    
    return results

def execute_due_actions(agent: ProjectManagerAgent):
    current_time = pd.Timestamp.now()
    due_actions = agent.action_db.get_due_actions(current_time)
    for thread_id, action in due_actions:
        print(f"\nExecuting delayed action for thread: {thread_id}")
        print(f"Action: {action['description']}")
        
        thread = agent.slack_interactor.fetch_thread(thread_id)
        if thread:
            agent.read_thread(thread)
            response = agent._generate_action_response(action)
            agent.slack_interactor.post_thread_reply(thread, response, username=agent.username)
            print(f"Posted response in thread: {thread_id}")
            
            agent.action_db.remove_action(thread_id, action['description'])
            print(f"Removed executed action from database")
        else:
            print(f"Could not fetch thread {thread_id} for action execution")

def main():
    slack_interactor = SlackInteractor()
    llm = ClaudeLLM()
    action_db = ActionDatabase()
    project_manager = ProjectManagerAgent(llm, action_db, slack_interactor)
    sarcastic_agent = SarcasticAgent(llm, action_db, slack_interactor)

    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            print("\nFetching new messages...")
            data = slack_interactor.fetch_new_messages()
            threads = slack_interactor.organize_threads(data)
            print(f"Found {len(threads)} threads with new messages.")

            results = process_threads(project_manager, sarcastic_agent, threads)
            
            print("\nChecking for due actions...")
            execute_due_actions(project_manager)
            
            time.sleep(SLEEP_PERIOD)

        except KeyboardInterrupt:
            print("\nInterrupted by user. Shutting down...")
            sys.exit(0)

        except Exception as e:
            print(f"An error occurred: {e}")
            print(f"Waiting for {SLEEP_PERIOD} seconds before retrying...")
            time.sleep(SLEEP_PERIOD)

if __name__ == "__main__":
    main()