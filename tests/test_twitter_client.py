from collections import OrderedDict
from unittest.mock import AsyncMock, Mock, call, patch

import fixtures.prompts as test_prompts
import pytest
from conftest import (
    AGENT_TWITTER_HANDLE,
    agent_profile,
    build_db_tweet,
    build_hydrated_tweet,
    build_reply_reference,
    build_tweepy_response,
    build_tweet,
    build_tweet_evaluation,
    build_tweet_mention,
    build_user,
    check_tweet_mention_equality,
    generate_random_id,
    generate_random_username,
)
from fixtures.prompts import normalize_prompts
from sqlalchemy.orm import Session
from tweepy.asynchronous import AsyncClient

from echos_lab.db import db_connector
from echos_lab.engines import prompts
from echos_lab.engines.personalities.profiles import FollowedAccount
from echos_lab.twitter import twitter_client
from echos_lab.twitter.types import HydratedTweet, TweetMention


@pytest.mark.asyncio
class TestHydratedTweet:
    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_hydrated_tweet(self, mock_get_username: AsyncMock):
        """
        Tests the username lookup from a hydrated tweet
        """
        username = "userA"
        user_id = generate_random_id()

        # Build a raw tweet from the given user
        raw_tweet = build_tweet(id=1, text="some tweet", author_id=user_id)

        # Build the hydrated tweet
        hydrated_tweet = HydratedTweet(raw_tweet)

        # Mock the API response that returns the username
        mock_get_username.return_value = username

        # Get the username from the hydrated tweet
        assert await hydrated_tweet.get_username() == username


