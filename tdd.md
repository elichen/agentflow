# Slack Bot Technical Design Document

## 1. System Overview

The Slack Bot is an automated system designed to monitor Slack conversations, process messages, and perform actions based on the content. It utilizes a Language Model (LLM) to analyze conversations and make decisions about necessary actions. The system is built with a modular architecture to allow for easy extension and maintenance.

## 2. Core Components

### 2.1 SlackInteractor (slack.py)

Responsible for all interactions with the Slack API.

#### Key Methods:
- `fetch_new_messages() -> pd.DataFrame`
- `post_message(channel: str, text: str) -> Dict[str, Any]`
- `post_thread_reply(thread: Dict[str, Any], reply_text: str) -> Dict[str, Any]`
- `organize_threads(new_messages: pd.DataFrame) -> List[Dict[str, Any]]`
- `fetch_thread(thread_ts: str) -> Optional[Dict[str, Any]]`

### 2.2 LLMInterface (llm_interface.py)

Defines the interface for interacting with Language Models.

#### Methods:
- `generate_response(prompt: str) -> str`

### 2.3 ClaudeLLM (claude_llm.py)

Implements the LLMInterface for the Claude model.

#### Key Attributes:
- `client: anthropic.Anthropic`
- `model: str`

#### Methods:
- `generate_response(prompt: str) -> str`

### 2.4 AgentInterface (agent_interface.py)

Defines the interface for agent actions.

#### Methods:
- `read_thread(thread: Dict[str, Any]) -> None`
- `decide_action() -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]`
- `execute_immediate_action(action: Dict[str, Any]) -> str`
- `schedule_delayed_action(action: Dict[str, Any]) -> None`

### 2.5 ProjectManagerAgent (project_manager_agent.py)

Implements the AgentInterface for project management tasks.

#### Key Attributes:
- `llm: LLMInterface`
- `action_db: ActionDatabase`
- `slack_interactor: SlackInteractor`
- `current_thread: Optional[Dict[str, Any]]`

#### Methods:
- All methods from AgentInterface
- `identify_open_action_items(thread: Dict[str, Any]) -> bool`
- `_generate_prompt() -> str`
- `_extract_actions_from_response(raw_response: str) -> List[Dict[str, Any]]`
- `_create_check_in_action() -> Dict[str, Any]`
- `_generate_action_response(action: Dict[str, Any]) -> str`
- `_parse_execution_time(time_str: str) -> pd.Timestamp`
- `_generate_open_items_prompt(thread: Dict[str, Any]) -> str`
- `_format_thread_messages() -> str`

### 2.6 ActionDatabase (db.py)

Manages the storage and retrieval of scheduled actions.

#### Key Attributes:
- `file_path: str`
- `actions: Dict[str, List[Dict[str, Any]]]`

#### Methods:
- `load_actions() -> Dict[str, List[Dict[str, Any]]]`
- `save_actions() -> None`
- `add_action(thread_id: str, channel: str, description: str, execution_time: pd.Timestamp) -> None`
- `get_actions(thread_id: str) -> List[Dict[str, Any]]`
- `remove_action(thread_id: str, description: str) -> bool`
- `get_due_actions(current_time: pd.Timestamp) -> List[Tuple[str, Dict[str, Any]]]`
- `get_all_thread_ids() -> List[str]`
- `get_actions_by_agent(agent_id: str) -> List[Dict[str, Any]]`

### 2.7 Runner (runner.py)

Orchestrates the entire process.

#### Key Functions:
- `process_threads(agent: ProjectManagerAgent, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]`
- `execute_due_actions(agent: ProjectManagerAgent) -> None`
- `main() -> None`

## 3. Data Flow

1. Runner fetches new messages using SlackInteractor
2. New messages are organized into threads
3. Each thread is processed by ProjectManagerAgent
4. ProjectManagerAgent uses ClaudeLLM to analyze the thread and decide on actions
5. If open action items are identified, ProjectManagerAgent schedules a future check-in
6. Immediate actions are executed, and delayed actions (including check-ins) are stored in ActionDatabase
7. Runner periodically checks for due actions and executes them

## 4. Key Functionalities

### 4.1 Thread Processing
- The system processes each thread to determine if any action is required
- Uses LLM to analyze thread content and make decisions
- Can execute immediate actions or schedule delayed actions

### 4.2 Action Scheduling and Execution
- Supports scheduling of delayed actions
- Executes due actions at the appropriate time
- Enforces one delayed action per thread constraint

### 4.3 Open Action Item Identification
- Identifies threads with open action items
- Schedules future check-ins for threads with open items

## 5. Constraints and Rules

- One delayed action per thread: If a new delayed action is scheduled for a thread that already has one, the existing action is replaced
- All thread IDs are converted to strings when used as keys in the ActionDatabase
- The system uses environment variables for API keys and tokens

## 6. Error Handling and Logging

- Errors are caught in the main loop of the runner and logged
- The system will wait for a specified period before retrying after an error

## 7. Configuration

- Slack API tokens: SLACK_USER_TOKEN, SLACK_BOT_TOKEN
- Anthropic API key: ANTHROPIC_API_KEY
- Sleep period between cycles: SLEEP_PERIOD (default: 60 seconds)

## 8. Future Improvements

- Implement support for multiple Slack workspaces
- Add a persistent storage solution for conversation history
- Use asyncio for improved performance in handling multiple threads and actions

## 9. Testing

Sanity tests are implemented to ensure core functionalities:
- Action scheduling
- Due action execution
- Thread processing
- One delayed action per thread constraint
- Handling of timestamp-based thread IDs

## 10. Dependencies

- pandas
- anthropic
- python-dateutil
- slack_sdk

This Technical Design Document serves as the definitive source of truth for the Slack Bot system. It provides a comprehensive overview of the system's architecture, components, and functionalities, allowing for accurate reconstruction or modification of the codebase.
