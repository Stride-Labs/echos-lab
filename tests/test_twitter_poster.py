from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from conftest import (
    AGENT_TWITTER_HANDLE,
    agent_profile,
    build_db_tweet,
    build_hydrated_tweet,
    build_tweet,
    build_tweet_evaluation,
)
from tweepy.asynchronous import AsyncClient

from echos_lab.engines.personalities.profiles import FollowedAccount
from echos_lab.twitter import twitter_poster
from echos_lab.twitter.types import FollowerTweet, TweetMention


@pytest.mark.asyncio
class TestPostTweetResponse:
    @patch("echos_lab.engines.full_agent_tools.caption_meme_from_tweet_evaluation")
    @patch("echos_lab.twitter.twitter_poster.reply_to_tweet_with_image")
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
        await twitter_poster.post_tweet_response(
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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
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
        await twitter_poster.post_tweet_response(
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

    @patch("echos_lab.twitter.twitter_poster.post_tweet")
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
        await twitter_poster.post_tweet_response(
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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
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
        await twitter_poster.post_tweet_response(
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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
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
        await twitter_poster.post_tweet_response(
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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_thread(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
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
        await twitter_poster.reply_to_mentions(agent_profile=agent_profile, mentions=mentions)

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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_quote_tweet(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
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
        await twitter_poster.reply_to_mentions(agent_profile=agent_profile, mentions=[mention])

        # Confirm calls
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_mentions_below_response_rating(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
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
        await twitter_poster.reply_to_mentions(agent_profile=agent_profile, mentions=mentions)

        # Confirm calls - ony the first mention should have a response
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )


@pytest.mark.asyncio
class TestReplyToFollowers:
    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_thread(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests conditionally replying to a followed account in a new thread
        """
        tweet1 = build_db_tweet(1, "original 1", conversation_id=1)
        tweet2 = build_db_tweet(2, "original 2", conversation_id=2)

        follower_tweet1 = FollowerTweet(tweet=tweet1, username="userA")
        follower_tweet2 = FollowerTweet(tweet=tweet2, username="userB")

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
        await twitter_poster.reply_to_followers(agent_profile=agent_profile, tweets=tweets)

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
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_quote_tweet(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests conditionally quote tweeting a tweet from a follower
        """
        tweet = build_db_tweet(1, "original 1")
        follower_tweet = twitter_poster.FollowerTweet(tweet=tweet, username="userA")

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
        await twitter_poster.reply_to_followers(agent_profile=agent_profile, tweets=[follower_tweet])

        # Confirm calls
        mock_post.assert_called_with(
            agent_username=AGENT_TWITTER_HANDLE, text=response_text, quote_tweet_id=tweet_id_responded
        )

    @patch("random.random")
    @patch("echos_lab.engines.post_maker.generate_reply_guy_tweet")
    @patch("echos_lab.twitter.twitter_poster.post_tweet")
    @patch("echos_lab.twitter.twitter_client.get_tweets_from_user_id")
    @patch("echos_lab.twitter.twitter_client.has_high_follower_count")
    async def test_reply_to_followers_random_skip(
        self,
        mock_has_high_follower_count: AsyncMock,
        mock_recent_tweets: AsyncMock,
        mock_post: AsyncMock,
        mock_generate_reply: AsyncMock,
        mock_random: Mock,
    ):
        """
        Tests randomly skipping a reply to a follower
        """
        tweet1 = build_db_tweet(1, "original 1", conversation_id=1)
        tweet2 = build_db_tweet(2, "original 2", conversation_id=2)

        follower_tweet1 = FollowerTweet(tweet=tweet1, username="userA")  # skipped
        follower_tweet2 = FollowerTweet(tweet=tweet2, username="userB")

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
        await twitter_poster.reply_to_followers(agent_profile=agent_profile, tweets=tweets)

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is True

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

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
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_tag_in_original(self):
        """
        Test preventing response when there's an image in the original post
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot", include_image=True), username="UserA"),
            original_tweet=None,
            replies=[],
        )
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_tag_in_direct_reply(self):
        """
        Test preventing response when there's an image in the original post and the tag is in the reply
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Original", include_image=True), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@bot"), username="UserA"),
            replies=[],
        )
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False

    async def test_media_in_tweet_in_tagged_reply(self):
        """
        Test preventing response when there's an image in the tagged tweet reply
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "Original"), username="UserA"),
            tagged_tweet=build_hydrated_tweet(build_tweet(2, "@bot", include_image=True), username="UserA"),
            replies=[],
        )
        assert await twitter_poster.should_reply_to_mention(self.bot_handle, mention) is False
