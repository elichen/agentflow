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
from agent_interface import BaseAgent  # Changed from AgentInterface to BaseAgent
from config import CONFIG

SLEEP_PERIOD = CONFIG['runner']['sleep_period']

def process_threads(agents: List[BaseAgent], threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    
    for thread in threads:
        print(f"\n{'='*50}")
        print(f"Processing thread in channel: {thread['channel']}")
        print(f"Thread timestamp: {thread['thread_ts']}")
        print(f"Last message content:\n{thread['messages'][-1]['text']}")
        
        thread_result = {
            'channel': thread['channel'],
            'thread_ts': thread['thread_ts'],
            'executed_actions': [],
            'new_actions': [],
        }
        
        for agent in agents:
            agent.read_thread(thread)
            action_needed, immediate_action, delayed_action = agent.decide_action()
            
            if immediate_action:
                result = agent.execute_immediate_action(immediate_action)
                thread_result['executed_actions'].append(f"{agent.get_name()}: {result}")
                print(f"\nExecuted immediate action for {agent.get_name()}: {result}")
            
            if delayed_action:
                agent.schedule_delayed_action(delayed_action)
                thread_result['new_actions'].append(f"{agent.get_name()} Scheduled: {delayed_action['description']} (Execute at: {delayed_action['execution_time']})")
                print(f"\nNew action scheduled for {agent.get_name()}: {delayed_action['description']}")
        
        if not thread_result['executed_actions'] and not thread_result['new_actions']:
            print("\nNo actions needed.")
        
        results.append(thread_result)
        
        print(f"{'='*50}\n")
    
    return results

def execute_due_actions(agents: List[BaseAgent]):
    current_time = pd.Timestamp.now()
    for agent in agents:
        due_actions = agent.action_db.get_due_actions(current_time)
        for thread_id, action in due_actions:
            print(f"\nExecuting delayed action for {agent.get_name()} in thread: {thread_id}")
            print(f"Action: {action['description']}")
            
            thread = agent.slack_interactor.fetch_thread(thread_id)
            if thread:
                agent.read_thread(thread)
                prompt = agent._generate_prompt(due_task_description=action['description'])
                llm_response = agent.llm.generate_response(prompt)
                
                if not agent._is_rejection_response(llm_response):
                    actions = agent._extract_actions_from_response(llm_response)
                    immediate_action = next((a for a in actions if a['type'] == 'immediate'), None)
                    
                    if immediate_action:
                        response = immediate_action['response']
                        agent.slack_interactor.post_thread_reply(thread, response, username=agent.get_name())
                        print(f"Posted response in thread: {thread_id}")
                    else:
                        print(f"No immediate action generated for due task in thread: {thread_id}")
                else:
                    print(f"LLM rejected generating a response for due task in thread: {thread_id}")
                
                agent.action_db.remove_action(thread_id, action['description'])
                print(f"Removed executed action from database")
            else:
                print(f"Could not fetch thread {thread_id} for action execution")

def main():
    slack_interactor = SlackInteractor()
    llm = ClaudeLLM()
    action_db = ActionDatabase()
    
    agents = [
        ProjectManagerAgent(llm, action_db, slack_interactor),
        SarcasticAgent(llm, action_db, slack_interactor)
    ]

    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            print("\nFetching new messages...")
            data = slack_interactor.fetch_new_messages()
            threads = slack_interactor.organize_threads(data)
            print(f"Found {len(threads)} threads with new messages.")

            results = process_threads(agents, threads)
            
            print("\nChecking for due actions...")
            execute_due_actions(agents)
            
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