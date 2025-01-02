from unittest.mock import AsyncMock, patch

import pytest
from conftest import build_tweet, build_tweet_mention
from sqlalchemy.orm import Session

from echos_lab.db import db_connector, models
from echos_lab.db.models import QueryType
from echos_lab.twitter import twitter_pipeline
from echos_lab.twitter.types import TweetExclusions


@pytest.mark.asyncio
class TestGetUserIdFromUsername:
    async def test_get_user_id_from_username_in_db(self, db: Session):
        """
        Tests fetching a user ID from a username when the user is in the database
        """
        user_id = 1
        username = "user"

        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        assert await twitter_pipeline.get_user_id_from_username(db, username) == user_id

    @patch("echos_lab.twitter.twitter_client.get_user_id_from_username")
    async def test_get_user_id_from_username_not_in_db(self, mock_get_user_id: AsyncMock, db: Session):
        """
        Tests fetching a user ID from a username when the user is NOT in the database
        """
        user_id = 1
        username = "user"

        mock_get_user_id.return_value = user_id

        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        assert await twitter_pipeline.get_user_id_from_username(db, username) == user_id


@pytest.mark.asyncio
class TestGetUsernameFromId:
    async def test_get_username_from_user_id_in_db(self, db: Session):
        """
        Tests fetching a username from a user ID when the user is in the database
        """
        user_id = 1
        username = "user"

        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        assert await twitter_pipeline.get_username_from_user_id(db, user_id) == username

    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_get_username_from_user_id_not_in_db(self, mock_get_username: AsyncMock, db: Session):
        """
        Tests fetching a username from a user ID when the user is NOT in the database
        """
        user_id = 1
        username = "user"

        mock_get_username.return_value = username

        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        assert await twitter_pipeline.get_username_from_user_id(db, user_id) == username


@pytest.mark.asyncio
class TestCheckpoint:
    async def test_create_get_checkpoint(self, db: Session):
        """
        Tests creating and getting a checkpoint
        """
        agent = "agent"

        # Add three users to the database
        for user_id in [1, 2, 3]:
            db_connector.add_twitter_user(db, user_id=user_id, username=f"user_{user_id}")

        # Create 3 checkpoints
        await twitter_pipeline.create_checkpoint(db, agent, user_id=1, query_type=QueryType.USER_MENTIONS, tweet_id=100)
        await twitter_pipeline.create_checkpoint(db, agent, user_id=2, query_type=QueryType.USER_TWEETS, tweet_id=200)
        await twitter_pipeline.create_checkpoint(db, "diff", user_id=3, query_type=QueryType.USER_TWEETS, tweet_id=300)

        # Fetch 2 of them
        checkpoint1 = twitter_pipeline.get_checkpoint(db, agent, user_id=1, query_type=QueryType.USER_MENTIONS)
        checkpoint2 = twitter_pipeline.get_checkpoint(db, agent, user_id=2, query_type=QueryType.USER_TWEETS)

        assert checkpoint1 and checkpoint1.last_tweet_id == 100
        assert checkpoint2 and checkpoint2.last_tweet_id == 200

        # Test None result from wrong query type
        assert not twitter_pipeline.get_checkpoint(db, agent, user_id=2, query_type=QueryType.USER_MENTIONS)

        # Test None result from wrong user ID
        assert not twitter_pipeline.get_checkpoint(db, agent, user_id=4, query_type=QueryType.USER_TWEETS)

    async def test_update_checkpoint(self, db: Session):
        """
        Tests updating a checkpoint
        """
        agent = "agent"

        # Add four users to the database
        for user_id in [1, 2, 3, 9]:
            db_connector.add_twitter_user(db, user_id=user_id, username=f"user_{user_id}")

        # Create 3 checkpoints
        await twitter_pipeline.create_checkpoint(db, agent, user_id=1, query_type=QueryType.USER_MENTIONS, tweet_id=100)
        await twitter_pipeline.create_checkpoint(db, agent, user_id=2, query_type=QueryType.USER_TWEETS, tweet_id=200)
        await twitter_pipeline.create_checkpoint(db, "diff", user_id=9, query_type=QueryType.USER_TWEETS, tweet_id=300)

        # Update 2 of them
        update1 = await twitter_pipeline.update_checkpoint(
            db, agent, user_id=1, query_type=QueryType.USER_MENTIONS, tweet_id=777
        )
        update2 = await twitter_pipeline.update_checkpoint(
            db, agent, user_id=2, query_type=QueryType.USER_TWEETS, tweet_id=888
        )

        # Update a checkpoint that doesn't yet exist
        update3 = await twitter_pipeline.update_checkpoint(
            db, agent, user_id=3, query_type=QueryType.USER_TWEETS, tweet_id=999
        )

        # Confirm responses from updates
        assert update1.last_tweet_id == 777
        assert update2.last_tweet_id == 888
        assert update3.last_tweet_id == 999

        # Retreive the updated checkpoints with get_checkpoint
        checkpoint1 = twitter_pipeline.get_checkpoint(db, agent, user_id=1, query_type=QueryType.USER_MENTIONS)
        checkpoint2 = twitter_pipeline.get_checkpoint(db, agent, user_id=2, query_type=QueryType.USER_TWEETS)
        checkpoint3 = twitter_pipeline.get_checkpoint(db, agent, user_id=3, query_type=QueryType.USER_TWEETS)

        assert checkpoint1 and checkpoint1.last_tweet_id == 777
        assert checkpoint2 and checkpoint2.last_tweet_id == 888
        assert checkpoint3 and checkpoint3.last_tweet_id == 999

    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_update_checkpoint_no_user(self, mock_get_username: AsyncMock, db: Session):
        """
        Tests trying to update the checkpoint when the userID does not exist
        """
        mock_get_username.return_value = None

        # Attempt to create a checkpoint when the user does not exist, it should error
        with pytest.raises(RuntimeError):
            await twitter_pipeline.create_checkpoint(
                db, "agent", user_id=1, query_type=QueryType.USER_MENTIONS, tweet_id=100
            )


