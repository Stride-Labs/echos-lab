from sqlalchemy.orm import Session
from typing import cast

from echos_lab.common.logger import logger
from echos_lab.common.utils import with_db
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.engines import post_maker, prompts
from echos_lab.twitter import twitter_client, twitter_pipeline
from echos_lab.twitter.types import HydratedTweet, RESPONSE_RATING_THRESHOLD_MENTIONS, MEME_RATING_THRESHOLD


@with_db
async def run_reply_guy_mentions_cycle(db: Session, agent_profile: AgentProfile, bot_start_time: str):
    """
    Main runner for an iteration of the mentions reply guy flow which:
    1. Fetches all replies since the last time the bot was run
    2. Generates a response for each and posts directly to twitter

    Args:
        db: Database session (injected by decorator)
        agent_profile: Profile configuration for the reply guy
        bot_start_time: UTC timestamp when bot was started, used for filtering mentions
    """
    # Lookup the bot's user ID
    agent_username = agent_profile.twitter_handle
    agent_id = await twitter_pipeline.require_user_id_from_username(db, agent_username)

    # Get new mentions
    mentions = await twitter_pipeline.get_user_mentions(
        db=db,
        agent_name=agent_profile.name,
        agent_id=agent_id,
        since_time=bot_start_time,
    )
    logger.info(f"Found {len(mentions)} mention{'' if len(mentions) == 1 else 's'}...")

    # Generate and post responses to each mention
    await twitter_client.reply_to_mentions(db=db, agent_profile=agent_profile, mentions=mentions)


@with_db
async def run_reply_guy_followers_cycle(db: Session, agent_profile: AgentProfile, bot_start_time: str):
    """
    Main runner for an iteration of the follower reply guy flow which:
    1. Fetches all tweets from relevant accounts since the last time the bot was run
    2. Generates a response for each and posts directly to twitter

    Args:
        db: Database session (injected by decorator)
        agent_profile: Profile configuration for the reply guy
        bot_start_time: UTC timestamp when bot was started, used for filtering tweets
    """
    # Lookup the bot's user ID
    agent_username = agent_profile.twitter_handle
    agent_id = await twitter_client.get_user_id_from_username(agent_username)
    if not agent_id:
        raise RuntimeError(f"User ID not found for agent @{agent_username}")

    # Extract just the usernames from the FollowedAccount objects
    usernames = [follower.username for follower in agent_profile.followers]

    # Get user IDs mapping
    user_id_mapping = await twitter_pipeline.get_user_ids_from_usernames(db, usernames)

    # Get all tweets
    tweets = await twitter_pipeline.get_all_follower_tweets(
        db=db,
        agent_name=agent_profile.name,
        user_id_mapping=user_id_mapping,
        since_time=bot_start_time,
    )

    # Generate and post responses to each tweet
    await twitter_client.reply_to_followers(db=db, agent_profile=agent_profile, tweets=tweets)


@with_db
async def reply_to_tweet(db: Session, agent_profile: AgentProfile, tweet_id: int) -> int | None:
    """
    Generates and posts a reply guy response to a specific tweet
    Returns the tweet ID of the response
    """
    # Fetch the tweet
    # TODO: use pipeline get_tweet_from_tweet_id
    tweet = await twitter_client.get_tweet_from_tweet_id(tweet_id)
    if not tweet:
        return None

    # Enrich the tweet with all the parents in the thread
    # It's not techically a mention, but the struct has the needed functionality
    mention = await twitter_client.enrich_user_mention(tweet)

    # If this was a thread, grab the author of the top parent,
    # otherwise grab the author last tweet in the reply
    original_tweet = mention.tagged_tweet if not mention.original_tweet else cast(HydratedTweet, mention.original_tweet)
    author = await original_tweet.get_username()

    # Get the recent tweets from this author
    author_recent_tweets = await twitter_client.get_author_recent_tweets(original_tweet.author_id)

    # Generate a response
    conversation_summary = await prompts.build_twitter_mentions_prompt(mention)
    response_evaluation = await post_maker.generate_reply_guy_tweet(
        agent_profile=agent_profile,
        author=author,
        tweet_summary=conversation_summary,
        author_recent_tweets=author_recent_tweets,
        agent_recent_tweets=[],
        allow_roasting=True,
    )

    if response_evaluation is None:
        return None

    # Post the response
    return await twitter_client.post_tweet_response(
        agent_profile=agent_profile,
        evaluation=response_evaluation,
        meme_threshold=MEME_RATING_THRESHOLD,
        text_threshold=RESPONSE_RATING_THRESHOLD_MENTIONS,
        conversation_id=mention.tagged_tweet.conversation_id,
        reply_to_tweet_id=mention.tagged_tweet.id,
        quote_tweet_id=original_tweet.id,
    )
