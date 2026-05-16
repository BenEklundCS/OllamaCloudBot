# OllamaCloudBot

A Discord bot that connects to a GitHub repository using an Ollama Cloud API key. @mention it to ask questions about the codebase, review pull requests, explain architecture, or write and open new PRs - all powered by a local or cloud-hosted LLM.

## What it can do

- **Explain code and architecture** - reads the file tree and relevant files, then summarizes
- **Review pull requests** - fetches the diff and posts a review comment directly on the PR
- **Write and open PRs** - generates code changes, creates a branch, commits, and opens a PR
- **Search the codebase** - finds files and symbols by keyword

## How it works

The bot runs an agentic loop. When you @mention it, your message is sent to Ollama Cloud along with a set of tools (GitHub API calls). The LLM decides which files to read, what searches to run, and what actions to take - then replies in Discord. No code is ever executed locally; everything goes through the GitHub API.

```
Discord @mention
  -> Ollama Cloud (tool-calling loop)
    -> GitHub API (read files, search, create PR)
  -> Discord reply
```

## Prerequisites

- Python 3.11+
- A [Discord application](https://discord.com/developers/applications) with a bot token
- A [GitHub App](https://github.com/settings/apps/new) installed on your target repo
- An [Ollama Cloud](https://ollama.com) account and API key

## Setup

### 1. GitHub App

1. Go to [github.com/settings/apps/new](https://github.com/settings/apps/new)
2. Give it a name, set any homepage URL
3. Uncheck **Active** under Webhooks (not needed)
4. Set these **Repository permissions**:
   - Contents: Read & Write
   - Pull requests: Read & Write
   - Metadata: Read (required, auto-selected)
5. Create the app - note the **App ID** on the settings page
6. Scroll down and click **Generate a private key** - download the `.pem` file
7. Click **Install App** - install it on **only the target repository** (not all repos)
8. Find your **Installation ID** from the install URL at `github.com/settings/installations`

### 2. Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and create a new application
2. Under **Bot**, enable **Message Content Intent**
3. Copy the bot token
4. Invite the bot to your server:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274877908992&scope=bot
   ```
   Replace `YOUR_CLIENT_ID` with the value from **OAuth2 > Client ID**

### 3. Configuration

```bash
cp .env.example .env
```

Fill in `.env`:

```env
DISCORD_TOKEN=your_discord_bot_token

GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./github-app.pem
GITHUB_INSTALLATION_ID=78901234
GITHUB_REPO=owner/repo-name

OLLAMA_CLOUD_API_KEY=your_ollama_api_key
OLLAMA_BASE_URL=https://ollama.com/v1
OLLAMA_MODEL=deepseek-v4-pro
```

Place your downloaded `.pem` file in the project directory.

### 4. Install and run

```bash
pip install -r requirements.txt
python3 bot.py
```

## Usage

@mention the bot in any channel it can read:

```
@HikePlannerBot explain the overall architecture
@HikePlannerBot review PR #14
@HikePlannerBot write a PR that adds pagination to the results endpoint
@HikePlannerBot where is the authentication logic?
```

## Security

- The GitHub App is scoped to a single repository and cannot access anything else on your account
- The bot cannot execute code - it only reads and writes via the GitHub API
- Anyone in your Discord server who can see the bot's channel can trigger it; consider restricting channel visibility or adding a role allowlist
- Never commit `.env` or `*.pem` - both are in `.gitignore`
- Rotate your bot token and private key if either is ever exposed

## Deployment

For an always-on server, run it as a systemd service:

```ini
[Unit]
Description=OllamaCloudBot
After=network.target

[Service]
WorkingDirectory=/path/to/OllamaCloudBot
ExecStart=python3 bot.py
Restart=on-failure
EnvironmentFile=/path/to/OllamaCloudBot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now ollamacloudbot
```

## Limitations

- Single-tenant: one bot instance serves one repository on one Discord server
- Large files are fetched in full - very large repos may hit context limits
- GitHub code search requires the repo to be indexed (may lag on new/private repos)
- Tool calls are capped at 15 per message to prevent runaway loops

## License

MIT