@pytest.mark.asyncio
class TestGetTweetFromTweetId:
    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_get_tweet_from_tweet_id_in_db(self, mock_get_tweet: AsyncMock, db: Session):
        """
        Tests fetching a tweet from the tweet ID when it's already in the database
        """
        tweet_id = 1
        tweet = build_tweet(tweet_id, "text")

        # Add a tweet to the database
        db_connector.add_tweepy_tweet(db, tweet)

        # Fetch via the ID
        tweet = await twitter_pipeline.get_tweet_from_tweet_id(db, tweet_id)
        assert tweet and tweet.tweet_id == tweet_id

        # Confirm the API was never called
        mock_get_tweet.assert_not_called()

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_tweet_id_not_in_db(self, mock_get_tweet: AsyncMock, db: Session):
        """
        Tests fetching a tweet from the tweet ID when it's not in the database
        and we have to fallback to the API
        """
        tweet_id = 1
        author_id = 10
        tweet = build_tweet(tweet_id, "text", author_id=author_id)

        # Add the author to the database
        db_connector.add_twitter_user(db, user_id=author_id, username="user")

        # We itentionally do not add the tweet to the database so it falls back to the API
        # Mock the API response
        mock_get_tweet.return_value = tweet

        # Fetch the tweet from the ID
        tweet = await twitter_pipeline.get_tweet_from_tweet_id(db, tweet_id)
        assert tweet and tweet.tweet_id == tweet_id

        # Confirm the API was called
        mock_get_tweet.assert_called_once()

    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_user_not_in_db(self, mock_get_tweet: AsyncMock, mock_get_username: AsyncMock, db: Session):
        """
        Tests fetching a tweet from the tweet ID when it's not in the database
        and we have to fallback to the API, but the user is also not in the database
        """
        tweet_id = 1
        author_id = 10
        username = "username"
        tweet = build_tweet(tweet_id, "text", author_id=author_id)

        # We itentionally do not add the tweet to the database so it falls back to the API
        # Mock the API response
        mock_get_tweet.return_value = tweet
        mock_get_username.return_value = username

        # Fetch the tweet from the ID
        tweet = await twitter_pipeline.get_tweet_from_tweet_id(db, tweet_id)
        assert tweet and tweet.tweet_id == tweet_id

        # Confirm the user was also added
        user = db_connector.get_twitter_user(db, user_id=author_id)
        assert user and user.username == username

        # Confirm the API was called
        mock_get_tweet.assert_called_once()
        mock_get_username.assert_called_once()

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_get_tweet_from_tweet_id_not_found(self, mock_get_tweet: AsyncMock, db: Session):
        """
        Tests fetching a tweet where it's not in the DB nor the API
        """
        tweet_id = 1
        tweet = build_tweet(tweet_id, "text")

        # We itentionally do not add the tweet to the database so it falls back to the API
        # Mock the API response to return no tweet
        mock_get_tweet.return_value = None

        # Fetch the tweet from the ID
        tweet = await twitter_pipeline.get_tweet_from_tweet_id(db, tweet_id)
        assert not tweet


