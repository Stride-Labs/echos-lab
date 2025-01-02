from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import BigInteger as SaBigInteger


# Custom integer type that will adjust based on Postgres vs SQLite
class BigIntegerType(SaBigInteger):
    pass


# TODO: Consider just changing the ID types to strings - would involve a lot of refactoring though
# Tradeoff is strings makes it a little safer that we don't exceed the limit, but ints gives us a
# little more safety that we have an actual twitter ID and not a different string
# Override the postgres bigint type to use BIGINT (to handle twitter IDs)
@compiles(BigIntegerType, 'postgresql')
def compile_big_integer_postgresql(type_, compiler, **kw):
    return 'BIGINT'


@compiles(BigIntegerType, 'sqlite')
def compile_big_integer_sqlite(type_, compiler, **kw):
    return 'INTEGER'


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class TweetType(str, Enum):
    """Types of tweet we track."""

    ORIGINAL = "original"
    QUOTE = "quote"
    REPLY = "reply"


class QueryType(str, Enum):
    """Types of Twitter API queries we track checkpoints for."""

    USER_TWEETS = "user_tweets"
    USER_MENTIONS = "user_mentions"


class TwitterUser(Base):
    """Twitter users we interact with."""

    __tablename__ = "twitter_users"

    user_id: Mapped[int] = mapped_column(BigIntegerType, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    tweets: Mapped[list["Tweet"]] = relationship("Tweet", back_populates="author")


class TwitterQueryCheckpoint(Base):
    """Tracks the last tweet ID we've processed for different types of Twitter API queries."""

    __tablename__ = "twitter_query_checkpoints"

    agent_name: Mapped[int] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("twitter_users.user_id"), primary_key=True)
    query_type: Mapped[QueryType] = mapped_column(String, primary_key=True)
    last_tweet_id: Mapped[int] = mapped_column(BigIntegerType, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user: Mapped["TwitterUser"] = relationship("TwitterUser")


class Tweet(Base):
    """Tweets we process or send."""

    __tablename__ = "tweets"

    tweet_id: Mapped[int] = mapped_column(BigIntegerType, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("twitter_users.user_id"))
    tweet_type: Mapped[TweetType] = mapped_column(String)
    conversation_id: Mapped[int] = mapped_column(BigIntegerType, index=True)
    reply_to_id: Mapped[int | None] = mapped_column(BigIntegerType, nullable=True)
    quote_tweet_id: Mapped[int | None] = mapped_column(BigIntegerType, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now(UTC))

    reply_to_tweet: Mapped["Tweet"] = relationship(
        "Tweet", primaryjoin="foreign(Tweet.reply_to_id) == remote(Tweet.tweet_id)", uselist=False
    )
    quote_tweet: Mapped["Tweet"] = relationship(
        "Tweet", primaryjoin="foreign(Tweet.quote_tweet_id) == remote(Tweet.tweet_id)", uselist=False
    )

    media: Mapped[list["TweetMedia"]] = relationship("TweetMedia", back_populates="tweet", cascade="all, delete-orphan")
    author: Mapped["TwitterUser"] = relationship("TwitterUser", back_populates="tweets")


class TweetMedia(Base):
    """Images or video associated with tweets"""

    __tablename__ = "tweet_media"

    tweet_id: Mapped[int] = mapped_column(BigIntegerType, ForeignKey("tweets.tweet_id"), primary_key=True)
    media_id: Mapped[str] = mapped_column(String, primary_key=True)

    tweet: Mapped["Tweet"] = relationship("Tweet", back_populates="media")


class TelegramMessage(Base):
    """Telegram messages we process."""

    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(BigIntegerType, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=lambda: datetime.now(UTC)
    )
    chat_id: Mapped[int] = mapped_column(BigIntegerType, nullable=False, index=True)
