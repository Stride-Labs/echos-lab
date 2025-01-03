# Deploying Your Echo Bot

This guide walks you through deploying your own Echo bot. Echo bots are AI-powered agents, with a custom personality, that can interact on Twitter. You can use Echo bots to promote your own projects, automatically answer community questions, or create an engaging social media presence or twin.

## Overview

In this tutorial, you will:

1. Set up your local environment
2. Configure your bot's credentials
3. Test the bot locally

## Prerequisites

Before starting, ensure you have:

- Python 3.11.x installed (the standard here at Stride Labs)
- Conda package manager installed
- A Twitter/X account for your bot

## Part 1: Local Installation

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

## Part 2: Credentials and Environment

1. Create you `.env` file from the template:

   ```bash
   cp .env.reply-guy.example .env
   ```

2. Follow [Credentials](https://github.com/Stride-Labs/echos-lab/blob/main/docs/credentials.md) to create credentials for:

   - Twitter: for reading and posting tweets
   - Anthropic: for generating responses and other LLM orchestration
   - ImgFlip: for generating meme images
   - (Optional) Slack: for triggering subtweets or forcing responses through slack

3. Add the relevant tokens to the `.env` file

## Part 3: Agent Profile

## Part 4: Cloud Deployment

You have two options for deploying your Echo bot: using
Docker Hub (recommended for simplicity) or Google Container
Registry (if you're using Google Cloud).

### Option 1: Docker Hub Deployment (Recommended)

1. Add these commands to your Makefile:

   ```makefile
   DOCKER_USERNAME ?= your-dockerhub-username
   IMAGE_NAME ?= echo-bot
   TAG ?= latest

   build-docker:
      @echo "Building Docker image: $(IMAGE_NAME):$(TAG)"
     @docker build --platform linux/amd64 \
   	--tag $(DOCKER_USERNAME)/$(IMAGE_NAME):$(TAG) \
   	--build-arg ENV_FILE=.env \
   	.

   push-docker:
     @echo "Pushing image to Docker Hub"
     @docker push $(DOCKER_USERNAME)/$(IMAGE_NAME):$(TAG)

   deploy-docker: build-docker push-docker
   ```

2. Login to Docker Hub:

   ```bash
   docker login
   ```

3. Build and push the Docker image:
   ```bash
   make deploy-docker DOCKER_USERNAME=your-username TAG=v1.0.0
   ```

### Option 2: Google Cloud Deployment

If you prefer using Google Cloud, follow these steps:

1. Add this to your Makefile instead:

   ```makefile
   PROJECT ?= your-project-id
   TAG ?= latest

   build-gcr:
       @echo "Building image for Google Cloud Registry"
       @docker buildx build --platform linux/amd64 \
           --tag gcr.io/$(PROJECT)/agents:echo-$(TAG) \
           --build-arg ENV_FILE=.env \
           .

   push-gcr:
       @echo "Pushing to Google Container Registry"
       @docker push gcr.io/$(PROJECT)/agents:echo-$(TAG)

   deploy-gcr: build-gcr push-gcr
   ```

2. Login to Google Cloud:

   ```bash
   gcloud auth login
   gcloud auth configure-docker
   ```

3. Build and deploy:

   ```bash
   make deploy-gcr PROJECT=your-project-id TAG=v1.0.0

   gcloud run deploy echo-bot \
     --image gcr.io/your-project-id/agents:echo-v1.0.0 \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --max-instances 1 \
     --min-instances 1
   ```

## Have Any Problems?

Possible issues you may encounger and how to solve them:

| Issue              | Solution                                                                                                                          |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Docker build fails | - Check if Docker daemon is running<br></br>- Verify your `.env` file exists<br></br>- Try building with `--no-cache` flag        |
| Push fails         | - Check if you're logged in (`docker login` or `gcloud auth login`)<br></br>- Verify your username/project ID                     |
| Deployment fails   | - Check your cloud provider's quota limits<br></br>- Verify account permissions<br></br>- Check if service name is unique         |
| Container crashes  | - Check logs with `docker logs` or cloud provider's logging interface<br></br>- Verify all required environment variables are set |

If neither of these solutions work, feel free to reach out.
