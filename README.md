# Echos Lab 🤖💬
- [Twitter OG](https://x.com/echosdotfun)

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
1. Install dependencies:
```bash ./install_requirements.sh```

2. Set up environment variables:
Create a `.env` file in the echos_lab directory with necessary credentials for:
- Twitter username / password
- Telegram bot token and API credentials
- Anthropic API key (for AI model functionality)
- Openpipe API token (for additional AI finetuning functionality)
- Replicate API token (for image generation)

3. Add `echos-lab` to your `PYTHONPATH`. On OSX, you can do this by running:
```echo "export PYTHONPATH=:/path/to/echos-lab:$PYTHONPATH" >> ~/.zshrc```

4. Initialize the bot:
```bash ./init_bot.sh```

### Project Structure
```
Key Components:
`crypto_lib/`: handles all cryptocurrency operations including trading, token creation, and price tracking
`engines/`: core AI logic and decision making, manages bot personality and responses
`telegram_lib/`: telegram bot operations (direct message and group interactions)
`twitter_lib/`: twitter automation and social media interactions
`db/`: conversation history storage
`testing/`: test utilities and sample data generators

Configuration Files:
.env: Environment variables and API keys
requirements.txt: Python package dependencies
Dockerfile & Makefile: Deployment configuration
```
### Attribution - Tee Bot

This repo is heavily inspired by https://github.com/tee-he-he/err_err_ttyl/tree/main.
