# Obtaining User and Bot Tokens in Slack

## Step 1: Create a Slack App

1. Go to the [Slack API: Applications](https://api.slack.com/apps) page.
2. Click on the "Create New App" button.
3. Provide a name for your app and select the workspace where you want to develop your app.

## Step 2: Add Scopes for Both User and Bot

1. Navigate to the "OAuth & Permissions" section on the left sidebar.
2. Under the "OAuth & Permissions" section, scroll down to "Scopes."
   - **User Token Scopes**: Add the scopes required for user-level actions (e.g., `channels:read`, `chat:write`, `users:read`).
   - **Bot Token Scopes**: Add the scopes required for bot-level actions (e.g., `chat:write`, `channels:read`, `groups:read`).

## Step 3: Add a Bot User

1. Go to the "App Home" section on the left sidebar.
2. Under the "App Home" section, scroll down to the "Bot Users" section.
3. Click the "Add a Bot User" button.
4. Configure the bot user settings as desired (e.g., display name, default username).

## Step 4: Install the App to Your Workspace

1. Go back to the "OAuth & Permissions" section.
2. Scroll up to the "OAuth Tokens & Redirect URLs" section.
3. Click on the "Install App to Workspace" button.
4. Follow the prompts to authorize the app and install it in your workspace.

## Step 5: Obtain the Tokens

1. After installing the app, you'll be redirected back to the "OAuth & Permissions" page.
   - **Bot User OAuth Token**: This is your bot token.
   - **User OAuth Token**: You can generate this by initiating the OAuth flow.

To initiate the OAuth flow and get a user token:
- Navigate to the "OAuth & Permissions" section.
- Scroll down to the "OAuth Tokens for Your Workspace" section.
- Use the OAuth URL provided to authorize and generate a user token.
