# runner.py

import time
import sys
from typing import List, Dict, Any
import pandas as pd
from slack import SlackInteractor
from claude_llm import ClaudeLLM
from project_manager_agent import ProjectManagerAgent
from sarcastic_agent import SarcasticAgent
from paul_graham_agent import PaulGrahamAgent  # Add this import
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
    action_db = agents[0].action_db  # Assuming all agents share the same action_db
    due_actions = action_db.get_due_actions(current_time)
    
    for thread_id, action in due_actions:
        agent_name = action['agent_name']
        agent = next((a for a in agents if a.get_name() == agent_name), None)
        
        if agent:
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
                
                action_db.remove_action(thread_id, action['description'])
                print(f"Removed executed action from database")
            else:
                print(f"Could not fetch thread {thread_id} for action execution")
        else:
            print(f"Could not find agent {agent_name} for executing action in thread: {thread_id}")

def main():
    workspaces = CONFIG['workspaces']
    slack_interactors = {
        workspace_config['name']: SlackInteractor(workspace_config)
        for _, workspace_config in workspaces.items()
    }
    llm = ClaudeLLM()

    agents = {}
    for workspace_name, slack_interactor in slack_interactors.items():
        action_db = ActionDatabase(workspace_name)
        agents[workspace_name] = [
            ProjectManagerAgent(llm, action_db, slack_interactor, workspace_name=workspace_name),
            SarcasticAgent(llm, action_db, slack_interactor, workspace_name=workspace_name),
            PaulGrahamAgent(llm, action_db, slack_interactor, workspace_name=workspace_name)
        ]
    
    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            for workspace_name, slack_interactor in slack_interactors.items():
                print(f"\nFetching new messages for workspace: {workspace_name}")
                data = slack_interactor.fetch_new_user_messages()
                threads = slack_interactor.organize_threads(data)
                print(f"Found {len(threads)} threads with new user messages in {workspace_name}.")

                if not slack_interactor.is_first_run:
                    results = process_threads(agents[workspace_name], threads)
                    print(f"\nChecking for due actions in {workspace_name}...")
                    execute_due_actions(agents[workspace_name])
                else:
                    print(f"First run for {workspace_name}. Skipping thread processing and due actions.")
                    slack_interactor.is_first_run = False
        
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