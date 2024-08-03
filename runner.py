import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor

SLEEP_PERIOD = 300

def main():
    interactor = SlackInteractor()
    llm_interactor = LLMInteractor()

    print("Slack Bot Runner started. Press Ctrl+C to stop.")

    while True:
        try:
            print("\nFetching new messages...")
            data = interactor.fetch_new_messages()
            threads = interactor.organize_threads(data)
            
            # Get thread IDs with open action items
            open_thread_ids = llm_interactor.action_db.get_all_open_thread_ids()
            
            # Combine new threads and threads with open items
            all_thread_ids = set([thread['thread_ts'] for thread in threads] + open_thread_ids)
            
            print(f"Reviewing {len(all_thread_ids)} threads.")

            for thread_id in all_thread_ids:
                thread = next((t for t in threads if t['thread_ts'] == thread_id), None)
                if thread is None:
                    # Fetch the thread if it's not in the new messages
                    thread = interactor.fetch_thread(thread_id)

                if thread:
                    print(f"Reviewing thread in channel: {thread['channel']}")
                    result = llm_interactor.review_and_remind(thread)
                    
                    if result['new_items']:
                        print(f"New action items identified: {', '.join(result['new_items'])}")
                    
                    if result['reminders'] != "No reminders needed at this time.":
                        print("Posting reminder to Slack...")
                        interactor.post_thread_reply(thread, result['reminders'])
                        print("Reminder posted successfully.")
                    else:
                        print("No reminders needed for this thread.")

            time.sleep(SLEEP_PERIOD)

        except KeyboardInterrupt:
            print("\nInterrupted by user. Shutting down...")
            sys.exit(0)

        except Exception as e:
            print(f"An error occurred: {e}")
            print("Waiting for 5 minutes before retrying...")
            time.sleep(300)

if __name__ == "__main__":
    main()