@pytest.mark.asyncio
class TestTweetMention:
    async def test_mention_type(self):
        """
        Tests the mention type of the object
        """
        original_mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "Hey @bot"), "tagging-user"),
            original_tweet=None,
            replies=[],
        )
        assert original_mention.mention_type == twitter_client.MentionType.TAGGED_IN_ORIGINAL

        direct_reply_mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my tweet"), "original-user"),
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), "tagging-user"),
            replies=[],
        )

        assert direct_reply_mention.mention_type == twitter_client.MentionType.TAGGED_IN_DIRECT_REPLY

        thread_mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my original tweet"), "original-user"),
            replies=[build_hydrated_tweet(build_tweet(1, "But I think..."), "replierA")],
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot what do you think?"), "tagging-user"),
        )
        assert thread_mention.mention_type == twitter_client.MentionType.TAGGED_IN_THREAD

    async def test_to_prompt_summary_original(self):
        """
        Tests building the LLM conversation summary from a tag in an original tweet
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "Hey @bot"), "tagging-user"),
            original_tweet=None,
            replies=[],
        )

        actual_summary = await mention.to_prompt_summary()
        expected_summary = """
        <tweet>
        @tagging-user
        Hey @bot
        </tweet>
        """

        assert normalize_prompts(actual_summary) == normalize_prompts(expected_summary)

    async def test_to_prompt_summary_direct_reply(self):
        """
        Tests building the LLM conversation summary from a direct reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my tweet"), "original-user"),
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), "tagging-user"),
            replies=[],
        )

        actual_summary = await mention.to_prompt_summary()
        expected_summary = """
        <original_tweet>
        @original-user
        This is my tweet
        </original_tweet>
        <reply_tagging_you>
        @tagging-user
        @bot
        </reply_tagging_you>
        """

        assert normalize_prompts(actual_summary) == normalize_prompts(expected_summary)

    async def test_to_prompt_summary_thread_reply(self):
        """
        Tests building the LLM conversation summary from a thread reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my original tweet"), "original-user"),
            replies=[
                build_hydrated_tweet(build_tweet(1, "But I think..."), "replierA"),
                build_hydrated_tweet(build_tweet(1, "But I think otherwise..."), "replierB"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot what do you think?"), "tagging-user"),
        )

        actual_summary = await mention.to_prompt_summary()
        expected_summary = """
        <original_tweet>
        @original-user
        This is my original tweet
        </original_tweet>

        <reply_1>
        @replierA
        But I think...
        </reply_1>
        
        <reply_2>
        @replierB
        But I think otherwise...
        </reply_2>

        <reply_tagging_you>
        @tagging-user
        @bot what do you think?
        </reply_tagging_you>
        """  # noqa

        assert normalize_prompts(actual_summary) == normalize_prompts(expected_summary)


@pytest.mark.asyncio
class TestBuildMentionPrompt:
    async def test_to_prompt_original(self):
        """
        Tests building the LLM conversation summary from a tag in an original tweet
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "Hey @bot"), "tagging-user"),
            original_tweet=None,
            replies=[],
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_ORIGINAL_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)

    async def test_to_prompt_direct_reply(self):
        """
        Tests building the LLM conversation summary from a direct reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my tweet"), "original-user"),
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), "tagging-user"),
            replies=[],
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_DIRECT_REPLY_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)

    async def test_to_prompt_thread_reply(self):
        """
        Tests building the LLM conversation summary from a thread reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my original tweet"), "original-user"),
            replies=[
                build_hydrated_tweet(build_tweet(1, "But I think..."), "replierA"),
                build_hydrated_tweet(build_tweet(1, "But I think otherwise..."), "replierB"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot what do you think?"), "tagging-user"),
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_THREAD_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)


@pytest.mark.asyncio
class TestGetUserIdFromUsername:
    async def test_get_user_id_from_username_success(self, mock_client: type[AsyncClient]):
        """
        Tests successfully fetching a user-id from username
        """
        username = generate_random_username()
        expected_user_id = 123

        # Build mocked response
        user = build_user(id=expected_user_id, username=username)
        response = build_tweepy_response(data=user)
        mock_client.get_user.return_value = response

        # Fetch user ID
        actual_user_id = await twitter_client.get_user_id_from_username(username)
        assert actual_user_id == expected_user_id
        mock_client.get_user.assert_called_once_with(username=username)

    async def test_get_user_id_from_username_no_data(self, mock_client: type[AsyncClient]):
        """
        Tests a response with no data (when the username is not found)
        """
        username = generate_random_username()

        # Build mocked response with no data
        response = build_tweepy_response(data=None)
        mock_client.get_user.return_value = response

        # It should return None
        actual_user_id = await twitter_client.get_user_id_from_username(username)
        assert actual_user_id is None


@pytest.mark.asyncio
class TestGetUsernameFromId:
    async def test_get_username_from_user_id_success(self, mock_client: type[AsyncClient]):
        """
        Tests successfully fetching a username from user ID
        """
        user_id = generate_random_id()
        expected_username = "user"

        # Build mocked response
        user = build_user(id=user_id, username=expected_username)
        response = build_tweepy_response(data=user)
        mock_client.get_user.return_value = response

        # Fetch username
        actual_username = await twitter_client.get_username_from_user_id(user_id)
        assert actual_username == expected_username
        mock_client.get_user.assert_called_once_with(id=user_id)

    async def test_get_username_from_user_id_no_data(self, mock_client: type[AsyncClient]):
        """
        Tests a response with no data (when the user ID is not found)
        """
        user_id = generate_random_id()

        # Build mocked response with no data
        response = build_tweepy_response(data=None)
        mock_client.get_user.return_value = response

        # It should return None
        actual_username = await twitter_client.get_username_from_user_id(user_id)
        assert actual_username is None


@pytest.mark.asyncio
class TestGetTweetFromTweetId:
    async def test_get_tweet_from_tweet_id_success(self, mock_client: type[AsyncClient]):
        """
        Tests successfully fetching a tweet
        """
        tweet_id = generate_random_id()

        # Build mocked response
        expected_tweet = build_tweet(tweet_id, text="My first tweet")
        response = build_tweepy_response(data=expected_tweet)
        mock_client.get_tweet.return_value = response

        # Fetch tweet
        actual_tweet = await twitter_client.get_tweet_from_tweet_id(tweet_id)
        assert actual_tweet == expected_tweet

        mock_client.get_tweet.assert_called_once()
        assert mock_client.get_tweet.call_args.kwargs["id"] == tweet_id

    async def test_get_tweet_from_tweet_id_no_data(self, mock_client: type[AsyncClient]):
        """
        Tests a response with no data (when the tweet is not found)
        """
        tweet_id = generate_random_id()

        # Build mocked response with no data
        response = build_tweepy_response(data=None)
        mock_client.get_tweet.return_value = response

        # It should return None
        actual_tweet = await twitter_client.get_tweet_from_tweet_id(tweet_id)
        assert actual_tweet is None


@pytest.mark.asyncio
class TestHasHighFollowerCount:
    async def test_has_high_follower_count_true(self, mock_client: type[AsyncClient]):
        """
        Tests an account with a high follower count
        """
        user_id = generate_random_id()
        followers = 100
        follower_threshold = 50

        user = build_user(id=user_id, username="username", followers=followers)
        mock_client.get_user.return_value = build_tweepy_response(data=user)

        assert await twitter_client.has_high_follower_count(user_id, threshold_num_followers=follower_threshold)

    async def test_has_high_follower_count_false(self, mock_client: type[AsyncClient]):
        """
        Tests an account with a low follower count
        """
        user_id = generate_random_id()
        followers = 50
        follower_threshold = 100

        user = build_user(id=user_id, username="username", followers=followers)
        mock_client.get_user.return_value = build_tweepy_response(data=user)

        assert not (await twitter_client.has_high_follower_count(user_id, threshold_num_followers=follower_threshold))

    async def test_has_high_follower_count_no_account(self, mock_client: type[AsyncClient]):
        """
        Tests with an account that's not found
        """
        user_id = generate_random_id()

        mock_client.get_user.return_value = build_tweepy_response(data=None)

        assert not (await twitter_client.has_high_follower_count(user_id, threshold_num_followers=10))


@pytest.mark.asyncio
class TestGetTweetsFromUserId:
    async def test_get_tweets_from_user_id_success(self, mock_client: type[AsyncClient]):
        """
        Tests successfully fetching tweets
        """
        user_id = generate_random_id()

        # Build mocked response
        newest_tweet_id = 2
        expected_tweets = [
            build_tweet(1, text="My first tweet"),
            build_tweet(2, text="My second tweet"),
        ]
        response = build_tweepy_response(data=expected_tweets, meta={"newest_id": newest_tweet_id})
        mock_client.get_users_tweets.return_value = response

        # Fetch tweets
        actual_tweets, actual_latest_tweet_id = await twitter_client.get_tweets_from_user_id(user_id)
        assert actual_tweets == expected_tweets
        assert actual_latest_tweet_id == newest_tweet_id

        mock_client.get_users_tweets.assert_called_once()
        assert mock_client.get_users_tweets.call_args.kwargs["id"] == user_id

    async def test_get_tweets_from_user_id_no_data(self, mock_client: type[AsyncClient]):
        """
        Tests a response with no data (when no tweets were not found)
        """
        user_id = generate_random_id()

        # Build mocked response with no data
        response = build_tweepy_response(data=None)
        mock_client.get_users_tweets.return_value = response

        # It should return None
        actual_tweets, actual_tweet_id = await twitter_client.get_tweets_from_user_id(user_id)
        assert actual_tweets == []
        assert actual_tweet_id is None


@pytest.mark.asyncio
class TestGetUserIdsFromUsernames:
    @patch("echos_lab.twitter.twitter_client.get_user_id_from_username")
    async def test_get_user_ids_from_usernames_success(self, mock_get_user_id: AsyncMock, db: Session):
        """
        Tests successfully gathering user IDs from usernames
        """
        user_id_A = 1
        user_id_B = 2

        username_A = "userA"
        username_B = "userB"

        usernames = [username_A, username_B]
        expected_user_id_mapping = {username_A: user_id_A, username_B: user_id_B}

        # Add userA to the database and mock the API response for userB
        # so that it's returned when it falls back to the API
        db_connector.add_twitter_user(db, user_id=user_id_A, username=username_A)
        mock_get_user_id.return_value = user_id_B

        # Get user IDs
        actual_user_id_mapping = await twitter_client.get_user_ids_from_usernames(db, usernames)
        assert actual_user_id_mapping == expected_user_id_mapping

        # Confirm the API was only called once
        mock_get_user_id.assert_called_once()

    @patch("echos_lab.twitter.twitter_client.get_user_id_from_username")
    async def test_get_user_ids_from_usernames_not_found(self, mock_get_user_id: AsyncMock, db: Session):
        """
        Tests handling of missing user ID
        """
        usernames = ["userA"]

        # We'll intentionally not add the twitter user to the database
        # so it falls back to the API
        # And then we'll also mock that API response to return None
        mock_get_user_id.return_value = None

        with pytest.raises(RuntimeError, match=r"Twitter User ID not found for handle @userA"):
            await twitter_client.get_user_ids_from_usernames(db, usernames)


@pytest.mark.asyncio
class TestGetAllFollowerTweets:
    @patch("echos_lab.twitter.twitter_pipeline.get_user_latest_tweets")
    async def test_get_all_follower_tweets_success(self, mock_get_user_tweets: AsyncMock, db: Session):
        """
        Tests retrieving tweets from multiple followers
        """
        since_time = "1"
        agent_name = "agent"

        # Setup ordered user mapping
        # It must be an ordered dict in order to line up with the mocked side effects
        userA, userB = "userA", "userB"
        user_id_mapping = OrderedDict([(userA, 1), (userB, 2)])

        # Build test tweets
        latest_tweet_A = 200
        latest_tweet_B = 400
        userA_tweets = [
            build_db_tweet(100, "tweet1", conversation_id=100),
            build_db_tweet(latest_tweet_A, "tweet2", conversation_id=latest_tweet_A),
        ]
        userB_tweets = [
            build_db_tweet(300, "tweet3", conversation_id=300),
            build_db_tweet(latest_tweet_B, "tweet4", conversation_id=latest_tweet_B),
        ]
        expected_tweets = [
            twitter_client.FollowerTweet(tweet=userA_tweets[0], username=userA),
            twitter_client.FollowerTweet(tweet=userA_tweets[1], username=userA),
            twitter_client.FollowerTweet(tweet=userB_tweets[0], username=userB),
            twitter_client.FollowerTweet(tweet=userB_tweets[1], username=userB),
        ]

        # Mock DB responses
        mock_get_user_tweets.side_effect = [userA_tweets, userB_tweets]

        # Get all follower tweets
        actual_tweets = await twitter_client.get_all_follower_tweets(
            db=db,
            agent_name=agent_name,
            user_id_mapping=user_id_mapping,  # type: ignore
            since_time=since_time,
        )
        assert actual_tweets == expected_tweets


@pytest.mark.asyncio
class TestGetParentTweets:
    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_get_parent_tweet(self, mock_get_tweet: AsyncMock):
        """
        Tests fetching the parent tweet with a successful response
        """
        original_id = 1
        reply_id = 2

        # Build the original and reply tweets
        original_tweet = build_tweet(original_id, "original")
        reply_tweet = build_tweet(reply_id, "reply")
        reply_tweet.referenced_tweets = [build_reply_reference(original_id)]
        reply_tweet.conversation_id = original_id

        # Mock the tweet lookup for the original tweet
        mock_get_tweet.return_value = original_tweet

        # Confirm the lookup returned the original tweet
        expected_parent = await twitter_client.get_parent_tweet(reply_tweet)
        assert expected_parent == original_tweet
        mock_get_tweet.assert_called_once_with(original_id)

    async def test_get_parent_tweet_is_root(self):
        """
        Tests fetching the parent tweet when the current tweet is already the root
        (as defined by the conversation ID)
        """
        original_id = 1

        # Build the original and reply tweet (the same tweet)
        original_tweet = build_tweet(1, "original")
        reply_tweet = original_tweet
        reply_tweet.conversation_id = original_id

        # Confirm the parent lookup returned none
        expected_parent = await twitter_client.get_parent_tweet(reply_tweet)
        assert expected_parent is None

    async def test_get_parent_tweet_no_ref(self):
        """
        Tests fetching the parent tweet when the current tweet is already the root
        (as defined by the references)
        """
        # Build the original and reply tweet (the same tweet)
        # However, don't set the conversation ID
        # Instead, just leave referenced_tweets empty
        original_tweet = build_tweet(1, "original")
        reply_tweet = original_tweet
        reply_tweet.referenced_tweets = None

        # Confirm the parent lookup returned none
        expected_parent = await twitter_client.get_parent_tweet(reply_tweet)
        assert expected_parent is None

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    async def test_get_parent_tweets(self, mock_get_tweet: AsyncMock):
        """
        Tests fetching all parent tweets in a thread
        """
        original_id = 1
        thread_1_id = 2
        thread_2_id = 3
        reply_id = 4

        # Build the original and reply tweets
        original_tweet = build_tweet(original_id, "original", created_at="1", conversation_id=1)
        thread1_tweet = build_tweet(thread_1_id, "thread1", created_at="2", conversation_id=1)
        thread2_tweet = build_tweet(thread_2_id, "thread2", created_at="3", conversation_id=1)
        reply_tweet = build_tweet(reply_id, "reply", created_at="4", conversation_id=1)

        thread1_tweet.referenced_tweets = [build_reply_reference(original_id)]
        thread2_tweet.referenced_tweets = [build_reply_reference(thread_1_id)]
        reply_tweet.referenced_tweets = [build_reply_reference(thread_2_id)]
        reply_tweet.conversation_id = original_id

        # Mock the tweet lookup in order of the functions calls
        # The calls go up the stack from reply to original
        mock_get_tweet.side_effect = [thread2_tweet, thread1_tweet, original_tweet]

        # Confirm the list of tweets is returned and sorted by time
        expected_parents = [original_tweet, thread1_tweet, thread2_tweet]
        actual_parents = await twitter_client.get_all_parent_tweets(reply_tweet)
        assert expected_parents == actual_parents


@pytest.mark.asyncio
class TestEnrichUserMention:
    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_enrich_user_mention_no_parent(self, mock_get_username: AsyncMock):
        """
        Tests successfully enriching a tweet mention when there was no parent tweet
        """
        user_id = generate_random_id()
        username = generate_random_username()

        # Build the single tweet
        original_id = 1
        original_tweet = build_tweet(original_id, "original")
        original_tweet.author_id = user_id
        original_tweet.conversation_id = original_id

        # Mock the username lookup
        mock_get_username.return_value = username

        # Enrich
        expected_mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(original_tweet, username),
            original_tweet=None,
            replies=[],
        )
        actual_mention = await twitter_client.enrich_user_mention(original_tweet)
        check_tweet_mention_equality(actual_mention, expected_mention)

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_enrich_user_mention_one_parent(self, mock_get_username: AsyncMock, mock_get_tweet: AsyncMock):
        """
        Tests successfully enriching a tweet mention when there was one parent tweet
        """
        user_id = generate_random_id()
        username = generate_random_username()

        # Build the original and reply tweets
        original_id = 1
        reply_id = 2

        original_tweet = build_tweet(original_id, "original")
        original_tweet.author_id = user_id
        original_tweet.conversation_id = original_id

        reply_tweet = build_tweet(reply_id, "reply")
        reply_tweet.author_id = user_id
        reply_tweet.conversation_id = original_id
        reply_tweet.referenced_tweets = [build_reply_reference(original_id)]

        # Mock the username and tweet lookups
        mock_get_username.return_value = username
        mock_get_tweet.return_value = original_tweet

        # Enrich
        expected_mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(reply_tweet, username),
            original_tweet=build_hydrated_tweet(original_tweet, username),
            replies=[],
        )
        actual_mention = await twitter_client.enrich_user_mention(reply_tweet)
        check_tweet_mention_equality(actual_mention, expected_mention)

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_enrich_user_mention_long_thread(self, mock_get_username: AsyncMock, mock_get_tweet: AsyncMock):
        """
        Tests successfully enriching a tweet mention when there were multiple parent tweets
        """
        user_id = generate_random_id()
        username = generate_random_username()

        # Build the original and reply tweets
        original_id = 1
        thread_id = 2
        reply_id = 3

        original_tweet = build_tweet(original_id, "original", created_at="1")
        original_tweet.author_id = user_id
        original_tweet.conversation_id = original_id

        thread_tweet = build_tweet(thread_id, "thread", created_at="2")
        thread_tweet.author_id = user_id
        thread_tweet.conversation_id = original_id
        thread_tweet.referenced_tweets = [build_reply_reference(original_id)]

        reply_tweet = build_tweet(reply_id, "reply", created_at="3")
        reply_tweet.author_id = user_id
        reply_tweet.conversation_id = thread_id
        reply_tweet.referenced_tweets = [build_reply_reference(thread_id)]

        # Mock the username and tweet lookups
        mock_get_username.return_value = username
        mock_get_tweet.side_effect = [thread_tweet, original_tweet]

        # Enrich
        expected_mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(reply_tweet, username),
            original_tweet=build_hydrated_tweet(reply_tweet, username),
            replies=[build_hydrated_tweet(thread_tweet, username)],
        )
        actual_mention = await twitter_client.enrich_user_mention(reply_tweet)
        check_tweet_mention_equality(actual_mention, expected_mention)

    @patch("echos_lab.twitter.twitter_client.get_tweet_from_tweet_id")
    @patch("echos_lab.twitter.twitter_client.get_username_from_user_id")
    async def test_enrich_user_mention_username_not_found(
        self,
        mock_get_username: AsyncMock,
        mock_get_tweet: AsyncMock,
    ):
        """
        Tests successfully enriching a tweet mention when the username could not be found
        """
        user_id = generate_random_id()

        # Build the original and reply tweets
        original_id = 1
        reply_id = 2

        original_tweet = build_tweet(original_id, "original")
        original_tweet.author_id = user_id
        original_tweet.conversation_id = original_id

        reply_tweet = build_tweet(reply_id, "reply")
        reply_tweet.author_id = user_id
        reply_tweet.conversation_id = original_id
        reply_tweet.referenced_tweets = [build_reply_reference(original_id)]

        # Mock the username and tweet lookups
        # Since the username lookup is none, it should be displayed as "Unknown"
        mock_get_username.return_value = None
        mock_get_tweet.return_value = original_tweet

        # Enrich
        expected_mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(reply_tweet, "Unknown"),
            original_tweet=build_hydrated_tweet(original_tweet, "Unknown"),
            replies=[],
        )
        actual_mention = await twitter_client.enrich_user_mention(reply_tweet)
        check_tweet_mention_equality(actual_mention, expected_mention)


