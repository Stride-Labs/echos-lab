# Deploying an Echo

This guide walks you through deploying your own Echo bot. Echo's are AI-powered agents, with a custom personality, that can interact on Twitter. You can use Echo's to promote your own projects, automatically answer community questions, or create an engaging social media presence or twin.

## Overview

In this tutorial, you will:

1. Set up your local environment
2. Configure your bot's credentials
3. Test the bot locally

## Prerequisites

Before starting, ensure you have:

- Python 3.11.x installed
- Miniconda package manager installed
- A Twitter/X account for your agent

## Local Installation

1. Create and activate a new conda environment:
   ```bash
   conda create -n echos python=3.11
   conda activate echos
   ```
2. Clone the repository:
   ```bash
   git clone https://github.com/stride-labs/echos-lab.git
   cd echos-lab
   ```
3. Install dependencies:

   ```bash
   make install
   ```

   This will install the package and its dependencies. You might see some
   warnings about `uvloop` -- these are normal.

4. You should now be able to run `echos` commands from the repo root directory
   ```bash
   echos --help
   ```

## Credentials and Environment

1. Create you `.env` file from the template:

   ```bash
   cp .env.reply-guy.example .env
   ```

2. Add your agent's name under `AGENT_NAME`

3. Follow the relevant sections in the [Credentials Guide](https://github.com/Stride-Labs/echos-lab/blob/main/docs/credentials.md) to create credentials for:

   - **Twitter**: for reading and posting tweets
   - **Anthropic**: for generating responses and other LLM orchestration
   - **ImgFlip**: for generating meme images
   - **Slack** (Optional): for triggering subtweets or forcing responses through slack

4. Add the relevant tokens to the `.env` file

## Agent Profile

1. Create a new profile using the example template

   ```bash
   echos init --name {agent-name} --twitter-handle {twitter-handle}
   ```

2. Open the agent profile at `~/.echos/{agent-name}.yaml` from your preferred editor and update the personality to your desired specifications.

## Local Deployment

Start the reply guy with:

```bash
echos reply-guy

# Or if you don't want slack configured:
echos reply-guy --disable-slack
```

Your agent will now poll for mentions or posts from followed accounts. Tag your agent to try it out!
