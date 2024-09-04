# runner.py

import time
import sys
from typing import List, Dict, Any
import pandas as pd
from slack_interactor import SlackInteractor
from claude_llm import ClaudeLLM
from db import ActionDatabase
from config import CONFIG
from agent_interface import BaseAgent
from project_manager_agent import ProjectManagerAgent
from sarcastic_agent import SarcasticAgent
from paul_graham_agent import PaulGrahamAgent
from drunk_agent import DrunkAgent
import random

class Runner:
    def __init__(self):
        self.reset_from_config()

    def reset_from_config(self):
        self.workspaces = CONFIG['workspaces']
        self.slack_interactors = {
            workspace_config['name']: SlackInteractor(workspace_config)
            for workspace_config in self.workspaces
        }
        self.agents = self._initialize_agents()
        self.sleep_period = CONFIG['runner']['sleep_period']

    def _initialize_agents(self):
        agents = {}
        agent_classes = {
            'ProjectManagerAgent': ProjectManagerAgent,
            'SarcasticAgent': SarcasticAgent,
            'PaulGrahamAgent': PaulGrahamAgent,
            'DrunkAgent': DrunkAgent
        }

        for workspace_config in self.workspaces:
            workspace_name = workspace_config['name']
            slack_interactor = self.slack_interactors[workspace_name]
            action_db = ActionDatabase(workspace_name)
            agents[workspace_name] = []

            for agent_config in workspace_config.get('agents', []):
                agent_name = agent_config['name']
                llm_type = agent_config['llm_type']
                if agent_name in agent_classes:
                    agent_class = agent_classes[agent_name]
                    agent = agent_class(llm_type, action_db, slack_interactor, workspace_name=workspace_name)
                    agents[workspace_name].append(agent)
                else:
                    print(f"Warning: Unknown agent type '{agent_name}' for workspace '{workspace_name}'")

        return agents

    def run_one_loop(self):
        for workspace_name, slack_interactor in self.slack_interactors.items():
            print(f"\nFetching new messages for workspace: {workspace_name}")
            data = slack_interactor.fetch_new_user_messages()
            threads = slack_interactor.organize_threads(data)
            print(f"Found {len(threads)} threads with new user messages in {workspace_name}.")

            if not slack_interactor.is_first_run:
                results = self._process_threads(self.agents[workspace_name], threads)
                print(f"\nChecking for due actions in {workspace_name}...")
                self._execute_due_actions(self.agents[workspace_name])
            else:
                print(f"First run for {workspace_name}. Skipping thread processing and due actions.")
                slack_interactor.is_first_run = False

    def main(self):
        print("Slack Bot Runner started. Press Ctrl+C to stop.")

        while True:
            try:
                self.run_one_loop()
                time.sleep(self.sleep_period)
            except KeyboardInterrupt:
                print("\nInterrupted by user. Shutting down...")
                sys.exit(0)
            except Exception as e:
                print(f"An error occurred: {e}")
                print(f"Waiting for {self.sleep_period} seconds before retrying...")
                time.sleep(self.sleep_period)

    def _process_threads(self, agents, threads):
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
            
            # Shuffle the agents list for this thread
            shuffled_agents = random.sample(agents, len(agents))
            
            for agent in shuffled_agents:
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

    def _execute_due_actions(self, agents: List[BaseAgent]):
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

if __name__ == "__main__":
    runner = Runner()
    runner.main()