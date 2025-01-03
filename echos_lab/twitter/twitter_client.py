from typing import Tuple, cast

from tweepy import Response, Tweet, User

from echos_lab.twitter import twitter_auth
from echos_lab.twitter.types import (
    TWEET_FIELDS,
    HydratedTweet,
    ReferenceTypes,
    TweetMention,
)


async def get_user_id_from_username(username: str) -> int | None:
    """
    Grabs the user ID from a username using tweepy
    Returns None if the username does not exist
    """
    client = twitter_auth.get_tweepy_async_client()
    response = await client.get_user(username=username)
    response = cast(Response, response)

    if not response.data:
        return None

    user = cast(User, response.data)
    return int(user.id)


async def get_username_from_user_id(user_id: int) -> str | None:
    """
    Grabs the user name from a user ID using tweepy
    Returns None if the user ID does not exist
    """
    client = twitter_auth.get_tweepy_async_client()
    response = await client.get_user(id=user_id)
    response = cast(Response, response)

    if not response.data:
        return None

    user = cast(User, response.data)
    return user.username


async def get_tweet_from_tweet_id(tweet_id: int) -> Tweet | None:
    """
    Fetches a tweet from the tweet ID
    Returns None if the tweet does not exist
    """
    client = twitter_auth.get_tweepy_async_client()
    response = await client.get_tweet(
        id=tweet_id,
        tweet_fields=TWEET_FIELDS,
        expansions=["author_id"],
        user_fields=["username"],
    )
    response = cast(Response, response)

    if not response.data:
        return None

    tweet = cast(Tweet, response.data)
    return tweet


# TODO: Once the DB is integrated, make this function smarter about grabbing tweets
# For instance if trying to grab the last 10 tweets from a user, we can first grab
# the tweets since our last checkpoint, and if thats less than 10, then we can search
# the DB for the remainder
async def get_tweets_from_user_id(
    user_id: int,
    since_id: int | None = None,
    since_time: str | None = None,
    num_tweets: int | None = None,
) -> tuple[list[Tweet], int | None]:
    """
    Query tweets from a specific user ID.

    Args:
        user_id: The ID of the user to fetch tweets for
        since_tweet_id: The tweet ID from where to start our search
        since_time: The UTC timestamp of the oldest time a tweet can be from
        num_tweets: The number of recent tweets to return

    Returns:
        Tuple of (list of tweets, newest tweet ID if any found)
    """
    client = twitter_auth.get_tweepy_async_client()

    response = await client.get_users_tweets(
        id=user_id,
        tweet_fields=TWEET_FIELDS,
        start_time=since_time,
        since_id=since_id,
        max_results=num_tweets,
        expansions=["author_id"],
        user_fields=["username"],
    )
    response = cast(Response, response)

    if not response.data:
        return [], None

    tweets = cast(list[Tweet], response.data)
    latest_tweet_id = int(response.meta["newest_id"]) if "newest_id" in response.meta else None

    return tweets, latest_tweet_id


async def has_high_follower_count(user_id: int, threshold_num_followers: int = 1000) -> bool:
    """
    Checks if a user has a high follower count

    Args:
        user_id (int): The user ID to check
        threshold_num_followers (int): The threshold for what constitutes a high follower count

    Returns:
        bool: True if the user has more followers than the threshold, False otherwise
    """
    client = twitter_auth.get_tweepy_async_client()

    response = await client.get_user(id=user_id, user_fields="public_metrics")
    response = cast(Response, response)

    if not response or not response.data:
        return False

    user = cast(User, response.data)
    return user.public_metrics["followers_count"] >= threshold_num_followers


async def get_parent_tweet(tweet: Tweet) -> Tweet | None:
    """
    Given a tweet, checks if the tweet is a reply tweet, and, if so,
    retreives the parent tweet
    Returns None if there is no parent tweet
    """
    is_root_tweet = tweet.id == tweet.conversation_id
    if is_root_tweet:
        return None

    if not tweet.referenced_tweets:
        return None

    parent_tweet_id = next(tweet.id for tweet in tweet.referenced_tweets if tweet.type == ReferenceTypes.REPLY)
    if not parent_tweet_id:
        return None

    # TODO: use pipeline get_tweet_from_tweet_id
    return await get_tweet_from_tweet_id(parent_tweet_id)


async def get_all_parent_tweets(tweet: Tweet) -> list[Tweet]:
    """
    Recursively traverses all replies up to a root tweet and returns
    a list of all the tweets
    The returend list will be sorted by time such that the earliest/root
    tweet will be first in the list
    """
    parent_tweets = []
    while True:
        parent_tweet = await get_parent_tweet(tweet)
        if parent_tweet:
            parent_tweets.append(parent_tweet)
            tweet = parent_tweet
            continue
        break

    return sorted(parent_tweets, key=lambda i: i.created_at)


