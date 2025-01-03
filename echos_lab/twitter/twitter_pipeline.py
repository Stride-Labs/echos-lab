from typing import List

from sqlalchemy.orm import Session

from echos_lab.db import db_connector, models
from echos_lab.db.models import QueryType, TwitterQueryCheckpoint, TwitterUser
from echos_lab.twitter import twitter_client, twitter_helpers
from echos_lab.twitter.types import TweetExclusions, TweetMention


def get_checkpoint(
    db: Session,
    agent_name: str,
    user_id: int,
    query_type: QueryType,
) -> TwitterQueryCheckpoint | None:
    """
    Get an existing checkpoint for a given user and query type.

    Args:
        db: Database session
        agent_name: The name of the agent associated with the checkpoint
        user_id: Twitter user ID
        query_type: Type of query to get checkpoint for

    Returns:
        Checkpoint if found, else None
    """
    return (
        db.query(TwitterQueryCheckpoint)
        .filter_by(
            agent_name=agent_name,
            user_id=user_id,
            query_type=query_type,
        )
        .first()
    )


async def create_checkpoint(
    db: Session,
    agent_name: str,
    user_id: int,
    query_type: QueryType,
    tweet_id: int,
) -> TwitterQueryCheckpoint:
    """
    Create a new checkpoint with the specified tweet ID, for a given user and query type.

    Args:
        db: Database session
        agent_name: The name of the agent associated with the checkpoint
        user_id: Twitter user ID
        query_type: Type of query to get checkpoint for
        tweet_id: ID of the tweet to checkpoint.

    Returns:
        Created checkpoint
    """
    # Ensure the user already exists in the database (since the checkpoint table has a foreign key)
    await assert_user_exists(db, user_id=user_id)

    checkpoint = TwitterQueryCheckpoint(
        agent_name=agent_name,
        user_id=user_id,
        query_type=query_type,
        last_tweet_id=tweet_id,
    )
    db.add(checkpoint)
    db.commit()
    return checkpoint


async def update_checkpoint(
    db: Session,
    agent_name: str,
    user_id: int,
    query_type: QueryType,
    tweet_id: int,
) -> TwitterQueryCheckpoint:
    """
    Update existing checkpoint or create new one with specified tweet ID.

    Args:
        db: Database session
        agent_name: The name of the agent associated with the checkpoint
        user_id: Twitter user ID
        query_type: Type of query to update checkpoint for
        tweet_id: New tweet ID to save

    Returns:
        Updated or created checkpoint
    """
    checkpoint = get_checkpoint(db, agent_name=agent_name, user_id=user_id, query_type=query_type)
    if checkpoint:
        checkpoint.last_tweet_id = tweet_id
        db.commit()
        return checkpoint
    else:
        return await create_checkpoint(
            db,
            agent_name=agent_name,
            user_id=user_id,
            query_type=query_type,
            tweet_id=tweet_id,
        )


async def get_user_id_from_username(db: Session, username: str) -> int | None:
    """
    Look up user ID for a username. If not in DB, queries Twitter API.
    Creates user entry if found via API.
    """
    # First check DB
    user = db_connector.get_twitter_user(db, username=username)
    if user:
        return user.user_id

    # If not in DB, try Twitter API
    user_id = await twitter_client.get_user_id_from_username(username)
    if user_id:
        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        return user_id

    return None


async def get_username_from_user_id(db: Session, user_id: int) -> str | None:
    """
    Look up username for a user ID. If not in DB, queries Twitter API.
    Creates user entry if found via API.
    """
    # First check DB
    user = db.query(TwitterUser).filter_by(user_id=user_id).first()
    if user:
        return user.username

    # If not in DB, try Twitter API
    username = await twitter_client.get_username_from_user_id(user_id)
    if username:
        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        return username

    return None


async def get_user_ids_from_usernames(db: Session, usernames: list[str]) -> dict[str, int]:
    """
    Given a list of usernames, returns a mapping of username -> user ID.
    First tries DB lookup, then falls back to API query.

    Args:
        db: Database session
        usernames: List of Twitter usernames to look up

    Returns:
        Dictionary of username -> Twitter user ID

    Raises:
        RuntimeError: If any username cannot be found in DB or via API
    """
    user_ids = {}
    for username in usernames:
        user_id = await require_user_id_from_username(db, username)
        user_ids[username] = user_id

    return user_ids


async def require_user_id_from_username(db: Session, username: str) -> int:
    """
    Fetches the user ID from the username and raises an exception if not found
    This is useful when grabbing the agent's user ID where we want to abort immediately if not found
    """
    user_id = await get_user_id_from_username(db, username)
    if not user_id:
        raise RuntimeError(f"Twitter User ID not found for handle @{username}")
    return user_id


