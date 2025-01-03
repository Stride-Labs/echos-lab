import json
import os
import re
import time

from tweepy import Tweet

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env
from echos_lab.twitter.types import ReferenceTypes, TweetExclusions

default_cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.env")
COOKIES_PATH = get_env(envs.TWITTER_COOKIES_PATH, default_cookies_path)

MAX_COOKIES_LENGTH = 48 * 60 * 60  # how long cookies last in seconds, e.g. 48 hours


def get_tweet_url(username: str, tweet_id: int) -> str:
    """
    Builds the twitter URL from a username and tweet ID
    """
    return f"https://twitter.com/{username}/status/{tweet_id}"


def remove_tweet_reply_tags(tweet_contents: str) -> str:
    """
    Given the full tweet contents (including reply tags) in the format:
        e.g. "@userA @userB @userC some tweet message"

    Returns just the part after the tags:
        e.g. "some tweet message"

    Note: we don't know for sure if the last tag was a part of the actual message or not,
    so this function should be taken with a grain of salt!
    If there is no message after the last tag, the last tag is assumed to be the message
    (this is because you can't have empty tweets)
    """
    twitter_handle_regex = r"^(@\w+\s+)*"  # @ + {word-char} + {white-space}
    return re.sub(twitter_handle_regex, "", tweet_contents).strip()


def delete_cookies():
    """
    Deletes the cookies file
    """
    if os.path.exists(COOKIES_PATH):
        os.remove(COOKIES_PATH)


def write_cookies(cookies: dict):
    """
    Writes the updated cookies locally
    """
    with open(COOKIES_PATH, "w") as f:
        j = json.dumps(cookies).replace('"', '\\"').replace(" ", "")
        f.write(f"X_AUTH_TOKENS={j}\n")


def get_cookies_file_age() -> int | None:
    """
    Returns the age of the cookies file in seconds.
    If the file does not exist, returns None
    """
    if os.path.exists(COOKIES_PATH):
        return int(time.time() - os.path.getmtime(COOKIES_PATH))
    return None


def are_cookies_stale() -> bool | None:
    """
    Returns True if the cookies file is older than MAX_COOKIES_LENGTH.
    Returns False if the cookies files is younger than MAX_COOKIES_LENGTH
    Returns None if the cookies file does not exist
    """
    cookies_age = get_cookies_file_age()
    if not cookies_age:
        return None
    return cookies_age > MAX_COOKIES_LENGTH


def load_cookies() -> dict:
    """
    Returns the auth_token, ct0, and bearer_token from the cookies.env file.
    Raises if the cookies file doesn't exist (meaning the user has to login first)
    """
    if not os.path.exists(COOKIES_PATH):
        raise RuntimeError("Twitter cookies not found, please log in first")

    with open(COOKIES_PATH, "r") as f:
        content = f.read()
        return json.loads(content.split("=")[1].replace('\\\"', '"'))


def filter_tweet_exclusions(tweets: list[Tweet], exclusions: list[TweetExclusions] | None) -> list[Tweet]:
    """
    Filters down a list of tweets based on some exclusion criteria
    This is handled explicitly cause the API does not handle them reliably
    """
    # API exclusions are not reliable, we must do them explicitly
    exclusions = exclusions or []
    replies_excluded = TweetExclusions.REPLIES in exclusions
    quote_tweets_excluded = TweetExclusions.QUOTE_TWEETS in exclusions
    retweets_excluded = TweetExclusions.RETWEETS in exclusions

    def _should_exclude(tweet: Tweet):
        references = tweet.referenced_tweets or []

        should_exclude_reply = replies_excluded and any(ref.type == ReferenceTypes.REPLY for ref in references)
        should_exclude_quote = quote_tweets_excluded and any(ref.type == ReferenceTypes.QUOTE for ref in references)
        should_exclude_retweet = retweets_excluded and any(ref.type == ReferenceTypes.RETWEET for ref in references)

        return should_exclude_reply or should_exclude_quote or should_exclude_retweet

    return [tweet for tweet in tweets if not _should_exclude(tweet)]