# TODO: rename to `enrich_tweet_thread` and rename `TweetMention` to `TweetThread`
async def enrich_user_mention(tweet: Tweet) -> TweetMention:
    """
    Enriches a user mention with:
     * The username of the author
     * Each parent tweet in the thread
     * The root tweet
    """
    tagged_tweet = HydratedTweet(tweet)
    parent_tweets = [HydratedTweet(t) for t in await get_all_parent_tweets(tweet)]

    original_tweet = parent_tweets[0] if parent_tweets else None
    replies = parent_tweets[1:]  # removes root

    mention = TweetMention(
        tagged_tweet=tagged_tweet,
        original_tweet=original_tweet,
        replies=replies,
    )

    return mention


async def get_user_mentions_batch(
    user_id: int,
    since_tweet_id: int | None,
    since_time: str | None,
    max_results: int | None = None,
) -> Tuple[list[TweetMention], int | None] | None:
    """
    Returns a batch of user mentions, given the user ID
    This represents a single API request to get the latest mentions and can
    return no more than 100 tweets

    Args:
        user_id: The ID of the username that's being tagged
        since_tweet_id: The tweet ID from where to start our search, should be the latest
          tweet that we responded to
        since_time: The UTC timestamp of the oldest time a tweet can be from
        max_result: The max number of tweets to return from this request, can be
          no greater than 100

    Returns:
        A list of tweets, and the latest tweet ID (to identify where to start
        the search in the next iteration)
        The tweets are enriched with any relevant parent tweets or usernames
        Returns None if no mentions are found
    """
    client = twitter_auth.get_tweepy_async_client()
    response = await client.get_users_mentions(
        user_id,
        since_id=since_tweet_id,
        start_time=since_time,
        max_results=max_results,
        tweet_fields=TWEET_FIELDS,
        expansions=["author_id"],
        user_fields=["username"],
    )
    response = cast(Response, response)

    if not response.data:
        return None

    raw_tweets = cast(list[Tweet], response.data)
    latest_tweet_id = int(response.meta["newest_id"]) if "newest_id" in response.meta else None

    # TODO: consider using async.gather, need to be cautious of rate limit though
    mentions = [await enrich_user_mention(tweet) for tweet in raw_tweets]

    return mentions, latest_tweet_id


async def get_all_user_mentions(
    user_id: int,
    since_tweet_id: int | None,
    since_time: str | None,
    batch_size: int = 100,
) -> Tuple[list[TweetMention], int | None]:
    """
    Retrieves any mentions since the last time the bot was run
    This will continuously request batches of new mentions until all tweets
    since the last run have been retrieved

    In practice either since_tweet_id OR since_time will be provided, but not both
    since_time is used until a batch has been retreived, and then since_tweet_id will be used

    Args:
        user_id: The ID of the bot that's being tagged
        since_tweet_id: The ID of the last tweet that was handled
        since_time: The UTC timestamp of the oldest time a tweet can be from
        batch_size: The number of tweets to request in a single API request

    Returns:
        A list of mentions, sorted by time, and the latest tweet ID
    """
    # Continuously request batches of mentions since the last time the bot was run
    mentions: list[TweetMention] = []
    while True:
        # Fetch the next batch of tweets
        result = await get_user_mentions_batch(
            user_id=user_id,
            since_tweet_id=since_tweet_id,
            since_time=since_time,
            max_results=batch_size,
        )
        if not result:
            break

        # Append the tweets to the list and update the since_tweet_id for next search
        mentions_batch, last_tweet_id = result
        mentions += mentions_batch
        since_tweet_id = last_tweet_id

        # If we got less than max results, no need to fetch any more mentions
        if len(mentions_batch) < batch_size:
            break

    # Sort so the older tweets are first
    # NOTE: Consider prioritizing certain accounts first
    mentions = sorted(mentions, key=lambda i: i.tagged_tweet.created_at)

    return mentions, since_tweet_id


# TODO: Use DB in combination with API
async def get_author_recent_tweets(author_id: int) -> list[Tweet]:
    """
    Get's the recent tweets from an author
    If the account is large, returns the last 15 tweets, otherwise returns the last 5
    """
    # if the author is a large account, fetch more historical tweets before responding
    is_large_account = await has_high_follower_count(author_id)
    num_author_tweets = 15 if is_large_account else 5
    author_recent_tweets, _ = await get_tweets_from_user_id(author_id, num_tweets=num_author_tweets)
    return author_recent_tweets
