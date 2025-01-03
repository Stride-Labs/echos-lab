import json
import os
from functools import lru_cache

import tweepy
from fuzzywuzzy import fuzz
from langchain_anthropic import ChatAnthropic
from openpipe import OpenAI

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.crypto_lib import crypto_connector
from echos_lab.db import models
from echos_lab.engines import agent_context, prompts
from echos_lab.engines import legacy
from echos_lab.engines.profiles import AgentProfile, LegacyAgentProfile
from echos_lab.engines.prompts import (
    SubTweetEvaluation,
    TweetEvaluation,
    XMLAttributeParser,
)

base_path = os.path.dirname(os.path.abspath(__file__))
TWEET_DATA_PATH = f"{base_path}/tweet_data"
if not os.path.exists(TWEET_DATA_PATH):
    os.makedirs(TWEET_DATA_PATH)


# Module level executor singleton storage
_reply_guy_llm: ChatAnthropic | None = None
_open_ai_client: OpenAI | None = None


def get_reply_guy_llm(model_name: str) -> ChatAnthropic:
    """
    Singleton to get or create a new Claude LLM client
    """
    global _reply_guy_llm
    if _reply_guy_llm is None:
        get_env_or_raise(envs.ANTHROPIC_API_KEY)
        _reply_guy_llm = ChatAnthropic(
            model_name=model_name,
            timeout=120,
            max_retries=2,
            stop=None,
            verbose=True,
        )
    return _reply_guy_llm


def get_open_api_client() -> OpenAI:
    """
    Singleton to get or create a new OpenAI client
    """
    global _open_ai_client
    if _open_ai_client is None:
        openpipe_api_key = get_env_or_raise(envs.OPENPIPE_API_KEY)
        _open_ai_client = OpenAI(openpipe={"api_key": openpipe_api_key})
    return _open_ai_client


@lru_cache
def load_tweet_data() -> list[str]:
    """
    Loads tweet data from all of the .jsonl files in "tweet_data" directory.
    """
    tweets = []
    for file in os.listdir(TWEET_DATA_PATH):
        if file.endswith(".jsonl"):
            with open(f"{TWEET_DATA_PATH}/{file}", "r") as f:
                for line in f:
                    data = json.loads(line)
                    if "text" in data:
                        tweets.append(data["text"])
    return tweets


def verify_tweet_dissimilar_from_tweet_data(tweet_contents: str, threshold=85) -> bool:
    """
    Calculates similarity score between the generated tweet and all tweets in the tweet data.

    If the similarity score is above a certain threshold, the tweet is considered similar.

    Args:
        tweet_contents: The text of the tweet to compare

    Returns:
        bool: True if the tweet is dissimilar, False if the tweet is similar
    """
    tweets = load_tweet_data()
    for tweet in tweets:
        similarity = fuzz.ratio(tweet, tweet_contents)
        if similarity > threshold:
            return False
    return True


def generate_tweet_from_model(model_name: str, sentiment: str, subject_matter: str, replying_to: str) -> str:
    """
    Generate a new post or reply based on a few words of a prompt.

    Args:
        sentiment: the sentiment (positive, negative, neutral) of the tweet
        short_context: a short string of text to generate a tweet from
        replying_to: the text of a tweet you want to reply to

    Returns:
        str: Generated post or reply
    """
    client = get_open_api_client()

    if replying_to != "":
        prompt = f"Generate a spicy reply to this tweet: {replying_to}"
    else:
        prompt = (
            f"Here is the sentiment (positive/neutal/negative) and a list of topics to "
            f"tweet about: {sentiment}: {subject_matter}"
        )
    print(prompt, model_name)

    completion = client.chat.completions.create(  # type: ignore
        model=f"{model_name}",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a twitter persona. You take in a list of topics and "
                    "send tweets that are related to those topics."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        tool_choice="auto",
        tools=[
            {
                "function": {
                    "name": "generate_tweet",
                    "parameters": {
                        "type": "object",
                        "properties": {"tweet": {"type": "string"}},
                    },
                },
                "type": "function",
            }
        ],
        temperature=0.9,
        openpipe={"tags": {"prompt_id": "counting", "any_key": "any_value"}},
    )
    tweet = completion.choices[0].message.content

    if verify_tweet_dissimilar_from_tweet_data(tweet):
        return tweet
    else:
        return "Generated tweet was invalid. Please try again."


