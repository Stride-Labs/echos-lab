import io
import random
from typing import cast

import requests
from sqlalchemy.orm import Session
from tweepy import Response

from echos_lab.common.logger import logger
from echos_lab.common.utils import with_db
from echos_lab.db import db_connector
from echos_lab.db.models import TweetType
from echos_lab.engines import full_agent_tools, post_maker, prompts
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.engines.prompts import TweetEvaluation
from echos_lab.twitter import twitter_pipeline, twitter_auth, twitter_helpers, twitter_client
from echos_lab.twitter.types import (
    FollowerTweet,
    HydratedTweet,
    MentionType,
    TweetMention,
    RESPONSE_RATING_THRESHOLD_FOLLOWERS,
    RESPONSE_RATING_THRESHOLD_MENTIONS,
    MEME_RATING_THRESHOLD,
)


@with_db
async def post_tweet(
    db: Session,
    agent_username: str,
    text: str,
    in_reply_to_tweet_id: int | None = None,
    quote_tweet_id: int | None = None,
    conversation_id: int | None = None,
    media_ids: list[str] | None = None,
) -> int | None:
    """
    Posts a tweet using tweepy

    Args:
        db: The database session (passed in automatically with `with_db`)
        agent_username: The twitter username of the agent
        text: The tweet text
        in_reply_to_tweet_id: If replying, the ID of the tweet to reply to
        quote_tweet_id: If quote tweeting, the ID of the tweet to quote tweet
        conversation_id: If replying to a tweet, the ID of the parent tweet in the thread
        media_ids: If tweeting with an image, the IDs of the images that were uploaded

    Returns:
        The tweet ID if successfull, or None otherwise
    """
    assert not (
        in_reply_to_tweet_id and not conversation_id
    ), "If replying to a tweet, you must pass the conversation ID"

    async_client = twitter_auth.get_tweepy_async_client()

    # TODO remove this temporary, hacky fix
    # This is so the agents don't tag each other
    REPLACE_AGENT_HANLDES = [
        ("@vito_him", "Vito"),
        ("@inj_ai", "Inj Intern"),
        ("@derp_echo", "Derp"),
        ("@clara_echo", "Clara"),
        ("@hal_echo", "Hal"),
        ("@tuskthemammoth", "Tusk The Mammoth"),
    ]
    for handle, name in REPLACE_AGENT_HANLDES:
        text = text.replace(handle, name)

    # Post the tweet
    response = await async_client.create_tweet(
        text=text,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
        quote_tweet_id=quote_tweet_id,
        media_ids=media_ids,
    )
    response = cast(Response, response)
    if not response.data:
        return None

    # Extract the tweet ID and
    response_tweet_id = response.data.get("id")
    if not response_tweet_id:
        return None
    response_tweet_id = int(response_tweet_id)

    # If a reply or quote tweet ID were passed, the TweetType should be
    # REPLY/QUOTE respecitvely. Otherwise it should be ORIGINAL
    # If it was not a direct reply, the conversation ID should be the
    # returned response ID
    tweet_type: TweetType
    if in_reply_to_tweet_id is not None:
        tweet_type = TweetType.REPLY
    elif quote_tweet_id is not None:
        tweet_type = TweetType.QUOTE
        conversation_id = response_tweet_id
    else:
        tweet_type = TweetType.ORIGINAL
        conversation_id = response_tweet_id

    # Get the agent's twitter ID
    agent_id = await twitter_pipeline.require_user_id_from_username(db, agent_username)

    # Write the tweet to the database
    db_connector.add_tweet(
        db=db,
        tweet_id=response_tweet_id,
        text=text,
        author_id=agent_id,
        tweet_type=tweet_type,
        conversation_id=conversation_id,
        reply_to_id=in_reply_to_tweet_id,
        quote_tweet_id=quote_tweet_id,
        media_ids=media_ids,
    )

    logger.info(f"{tweet_type.capitalize()} tweet{' with image ' if media_ids else ' '}successful\n")

    return response_tweet_id


