# AgentFlow
AgentFlow is an open-source framework for creating persistent, intelligent AI agents capable of managing tasks and actions across extended periods. It breaks free from the constraints of traditional chat-based AI interactions, enabling the development of always-on agents that can schedule and execute tasks autonomously.

## Key Features
- Persistent, always-on AI agents
- No API endpoint required - easy to run anywhere
- Autonomous task scheduling and execution

## Configuration
Before running the application, you need to set up your configuration:

1. Copy the template configuration file:
   ```
   cp config.template.yaml config.yaml
   ```

2. Open `config.yaml` in a text editor

3. Replace the placeholder values with your actual API tokens and keys:
   - Replace `your_slack_bot_token_here` with your Slack bot token
   - Replace `your_slack_user_token_here` with your Slack user token
   - Replace `your_anthropic_api_key_here` with your Anthropic API key
   - Replace `your_openai_api_key_here` with your OpenAI API key

   For instructions on obtaining Slack tokens, refer to the [slack_tokens.md](slack_tokens.md) file in this repository.

4. (Optional) Adjust the `sleep_period` value if you want to change how often the main loop runs (default is 300 seconds or 5 minutes)

5. Save and close the file

## Obtaining Slack Tokens
For detailed instructions on how to create a Slack app and obtain the necessary tokens, please refer to the [slack_tokens.md](slack_tokens.md) file in this repository. This file provides step-by-step guidance on:
- Creating a Slack app using the `manifest.yml` file
- Installing the app to your workspace
- Obtaining both the Bot User OAuth Token and User OAuth Token
- Securely adding these tokens to your app configuration

## Running
To start the AgentFlow system, run:
```
run.sh
```
Note: AgentFlow is designed to run without requiring an API endpoint, making it easy to deploy and run on various environments, including local machines, servers, or cloud platforms.