def generate_tweet_from_model_hal(
    mode: str,
    recent_tweets: str,
    timeline: str,
    respond_to: str = "No tweet to respond to.",
):
    agent_profile = LegacyAgentProfile.from_yaml("hal")

    llm = ChatAnthropic(
        model_name=agent_profile.model_name,
        temperature=0.9,
        timeout=None,
        max_retries=2,
        stop=None,
        verbose=True,
    )
    prompt = legacy.get_hal_tweet_prompt()
    prompt = prompt.replace("INSERT_MODE", mode)
    prompt = prompt.replace("RECENT_TWEETS_HERE", recent_tweets)
    prompt = prompt.replace("INSERT_TIMELINE_HERE", timeline)
    prompt = prompt.replace("INSERT_RESPONSE_TWEET_HERE", respond_to)
    prompt = prompt.replace("INSERT_ADDRESS_HERE", crypto_connector.get_address())
    print(prompt)
    messages = [
        ("human", prompt),
    ]
    response = llm.invoke(messages)
    response_text = str(response.content)
    print(f"RAW RESPONSE:\n{response_text}")
    try:
        tweet = response_text.split("<tweet>")[1].split("</tweet>")[0].strip()
        return tweet
    except Exception:
        return ""


async def generate_reply_guy_tweet(
    agent_profile: AgentProfile,
    author: str,
    tweet_summary: str,
    author_recent_tweets: list[tweepy.Tweet],
    agent_recent_tweets: list[models.Tweet],
    allow_roasting: bool,
) -> TweetEvaluation | None:
    """
    Generates a tweet in response to someone tagging the bot

    Args:
        agent_profile: The agent's configuration
        author: The username of the person who posted the original tweet
        tweet_summary: A summary of the tweet thread context
        author_recent_tweets: A list of the author's recent tweets
        agent_recent_tweets: A list of the agent's recent tweets
        allow_roasting: Bool indicating whether the agent should be able to roast

    Returns:
        The generated response, or None if below quality threshold
    """
    print(f"Responding to tweet from @{author}: {tweet_summary}")

    # Get the global and local contexts and build the associated prompt
    global_context, local_context = agent_context.get_agent_context_from_profile(agent_profile)
    crypto_context = prompts.build_crypto_context_prompt(
        global_context=global_context,
        local_context=local_context,
        author=author,
    )

    # Get the text summary of the author's recent tweets
    author_tweets_summary = prompts.build_author_recent_tweets_prompt(author, author_recent_tweets)

    # Get the text summary of the agent's recent tweets
    agent_tweets_summary = prompts.build_agent_recent_tweets_prompt(agent_recent_tweets)

    # Generate the full prompt
    prompt = prompts.get_reply_guy_prompt(agent_profile, allow_roasting)

    # Build the LLM pipeline
    llm = get_reply_guy_llm(agent_profile.model_name)
    parser = XMLAttributeParser()
    chain = prompt | llm | parser | TweetEvaluation.from_xml

    # Finally call the LLM agent with the full prompt and templated context
    response: TweetEvaluation = await chain.ainvoke(
        {
            "crypto_context": crypto_context,
            "tweet_summary": tweet_summary,
            "author_recent_tweets": author_tweets_summary,
            "agent_recent_tweets": agent_tweets_summary,
        }
    )
    print(str(response))

    return response


async def generate_subtweet(agent_profile: AgentProfile, tweet_topic: str) -> SubTweetEvaluation:
    """
    Generates a subtweet on the specified topic
    """
    print(f'Generating a subtweet for "{tweet_topic}"')

    # Get the global and local contexts and build the associated prompt
    global_context, local_context = agent_context.get_agent_context_from_profile(agent_profile)
    crypto_context = prompts.build_crypto_context_prompt(global_context=global_context, local_context=local_context)

    llm = get_reply_guy_llm(agent_profile.model_name)
    prompt = prompts.get_subtweet_prompt(agent_profile)
    parser = XMLAttributeParser()

    chain = prompt | llm | parser | SubTweetEvaluation.from_xml
    response: SubTweetEvaluation = await chain.ainvoke(
        {
            "topic": tweet_topic,
            "crypto_context": crypto_context,
        }
    )

    print(str(response))

    return response
