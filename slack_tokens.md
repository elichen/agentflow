# Obtaining User and Bot Tokens in Slack

## Step 1: Create a Slack App using manifest.yml

1. Go to the [Slack API: Applications](https://api.slack.com/apps) page.
2. Click on the "Create New App" button.
3. Choose "From an app manifest" option.
4. Select the workspace where you want to develop your app.
5. Copy and paste the contents of the `manifest.yml` file from your codebase into the provided text area.
6. Review the settings and click "Create" to finalize the app creation.

## Step 2: Install the App to Your Workspace

1. After creating the app, you'll be on the app's management page.
2. Click on the "Install to Workspace" button under "Install App" menu.
3. Review the permissions and click "Allow" to install the app to your workspace.

## Step 3: Obtain the Tokens

1. After installation, you'll be redirected to the "OAuth & Permissions" page.
2. Under "OAuth Tokens for Your Workspace", you'll find:
   - **Bot User OAuth Token**: This is your bot token.
   - **User OAuth Token**: This is your user token.

## Step 4: Add Tokens to Your App Configuration

1. Manually copy the Bot User OAuth Token and User OAuth Token.
2. Paste these tokens into your app's configuration file as required.

Note: Always keep these tokens secure and never share them publicly or commit them to version control.
