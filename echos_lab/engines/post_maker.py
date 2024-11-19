from echos_lab.engines import agent_interests
from echos_lab.crypto_lib import crypto_connector
from openpipe import OpenAI
from fuzzywuzzy import fuzz

from functools import lru_cache
from typing import List
import json
import os

from langchain_anthropic import ChatAnthropic

HAL_MODEL = "claude-3-5-sonnet-20241022"

MODEL_NAME = "openpipe:blue-pears-fail"
if agent_interests.MODEL_NAME != "":
    MODEL_NAME = agent_interests.MODEL_NAME

OPENPIPE_API_KEY = os.getenv("OPENPIPE_API_KEY", "")
if OPENPIPE_API_KEY == "":
    raise ValueError("OPENPIPE_API_KEY environment variable not set.")

client = OpenAI(openpipe={"api_key": f"{OPENPIPE_API_KEY}"})

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
TWEET_DATA_PATH = f"{BASE_PATH}/tweet_data"
if not os.path.exists(TWEET_DATA_PATH):
    os.makedirs(TWEET_DATA_PATH)


@lru_cache
def load_tweet_data() -> List[str]:
    """
    Loads tweet data from all of the .jsonl files in "tweet_data" directory.
    """
    tweets = []
    for file in os.listdir(TWEET_DATA_PATH):
        if file.endswith(".jsonl"):
            with open(f"{TWEET_DATA_PATH}/{file}", "r") as f:
                for line in f:
                    data = json.loads(line)
                    if 'text' in data:
                        tweets.append(data['text'])
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


def generate_tweet_from_model(sentiment: str, subject_matter: str, replying_to: str) -> str:
    """
    Generate a new post or reply based on a few words of a prompt.

    Args:
        sentiment: the sentiment (positive, negative, neutral) of the tweet
        short_context: a short string of text to generate a tweet from
        replying_to: the text of a tweet you want to reply to

    Returns:
        str: Generated post or reply
    """
    if replying_to != "":
        prompt = f"Generate a spicy reply to this tweet: {replying_to}"
    else:
        prompt = (
            f"Here is the sentiment (positive/neutal/negative) and a list of topics to "
            f"tweet about: {sentiment}: {subject_matter}"
        )
    print(prompt, MODEL_NAME)
    completion = client.chat.completions.create(  # type: ignore
        model=f"{MODEL_NAME}",
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
                    "parameters": {"type": "object", "properties": {"tweet": {"type": "string"}}},
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
    llm = ChatAnthropic(
        model_name=HAL_MODEL,
        temperature=0.9,
        timeout=None,
        max_retries=2,
        stop=None,
        verbose=True,
    )
    prompt = agent_interests.TWEET_PROMPT
    prompt = prompt.replace('INSERT_MODE', mode)
    prompt = prompt.replace('RECENT_TWEETS_HERE', recent_tweets)
    prompt = prompt.replace('INSERT_TIMELINE_HERE', timeline)
    prompt = prompt.replace('INSERT_RESPONSE_TWEET_HERE', respond_to)
    prompt = prompt.replace('INSERT_ADDRESS_HERE', crypto_connector.get_address())
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
