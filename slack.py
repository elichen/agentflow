import os
import time
import random
from typing import List, Dict, Any, Callable

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
        param_oldest = self.conversations_oldest or 0
        return self.exponential_backoff(
            self.user_client.conversations_history,
            channel=channel_id,
            limit=200,
            oldest=param_oldest,
            cursor=cursor
        )

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
        ch_ts = list(zip(channels, time_stamps))
        all_threads = []
        for channel, ts in ch_ts:
            temp = self.fetch_thread_messages(channel, ts)
            temp = temp[1:]  # remove parent message
            for x in temp:
                x['channel_id'] = channel
            all_threads.extend(temp)
        all_threads = pd.DataFrame(all_threads)
        return all_threads[['type', 'ts', 'user', 'thread_ts', 'text', 'channel_id']]

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
            old_threads = old_messages.loc[old_messages.ts == old_messages.thread_ts]
            if not old_threads.empty:
                self.conversations_oldest = old_threads.sort_values('ts', ascending=False).iloc[0].ts.timestamp()
                print(f"Set conversations_oldest to {self.conversations_oldest}")
            else:
                print("No threads found in old_messages")
        else:
            print("old_messages DataFrame is empty")

    def fetch_all_data(self, chunk_len: int = 1000, file_path: str = 'complete_conversations.pkl') -> pd.DataFrame:
        # Load old messages if file exists
        old_messages = pd.DataFrame()
        if os.path.exists(file_path):
            old_messages = self.load_old_messages(file_path)
            self.set_conversations_oldest(old_messages)
            print(f"Loaded {len(old_messages)} old messages")

        # Fetch new data
        all_users = self.fetch_user_list()
        all_channels = pd.DataFrame(self.fetch_conversations())
        all_channels = all_channels[['id', 'name']]
        all_channels.rename({'name': 'channel_name'}, axis=1, inplace=True)

        all_channels_convos = self.fetch_mess_from_multi_channels(all_channels.id)

        parent_threads = all_channels_convos.loc[
            all_channels_convos.ts == all_channels_convos.thread_ts
        ]

        chunks = list(range(0, len(parent_threads), chunk_len)) + [len(parent_threads)]
        all_threads = []
        for i in tqdm(range(len(chunks) - 1)):
            temp = self.fetch_multi_threads(
                parent_threads.channel_id.iloc[chunks[i]:chunks[i+1]],
                parent_threads.ts.iloc[chunks[i]:chunks[i+1]]
            )
            all_threads.append(temp)

        all_threads = pd.concat(all_threads) if all_threads else pd.DataFrame()

        new_data = pd.concat([all_threads, all_channels_convos])
        new_data = self.clean_convo_data(new_data)
        new_data = new_data.merge(all_users, left_on='user', right_on='id', how='left')
        new_data = new_data.merge(all_channels, left_on='channel_id', right_on='id', how='left')
        new_data = new_data.drop(['id_x', 'id_y'], axis=1)
        new_data = new_data.reset_index(drop=True)

        # Combine old and new data
        final_data = pd.concat([new_data, old_messages]).drop_duplicates(subset=['ts', 'channel_id', 'user'], keep='first')
        final_data = final_data.sort_values('ts', ascending=False).reset_index(drop=True)

        # Save the combined data
        self.save_conversations(final_data, file_path)
        print(f"Saved {len(final_data)} messages to {file_path}")

        return final_data

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

# Usage example:
# interactor = SlackInteractor()
# data = interactor.fetch_all_data()  # This will load old messages, fetch new ones, and save the combined result
# stats = interactor.get_conversation_stats(data)
# interactor.post_message('general', 'Hello, World!')