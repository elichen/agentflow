import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor
import pandas as pd
from typing import List, Dict, Any

SLEEP_PERIOD = 60  # 1 minute for more frequent checks

def process_threads(interactor: SlackInteractor, llm_interactor: LLMInteractor, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    
    for thread in threads:
        print(f"\n{'='*50}")
        print(f"Processing thread in channel: {thread['channel']}")
        print(f"Thread timestamp: {thread['thread_ts']}")
        print(f"Last message content:\n{thread['messages'][-1]['text']}")
        
        result, raw_llm_response = llm_interactor.process_thread(thread, return_raw_response=True)
        
        print(f"\nRaw LLM Response:\n{raw_llm_response}")
        
        thread_result = {
            'channel': thread['channel'],
            'thread_ts': thread['thread_ts'],
            'executed_actions': result['executed_actions'],
            'new_actions': result['new_actions'],
        }
        
        if result['executed_actions']:
            for action in result['executed_actions']:
                print(f"\nExecuted action: {action}")
        
        if result['new_actions']:
            for action in result['new_actions']:
                print(f"\nNew action scheduled: {action}")
        
        if not result['executed_actions'] and not result['new_actions']:
            print("\nNo actions needed.")
        
        results.append(thread_result)
        
        print(f"{'='*50}\n")
    
    return results

def execute_due_actions(interactor: SlackInteractor, llm_interactor: LLMInteractor):
    current_time = pd.Timestamp.now()
    due_actions = llm_interactor.action_db.get_due_actions(current_time)
    for thread_id, action in due_actions:
        print(f"\nExecuting action for thread: {thread_id}")
        print(f"Action: {action['description']}")
        
        thread = interactor.fetch_thread(thread_id)
        if thread:
            response = llm_interactor.generate_action_response(thread_id, action)
            interactor.post_thread_reply(thread, response)
            print(f"Posted response in thread: {thread_id}")
            
            llm_interactor.action_db.remove_action(thread_id, action['description'])
            print(f"Removed executed action from database")
        else:
            print(f"Could not fetch thread {thread_id} for action execution")

def main():
    interactor = SlackInteractor()
    llm_interactor = LLMInteractor(interactor)

    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            print("\nFetching new messages...")
            data = interactor.fetch_new_messages()
            threads = interactor.organize_threads(data)
            print(f"Found {len(threads)} threads with new messages.")

            results = process_threads(interactor, llm_interactor, threads)
            
            print("\nChecking for due actions...")
            execute_due_actions(interactor, llm_interactor)
            
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