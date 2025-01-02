import random
from datetime import UTC, datetime, timedelta

import pytest
import tweepy
from conftest import build_db_tweet, build_tweet
from sqlalchemy.orm import Session

from echos_lab.db import db_connector
from echos_lab.db.models import TweetMedia, TweetType, TwitterUser


class TestAddGetTelegramMessage:
    def test_add_telegram_message(self, db: Session):
        """Test adding and retrieving Telegram messages."""
        # Add message
        message = db_connector.add_telegram_message(db=db, username="testuser", message="Hello, world!", chat_id=123)

        # Verify it was added
        assert message.user_id == "testuser"
        assert message.content == "Hello, world!"
        assert message.chat_id == 123
        assert isinstance(message.created_at, datetime)

        # Test retrieval
        messages = db_connector.get_telegram_messages(db, chat_id=123)
        assert len(messages) == 1
        assert messages[0].content == "Hello, world!"

    def test_get_telegram_messages_ordering(self, db: Session):
        """Test message retrieval ordering."""
        # Add messages in non-chronological order
        msgs = [("user1", "First", 123), ("user2", "Second", 123), ("user1", "Third", 123)]
        for user, content, chat_id in msgs:
            db_connector.add_telegram_message(db, user, content, chat_id)

        # Get messages with limit
        messages = db_connector.get_telegram_messages(db, chat_id=123, history=2)
        assert len(messages) == 2
        assert messages[0].content == "Third"  # Most recent first
        assert messages[1].content == "Second"

    def test_telegram_message_timestamp(self, db: Session):
        """Test that timestamps are stored correctly with UTC."""
        message = db_connector.add_telegram_message(db=db, username="testuser", message="Test", chat_id=123)
        assert message.created_at.tzinfo is None  # Should be naive UTC
        messages = db_connector.get_telegram_messages(db, chat_id=123)
        assert message.created_at == messages[0].created_at

    def test_multiple_chat_messages(self, db: Session):
        """Test handling messages from different chats."""
        db_connector.add_telegram_message(db, "user1", "Chat1", 123)
        db_connector.add_telegram_message(db, "user2", "Chat2", 456)

        chat1_msgs = db_connector.get_telegram_messages(db, chat_id=123)
        chat2_msgs = db_connector.get_telegram_messages(db, chat_id=456)

        assert len(chat1_msgs) == 1
        assert len(chat2_msgs) == 1

    def test_large_telegram_chat_id(self, db: Session):
        """Test handling large Telegram chat IDs (negative and positive)."""
        large_negative_id = -1002390254270  # Real Telegram group ID
        message = db_connector.add_telegram_message(
            db=db, username="testuser", message="Test", chat_id=large_negative_id
        )
        assert message.chat_id == large_negative_id


class TestAddTweet:
    def test_add_tweet(self, db: Session):
        """Test adding and retrieving tweets."""
        # Create user first
        user = db_connector.add_twitter_user(db, user_id=12345, username="testuser")

        tweet = db_connector.add_tweet(
            db=db,
            tweet_id=1,
            text="Test tweet",
            author_id=user.user_id,
            created_at=datetime.now(UTC),
            tweet_type=TweetType.ORIGINAL,
            conversation_id=1,
            media_ids=["mediaA", "mediaB"],
        )

        assert tweet.tweet_id == 1  # Changed from id to tweet_id
        assert tweet.text == "Test tweet"
        assert tweet.author.username == "testuser"
        assert tweet.tweet_type == TweetType.ORIGINAL
        assert tweet.conversation_id == 1
        assert tweet.reply_to_id is None

        # Confirm media was written
        medias = db.query(TweetMedia.media_id).filter(TweetMedia.tweet_id == 1).all()
        assert sorted(medias) == [("mediaA",), ("mediaB",)]

        # Test reply
        reply = db_connector.add_tweet(
            db=db,
            tweet_id=2,
            text="Test reply",
            author_id=user.user_id,
            created_at=datetime.now(UTC) + timedelta(seconds=1),
            tweet_type=TweetType.REPLY,
            conversation_id=1,
            reply_to_id=1,
        )

        assert reply.reply_to_id == 1
        assert reply.tweet_type == TweetType.REPLY

        # Test quote tweet
        quote = db_connector.add_tweet(
            db=db,
            tweet_id=3,
            text="Test quote",
            author_id=user.user_id,
            created_at=datetime.now(UTC) + timedelta(seconds=2),
            tweet_type=TweetType.QUOTE,
            conversation_id=1,
            quote_tweet_id=1,
        )

        assert quote.quote_tweet_id == 1
        assert quote.tweet_type == TweetType.QUOTE

    def test_add_tweet_thread(self, db: Session):
        """Test storing and retrieving a Twitter conversation thread."""
        # Create user
        user = db_connector.add_twitter_user(db, user_id=123, username="test_user")

        # Create original tweet
        original = db_connector.add_tweet(
            db,
            tweet_id=1,
            text="Original tweet",
            author_id=user.user_id,
            created_at=datetime.now(UTC),
            tweet_type=TweetType.ORIGINAL,
            conversation_id=1,
        )

        # Add reply
        reply = db_connector.add_tweet(
            db,
            tweet_id=2,
            text="Reply tweet",
            author_id=user.user_id,
            created_at=datetime.now(UTC) + timedelta(seconds=10),
            tweet_type=TweetType.REPLY,
            conversation_id=1,
            reply_to_id=1,
        )

        # Verify thread connection
        assert reply.reply_to_id == original.tweet_id
        assert reply.conversation_id == original.tweet_id


