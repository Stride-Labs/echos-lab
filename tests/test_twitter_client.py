from unittest.mock import AsyncMock, patch

import fixtures.prompts as test_prompts
import pytest
from conftest import (
    build_hydrated_tweet,
    build_reply_reference,
    build_tweepy_response,
    build_tweet,
    build_tweet_mention,
    build_user,
    check_tweet_mention_equality,
    generate_random_id,
    generate_random_username,
)
from fixtures.prompts import normalize_prompts
from tweepy.asynchronous import AsyncClient

from echos_lab.engines import prompts
from echos_lab.twitter import twitter_client
from echos_lab.twitter.types import HydratedTweet, MentionType, TweetMention


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
        assert original_mention.mention_type == MentionType.TAGGED_IN_ORIGINAL

        direct_reply_mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my tweet"), "original-user"),
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), "tagging-user"),
            replies=[],
        )

        assert direct_reply_mention.mention_type == MentionType.TAGGED_IN_DIRECT_REPLY

        thread_mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my original tweet"), "original-user"),
            replies=[build_hydrated_tweet(build_tweet(1, "But I think..."), "replierA")],
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot what do you think?"), "tagging-user"),
        )
        assert thread_mention.mention_type == MentionType.TAGGED_IN_THREAD

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
