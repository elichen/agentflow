import os
import time
import random
from typing import List, Dict, Any, Callable
from collections import defaultdict

import pandas as pd
import numpy as np
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tqdm import tqdm

class SlackInteractor:
    def __init__(self, user_token: str = None, bot_token: str = None, max_retries: int = 5, base_delay: float = 1):
        self.user_token = user_token or os.environ.get('SLACK_USER_TOKEN')
        self.bot_token = bot_token or os.environ.get('SLACK_BOT_TOKEN')
        self.user_client = WebClient(token=self.user_token)
        self.bot_client = WebClient(token=self.bot_token)
        self.conversations_oldest = None
        self.max_retries = max_retries
        self.base_delay = base_delay

    def exponential_backoff(self, func: Callable, *args, **kwargs) -> Any:
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    delay = (2 ** attempt + random.random()) * self.base_delay
                    print(f"Rate limited. Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    raise e
        raise Exception(f"Failed after {self.max_retries} attempts")

    @staticmethod
    def paginate(field: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                all_data = []
                response = func(*args, **kwargs)
                all_data.extend(response[field])
                next_cursor = response.data.get('response_metadata', {}).get('next_cursor')
                
                while next_cursor:
                    kwargs['cursor'] = next_cursor
                    response = func(*args, **kwargs)
                    all_data.extend(response[field])
                    next_cursor = response.data.get('response_metadata', {}).get('next_cursor')
                
                return all_data
            return wrapper
        return decorator

    @paginate('channels')
    def fetch_conversations(self, cursor: str = None) -> Dict[str, Any]:
        return self.exponential_backoff(
            self.user_client.conversations_list,
            types='public_channel',
            exclude_archived=True,
            limit=200,
            cursor=cursor
        )

    @paginate('messages')
    def fetch_channel_messages(self, channel_id: str, cursor: str = None) -> Dict[str, Any]:
        try:
            return self.user_client.conversations_history(
                channel=channel_id,
                limit=200,
                cursor=cursor
            )
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                delay = int(e.response.headers['Retry-After'])
                print(f"Rate limited. Retrying in {delay} seconds")
                time.sleep(delay)
                return self.fetch_channel_messages(channel_id, cursor)
            raise e

    @paginate('messages')
    def fetch_thread_messages(self, channel: str, time_stamp: str, cursor: str = None) -> Dict[str, Any]:
        return self.exponential_backoff(
            self.user_client.conversations_replies,
            channel=channel,
            ts=time_stamp,
            limit=200,
            cursor=cursor
        )

    def fetch_user_list(self) -> pd.DataFrame:
        all_users = self.exponential_backoff(self.user_client.users_list)
        all_users = pd.DataFrame(all_users['members'])
        all_users = all_users.loc[
            ~(all_users.real_name.isna()),
            ['id', 'name', 'is_bot']
        ]
        all_users['name'] = all_users.name.str.capitalize()
        all_users.rename({'name': 'user_name'}, axis=1, inplace=True)
        return all_users

    def fetch_mess_from_multi_channels(self, channels: List[str]) -> pd.DataFrame:
        out = []
        for channel in channels:
            temp = pd.DataFrame(self.fetch_channel_messages(channel_id=channel))
            temp['channel_id'] = channel
            out.append(temp)
        out = pd.concat(out)
        if len(out) > 0:
            out['subtype'] = out.get('subtype', np.nan)
            out['thread_ts'] = out.get('thread_ts', np.nan)
            out['user'] = out.get('user', np.nan)
            out = out[['type', 'subtype', 'ts', 'user', 'thread_ts', 'text', 'channel_id']]
        return out

    def fetch_multi_threads(self, channels: List[str], time_stamps: List[str]) -> pd.DataFrame:
        all_threads = []
        for channel, ts in zip(channels, time_stamps):
            thread_messages = self.fetch_thread_messages(channel, ts)
            for message in thread_messages:
                message['channel_id'] = channel
            all_threads.extend(thread_messages)
        
        if not all_threads:
            return pd.DataFrame(columns=['type', 'ts', 'user', 'thread_ts', 'text', 'channel_id'])
        
        all_threads_df = pd.DataFrame(all_threads)
        
        required_columns = ['type', 'ts', 'user', 'thread_ts', 'text', 'channel_id']
        for col in required_columns:
            if col not in all_threads_df.columns:
                all_threads_df[col] = None
        
        return all_threads_df[required_columns]

    @staticmethod
    def clean_convo_data(all_channels_convos: pd.DataFrame) -> pd.DataFrame:
        # Keep all messages, including bot messages
        all_channels_convos = all_channels_convos.copy()
        all_channels_convos['text_clean'] = (
            all_channels_convos.text
            .str.replace('<.*?>', '', regex=True)
            .str.replace('\n', ' ', regex=True)
        )
        all_channels_convos['text_len'] = all_channels_convos.text_clean.str.len()
        all_channels_convos['ts'] = pd.to_datetime(all_channels_convos.ts, unit='s')
        all_channels_convos['thread_ts'] = pd.to_datetime(all_channels_convos.thread_ts, unit='s')
        return all_channels_convos

    def set_conversations_oldest(self, old_messages: pd.DataFrame):
        if not old_messages.empty:
            # Set to the oldest message timestamp instead of the newest
            self.conversations_oldest = old_messages['ts'].min().timestamp()
            print(f"Set conversations_oldest to {self.conversations_oldest}")
        else:
            self.conversations_oldest = None
            print("No old messages, will fetch all available messages")

    def fetch_new_messages(self, chunk_len: int = 1000, file_path: str = 'complete_conversations.pkl') -> pd.DataFrame:
        # Load old messages if file exists
        old_messages = pd.DataFrame()
        if os.path.exists(file_path):
            old_messages = self.load_old_messages(file_path)
            self.set_conversations_oldest(old_messages)
            print(f"Loaded {len(old_messages)} old messages")
        else:
            print("No existing messages found. Will fetch all available messages.")

        # Fetch new data
        all_users = self.fetch_user_list()
        all_channels = pd.DataFrame(self.fetch_conversations())
        all_channels = all_channels[['id', 'name']]
        all_channels.rename({'name': 'channel_name'}, axis=1, inplace=True)

        all_channels_convos = self.fetch_mess_from_multi_channels(all_channels.id)

        # Fetch all thread replies
        thread_parents = all_channels_convos[all_channels_convos['thread_ts'].notna()]
        
        if not thread_parents.empty:
            all_threads = self.fetch_multi_threads(thread_parents['channel_id'].tolist(), thread_parents['ts'].tolist())
            new_data = pd.concat([all_channels_convos, all_threads], ignore_index=True)
        else:
            new_data = all_channels_convos

        new_data = self.clean_convo_data(new_data)
        new_data = new_data.merge(all_users, left_on='user', right_on='id', how='left')
        new_data = new_data.merge(all_channels, left_on='channel_id', right_on='id', how='left')
        new_data = new_data.drop(['id_x', 'id_y'], axis=1)
        new_data = new_data.reset_index(drop=True)

        # Identify new messages
        if not old_messages.empty:
            old_messages['message_id'] = old_messages['ts'].astype(str) + '_' + old_messages['channel_id'].astype(str) + '_' + old_messages['user'].astype(str)
            new_data['message_id'] = new_data['ts'].astype(str) + '_' + new_data['channel_id'].astype(str) + '_' + new_data['user'].astype(str)

            new_message_ids = set(new_data['message_id']) - set(old_messages['message_id'])
            new_messages = new_data[new_data['message_id'].isin(new_message_ids)].drop('message_id', axis=1)
        else:
            new_messages = new_data

        # Sort and reset index
        new_messages = new_messages.sort_values('ts', ascending=False).reset_index(drop=True)

        print(f"Found {len(new_messages)} new messages")

        # Update the complete conversations file
        if not old_messages.empty:
            old_messages = old_messages.drop('message_id', axis=1)
        updated_data = pd.concat([new_messages, old_messages]).drop_duplicates(subset=['ts', 'channel_id', 'user'], keep='first')
        updated_data = updated_data.sort_values('ts', ascending=False).reset_index(drop=True)
        self.save_conversations(updated_data, file_path)
        print(f"Updated {file_path} with new messages")

        return new_messages

    def fetch_all_data(self, chunk_len: int = 1000, file_path: str = 'complete_conversations.pkl') -> pd.DataFrame:
        # This method now uses the same logic as fetch_new_messages
        new_messages = self.fetch_new_messages(chunk_len, file_path)
        
        # Load the updated complete conversations file
        all_messages = self.load_old_messages(file_path)
        
        return all_messages

    def get_conversation_stats(self, final: pd.DataFrame) -> pd.DataFrame:
        stats = final.groupby('user_name').agg(
            max_len=pd.NamedAgg('text_len', 'max'),
            total_length=pd.NamedAgg('text_len', 'sum'),
            total_messages=pd.NamedAgg('text', 'count'),
        )
        stats['average_message_size'] = stats.total_length / stats.total_messages
        return stats.sort_values('average_message_size', ascending=False)

    def load_old_messages(self, file_path: str) -> pd.DataFrame:
        return pd.read_pickle(file_path)

    def save_conversations(self, data: pd.DataFrame, file_path: str) -> None:
        data.to_pickle(file_path)

    def post_message(self, channel: str, text: str) -> Dict[str, Any]:
        return self.exponential_backoff(
            self.bot_client.chat_postMessage,
            channel=f"#{channel}",
            text=text,
            as_user='Slackbot'
        )

    def post_thread_reply(self, thread: Dict[str, Any], reply_text: str) -> Dict[str, Any]:
        """
        Posts a reply to a specific thread in Slack.

        :param thread: A dictionary containing thread information, as returned by organize_threads()
        :param reply_text: The text of the reply to post
        :return: The response from the Slack API
        """
        channel = thread['channel']
        thread_ts = thread['thread_ts']

        # Convert thread_ts to a string if it's a Timestamp object
        if isinstance(thread_ts, pd.Timestamp):
            thread_ts = thread_ts.timestamp()
        elif isinstance(thread_ts, str):
            # If it's already a string, ensure it's in the correct format
            try:
                thread_ts = float(thread_ts)
            except ValueError:
                # If it can't be converted to float, it might already be in the correct format
                pass

        try:
            result = self.exponential_backoff(
                self.bot_client.chat_postMessage,
                channel=channel,
                text=reply_text,
                thread_ts=str(thread_ts)  # Convert to string for consistency
            )
            print(f"Posted reply to thread {thread_ts} in channel {channel}")
            return result
        except SlackApiError as e:
            print(f"Error posting reply to thread: {e}")
            raise e
            
    def organize_threads(self, new_messages: pd.DataFrame, file_path: str = 'complete_conversations.pkl') -> List[Dict[str, Any]]:
        if new_messages is None or new_messages.empty:
            return []  # Return an empty list if there are no new messages

        # Load cached messages
        if os.path.exists(file_path):
            cached_messages = self.load_old_messages(file_path)
        else:
            cached_messages = pd.DataFrame()

        # Combine new and cached messages
        all_messages = pd.concat([new_messages, cached_messages]).drop_duplicates(subset=['ts', 'channel_id', 'user'], keep='first')
        
        # Sort messages by timestamp (oldest first)
        sorted_messages = all_messages.sort_values('ts')

        # Create a set of thread_ts values from new_messages, including top-level messages
        new_message_threads = set(new_messages['thread_ts'].dropna().unique()) | set(new_messages['ts'])

        # Group messages by thread_ts (or ts if it's the start of a thread)
        threads = defaultdict(list)
        for _, message in sorted_messages.iterrows():
            thread_ts = message['thread_ts'] if pd.notna(message['thread_ts']) else message['ts']
            if thread_ts in new_message_threads:
                threads[thread_ts].append(message.to_dict())

        # Organize threads and remove duplicates
        organized_threads = []
        for thread_ts, messages in threads.items():
            thread = {
                'channel': messages[0]['channel_name'],
                'thread_ts': thread_ts,
                'messages': []
            }
            seen_messages = set()
            for message in messages:
                message_key = (message['ts'], message['user'], message['text'])
                if message_key not in seen_messages:
                    thread['messages'].append({
                        'ts': message['ts'],
                        'user': message['user_name'],
                        'text': message['text'],
                        'is_bot': message.get('is_bot', False)
                    })
                    seen_messages.add(message_key)
            
            # Include all threads, even those with only one message
            organized_threads.append(thread)

        # Sort threads by their first message's timestamp
        organized_threads.sort(key=lambda x: x['thread_ts'])

        return organized_threads

# Usage example:
# interactor = SlackInteractor()
# new_messages = interactor.fetch_new_messages()
# threads = interactor.organize_threads(new_messages)
# print(f"Organized {len(threads)} threads from {len(new_messages)} messages")