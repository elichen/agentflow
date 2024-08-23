# agent_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional

class AgentInterface(ABC):
    @abstractmethod
    def read_thread(self, thread: Dict[str, Any]) -> None:
        """
        Read and process a thread.

        Args:
            thread (Dict[str, Any]): The thread to be processed.
        """
        pass

    @abstractmethod
    def decide_action(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Decide on the next action based on the thread content.

        Returns:
            Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]: 
            A tuple containing:
            - Boolean indicating if any action is needed
            - Dictionary describing an immediate action (if any)
            - Dictionary describing a delayed action (if any)
        """
        pass

    @abstractmethod
    def execute_immediate_action(self, action: Dict[str, Any]) -> str:
        """
        Execute an immediate action.

        Args:
            action (Dict[str, Any]): The action to be executed.

        Returns:
            str: The result of the action execution.
        """
        pass

    @abstractmethod
    def schedule_delayed_action(self, action: Dict[str, Any]) -> None:
        """
        Schedule a delayed action.

        Args:
            action (Dict[str, Any]): The action to be scheduled.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the name of the agent.
        """
        pass
    
    def _format_thread_messages(self) -> str:
        if not hasattr(self, 'current_thread') or self.current_thread is None:
            return ""
        formatted_messages = []
        for message in self.current_thread['messages']:
            if message.get('is_bot', False):
                user_type = "Bot"
                username = message['username']
            else:
                user_type = "Human"
                username = message['user']
            formatted_messages.append(f"{user_type} {username} ({message['minutes_ago']} minutes ago): {message['text']}")
        return "\n".join(formatted_messages)