async def require_username_from_user_id(db: Session, user_id: int) -> str:
    """
    Fetches the username from the user ID and raises an exception if not found
    """
    username = await get_username_from_user_id(db, user_id)
    if not username:
        raise RuntimeError(f"Twitter username not found for ID {user_id}")
    return username


async def add_twitter_user(db: Session, user_id: int | None = None, username: str | None = None):
    """
    Given either a user_id or username, stores the user in the database if it doesn't already exist

    Args:
        db: The database session
        user_id: Optional user_id of user to add
        username: Optional username of user to add

    Raises:
        RuntimeError if the user cannot be found from the API
    """
    assert user_id or username, "User ID or username must be specified when storing a new user"

    # If both a user_id and username is specified, add the user with those field
    if user_id and username:
        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        return

    # If just a user_id or just a username is specified, call the respective pipeline
    # function that will query via the API if appropriate
    if user_id:
        await require_username_from_user_id(db, user_id=user_id)
        return
    if username:
        await require_user_id_from_username(db, username=username)
        return


async def assert_user_exists(db: Session, user_id: int):
    """
    Since many tables have a user ID as the foreign key, we often have to make sure
    the user exists in the Users table

    This function will:
    - Attempt to retreive the user from the database
    - If not found, it will try to query for the User via the API
    - If nothing is returned, it raises an error
    """
    if not await get_username_from_user_id(db, user_id=user_id):
        raise RuntimeError(f"UserID {user_id} not found in database or twitter API")


async def get_mentions_last_replied_tweet(db: Session, agent_name: str, agent_id: int) -> int | None:
    """
    Get last replied tweet ID for mentions timeline.

    Args:
        db: Database session
        agent_name: Name of the agent
        agent_id: Twitter ID of the agent
    """
    checkpoint = get_checkpoint(db, agent_name=agent_name, user_id=agent_id, query_type=QueryType.USER_MENTIONS)
    return checkpoint.last_tweet_id if checkpoint else None


async def save_mentions_last_replied_tweet(db: Session, agent_name: str, agent_id: int, tweet_id: int) -> None:
    """
    Save last replied tweet ID for mentions timeline.

    Args:
        db: Database session
        agent_name: Name of the agent
        agent_id: Twitter ID of the agent
        tweet_id: ID of the last replied tweet
    """
    await update_checkpoint(
        db,
        agent_name=agent_name,
        user_id=agent_id,
        query_type=QueryType.USER_MENTIONS,
        tweet_id=tweet_id,
    )


async def update_db_with_tweet_ids(db: Session, notif_context_tuple: List[tuple[str, str]]) -> list[tuple[str, str]]:
    """Track seen tweets in database and return unseen tweets."""
    existing_tweet_ids = {tweet.tweet_id for tweet in db.query(models.Tweet.tweet_id).all()}
    filtered_notif_context_tuple = [
        (context, tweet_id) for (context, tweet_id) in notif_context_tuple if int(tweet_id) not in existing_tweet_ids
    ]

    for _, tweet_id in filtered_notif_context_tuple:
        await get_tweet_from_tweet_id(db, tweet_id=int(tweet_id))  # stores in DB

    return filtered_notif_context_tuple


async def get_tweet_from_tweet_id(db: Session, tweet_id: int) -> models.Tweet | None:
    """
    Retreives a tweet from the tweet ID
    - Attempts to retreive the tweet from the database
    - If not found, queries using the API
    - If it queried for the tweet, saves the tweet to the database after

    Args:
        db: Database session
        tweet_id: The tweet ID

    Returns:
        A database tweet object or None if the tweet doesn't exist
    """
    # Attempt to retreive the tweet from the database
    db_tweet = db.query(models.Tweet).where(models.Tweet.tweet_id == tweet_id).first()

    # If found, return it
    if db_tweet:
        return db_tweet

    # If not found, query via the API
    api_tweet = await twitter_client.get_tweet_from_tweet_id(tweet_id)

    # If nothing is returned from the API, the tweet doesn't exist
    if not api_tweet:
        return None

    # Before storing the tweet, we need to make sure the user is stored
    await add_twitter_user(db, user_id=api_tweet.author_id)

    # Finally, save the tweet to the DB and return the DB version
    return db_connector.add_tweepy_tweet(db, api_tweet)