class TestAddGetTwitterUser:
    def test_twitter_user_operations(self, db: Session):
        """Test Twitter user creation and retrieval."""
        # Add user
        user = db_connector.add_twitter_user(db=db, user_id=12345, username="testuser")
        assert user.user_id == 12345
        assert user.username == "testuser"

        # Get by user_id
        fetched_by_id = db_connector.get_twitter_user(db=db, user_id=12345)
        assert fetched_by_id is not None
        assert fetched_by_id.username == "testuser"

        # Get by username
        fetched_by_name = db_connector.get_twitter_user(db=db, username="testuser")
        assert fetched_by_name is not None
        assert fetched_by_name.user_id == 12345

        # Test username update
        updated_user = db_connector.add_twitter_user(db=db, user_id=12345, username="newname")
        assert updated_user.username == "newname"
        assert updated_user.user_id == user.user_id

    def test_duplicate_twitter_user(self, db: Session):
        """Test handling duplicate Twitter users."""
        user1 = db_connector.add_twitter_user(db, user_id=123, username="old_name")
        user2 = db_connector.add_twitter_user(db, user_id=123, username="new_name")

        assert user1.user_id == user2.user_id
        assert user2.username == "new_name"  # Username should be updated

    def test_invalid_tweet_reference(self, db: Session):
        """Test adding tweet with invalid reply reference."""
        user = db_connector.add_twitter_user(db, user_id=123, username="test_user")

        tweet = db_connector.add_tweet(
            db,
            tweet_id=1,
            text="Test tweet",
            author_id=user.user_id,
            tweet_type=TweetType.REPLY,
            conversation_id=999,  # Non-existent conversation
            reply_to_id=888,  # Non-existent tweet
        )

        assert tweet.reply_to_id == 888  # Should allow invalid references

    def test_get_twitter_user_not_found(self, db: Session):
        """Test getting non-existent Twitter user."""
        assert db_connector.get_twitter_user(db=db, user_id=99999) is None
        assert db_connector.get_twitter_user(db=db, username="nonexistent") is None

    def test_get_twitter_user_invalid_args(self, db: Session):
        """Test getting Twitter user with invalid arguments."""
        with pytest.raises(ValueError):
            db_connector.get_twitter_user(db=db)