@pytest.mark.asyncio
class TestGetUserMentions:
    @patch("echos_lab.twitter.twitter_client.enrich_user_mention")
    async def test_get_user_mentions_batch_success(self, mock_enrich: AsyncMock, mock_client: type[AsyncClient]):
        """
        Tests successfully getting a batch of mentions
        """
        user_id = generate_random_id()
        newest_tweet_id = generate_random_id()

        mention_tweets = [
            build_tweet(1, text="Tagging @bot"),
            build_tweet(2, text="Tagging @bot"),
        ]

        expected_mentions = [
            build_tweet_mention(mention_tweets[0], "user1"),
            build_tweet_mention(mention_tweets[1], "user2"),
        ]

        # Build response from get_user_mentions
        response = build_tweepy_response(mention_tweets, meta={"newest_id": newest_tweet_id})
        mock_client.get_users_mentions.return_value = response

        # Mock enrich response
        mock_enrich.side_effect = expected_mentions

        # Call get user batch
        result = await twitter_client.get_user_mentions_batch(
            user_id,
            since_tweet_id=None,
            since_time=None,
        )
        assert result is not None

        actual_mentions, actual_last_last_id = result
        assert actual_mentions == expected_mentions
        assert actual_last_last_id == newest_tweet_id

        mock_client.get_users_mentions.assert_called_once()
        assert mock_client.get_users_mentions.call_args.args[0] == user_id
        assert mock_enrich.call_count == 2

    async def test_get_user_mentions_batch_no_data(self, mock_client: type[AsyncClient]):
        """
        Tests fetching user mentions when none are found
        """
        user_id = generate_random_id()

        # Build None response
        response = build_tweepy_response(data=None)
        mock_client.get_users_mentions.return_value = response

        # Call get user batch
        result = await twitter_client.get_user_mentions_batch(
            user_id,
            since_tweet_id=None,
            since_time=None,
        )
        assert result is None

    @patch("echos_lab.twitter.twitter_client.get_user_mentions_batch")
    async def test_get_all_user_mentions_one_partial_batch(self, mock_get_mentions: AsyncMock):
        """
        Tests calling get all user mentions when there's only one batch request
        and the first request returns less tweets than the batch size
        """
        batch_size = 2
        user_id = generate_random_id()

        expected_mentions = [
            build_tweet_mention(build_tweet(1, text="Tagging @bot", created_at="1"), "userA"),
        ]
        latest_tweet_id = 1

        # Build response from get_user_mentions_batch
        # Since the response size is less than the batch size, the loop should break
        mock_get_mentions.return_value = (expected_mentions, latest_tweet_id)

        # Call get all user mentions
        actual_mentions, actual_last_last_id = await twitter_client.get_all_user_mentions(
            user_id,
            since_tweet_id=None,
            since_time=None,
            batch_size=batch_size,
        )

        assert actual_mentions == expected_mentions
        assert actual_last_last_id == latest_tweet_id
        mock_get_mentions.assert_called_once()
        assert mock_get_mentions.call_args.kwargs["since_tweet_id"] is None

    @patch("echos_lab.twitter.twitter_client.get_user_mentions_batch")
    async def test_get_all_user_mentions_one_full_batch(self, mock_get_mentions: AsyncMock):
        """
        Tests calling get all user mentions when there's two requests called
        but the second request returns no data
        """
        batch_size = 2
        user_id = generate_random_id()

        expected_mentions = [
            build_tweet_mention(build_tweet(1, text="Tagging @bot", created_at="1"), "userA"),
            build_tweet_mention(build_tweet(2, text="Tagging @bot", created_at="2"), "userB"),
        ]
        latest_tweet_id = 2

        # Build response from get_user_mentions_batch
        # The first response will have the 2 mentions (equal to batch size)
        # and the second response will be None, which will break the loop
        response1 = (expected_mentions, latest_tweet_id)
        response2 = None
        mock_get_mentions.side_effect = [response1, response2]

        # Call get all user mentions
        actual_mentions, actual_last_last_id = await twitter_client.get_all_user_mentions(
            user_id,
            since_tweet_id=None,
            since_time=None,
            batch_size=batch_size,
        )
        assert actual_mentions == expected_mentions
        assert actual_last_last_id == latest_tweet_id

        # Confirm function calls
        assert mock_get_mentions.call_count == 2
        assert mock_get_mentions.call_args_list[0].kwargs["since_tweet_id"] is None
        assert mock_get_mentions.call_args_list[1].kwargs["since_tweet_id"] == latest_tweet_id

    @patch("echos_lab.twitter.twitter_client.get_user_mentions_batch")
    async def test_get_all_user_mentions_multiple_batches(self, mock_get_mentions: AsyncMock):
        """
        Tests calling get all user mentions when multiple batches were requested
        and tweets were returned in both batches
        """
        batch_size = 2
        user_id = generate_random_id()

        expected_mentions = [
            build_tweet_mention(build_tweet(1, text="Tagging @bot", created_at="1"), "userA"),
            build_tweet_mention(build_tweet(2, text="Tagging @bot", created_at="2"), "userB"),
            build_tweet_mention(build_tweet(3, text="Tagging @bot", created_at="2"), "userB"),
        ]
        latest_tweet_id_1 = 2
        latest_tweet_id_2 = 3

        # Build response from get_user_mentions_batch
        # The first response will have the 2 mentions (equal to batch size)
        # and the second response will have 1 mention (less than batch size)
        # which will break the loop
        response1 = (expected_mentions[:2], latest_tweet_id_1)
        response2 = (expected_mentions[2:], latest_tweet_id_2)
        mock_get_mentions.side_effect = [response1, response2]

        # Call get all user mentions
        actual_mentions, actual_last_last_id = await twitter_client.get_all_user_mentions(
            user_id,
            since_tweet_id=None,
            since_time=None,
            batch_size=batch_size,
        )
        assert actual_mentions == expected_mentions
        assert actual_last_last_id == latest_tweet_id_2

        # Confirm function calls
        assert mock_get_mentions.call_count == 2
        assert mock_get_mentions.call_args_list[0].kwargs["since_tweet_id"] is None
        assert mock_get_mentions.call_args_list[1].kwargs["since_tweet_id"] == latest_tweet_id_1

    @patch("echos_lab.twitter.twitter_client.get_user_mentions_batch")
    async def test_get_all_user_mentions_no_data(self, mock_get_mentions: AsyncMock):
        """
        Tests calling get all user mentions with no data returned from the first request
        """
        batch_size = 2
        user_id = generate_random_id()

        # Mock response from get_user_mentions so that it returns no
        mock_get_mentions.return_value = None

        # Call get all user mentions
        actual_mentions, latest_tweet_id = await twitter_client.get_all_user_mentions(
            user_id,
            since_tweet_id=None,
            since_time=None,
            batch_size=batch_size,
        )
        assert actual_mentions == []
        assert latest_tweet_id is None


