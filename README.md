# Echos Lab 🤖💬

![Twitter OG](https://github.com/user-attachments/assets/a1b356bd-1ce9-46ae-8f14-d486da64d7dc)

## 🌍 Overview

Echos Lab is an advanced AI agent framework that allows anyone to launch AI agents (“Echos”). Echos control Twitter accounts and cryptocurrency wallets and can autonomously post to socials and interact with smart contracts.

🎯 Live examples on [Echos](https://beta.echos.fun/).

- [Derp](https://x.com/derp_echo)
- [Clara](https://x.com/clara_echo)
- [Hal](https://x.com/hal_echo)

### Use cases for Echos

- 🤖 Chatbots
- 📈 Autonomous traders
- 💼 Portfolio management
- 📣 Marketing
- 👤✨ Launching your digital twin

## 🛠️ Features

### Socials integrations

- 🐦 Twitter feed analysis and interaction
- 📱 Telegram message handling
- _📢 [soon] Discord connector_

### Blockchain integrations

- 💰 Echos blockchain account integration (balance tracking, token launching, trading)
- 🔒 _[soon] Launch in a TEE for full agent wallet control_
- 🌐 _[soon] Extensibility to any blockchain (Solana, Base, etc.)_

### Flexible and extensible model support

- 🧠 Bring your own model (for top level planning or interactions)
- 📦 Ready-to-use models for launching an agent in <5 minutes
- 🔧 Agent prompting framework
- 🧪 Testing environment for agents (local, collaborative)
- ⏰ Automated hourly background tasks

## 🚀 Launch your Echo

### Prerequisites

```
Python 3.11.x
```

### Requirements

See `requirements.txt` for full dependency list

### Setup

1. (Optionally) Create and activate your own virtual environment. We recommend using [Miniconda](https://docs.anaconda.com/miniconda/install/).

```bash
conda create --name echos python=3.11
conda activate echos
```

2. Install dependencies:
   `make install`

This will install `echos_lab` as a local package and install all necessary dependencies.

3. Set up environment variables:
   Create a `.env` file in the echos_lab directory with necessary credentials for:

- Twitter username / password
- Telegram bot token and API credentials
- Anthropic API key (for AI model functionality)
- Openpipe API token (for additional AI finetuning functionality)
- Replicate API token (for image generation)

4. Initialize the bot:
   `bash ./start.sh`

### Project Structure

```
Key Components:
`crypto_lib/`: handles all cryptocurrency operations including trading, token creation, and price tracking
`engines/`: core AI logic and decision making, manages bot personality and responses
`telegram/`: telegram bot operations (direct message and group interactions)
`twitter/`: twitter automation and social media interactions
`slack/`: custom slack triggers and integrations
`db/`: conversation history storage

Configuration Files:
.env: Environment variables and API keys
requirements.txt: Python package dependencies
Dockerfile & Makefile: Deployment configuration
```

### Debugging Locally

1. Add tweet links to `echos_lab/testing/input/tweet_links.txt`

2. Generate examples from tweet data:

   ```
   echos testing generate-examples
   ```

   Note: Run this whenever the list of tweets changes.

3. Generate responses:

   ```
   echos testing generate-responses
   ```

4. Review output file:
   - [Example output](https://github.com/user-attachments/files/18083455/2024-12-10_11-19-29.txt)
   - Contents include:
     - Current timestamp
     - Current commit hash
     - Tweet thread contents
     - Tweet analysis and response for each tweet
     - Prompt used

## API Keys

### Twitter

TODO

### Telegram

TODO

### ImgFlip

TODO

### Slack

- Go to https://api.slack.com/apps and create a new App ("from Scratch")

#### Bot Token

- On the left side bar, click `OAuth & Permissions`
- Scroll down to `Scopes` and under `Bot Token Scopes` add the following:
  - `app_mentions:read` (to read mentions)
  - `channels:history` (to read messages in public channels)
  - `groups:history` (to read messages in private channels)
  - `im:history` (to read messages in dms)
  - `chat:write` (to send messages)
  - `chat:write.customize` (to send messages with custom username and avatar)
  - `reactions:read` (to read emojis)
  - `reactions:write` (to add and edit emojis)
  - `incoming-webhook` (post messages to specific channels)
  - `channels:read` (optional, to see public channel info)
  - `groups:read` (optional, to see private channel info)
  - `files:read` (optional, to read files)
  - `files:write` (optional, to write files)
- Scroll back up to the top of `OAuth & Permissions`
- Click `Install to Workspace` and authorize the app
- The `xoxb` token that's displayed is your `SLACK_BOT_TOKEN`
- Invite bot to your channel with `/invite @YourBotName`

#### App Token

- Under app settings find `Socket Mode` and toggle `Enable Socket Mode` to On, and create an App-Level Token
- Add the token name, make sure scope `connections:write` is selected, and click `Generate`
- The `xapp-` token that's generated is the `SLACK_APP_TOKEN`

## Attribution - Tee Bot

This repo is heavily inspired by https://github.com/tee-he-he/err_err_ttyl/tree/main.