class TestGetUserLatestTweets:
    def test_get_user_latest_tweets(self, db: Session):
        """Tests retrieving the latest N tweets from a user"""
        now = datetime.now(UTC)

        # Add the user
        user_id = 1000
        username = "user"
        db.add(TwitterUser(user_id=user_id, username=username))
        db.commit()

        # Add a collection of tweets to the DB
        expected_tweet_ids = [1, 2, 3]
        tweets = [
            # Tweets that should be returned
            build_db_tweet(1, "tweet1", author_id=user_id, created_at=now),
            build_db_tweet(2, "tweet2", author_id=user_id, created_at=now - timedelta(minutes=1)),
            build_db_tweet(3, "tweet3", author_id=user_id, created_at=now - timedelta(minutes=2)),
            # Tweets from different author
            build_db_tweet(4, "tweet4", author_id=99999, created_at=now),
            build_db_tweet(5, "tweet5", author_id=99999, created_at=now),
            # Older tweets (should not be returned)
            build_db_tweet(6, "tweet6", author_id=user_id, created_at=now - timedelta(minutes=3)),
            build_db_tweet(7, "tweet7", author_id=user_id, created_at=now - timedelta(minutes=4)),
        ]
        random.shuffle(tweets)
        db.bulk_save_objects(tweets)

        # Retrieve the 3 latest tweets by user ID
        latest_tweets = db_connector.get_user_latest_tweets(db, user_id=user_id, num_tweets=3)
        latest_tweet_ids = [tweet.tweet_id for tweet in latest_tweets]
        assert latest_tweet_ids == expected_tweet_ids, "tweets by user ID"

        # Retrieve the 3 latest tweets by username
        latest_tweets = db_connector.get_user_latest_tweets(db, username=username, num_tweets=3)
        latest_tweet_ids = [tweet.tweet_id for tweet in latest_tweets]
        assert latest_tweet_ids == expected_tweet_ids, "tweets by username"

    def test_get_user_latest_tweets_empty(self, db: Session):
        """Tests retrieving the latest N tweets from a user"""
        now = datetime.now(UTC)

        # Add two users to the database - one that will have tweets (userA),
        # and the other that will not (userB)
        user_id_A = 1000
        user_id_B = 2000
        username_A = "userA"
        username_B = "userB"
        db.add(TwitterUser(user_id=user_id_A, username=username_A))
        db.add(TwitterUser(user_id=user_id_B, username=username_B))
        db.commit()

        # Add a collection of tweets to the DB, but only for userA
        tweets = [
            build_db_tweet(4, "tweet4", author_id=user_id_A, created_at=now),
            build_db_tweet(5, "tweet5", author_id=user_id_A, created_at=now),
        ]
        random.shuffle(tweets)
        db.bulk_save_objects(tweets)

        # Attempt to retreive the latest tweets from userB - should return an empty list
        latest_tweets = db_connector.get_user_latest_tweets(db, user_id=user_id_B, num_tweets=3)
        assert latest_tweets == []

        # Attempt to retreive by username from userB, it should also be empty
        latest_tweets = db_connector.get_user_latest_tweets(db, username=username_B, num_tweets=3)
        assert latest_tweets == []

        # Attempt to retreive by a username that's not in the DB, it should also be empty
        latest_tweets = db_connector.get_user_latest_tweets(db, username="unknown", num_tweets=3)
        assert latest_tweets == []