async def reply_to_tweet_with_image(
    agent_username: str,
    image_url: str,
    conversation_id: int,
    reply_to_id: int,
    response_text: str = "",
) -> int | None:
    """
    Replies to a tweet with an image (and optionally, text)
    - downloads image from URL
    - uploads image to Twitter (waits until upload is complete)
    - posts tweet with image media

    Args:
        agent_username: The twitter username of the agent
        image_url: The URL of the image that should be posted
        conversation_id: The ID of the parent tweet in the thread
        reply_to_id: The ID of the tweet that's being replied to
        response_text: The text associated with the tweet

    Returns:
        The tweet ID (or None if post failed)
    """
    logger.info(f"Image URL: {image_url}")

    # instantiate a new Tweepy API instance for media upload (requires v1 API)
    oauth1_client = twitter_auth.get_tweepy_oauth1_client()

    # Download the image
    response = requests.get(image_url)
    if response.status_code != 200:
        logger.error("Failed to download the image.")
        return None

    # Convert bytes data to a file-like object
    image_data = response.content
    image_file = io.BytesIO(image_data)

    # Upload the image to Twitter using chunked upload
    media_response = oauth1_client.media_upload(
        filename="img",
        file=image_file,
        media_category="tweet_image",
        chunked=True,
        wait_for_async_finalize=True,
    )
    media_id = media_response.media_id
    logger.info(f"Meme image uploaded to Twitter with media ID: {media_id}")

    # Step 3: Post the tweet with the image
    return await post_tweet(
        agent_username=agent_username,
        text=response_text,
        conversation_id=conversation_id,
        in_reply_to_tweet_id=reply_to_id,
        media_ids=[media_id],
    )


async def should_reply_to_mention(bot_handle: str, mention: TweetMention) -> bool:
    """
    Returns a bool indicating whether to reply to the given mention

    For tags in original tweets, we always want to reply
    However, for threads, we want to consider whether we're actually being summoned,
    or if they just happend to be replying to us

    Important Context:
        In threads, the text of each tweet is prefixed with the accounts that are
        already in the thread

        For instance, if we have userA -> userB -> userC and then userD replies,
        then userD's message will be prefixed with "@userC @userB @userA" regardless
        of if they meant to intentionally tag that user

        If the reply explicitly tags the user, the tag will appear twice
        e.g. userA: hey                | Appears as "hey"
             userB: hi                 | Appears as "@userA hi"
             userC: @userB hey guys    | Appears as "@userB @userA @userB hey guys"

        If a new user is tagged in any message, they're included in the prefix
        from that point onwards (even if they never response themselves)
        e.g. userA: hey             | Appears as "hey"
             userB: hi              | Appears as "@userA hi"
             userC: adding @bot     | Appears as "@userB @userA adding @bot"
             userB: hey             | Appears as "@userC @userA @bot hey"
             (notice the bot is tagged in the prefix of the last tweet)

        The ordering of the usernames is in order of recency of last response,
        and a message does not include their own username in the prefix

    When determining if we want to reply to a thread, we want to separate out the
    prefix from the message contents (as best we can), and then we'll reply if
    it appears that the bot was explicitly tagged, identified if:
       - The bot tag is after the start of the message contents
       - The bot is tagged twice
       - The bot is tagged once and:
          - The bot is not tagged earlier in the thread
          - The bot has not responded earlier in the thread
    As both of those indicate that there was an explicit tag
    """
    # Ensure the handles starts with @
    bot_handle = bot_handle if bot_handle.startswith("@") else f"@{bot_handle}"

    # Don't respond to tweets that have an image or video
    if mention.tagged_tweet.has_media or (mention.original_tweet and mention.original_tweet.has_media):
        return False

    # Always respond to tags in the original tweet
    if mention.mention_type == MentionType.TAGGED_IN_ORIGINAL:
        return True

    # Extract all the tags at the start of the message
    tagged_tweet_contents = mention.tagged_tweet.text
    original_tweet_contents = cast(HydratedTweet, mention.original_tweet).text
    message = twitter_helpers.remove_tweet_reply_tags(mention.tagged_tweet.text)

    # If the bot is not tagged at all, we should obviously not respond
    # (although this case should not be possible since we only grab messages with a tag)
    if bot_handle not in tagged_tweet_contents:
        return False

    # If the bot is tagged in the message contents, it was obviously explicit
    # e.g. @guyInThread hey @bot
    if bot_handle in message:
        return True

    # If the bot is tagged twice, it was obviously explicit
    # e.g. @guyInThread @bot @otherGuyInThread @bot i'm talking to you
    num_bot_tags = tagged_tweet_contents.count(bot_handle)
    if num_bot_tags >= 2:
        return True

    # By this point, we know the bot should be tagged *exactly once* in the message
    assert num_bot_tags == 1

    # If it's a direct reply, only reply if the tag originated from the direct reply
    # We can identify this by confirming the original tweet *did not* tag the bot
    bot_tagged_in_original = bot_handle in original_tweet_contents
    if mention.mention_type == MentionType.TAGGED_IN_DIRECT_REPLY:
        should_reply = not bot_tagged_in_original
        return should_reply

    # By this point, we know the bot was tagged once AND we're in a thread
    # Check if the bot has already responded in the thread
    previous_repliers = [await tweet.get_username() for tweet in mention.replies]
    bot_replied_earlier = bot_handle.replace("@", "") in previous_repliers

    # Check if this is the first time the bot was tagged
    bot_tagged_earlier = bot_tagged_in_original or any(bot_handle in tweet.text for tweet in mention.replies)

    # If they *did not* respond earlier, than this tag must be the first summon
    # and it should respond
    if not bot_replied_earlier and not bot_tagged_earlier:
        return True

    # If they *did* respond earlier, than this tag is just a part of the reply prefix
    # and it should not respond
    return False