@pytest.mark.asyncio
class TestUserLatestTweets:
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    async def test_get_user_latest_tweets_with_checkpoint(self, mock_get_tweets: AsyncMock, db: Session):
        """
        Tests querying tweets for a user since the last checkpoint
        """
        agent = "agent"
        user_id = 1
        last_tweet_id = 10
        since_time = "1"

        # Create a user and checkpoint in the database
        db_connector.add_twitter_user(db, user_id=user_id, username="user")
        await twitter_pipeline.create_checkpoint(
            db, "agent", user_id=1, query_type=QueryType.USER_TWEETS, tweet_id=last_tweet_id
        )

        # Mock the response from get_user_latest tweets to return two tweets
        new_tweet_ids = [11, 12]
        returned_tweets = [
            build_tweet(11, "tweet1", author_id=user_id),
            build_tweet(12, "tweet2", author_id=user_id),
        ]
        mock_get_tweets.return_value = (returned_tweets, 12)

        # Call get latest tweets
        tweets = await twitter_pipeline.get_user_latest_tweets(db, agent, since_time=since_time, user_id=user_id)

        # Confirm the API query was called without the since_time
        assert mock_get_tweets.call_args.kwargs["since_time"] is None
        assert mock_get_tweets.call_args.kwargs["since_id"] == last_tweet_id

        # Confirm the returned tweets match the input
        assert [tweet.tweet_id for tweet in tweets] == new_tweet_ids

        # Confirm the tweets were saved
        assert [tweet.tweet_id for tweet in db.query(models.Tweet).all()] == new_tweet_ids

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_TWEETS)
        assert checkpoint and checkpoint.last_tweet_id == new_tweet_ids[-1]

    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    async def test_get_user_latest_tweets_no_checkpoint(self, mock_get_tweets: AsyncMock, db: Session):
        """
        Tests querying tweets for a user when there are no checkpoints found
        """
        agent = "agent"
        user_id = 1
        since_time = "1"

        # Create a user in the database, but intentionally avoid adding a checkpoint
        db_connector.add_twitter_user(db, user_id=user_id, username="user")

        # Mock the response from get_user_latest tweets to return two tweets
        new_tweet_ids = [11, 12]
        returned_tweets = [
            build_tweet(11, "tweet1", author_id=user_id),
            build_tweet(12, "tweet2", author_id=user_id),
        ]
        mock_get_tweets.return_value = (returned_tweets, 12)

        # Call get latest tweets
        tweets = await twitter_pipeline.get_user_latest_tweets(db, agent, since_time=since_time, user_id=user_id)

        # Confirm the API query was called with the since_time
        assert mock_get_tweets.call_args.kwargs["since_time"] == since_time
        assert mock_get_tweets.call_args.kwargs["since_id"] is None

        # Confirm the returned tweets match the input
        assert [tweet.tweet_id for tweet in tweets] == new_tweet_ids

        # Confirm the tweets were saved
        assert [tweet.tweet_id for tweet in db.query(models.Tweet).all()] == new_tweet_ids

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_TWEETS)
        assert checkpoint and checkpoint.last_tweet_id == new_tweet_ids[-1]

    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    async def test_get_user_latest_tweets_from_username(self, mock_get_tweets: AsyncMock, db: Session):
        """
        Tests querying tweets for a user from the username
        """
        agent = "agent"
        user_id = 1
        username = "user"
        last_tweet_id = 10
        since_time = "1"

        # Create a user and checkpoint in the database
        db_connector.add_twitter_user(db, user_id=user_id, username=username)
        await twitter_pipeline.create_checkpoint(
            db, "agent", user_id=1, query_type=QueryType.USER_TWEETS, tweet_id=last_tweet_id
        )

        # Mock the response from get_user_latest tweets to return one tweet
        new_tweet_ids = [11, 12]
        returned_tweets = [
            build_tweet(11, "tweet1", author_id=user_id),
            build_tweet(12, "tweet2", author_id=user_id),
        ]
        mock_get_tweets.return_value = (returned_tweets, 12)

        # Call get latest tweets with the username
        tweets = await twitter_pipeline.get_user_latest_tweets(db, agent, since_time=since_time, username=username)

        # Confirm the returned tweets and DB tweets match the input
        assert [tweet.tweet_id for tweet in tweets] == new_tweet_ids
        assert [tweet.tweet_id for tweet in db.query(models.Tweet).all()] == new_tweet_ids

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_TWEETS)
        assert checkpoint and checkpoint.last_tweet_id == new_tweet_ids[-1]

    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    async def test_get_user_latest_tweets_exclusions(self, mock_get_tweets: AsyncMock, db: Session):
        """
        Tests querying tweets for a user with exclusions
        """
        agent = "agent"
        user_id = 1
        last_tweet_id = 10
        since_time = "1"

        # Create a user and checkpoint in the database
        db_connector.add_twitter_user(db, user_id=user_id, username="user")
        await twitter_pipeline.create_checkpoint(
            db, "agent", user_id=1, query_type=QueryType.USER_TWEETS, tweet_id=last_tweet_id
        )

        # Mock the response from get_user_latest tweets to return one two tweet
        # However, make the second tweet be a quote tweet
        returned_tweets = [
            build_tweet(11, "tweet1", author_id=user_id),
            build_tweet(12, "tweet2", author_id=user_id, reference_id=1, reference_type="quoted"),
        ]
        mock_get_tweets.return_value = (returned_tweets, 12)

        # Call get latest tweets
        tweets = await twitter_pipeline.get_user_latest_tweets(
            db, agent, since_time=since_time, user_id=user_id, exclusions=[TweetExclusions.QUOTE_TWEETS]
        )

        # Confirm the returned tweets only includes the first tweet (since the 2nd was excluded)
        assert len(tweets) == 1
        assert tweets[0].tweet_id == 11

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_TWEETS)
        assert checkpoint and checkpoint.last_tweet_id == 12


