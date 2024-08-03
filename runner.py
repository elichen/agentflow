import time
import sys
from slack import SlackInteractor
from llm import LLMInteractor

SLEEP_PERIOD = 300

def main():
    interactor = SlackInteractor()
    llm_interactor = LLMInteractor()
    guideline_prompt = "Please provide a helpful and concise response to the conversation above."

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
                    response = llm_interactor.review_and_remind(thread)
                    if response != "No reminders needed at this time.":
                        print("Posting reminder to Slack...")
                        interactor.post_thread_reply(thread, response)
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