async def post_tweet_response(
    agent_profile: AgentProfile,
    evaluation: TweetEvaluation,
    meme_threshold: int,
    text_threshold: int,
    conversation_id: int,
    reply_to_tweet_id: int,
    quote_tweet_id: int,
):
    """
    Handles posting a reply guy tweet via the following rules:
      1. If the meme rating is above the threshold, generates a meme image
         and replies directly
      2. If the meme rating is not high enough, or the meme generation fails,
         reply only if the response rating is high enough
      3. If responding with text, reply either with a quote tweet or direct response

    Args:
        agent_profile: The agent's profile configuration
        evaluation: The LLM's analysis of the tweet and corresponding response
        meme_threshold: The threshold (0-10) that must be met by the meme rating
          in order to respond with a meme
        text_threshold: The threshold (0-10) that must be met by the generic
          response rating in order to respond with text
        reply_tweet_id: The ID of the tweet that should be replied to (in the
          event that the response is a direct reply)
        quote_tweet_id: The ID of the tweet that should quote tweeted (in the
          event that the response is a quote tweet)

    NOTE: Both reply_tweet_id and quote_tweet_id must be specified
    The type of tweet will be determined randomly
    """
    # If meme rating is above the threshold, post it instead of a text response
    # If the meme generation fails, fall back to the text response
    if int(evaluation.meme_rating) >= meme_threshold:
        logger.info("Response above meme threshold, generating meme")
        meme_caption = full_agent_tools.caption_meme_from_tweet_evaluation(evaluation)
        if meme_caption is not None:
            return await reply_to_tweet_with_image(
                agent_username=agent_profile.twitter_handle,
                image_url=meme_caption["url"],
                conversation_id=conversation_id,
                reply_to_id=reply_to_tweet_id,
            )

    # If the text rating is below the threshold, skip this tweet
    if int(evaluation.response_rating) < text_threshold:
        logger.info(
            f"Response to tag rating was {evaluation.response_rating}, below {text_threshold}. Bailing on post.\n\n"
        )
        return

    # Conditionally quote tweet reply instead of replying in the thread
    should_quote_tweet = random.random() <= agent_profile.quote_tweet_threshold

    # If the random threshold was breached, submit response as a quote tweet
    response_tweet = evaluation.response
    if should_quote_tweet:
        return await post_tweet(
            agent_username=agent_profile.twitter_handle,
            text=response_tweet,
            quote_tweet_id=quote_tweet_id,
        )

    # Otherwise, post it as a thread in the response
    return await post_tweet(
        agent_username=agent_profile.twitter_handle,
        text=response_tweet,
        conversation_id=conversation_id,
        in_reply_to_tweet_id=reply_to_tweet_id,
    )