async def get_user_latest_tweets(
    db: Session,
    agent_name: str,
    since_time: str,
    user_id: int | None = None,
    username: str | None = None,
    exclusions: list[TweetExclusions] | None = None,
) -> list[models.Tweet]:
    """
    Queries and stores the latest tweets for a given user ID
    Tweets are fetched since the last checkpoint and the checkpoint is updated at the end

    Note: The checkpoint is specific to each agent

    Args:
        db: The database session
        agent_name: The name of the agent (e.g. "vito")
        since_time: UTC timestamp of oldest allowable tweet (fallback if no checkpoint)
        user_id: The ID of the user to fetch tweets for. If this is not specified, the
          username must be specified
        username: The username of the account to fetch tweets for
        exclusions: List of tweet types to exclude

    Returns:
        List of tweets
    """
    # Ensure either the user_id or username was passed
    assert user_id or username, "Either the user_id or username must be specified"

    # If the user_id was not specfied, look it up from the username
    if not user_id:
        user_id = await require_user_id_from_username(db, str(username))

    # Grab the checkpoint from the last time we queried for this user
    checkpoint = get_checkpoint(db, agent_name=agent_name, user_id=user_id, query_type=QueryType.USER_TWEETS)

    # If checkpoints is None, that means the user probably doesn't exist yet
    # and we should filter the search by time
    # Otherwise, if the checkpoint exists, use the latest_tweet_id to filter the search
    time_filter = None if checkpoint else since_time
    id_filter = checkpoint.last_tweet_id if checkpoint else None

    tweepy_tweets, latest_tweet_id = await twitter_client.get_tweets_from_user_id(
        user_id=user_id,
        since_time=time_filter,
        since_id=id_filter,
    )

    # If there are new tweets, update the checkpoint
    if latest_tweet_id:
        await update_checkpoint(
            db, agent_name=agent_name, user_id=user_id, query_type=QueryType.USER_TWEETS, tweet_id=latest_tweet_id
        )

    # Filter down to just the tweets that were not excluded
    tweepy_tweets = twitter_helpers.filter_tweet_exclusions(tweepy_tweets, exclusions=exclusions)

    # Store the new tweets in the database
    return db_connector.add_tweepy_tweets(db, tweepy_tweets)


async def get_user_mentions(db: Session, agent_name: str, agent_id: int, since_time: str) -> list[TweetMention]:
    """
    Queries and stores the latest mentions for a given user account
    Mentions are fetched since the last checkpoint and the checkpoint is updated at the end

    Args:
        db: The database session
        agent_name: The name of the agent (e.g. "vito")
        agent_id: The twitter ID of the agent
        since_time: UTC timestamp of oldest allowable tweet (fallback if no checkpoint)
        exclusions: List of tweet types to exclude

    """
    # Grab the checkpoint from the last time we queried for this user
    checkpoint = get_checkpoint(db, agent_name=agent_name, user_id=agent_id, query_type=QueryType.USER_MENTIONS)

    # If checkpoints is None, that means the user probably doesn't exist yet
    # and we should filter the search by time
    # Otherwise, if the checkpoint exists, use the latest_tweet_id to filter the search
    time_filter = None if checkpoint else since_time
    id_filter = checkpoint.last_tweet_id if checkpoint else None

    mentions, latest_tweet_id = await twitter_client.get_all_user_mentions(
        user_id=agent_id,
        since_tweet_id=id_filter,
        since_time=time_filter,
    )

    # If there are new tweets, update the checkpoint
    if latest_tweet_id:
        await update_checkpoint(
            db, agent_name=agent_name, user_id=agent_id, query_type=QueryType.USER_MENTIONS, tweet_id=latest_tweet_id
        )

    # Extract the tweepy tweets and authors from the mention's struct
    tweepy_tweets = []
    author_ids: list[int] = []
    for mention in mentions:
        if mention.original_tweet:
            tweepy_tweets.append(mention.original_tweet)
            author_ids.append(mention.original_tweet.author_id)

        tweepy_tweets.extend(mention.replies)
        tweepy_tweets.append(mention.tagged_tweet)

        author_ids.extend([reply.author_id for reply in mention.replies])
        author_ids.append(mention.tagged_tweet.author_id)

    # TODO: Find a better way to organize this
    # Make sure we have all the author IDs stored
    for author_id in author_ids:
        username = await require_username_from_user_id(db, author_id)
        db_connector.add_twitter_user(db, user_id=author_id, username=username)

    # Store the new tweets in the database
    # TODO: Store the replies/originals when fetching up the tree
    # and only store the tagged tweets here
    db_connector.add_tweepy_tweets(db, tweepy_tweets)

    # Return the mentions
    # TODO: Return the DB tweet types instead
    return mentions
