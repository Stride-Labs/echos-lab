import random
from datetime import UTC, datetime
from typing import Any, Generator
from unittest.mock import AsyncMock, patch

import pytest
import tweepy
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from tweepy import ReferencedTweet, Response, User
from tweepy.asynchronous import AsyncClient

from echos_lab.common.env import DOT_ENV_PATH
from echos_lab.db import models
from echos_lab.db.db_setup import get_db
from echos_lab.db.models import Base
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.engines.prompts import TweetEvaluation
from echos_lab.twitter import twitter_client

AGENT_TWITTER_HANDLE = "bot"

agent_profile = AgentProfile(
    name="tester",
    twitter_handle=AGENT_TWITTER_HANDLE,
    model_name="model",
    quote_tweet_threshold=0.2,
    personality="",
    backstory="",
    mannerisms="",
    preferences="",
    tweet_analysis_prompt="",
    tweet_reply_prompt="",
    subtweet_analysis_prompt="",
    subtweet_creation_prompt="",
)

INTEGRATION_DB_URL = "postgresql://user:password@localhost:5432/echos"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")


@pytest.fixture(autouse=True)
def clear_prod_env(monkeypatch: pytest.MonkeyPatch):
    """Clears any enironment variables set in .env so environment is consistent across users"""
    if DOT_ENV_PATH.exists():
        prod_env = dotenv_values(DOT_ENV_PATH)
        for key in prod_env:
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="function")
def mock_client():
    """Fixture to provide a mock tweepy client"""
    client = AsyncMock(spec=AsyncClient)
    with patch("echos_lab.twitter.twitter_client.get_tweepy_async_client", return_value=client):
        yield client


@pytest.fixture(scope="function")
def integration_test_db() -> Generator[Session, None, None]:
    """Fixture for integration tests using real PostgreSQL database."""
    with get_db() as session:
        yield session


@pytest.fixture(scope="function")
def db(request) -> Generator[Session, None, None]:
    """Smart fixture that provides appropriate database session based on test type."""
    if request.node.get_closest_marker('integration'):
        # For integration tests, use PostgreSQL
        engine = create_engine(INTEGRATION_DB_URL)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        with TestingSessionLocal() as session:
            yield session
    else:
        # For unit tests, use SQLite
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(engine)


def generate_random_id() -> int:
    """Generates a random user ID or tweet ID to avoid caching across tests"""
    # Generate a random 19-digit integer (typical Twitter ID length)
    return random.randint(1000000000000000000, 2000000000000000000)


def generate_random_username() -> str:
    """Generates a random user name to avoid caching across tests"""
    user_id = generate_random_id()
    return f"user-{user_id}"


def build_tweepy_response(data: Any, meta: dict = {}):
    """Builds the tweepy API response object"""
    return Response(data=data, meta=meta, includes={}, errors={})


def build_user(id: int, username: str, name: str = "Test User", followers: int = 10) -> User:
    """Builds the tweepy User struct"""
    return User(
        {
            "id": id,
            "name": name,
            "username": username,
            "public_metrics": {"followers_count": followers},
        }
    )


def build_tweet(
    id: int,
    text: str,
    conversation_id: int | None = None,
    created_at: str = "1",
    author_id: int | None = None,
    include_image: bool = False,
    reference_id: int | None = None,
    reference_type: str | None = None,
) -> tweepy.Tweet:
    """Builds a tweepy tweet object"""
    valid_reference = (reference_id is None) == (reference_type is None)
    assert valid_reference, "reference_id and reference_type must either both be specified or both be None"

    conversation_id = conversation_id or id
    created_at = f"2024-01-01T00:00:0{created_at}.000Z"  # must be valid time string
    attachments = {"media_keys": ["X"]} if include_image else None
    author_id = author_id or generate_random_id()

    references = []
    if reference_id and reference_type:
        references = [ReferencedTweet({"id": reference_id, "type": reference_type})]

    return tweepy.Tweet(
        {
            "id": id,
            "text": text,
            "edit_history_tweet_ids": [],
            "created_at": created_at,
            "conversation_id": conversation_id,
            "author_id": author_id,
            "attachments": attachments,
            "referenced_tweets": references,
        }
    )


def build_db_tweet(
    id: int,
    text: str,
    author_id: int = 1,
    tweet_type: models.TweetType = models.TweetType.ORIGINAL,
    created_at: datetime = datetime.now(UTC),
    conversation_id: int | None = None,
    reply_to_id: int | None = None,
    quote_tweet_id: int | None = None,
) -> models.Tweet:
    """Builds a DB tweet object"""
    conversation_id = conversation_id or id  # default conversation ID to tweet ID
    return models.Tweet(
        tweet_id=id,
        text=text,
        author_id=author_id,
        tweet_type=tweet_type,
        conversation_id=conversation_id,
        created_at=created_at,
        reply_to_id=reply_to_id,
        quote_tweet_id=quote_tweet_id,
    )


def build_hydrated_tweet(tweet: tweepy.Tweet, username: str = "userA") -> twitter_client.HydratedTweet:
    """Builds a hydrated tweet with the get_username function mocked"""
    hydrated_tweet = twitter_client.HydratedTweet(tweet, username)
    return hydrated_tweet


def build_tweet_mention(tweet: tweepy.Tweet, username: str):
    """Builds a tweet mention object without a parent tweet"""
    return twitter_client.TweetMention(
        tagged_tweet=build_hydrated_tweet(tweet, username),
        original_tweet=None,
        replies=[],
    )


def build_reply_reference(id: int):
    """Builds a reply reference tweet"""
    return ReferencedTweet({"id": id, "type": "replied_to"})


def build_tweet_evaluation(
    text: str,
    rating: int,
    meme_name: str = "default_name",
    meme_id: int = 0,
    meme_caption: str = "default_caption",
    meme_rating: int = 5,
):
    """Builds a reply guy response"""
    return TweetEvaluation(
        response=text,
        tweet_analysis="",
        engagement_strategy="",
        response_rating=rating,
        meme_name=meme_name,
        meme_id=meme_id,
        meme_caption=meme_caption,
        meme_rating=meme_rating,
    )


def check_tweet_mention_equality(mentionA: twitter_client.TweetMention, mentionB: twitter_client.TweetMention) -> bool:
    """Helper function to convert two mentions are equal"""
    if not isinstance(mentionA, twitter_client.TweetMention) or isinstance(mentionB, twitter_client.TweetMention):
        return False

    taggedA, taggedB = mentionA.tagged_tweet, mentionB.tagged_tweet
    originalA, originalB = mentionA.original_tweet, mentionB.original_tweet
    repliesA, repliesB = mentionA.replies, mentionB.replies

    # First check that the underlying tweets and data lines up
    if taggedA != taggedB or originalA != originalB or repliesA != repliesB:
        return False

    # Then check the usernames for each tweets
    tagged_users_matches = taggedA.get_username() == taggedB.get_username()
    original_users_empty = not originalA and not originalB
    original_users_matches = bool((originalA and originalB) and (originalA.get_username() == originalB.get_username()))
    replies_users_match = all(rA.get_username() == rB.get_username() for (rA, rB) in zip(repliesA, repliesB))

    return tagged_users_matches and (original_users_empty or original_users_matches) and replies_users_match