class TestAddTweepyTweet:
    def test_add_tweepy_tweet_original(self, db: Session):
        """Tests adding an original tweepy tweet"""
        tweet_id = 1
        conversation_id = 1
        author_id = 100
        text = "some tweet"
        created_at = "2024-01-01T00:00:00.000Z"

        tweepy_tweet = tweepy.Tweet(
            {
                "id": tweet_id,
                "text": text,
                "edit_history_tweet_ids": [],
                "created_at": created_at,
                "conversation_id": conversation_id,
                "author_id": author_id,
            }
        )

        db_connector.add_tweepy_tweet(db, tweepy_tweet)
        db_tweet = db_connector.get_tweet(db, tweet_id)

        assert db_tweet, "tweet is non-empty"
        assert db_tweet.tweet_id == tweet_id, "tweet ID"
        assert db_tweet.text == text, "tweet text"
        assert db_tweet.author_id == author_id, "author ID"
        assert db_tweet.tweet_type == TweetType.ORIGINAL, "tweet type"
        assert db_tweet.conversation_id == conversation_id, "conversation ID"
        assert not db_tweet.reply_to_id, "reply to ID"
        assert not db_tweet.quote_tweet_id, "quote tweet ID"
        assert db_tweet.created_at == datetime(2024, 1, 1, 0, 0, 0, 0), "tweet created at"

    def test_add_tweepy_tweet_reply(self, db: Session):
        """Tests adding a reply tweet"""
        original_tweet_id = 1
        reply_tweet_id = 2
        author_id = 100
        created_at = "2024-01-01T00:00:00.000Z"

        original_tweet = tweepy.Tweet(
            {
                "id": original_tweet_id,
                "text": "some original post",
                "edit_history_tweet_ids": [],
                "created_at": created_at,
                "conversation_id": original_tweet_id,
                "author_id": author_id,
            }
        )

        response_tweet = tweepy.Tweet(
            {
                "id": reply_tweet_id,
                "text": "some reply",
                "edit_history_tweet_ids": [],
                "created_at": created_at,
                "conversation_id": original_tweet_id,
                "author_id": author_id,
                "referenced_tweets": [
                    tweepy.ReferencedTweet({"type": "replied_to", "id": original_tweet_id}),
                ],
            }
        )

        db_connector.add_tweepy_tweet(db, original_tweet)
        db_connector.add_tweepy_tweet(db, response_tweet)

        db_tweet = db_connector.get_tweet(db, reply_tweet_id)

        assert db_tweet, "tweet is non-empty"
        assert db_tweet.tweet_id == reply_tweet_id, "tweet ID"
        assert db_tweet.text == "some reply", "tweet text"
        assert db_tweet.author_id == author_id, "author ID"
        assert db_tweet.created_at == datetime(2024, 1, 1, 0, 0, 0, 0), "tweet created at"

        assert db_tweet.tweet_type == TweetType.REPLY, "tweet type"
        assert db_tweet.conversation_id == original_tweet_id, "conversation ID"
        assert db_tweet.reply_to_id == original_tweet_id, "reply to ID"
        assert not db_tweet.quote_tweet_id, "quote tweet ID"

    def test_add_tweepy_tweet_quote(self, db: Session):
        """Tests adding a reply tweet"""
        original_tweet_id = 1
        quote_tweet_id = 2
        author_id = 100
        created_at = "2024-01-01T00:00:00.000Z"

        original_tweet = tweepy.Tweet(
            {
                "id": original_tweet_id,
                "text": "some original post",
                "edit_history_tweet_ids": [],
                "created_at": created_at,
                "conversation_id": original_tweet_id,
                "author_id": author_id,
            }
        )

        quote_tweet = tweepy.Tweet(
            {
                "id": quote_tweet_id,
                "text": "some reply",
                "edit_history_tweet_ids": [],
                "created_at": created_at,
                "conversation_id": original_tweet_id,
                "author_id": author_id,
                "referenced_tweets": [
                    tweepy.ReferencedTweet({"type": "quoted", "id": original_tweet_id}),
                ],
            }
        )

        db_connector.add_tweepy_tweet(db, original_tweet)
        db_connector.add_tweepy_tweet(db, quote_tweet)

        db_tweet = db_connector.get_tweet(db, quote_tweet_id)

        assert db_tweet, "tweet is non-empty"
        assert db_tweet.tweet_id == quote_tweet_id, "tweet ID"
        assert db_tweet.text == "some reply", "tweet text"
        assert db_tweet.author_id == author_id, "author ID"
        assert db_tweet.created_at == datetime(2024, 1, 1, 0, 0, 0, 0), "tweet created at"

        assert db_tweet.tweet_type == TweetType.QUOTE, "tweet type"
        assert db_tweet.conversation_id == original_tweet_id, "conversation ID"
        assert not db_tweet.reply_to_id, "reply to ID"
        assert db_tweet.quote_tweet_id == original_tweet_id, "quote tweet ID"

    def test_add_tweepy_tweet_duplicate(self, db: Session):
        """Tests that attempting to add a tweet that already exists, acts as a no-op"""
        tweet_id = 1
        original_tweet = build_tweet(id=tweet_id, text="some tweet", conversation_id=1)
        duplicate_tweet = build_tweet(id=tweet_id, text="duplicate", conversation_id=1)

        db_connector.add_tweepy_tweet(db, original_tweet)
        db_connector.add_tweepy_tweet(db, duplicate_tweet)

        db_tweet = db_connector.get_tweet(db, tweet_id)

        assert db_tweet
        assert db_tweet.text == "some tweet"
