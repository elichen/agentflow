import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor
import pandas as pd
from typing import List, Dict, Any

SLEEP_PERIOD = 300

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
            'new_items': result['new_items'],
        }
        
        if result['new_items']:
            print(f"\nNew action items identified: {', '.join(result['new_items'])}")
        else:
            print("\nNo new action items identified.")
        
        results.append(thread_result)
        
        print(f"{'='*50}\n")
    
    return results

def check_and_post_reminders(interactor: SlackInteractor, llm_interactor: LLMInteractor):
    due_items = llm_interactor.action_db.get_due_items()
    for thread_id, item in due_items:
        reminder = llm_interactor.generate_reminder(thread_id, item)
        thread = interactor.fetch_thread(thread_id)
        if thread:
            interactor.post_thread_reply(thread, reminder)
            print(f"Posted reminder for item: {item['description']} in thread: {thread_id}")
        else:
            print(f"Could not fetch thread {thread_id} for reminder")

def main():
    interactor = SlackInteractor()
    llm_interactor = LLMInteractor()

    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            print("\nFetching new messages...")
            data = interactor.fetch_new_messages()
            threads = interactor.organize_threads(data)
            print(f"Found {len(threads)} threads with new messages.")

            results = process_threads(interactor, llm_interactor, threads)
            
            print("\nChecking for due items and posting reminders...")
            check_and_post_reminders(interactor, llm_interactor)
            
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