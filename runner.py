import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor
import pandas as pd
from typing import List, Dict, Any

SLEEP_PERIOD = 300

def process_threads(interactor: SlackInteractor, llm_interactor: LLMInteractor, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    open_thread_ids = llm_interactor.action_db.get_all_open_thread_ids()
    all_thread_ids = set([thread['thread_ts'] for thread in threads] + open_thread_ids)
    
    for thread_id in all_thread_ids:
        thread = next((t for t in threads if t['thread_ts'] == thread_id), None)
        if thread is None:
            thread = interactor.fetch_thread(thread_id)
        
        if thread:
            print(f"\n{'='*50}")
            print(f"Reviewing thread in channel: {thread['channel']}")
            print(f"Thread timestamp: {thread['thread_ts']}")
            print(f"Last message content:\n{thread['messages'][-1]['text']}")
            
            result, raw_llm_response = llm_interactor.review_and_remind(thread, return_raw_response=True)
            
            print(f"\nRaw LLM Response:\n{raw_llm_response}")
            
            thread_result = {
                'channel': thread['channel'],
                'thread_ts': thread['thread_ts'],
                'new_items': result['new_items'],
                'reminders': result['reminders'],
                'time_since_last_activity': result['time_since_last_activity'],
                'reminder_sent': False
            }
            
            if result['new_items']:
                print(f"\nNew action items identified: {', '.join(result['new_items'])}")
            else:
                print("\nNo new action items identified.")
            
            time_since_last_activity = result['time_since_last_activity']
            if time_since_last_activity > pd.Timedelta(days=1):
                if result['reminders'] != "No reminders needed at this time.":
                    print(f"Thread inactive for {time_since_last_activity}. Reminder content:")
                    print(result['reminders'])
                    thread_result['reminder_sent'] = True
                else:
                    print("No open items to remind about in this thread.")
            else:
                print(f"Thread active within last 24 hours (last activity: {time_since_last_activity} ago). No reminder sent.")
            
            results.append(thread_result)
        else:
            print(f"Could not fetch thread {thread_id}")
        
        print(f"{'='*50}\n")
    
    return results

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