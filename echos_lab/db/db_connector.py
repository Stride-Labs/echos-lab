from datetime import UTC, datetime
from typing import Sequence

import tweepy
from sqlalchemy import desc
from sqlalchemy.orm import Session

from echos_lab.db.models import (
    TelegramMessage,
    Tweet,
    TweetMedia,
    TweetType,
    TwitterUser,
)
from echos_lab.twitter_lib.types import ReferenceTypes


def add_telegram_message(db: Session, username: str, message: str, chat_id: int) -> TelegramMessage:
    """
    Add a new Telegram message to the database.

    Args:
        db: Database session
        username: Username or first name of sender
        message: Message content
        chat_id: Telegram chat ID

    Returns:
        The created TGMessage
    """
    new_message = TelegramMessage(
        user_id=username,
        content=message,
        chat_id=chat_id,
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message


def get_telegram_messages(db: Session, chat_id: int, history: int = 100) -> Sequence[TelegramMessage]:
    """Get recent messages from a Telegram chat.

    Args:
        db: Database session
        chat_id: Telegram chat ID to fetch from
        history: Number of recent messages to return

    Returns:
        Sequence of TGMessage objects ordered by creation time
    """
    return (
        db.query(TelegramMessage)
        .filter(TelegramMessage.chat_id == chat_id)
        .order_by(TelegramMessage.id.desc())
        .limit(history)
        .all()
    )


def add_tweet(
    db: Session,
    tweet_id: int,
    text: str,
    author_id: int,  # Removed author_username
    tweet_type: TweetType = TweetType.ORIGINAL,
    conversation_id: int | None = None,
    reply_to_id: int | None = None,
    quote_tweet_id: int | None = None,
    created_at: datetime | None = None,
    media_ids: list[str] | None = None,
) -> Tweet:
    """
    Add a new tweet to the database.
    This is used when saving tweets posted by the agent

    Args:
        db: Database session
        tweet_id: Twitter's tweet ID
        text: Tweet text
        author_id: Twitter's user ID
        tweet_type: Type of tweet (original, reply, quote, retweet)
        conversation_id: ID of the conversation this tweet belongs
        reply_to_id: ID of the reply this tweet belongs to
        quote_tweet_id: ID of the tweet that this tweet is quote tweeting
        created_at: Tweet creation date (defaults to the current time)
        media_ids: List of image or video IDs to attach

    Returns:
        The created Tweet
    """
    created_at = created_at or datetime.now(UTC)

    new_tweet = Tweet(
        tweet_id=tweet_id,
        text=text,
        author_id=author_id,
        created_at=created_at,
        tweet_type=tweet_type,
        conversation_id=conversation_id or tweet_id,
        reply_to_id=reply_to_id,
        quote_tweet_id=quote_tweet_id,
    )
    media = [TweetMedia(tweet_id=tweet_id, media_id=media_id) for media_id in media_ids or []]

    db.add(new_tweet)
    db.bulk_save_objects(media)
    db.commit()
    db.refresh(new_tweet)
    return new_tweet


def add_tweepy_tweet(db: Session, tweepy_tweet: tweepy.Tweet) -> Tweet:
    """
    Adds a tweepy tweet to the database
    This is used when saving tweets fetched from the twitter API

    Args:
        db: The database session
        tweepy_tweet: The tweepy tweet object returned from the query

    Returns:
        The tweet as a database object
    """
    # Check if we already have the tweet saved, if so return it
    db_tweet = get_tweet(db, tweepy_tweet.id)
    if db_tweet:
        return db_tweet

    # Determine if it was an original, quote, or reply tweet
    tweet_type = TweetType.ORIGINAL
    reply_to_id = None
    quote_tweet_id = None

    for reference in tweepy_tweet.referenced_tweets or []:
        if reference.type == ReferenceTypes.REPLY:
            tweet_type = TweetType.REPLY
            reply_to_id = reference.id
        elif reference.type == ReferenceTypes.QUOTE:
            tweet_type = TweetType.QUOTE
            quote_tweet_id = reference.id

    # Gather the list of media IDs in the event that there were photos/videos attached
    attachments = tweepy_tweet.attachments or {}
    media_ids = attachments.get("media_keys", [])
    media = [TweetMedia(tweet_id=tweepy_tweet.id, media_id=media_id) for media_id in media_ids]

    # Add the tweet and medias to the database
    db_tweet = Tweet(
        tweet_id=tweepy_tweet.id,
        text=tweepy_tweet.text,
        author_id=tweepy_tweet.author_id,
        created_at=tweepy_tweet.created_at,
        tweet_type=tweet_type,
        conversation_id=tweepy_tweet.conversation_id,
        reply_to_id=reply_to_id,
        quote_tweet_id=quote_tweet_id,
    )

    db.add(db_tweet)
    db.bulk_save_objects(media)
    db.commit()

    return db_tweet


def add_tweepy_tweets(db: Session, tweepy_tweets: list[tweepy.Tweet]) -> list[Tweet]:
    """
    Adds a list of tweepy tweets to the database
    This is used when saving tweets fetched from the twitter API

    Args:
        db: The database session
        tweepy_tweet: The list of tweepy tweet objects from the query response

    Returns:
        The list of tweet database objects
    """
    return [add_tweepy_tweet(db, tweet) for tweet in tweepy_tweets]


def get_tweet(db: Session, tweet_id: int) -> Tweet | None:
    """Get a tweet by its ID.

    Args:
        db: Database session
        tweet_id: Twitter's tweet ID

    Returns:
        Tweet object if found, None otherwise
    """
    return db.query(Tweet).filter(Tweet.tweet_id == tweet_id).first()


def get_twitter_user(
    db: Session,
    user_id: int | None = None,
    username: str | None = None,
) -> TwitterUser | None:
    """
    Get a Twitter user by ID or username.

    Args:
        db: Database session
        user_id: Optional Twitter user ID
        username: Optional Twitter username

    Returns:
        TwitterUser if found, None otherwise

    Raises:
        ValueError: If neither user_id nor username is provided
    """
    if user_id is not None:
        return db.query(TwitterUser).filter(TwitterUser.user_id == user_id).first()
    elif username is not None:
        return db.query(TwitterUser).filter(TwitterUser.username == username).first()
    raise ValueError("Must provide either user_id or username")


def add_twitter_user(
    db: Session,
    user_id: int,
    username: str,
) -> TwitterUser:
    """
    Add a new Twitter user or update username if user exists.

    Args:
        db: Database session
        user_id: Twitter user ID
        username: Twitter username

    Returns:
        The created/updated TwitterUser
    """
    user = get_twitter_user(db, user_id=user_id)
    if user:
        if user.username != username:
            user.username = username
            db.commit()
        return user

    user = TwitterUser(user_id=user_id, username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_latest_tweets(
    db: Session,
    user_id: int | None = None,
    username: str | None = None,
    num_tweets: int = 100,
) -> list[Tweet]:
    """
    Fetches a given user's latest tweets from the database
    """
    # Query by user_id if it's provided
    if user_id:
        return (
            db.query(Tweet).where(Tweet.author_id == user_id).order_by(desc(Tweet.created_at)).limit(num_tweets).all()
        )

    # Otherwise, query by username
    return (
        db.query(Tweet)
        .join(Tweet.author)
        .where(TwitterUser.username == username)
        .order_by(desc(Tweet.created_at))
        .limit(num_tweets)
        .all()
    )