@pytest.mark.asyncio
class TestAddTwitterUser:
    async def test_user_id_and_username(self, db: Session):
        """
        Tests adding a new user while specifying the user_id and username
        """
        user_id = 1
        username = "user"

        await twitter_pipeline.add_twitter_user(db, user_id=user_id, username=username)

        user = db_connector.get_twitter_user(db, user_id=user_id)
        assert user
        assert user.username == username

    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_user_id_only(self, mock_get_username: AsyncMock, db: Session):
        """
        Tests adding a new user while specifying the user_id only and querying the username
        """
        user_id = 1
        username = "user"

        mock_get_username.return_value = username
        await twitter_pipeline.add_twitter_user(db, user_id=user_id)

        user = db_connector.get_twitter_user(db, user_id=user_id)
        assert user
        assert user.username == username

    @patch("echos_lab.twitter.twitter_client.get_user_id_from_username")
    async def test_username_only(self, mock_get_user_id: AsyncMock, db: Session):
        """
        Tests adding a new user while specifying the username only and querying the user ID
        """
        user_id = 1
        username = "user"

        mock_get_user_id.return_value = user_id
        await twitter_pipeline.add_twitter_user(db, username=username)

        user = db_connector.get_twitter_user(db, user_id=user_id)
        assert user
        assert user.username == username

    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    @patch("echos_lab.twitter.twitter_client.get_user_id_from_username")
    async def test_user_not_found(self, mock_get_username: AsyncMock, mock_get_user_id: AsyncMock, db: Session):
        """
        Tests adding a new user when the user cannot be found
        """
        mock_get_username.return_value = None
        mock_get_user_id.return_value = None

        with pytest.raises(RuntimeError):
            await twitter_pipeline.add_twitter_user(db, user_id=1)

        with pytest.raises(RuntimeError):
            await twitter_pipeline.add_twitter_user(db, username="user")