@pytest.mark.asyncio
class TestPostTweetResponse:
    @patch("echos_lab.engines.full_agent_tools.caption_meme_from_tweet_evaluation")
    @patch("echos_lab.twitter.twitter_client.reply_to_tweet_with_image")
    async def test_post_tweet_response_meme(
        self, mock_reply_with_image: AsyncMock, mock_caption_meme: AsyncMock, mock_client: type[AsyncClient]
    ):
        """
        Tests posting a tweet response that returns a meme
        """
        tweet_id = 1

        # Create evaluation with a high meme rating
        meme_threshold = 5
        text_threshold = 5
        evaluation = build_tweet_evaluation("some response", rating=4, meme_rating=10)

        # Mock caption response to appear as if meme generation was successful
        image_url = "https://image.com"
        mock_caption_meme.return_value = {"url": image_url}

        # Call post tweet response
        await twitter_client.post_tweet_response(
            agent_profile=agent_profile,
            evaluation=evaluation,
            meme_threshold=meme_threshold,
            text_threshold=text_threshold,
            conversation_id=tweet_id,
            reply_to_tweet_id=tweet_id,
            quote_tweet_id=0,
        )

        # Confirm it called `reply_to_tweet_with_image`
        mock_reply_with_image.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, image_url=image_url, conversation_id=tweet_id, reply_to_id=tweet_id
        )

    @patch("random.random")
    @patch("echos_lab.engines.full_agent_tools.caption_meme_from_tweet_evaluation")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    async def test_post_tweet_response_meme_failed(
        self,
        mock_post: AsyncMock,
        mock_caption_meme: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests posting a tweet response where the meme generation failed
        and it fell back to posting text
        """
        tweet_id = 1

        # Create evaluation with a high meme rating and text rating
        meme_threshold = 5
        text_threshold = 5
        tweet_response = "some response"
        evaluation = build_tweet_evaluation(tweet_response, rating=10, meme_rating=10)

        # Mock caption response to appear as if meme generation failed
        mock_caption_meme.return_value = None

        # Mock random so a normal direct reply is sent
        mock_random.return_value = 0.99

        # Call post tweet response
        await twitter_client.post_tweet_response(
            agent_profile=agent_profile,
            evaluation=evaluation,
            meme_threshold=meme_threshold,
            text_threshold=text_threshold,
            conversation_id=tweet_id,
            reply_to_tweet_id=tweet_id,
            quote_tweet_id=0,
        )

        # Confirm it posted a normal direct reply
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE,
            text=tweet_response,
            conversation_id=tweet_id,
            in_reply_to_tweet_id=tweet_id,
        )

    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_post_tweet_response_no_tweet(self, mock_has_high_follower_count: AsyncMock, mock_post: AsyncMock):
        """
        Tests posting a tweet response where both responses are below
        the threshold and nothing is sent
        """
        # Create evaluation with a low meme rating and low rating
        meme_threshold = 5
        text_threshold = 5
        evaluation = build_tweet_evaluation("some response", rating=1, meme_rating=1)

        mock_has_high_follower_count.return_value = False

        # Call post tweet response
        await twitter_client.post_tweet_response(
            agent_profile=agent_profile,
            evaluation=evaluation,
            meme_threshold=meme_threshold,
            text_threshold=text_threshold,
            conversation_id=0,
            reply_to_tweet_id=0,
            quote_tweet_id=0,
        )

        # Confirm nothing was posted
        mock_post.assert_not_called()

    @patch("random.random")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_post_tweet_response_text_reply(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_post: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests posting a tweet with a direct tweet reply
        """
        tweet_id = 1

        # Create evaluation with a low meme rating but high text rating
        meme_threshold = 5
        text_threshold = 5
        tweet_response = "some response"
        evaluation = build_tweet_evaluation(tweet_response, rating=10, meme_rating=1)

        # Mock random so a normal direct reply is sent
        mock_random.return_value = 0.99
        mock_has_high_follower_count.return_value = False

        # Call post tweet response
        await twitter_client.post_tweet_response(
            agent_profile=agent_profile,
            evaluation=evaluation,
            meme_threshold=meme_threshold,
            text_threshold=text_threshold,
            conversation_id=tweet_id,
            reply_to_tweet_id=tweet_id,
            quote_tweet_id=0,
        )

        # Confirm it posted a normal direct reply
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE,
            text=tweet_response,
            conversation_id=tweet_id,
            in_reply_to_tweet_id=tweet_id,
        )

    @patch("random.random")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_post_tweet_response_text_quote_tweet(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_post: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests posting a quote tweet
        """
        tweet_id = 1

        # Create evaluation with a low meme rating but high text rating
        meme_threshold = 5
        text_threshold = 5
        tweet_response = "some response"
        evaluation = build_tweet_evaluation(tweet_response, rating=10, meme_rating=1)

        # Mock random so a quote tweet reply is sent
        mock_random.return_value = 0.01
        mock_has_high_follower_count.return_value = False

        # Call post tweet response
        await twitter_client.post_tweet_response(
            agent_profile=agent_profile,
            evaluation=evaluation,
            meme_threshold=meme_threshold,
            text_threshold=text_threshold,
            conversation_id=0,
            reply_to_tweet_id=0,
            quote_tweet_id=tweet_id,
        )

        # Confirm it posted a quote tweet
        mock_post.assert_called_with(agent_username=AGENT_TWITTER_HANDLE, text=tweet_response, quote_tweet_id=tweet_id)


@pytest.mark.asyncio
class TestReplyToMentions:
    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_thread(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests conditionally replying to some mentions in a new thread
        """
        # Mention 1 is an original tweet, we should reply
        conversation1 = 100
        mention1 = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot", conversation1), "userA"),
            original_tweet=None,
            replies=[],
        )

        # Mention 2 has the tag as a reply to an original tweet,
        # we should reply to this one
        conversation2 = 200
        mention2 = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post", conversation2), "userA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@userA Hey @bot", conversation2), "userA"),
            replies=[],
        )

        # Mention 3 is at the bottom of a thread, we should reply
        conversation3 = 300
        mention3 = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post", conversation3), "userA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@userB Some middle tweet", conversation3), "userB"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(3, "@userB @userC Hey @bot", conversation3), "userC"),
        )

        # Mention 4 was a response without a tag, we should not reply
        conversation4 = 400
        mention4 = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post", conversation4), "userA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@userB Some middle tweet", conversation4), "userB"),
                build_hydrated_tweet(build_tweet(3, "@userB @userC Hey @bot", conversation4), "userC"),
                build_hydrated_tweet(build_tweet(3, "@userC @userB @userA My bot reply", conversation4), "bot"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(3, "@bot @userC @userB @userA ok", conversation4), "userD"),
        )

        # We should respond to mentions 1, 2, and 3
        response1_text = "some response 1"
        response1 = build_tweet_evaluation(text=response1_text, rating=10)

        response2_text = "some response 2"
        response2 = build_tweet_evaluation(text=response2_text, rating=10)

        response3_text = "some response 3"
        response3 = build_tweet_evaluation(text=response3_text, rating=10)

        # Mock the responses
        # We need the random number generated to be greater than the quote tweet threshold
        # so that it replies normally in the thread
        mock_generate_reply.side_effect = [response1, response2, response3]
        mock_random.return_value = 0.99
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Call reply
        mentions = [mention1, mention2, mention3, mention4]
        await twitter_client.reply_to_mentions(db, agent_profile=agent_profile, mentions=mentions)

        # Confirm we responded twice
        calls = [
            call(
                agent_username=AGENT_TWITTER_HANDLE,
                text=response1_text,
                conversation_id=conversation1,
                in_reply_to_tweet_id=mention1.tagged_tweet.id,
            ),
            call(
                agent_username=AGENT_TWITTER_HANDLE,
                text=response2_text,
                conversation_id=conversation2,
                in_reply_to_tweet_id=mention2.tagged_tweet.id,
            ),
            call(
                agent_username=AGENT_TWITTER_HANDLE,
                text=response3_text,
                conversation_id=conversation3,
                in_reply_to_tweet_id=mention3.tagged_tweet.id,
            ),
        ]
        mock_post.assert_has_calls(calls)

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_quote_tweet(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests conditionally quote tweeting one of the replies
        """
        original_tweet = build_tweet(100, "original tweet")
        reply_tweet = build_tweet(1, f"reply @{agent_profile.twitter_handle}")  # Direct reply needs only single mention

        # Mention has the tag as a reply to an original tweet,
        # we should reply to this one
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(original_tweet, "userC"),
            tagged_tweet=build_hydrated_tweet(reply_tweet, "userB"),
            replies=[],
        )

        response_text = "some response"
        response = build_tweet_evaluation(text=response_text, rating=10)
        tweet_id_responded = original_tweet.id

        # Mock the responses
        # We need the random number generated to be less than the quote tweet threshold
        mock_generate_reply.return_value = response
        mock_random.return_value = 0.01
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Call reply
        await twitter_client.reply_to_mentions(db, agent_profile=agent_profile, mentions=[mention])

        # Confirm calls
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_below_response_rating(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests conditionally ignoring responses below the response rating
        """
        original_tweet = build_tweet(100, "original tweet")
        reply_tweet = build_tweet(1, f"reply @{agent_profile.twitter_handle}")

        # Mention has the tag as a reply to an original tweet,
        # we should reply to this one
        # We'll pass in two of these - however, the second one will have a None
        # response returned from the LLM, so we shouldn't reply to that one
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(original_tweet, "userC"),
            tagged_tweet=build_hydrated_tweet(reply_tweet, "userB"),
            replies=[],
        )
        mentions = [mention, mention]

        # Only give an LLM response to the first mention
        response_text = "some response"
        response = build_tweet_evaluation(text=response_text, rating=10)
        tweet_id_responded = original_tweet.id

        # Mock the responses
        # Return None from the second call to generate a reply (since we're mimicking
        # it being below the rating threshold)
        # We need the random number generated to be less than the quote tweet threshold
        mock_generate_reply.side_effect = [response, None]
        mock_random.return_value = 0.01
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Call reply
        await twitter_client.reply_to_mentions(db, agent_profile=agent_profile, mentions=mentions)

        # Confirm calls - ony the first mention should have a response
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )


@pytest.mark.asyncio
class TestReplyToFollowers:
    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_thread(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests conditionally replying to a followed account in a new thread
        """
        tweet1 = build_db_tweet(1, "original 1", conversation_id=1)
        tweet2 = build_db_tweet(2, "original 2", conversation_id=2)

        follower_tweet1 = twitter_client.FollowerTweet(tweet=tweet1, username="userA")
        follower_tweet2 = twitter_client.FollowerTweet(tweet=tweet2, username="userB")

        # Build up the responses - the first two should be valid
        # but the third will be below the rating threshold
        response1_text = "some response1"
        response1 = build_tweet_evaluation(text=response1_text, rating=10)

        response2_text = "some response2"
        response2 = build_tweet_evaluation(text=response2_text, rating=10)

        response3 = None

        # Mock the responses
        mock_generate_reply.side_effect = [response1, response2, response3]
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Mock the random number - it will be called multiple times
        # It will first be used to determine whether we should skip the tweet, and then
        # it will be used to determine whether we should quote tweet
        # We'll set it so that we should not skip the tweet, nor send a quote tweet
        mock_random.return_value = 0.9
        agent_profile.quote_tweet_threshold = 0.2  # below this will quote tweet (should NOT quote tweet)
        agent_profile.followers = [
            FollowedAccount("userA", reply_probability=0.95),  # below this will reply (should reply)
            FollowedAccount("userB", reply_probability=0.95),  # below this will reply (should reply)
        ]

        # Call reply
        tweets = [follower_tweet1, follower_tweet2]
        await twitter_client.reply_to_followers(db, agent_profile=agent_profile, tweets=tweets)

        # Confirm calls
        assert mock_post.call_count == 2
        mock_post.assert_has_calls(
            [
                call(
                    agent_username=AGENT_TWITTER_HANDLE,
                    text=response1_text,
                    conversation_id=tweet1.tweet_id,
                    in_reply_to_tweet_id=tweet1.tweet_id,
                ),
                call(
                    agent_username=AGENT_TWITTER_HANDLE,
                    text=response2_text,
                    conversation_id=tweet2.tweet_id,
                    in_reply_to_tweet_id=tweet2.tweet_id,
                ),
            ]
        )

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_quote_tweet(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests conditionally quote tweeting a tweet from a follower
        """
        tweet = build_db_tweet(1, "original 1")
        follower_tweet = twitter_client.FollowerTweet(tweet=tweet, username="userA")

        response_text = "some response"
        response = build_tweet_evaluation(text=response_text, rating=10)
        tweet_id_responded = tweet.tweet_id

        # Mock the responses
        mock_generate_reply.return_value = response
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Mock the random number - it will be called multiple times
        # It will first be used to determine whether we should skip the tweet, and then
        # it will be used to determine whether we should quote tweet
        # We'll set it so that we should not skip the tweet, but we should send a quote tweet
        mock_random.return_value = 0.1
        agent_profile.quote_tweet_threshold = 0.2  # below this will quote tweet (SHOULD quote tweet)
        agent_profile.followers = [
            FollowedAccount("userA", reply_probability=0.95),  # below this will reply (should reply)
            FollowedAccount("userB", reply_probability=0.95),  # below this will reply (should reply)
        ]

        # Call reply
        await twitter_client.reply_to_followers(db, agent_profile=agent_profile, tweets=[follower_tweet])

        # Confirm calls
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_client.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_random_skip(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
        db: Session,
    ):
        """
        Tests randomly skipping a reply to a follower
        """
        tweet1 = build_db_tweet(1, "original 1", conversation_id=1)
        tweet2 = build_db_tweet(2, "original 2", conversation_id=2)

        follower_tweet1 = twitter_client.FollowerTweet(tweet=tweet1, username="userA")  # skipped
        follower_tweet2 = twitter_client.FollowerTweet(tweet=tweet2, username="userB")

        # Build up the responses
        # The first user will be skipped, so mock reply should only be called once
        response_text2 = "some response2"
        response2 = build_tweet_evaluation(text=response_text2, rating=10)

        # Mock the responses
        mock_generate_reply.return_value = response2
        mock_recent_tweets.return_value = [], None
        mock_has_high_follower_count.return_value = False

        # Mock the random number - it will be called multiple times
        # It will first be used to determine whether we should skip the tweet, and then
        # it will be used to determine whether we should quote tweet
        # We'll set it so that we should should skip the tweet for the second user,
        # and we should not quote tweet
        mock_random.return_value = 0.9
        agent_profile.quote_tweet_threshold = 0.2  # below this will quote tweet (should NOT quote tweet)
        agent_profile.followers = [
            FollowedAccount("userA", reply_probability=0.1),  # below this will reply (should NOT reply)
            FollowedAccount("userB", reply_probability=0.95),  # below this will reply (should reply)
        ]

        # Call reply
        tweets = [follower_tweet1, follower_tweet2]
        await twitter_client.reply_to_followers(db, agent_profile=agent_profile, tweets=tweets)

        # Confirm calls
        mock_post.assert_called_once_with(
            agent_username=AGENT_TWITTER_HANDLE,
            text=response_text2,
            conversation_id=tweet2.tweet_id,
            in_reply_to_tweet_id=tweet2.tweet_id,
        )


@pytest.mark.asyncio
class TestShouldReplyToMentions:
    bot_handle = "bot"

    async def test_remove_tweet_reply_tags(self):
        """
        Tests removing the prefix of user tags from the tweet contents
        """
        assert twitter_client.remove_tweet_reply_tags("some message") == "some message"
        assert twitter_client.remove_tweet_reply_tags("@userA some message") == "some message"
        assert twitter_client.remove_tweet_reply_tags("@userA @userB @userC some message") == "some message"
        assert twitter_client.remove_tweet_reply_tags("@userA @userB @userC") == "@userC"
        assert twitter_client.remove_tweet_reply_tags("@userA") == "@userA"

    async def test_tag_in_original(self):
        """
        Tag in original tweet, should respond. Ex:

            UserA: @bot
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), username="UserA"),
            original_tweet=None,
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_direct_response(self):
        """
        Tag in direct response, should respond. Ex:

            UserA: Some post   | Appears as "Some post"
            UserB: @bot        | Appears as "@UserA @bot"
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@UserA @bot"), username="UserB"),
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_direct_response_with_message_before(self):
        """
        Tag in direct response where there's not other , should respond. Ex:

            UserA: Some post   | Appears as "Some post"
            UserB: Hey @bot        | Appears as "@UserA Hey @bot"
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@UserA Hey @bot"), username="UserB"),
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_direct_response_with_message_after(self):
        """
        Tag in direct response where there's not other , should respond. Ex:

            UserA: Some post   | Appears as "Some post"
            UserB: @bot reply  | Appears as "@UserA @bot reply"
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@UserA @bot reply"), username="UserB"),
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_two_person_thread(self):
        """
        Tag in two person thread, should response. Ex:

            UserA: Some post           | Appears as "Some post"
            UserB: Some response       | Appears as "@UserA Some response"
            UserA: Some new response   | Appears as "@UserB Some new response"
            UserB: @bot                | Appears as "@UserA @bot"
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(4, "@UserA @bot"), username="UserB"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_three_person_thread(self):
        """
        Tag in two person thread, should response. Ex:

            UserA: Some post                | Appears as "Some post"
            UserB: Some response            | Appears as "@UserA Some response"
            UserA: Some new response        | Appears as "@UserB Some new response"
            UserC: Some new new response    | Appears as "@UserA @UserB Some new new response"
            UserB: @bot                     | Appears as "@UserC @UserA @bot"
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
                build_hydrated_tweet(build_tweet(4, "@UserA @UserB Some new new response"), username="UserC"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(4, "@UserC @UserA @bot"), username="UserB"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_tag_in_thread_with_bot(self):
        """
        Tag in thread where the bot's already responded

            UserA: Some post                | Appears as "Some post"
            UserB: Some response            | Appears as "@UserA Some response"
            UserA: Some new response        | Appears as "@UserB Some new response"
            UserC: Some new new response    | Appears as "@UserA @UserB Some new new response"
            UserB: @bot                     | Appears as "@UserC @UserA @bot"
            bot:   Funny response           | Appears as "@UserB @UserC @UserA Funny response"
            UserC: @bot                     | Appears as "@bot @UserB @UserA @bot"   (two bot tags)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
                build_hydrated_tweet(build_tweet(4, "@UserA @UserB Some new new response"), username="UserC"),
                build_hydrated_tweet(build_tweet(5, "@UserC @UserA @bot"), username="userB"),
                build_hydrated_tweet(build_tweet(6, "@UserB @UserC @UserA Funny response"), username="bot"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(7, "@bot @UserB @UserA @bot"), username="UserC"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is True

    async def test_reply_to_bot_no_tag(self):
        """
        Response in thread where the bot's already responded
        We should not respond since there's no tag

            UserA: Some post                | Appears as "Some post"
            UserB: Some response            | Appears as "@UserA Some response"
            UserA: Some new response        | Appears as "@UserB Some new response"
            UserC: Some new new response    | Appears as "@UserA @UserB Some new new response"
            UserB: @bot                     | Appears as "@UserC @UserA @bot"
            bot:   Funny response           | Appears as "@UserB @UserC @UserA Funny response"
            UserC: ok                       | Appears as "@bot @UserB @UserA ok"   (one bot tag)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
                build_hydrated_tweet(build_tweet(4, "@UserA @UserB Some new new response"), username="UserC"),
                build_hydrated_tweet(build_tweet(5, "@UserC @UserA @bot"), username="userB"),
                build_hydrated_tweet(build_tweet(6, "@UserB @UserC @UserA Funny response"), username="bot"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(7, "@bot @UserB @UserA ok"), username="UserC"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_message_after_reply_to_bot_no_tag(self):
        """
        Response in thread where the bot's already responded
        We should not respond since there's no tag

            UserA: Some post                | Appears as "Some post"
            UserB: Some response            | Appears as "@UserA Some response"
            UserA: Some new response        | Appears as "@UserB Some new response"
            UserC: Some new new response    | Appears as "@UserA @UserB Some new new response"
            UserB: @bot                     | Appears as "@UserC @UserA @bot"
            bot:   Funny response           | Appears as "@UserB @UserC @UserA Funny response"
            UserC: ok                       | Appears as "@bot @UserB @UserA ok"
            UserB: ok                       | Appears as "@UserC @bot @UserA ok"
            UserA: ok                       | Appears as "@UserB @UserC @bot ok" (looks like bot tag)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
                build_hydrated_tweet(build_tweet(4, "@UserA @UserB Some new new response"), username="UserC"),
                build_hydrated_tweet(build_tweet(5, "@UserC @UserA @bot"), username="userB"),
                build_hydrated_tweet(build_tweet(6, "@UserB @UserC @UserA Funny response"), username="bot"),
                build_hydrated_tweet(build_tweet(7, "@bot @UserB @UserA ok"), username="userC"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(8, "@UserC @bot @UserA ok"), username="UserB"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_message_in_thread_no_tag_but_looks_like_tag(self):
        """
        Response in thread where the bot's already responded
        We should not respond since there's no tag

            UserA: Some post                | Appears as "Some post"
            UserB: Some response            | Appears as "@UserA Some response"
            UserA: Some new response        | Appears as "@UserB Some new response"
            UserC: Some new new response    | Appears as "@UserA @UserB Some new new response"
            UserB: @bot                     | Appears as "@UserC @UserA @bot"
            bot:   Funny response           | Appears as "@UserB @UserC @UserA Funny response"
            UserC: ok                       | Appears as "@bot @UserB @UserA ok"
            UserB: ok                       | Appears as "@UserC @bot @UserA ok"
            UserA: ok                       | Appears as "@UserB @UserC @bot ok" (looks like bot tag)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA Some response"), username="UserB"),
                build_hydrated_tweet(build_tweet(3, "@UserB Some new response"), username="UserA"),
                build_hydrated_tweet(build_tweet(4, "@UserA @UserB Some new new response"), username="UserC"),
                build_hydrated_tweet(build_tweet(5, "@UserC @UserA @bot"), username="userB"),
                build_hydrated_tweet(build_tweet(6, "@UserB @UserC @UserA Funny response"), username="bot"),
                build_hydrated_tweet(build_tweet(7, "@bot @UserB @UserA ok"), username="userC"),
                build_hydrated_tweet(build_tweet(8, "@UserC @bot @UserA ok"), username="userB"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(9, "@UserB @UserC @bot ok"), username="UserA"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_tag_in_original_tweet_looks_like_direct_reply_tag(self):
        """
        Response in a direct reply where the bot's has not responded, but was tagged in the original tweet
        so it looks like they're being summoned
        We should not respond

            UserA: Some post                | Appears as "Some post about @bot"
            UserB: Some response            | Appears as "@UserA @bot Some response" (looks like bot tag)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post about @bot"), username="UserA"),
            replies=[],
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@UserA @bot Some response"), username="UserA"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_tag_in_original_tweet_looks_like_thread_reply_tag(self):
        """
        Response in thread where the bot's has not responded, but was tagged in the original tweet
        so it looks like they're being summoned
        We should not respond

            UserA: Some post                | Appears as "Some post about @bot"
            UserB: Some response            | Appears as "@UserA @bot Some response"
            UserA: Some new response        | Appears as "@UserB @bot Some new response" (looks like bot tag)
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Some post about @bot"), username="UserA"),
            replies=[
                build_hydrated_tweet(build_tweet(2, "@UserA @bot Some response"), username="UserA"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(3, "@UserB @bot Some new response"), username="UserA"),
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_tag_in_original(self):
        """
        Test preventing response when there's an image in the original post
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot", include_image=True), username="UserA"),
            original_tweet=None,
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_tag_in_direct_reply(self):
        """
        Test preventing response when there's an image in the original post and the tag is in the reply
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Original", include_image=True), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@bot"), username="UserA"),
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_in_tagged_reply(self):
        """
        Test preventing response when there's an image in the tagged tweet reply
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Original"), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@bot", include_image=True), username="UserA"),
            replies=[],
        )
        assert await twitter_client.should_reply_to_mention(self.bot_handle, mention) is False