# TODO: consolidate this with reply_to_tweet
async def reply_to_mentions(db: Session, agent_profile: AgentProfile, mentions: list[TweetMention]):
    """
    Generates and posts a reply guy response to all mentions in the list
    The response will randomly be in the form of a reply tweet or quote tweet
    """
    for mention in mentions:
        if not await should_reply_to_mention(bot_handle=agent_profile.twitter_handle, mention=mention):
            continue

        # TODO: This stuff's getting confusing, try to simplify the original/tagged/root terminology
        is_original_tweet = mention.mention_type == MentionType.TAGGED_IN_ORIGINAL
        original_tweet = mention.tagged_tweet if is_original_tweet else cast(HydratedTweet, mention.original_tweet)

        # Get the author of the original tweet and grab the last few tweets of theirs
        author_username = await original_tweet.get_username()
        author_recent_tweets = await twitter_client.get_author_recent_tweets(original_tweet.author_id)

        # Generate a response with the LLM
        conversation_summary = await prompts.build_twitter_mentions_prompt(mention)
        response_evaluation = await post_maker.generate_reply_guy_tweet(
            agent_profile=agent_profile,
            author=author_username,
            tweet_summary=conversation_summary,
            author_recent_tweets=author_recent_tweets,
            agent_recent_tweets=[],
            allow_roasting=True,
        )
        if not response_evaluation:
            continue

        # Post the response
        await post_tweet_response(
            agent_profile=agent_profile,
            evaluation=response_evaluation,
            meme_threshold=MEME_RATING_THRESHOLD,
            text_threshold=RESPONSE_RATING_THRESHOLD_MENTIONS,
            conversation_id=mention.tagged_tweet.conversation_id,
            reply_to_tweet_id=mention.tagged_tweet.id,
            quote_tweet_id=original_tweet.id,
        )


async def reply_to_followers(db: Session, agent_profile: AgentProfile, tweets: list[FollowerTweet]):
    """
    Generates and posts a reply guy response to all tweets in the list
    """
    # Build a mapping from username -> reply probability
    reply_probability_mapping = {follower.username: follower.reply_probability for follower in agent_profile.followers}

    # Loop through each tweet and generate a response
    for tweet in tweets:
        if random.random() > reply_probability_mapping[tweet.username]:
            logger.info(f"Randomly skipping tweet from {tweet.username} to prevent spam")
            continue

        # Get the recent tweets from this author
        author_recent_tweets = await twitter_client.get_author_recent_tweets(tweet.tweet.author_id)

        # Generate a response
        tweet_summary = tweet.to_prompt()
        response_evaluation = await post_maker.generate_reply_guy_tweet(
            agent_profile=agent_profile,
            author=tweet.username,
            tweet_summary=tweet_summary,
            author_recent_tweets=author_recent_tweets,
            agent_recent_tweets=[],
            allow_roasting=False,
        )
        if response_evaluation is None:
            continue

        # Post the response
        await post_tweet_response(
            agent_profile=agent_profile,
            evaluation=response_evaluation,
            meme_threshold=MEME_RATING_THRESHOLD,
            text_threshold=RESPONSE_RATING_THRESHOLD_FOLLOWERS,
            conversation_id=tweet.tweet.conversation_id,
            reply_to_tweet_id=tweet.tweet.tweet_id,
            quote_tweet_id=tweet.tweet.tweet_id,
        )
