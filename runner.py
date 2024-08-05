import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor
import pandas as pd

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
            print(f"Found {len(threads)} threads with new messages.")

            for thread in threads:
                if not thread['messages'][-1]['is_bot']:
                    print(f"Reviewing thread in channel: {thread['channel']}")
                    result = llm_interactor.review_and_remind(thread)
                    
                    if result['new_items']:
                        print(f"New action items identified: {', '.join(result['new_items'])}")
                    
                    time_since_last_activity = result['time_since_last_activity']
                    if time_since_last_activity > pd.Timedelta(days=1):
                        if result['reminders'] != "No reminders needed at this time.":
                            print(f"Thread inactive for {time_since_last_activity}. Posting reminder to Slack...")
                            interactor.post_thread_reply(thread, result['reminders'])
                            print("Reminder posted successfully.")
                        else:
                            print("No open items to remind about in this thread.")
                    else:
                        print(f"Thread active within last 24 hours (last activity: {time_since_last_activity} ago). No reminder sent.")

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