@pytest.mark.asyncio
class TestUserMentions:
    @patch("echos_lab.twitter.twitter_client.get_all_user_mentions")
    async def test_get_user_mentions_with_checkpoint(self, mock_get_mentions: AsyncMock, db: Session):
        """
        Tests querying for user mentions since the last checkpoint
        """
        agent = "agent"
        user_id = 1
        last_tweet_id = 10
        since_time = "1"

        # Create a user and checkpoint in the database
        db_connector.add_twitter_user(db, user_id=user_id, username="user")
        await twitter_pipeline.create_checkpoint(
            db, "agent", user_id=1, query_type=QueryType.USER_MENTIONS, tweet_id=last_tweet_id
        )

        # Mock the response from get_all_user_mentions to return two mentions
        new_tweet_ids = [11, 12]
        returned_mentions = [
            build_tweet_mention(build_tweet(11, "tweet1", author_id=user_id), username="userA"),
            build_tweet_mention(build_tweet(12, "tweet2", author_id=user_id), username="userB"),
        ]
        mock_get_mentions.return_value = (returned_mentions, 12)

        # Call get user mentions
        mentions = await twitter_pipeline.get_user_mentions(db, agent, agent_id=user_id, since_time=since_time)

        # Confirm the API query was called without the since_time
        assert mock_get_mentions.call_args.kwargs["since_time"] is None
        assert mock_get_mentions.call_args.kwargs["since_tweet_id"] == last_tweet_id

        # Confirm the returned tweets match the input
        assert [mention.tagged_tweet.id for mention in mentions] == new_tweet_ids

        # Confirm the tweets were saved
        assert [tweet.tweet_id for tweet in db.query(models.Tweet).all()] == new_tweet_ids

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_MENTIONS)
        assert checkpoint and checkpoint.last_tweet_id == new_tweet_ids[-1]

    @patch("echos_lab.twitter.twitter_client.get_all_user_mentions")
    async def test_get_user_mentions_no_checkpoint(self, mock_get_mentions: AsyncMock, db: Session):
        """
        Tests querying for user mentions when there are no checkpoints found
        """
        agent = "agent"
        user_id = 1
        since_time = "1"

        # Create a user in the database, but intentionally avoid adding a checkpoint
        db_connector.add_twitter_user(db, user_id=user_id, username="user")

        # Mock the response from get_user_latest tweets to return two tweets
        new_tweet_ids = [11, 12]
        returned_mentions = [
            build_tweet_mention(build_tweet(11, "tweet1", author_id=user_id), username="userA"),
            build_tweet_mention(build_tweet(12, "tweet2", author_id=user_id), username="userB"),
        ]
        mock_get_mentions.return_value = (returned_mentions, 12)

        # Call get user mentions
        mentions = await twitter_pipeline.get_user_mentions(db, agent, agent_id=user_id, since_time=since_time)

        # Confirm the API query was called with the since_time
        assert mock_get_mentions.call_args.kwargs["since_time"] == since_time
        assert mock_get_mentions.call_args.kwargs["since_tweet_id"] is None

        # Confirm the returned tweets match the input
        assert [mention.tagged_tweet.id for mention in mentions] == new_tweet_ids

        # Confirm the tweets were saved
        assert [tweet.tweet_id for tweet in db.query(models.Tweet).all()] == new_tweet_ids

        # Confirm the checkpoint was updated
        checkpoint = twitter_pipeline.get_checkpoint(db, agent, user_id, query_type=QueryType.USER_MENTIONS)
        assert checkpoint and checkpoint.last_tweet_id == new_tweet_ids[-1]
