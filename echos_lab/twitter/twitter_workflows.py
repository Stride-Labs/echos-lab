from sqlalchemy.orm import Session

from echos_lab.common.logger import logger
from echos_lab.common.utils import with_db
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.twitter import twitter_client, twitter_pipeline


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
    user_id_mapping = await twitter_client.get_user_ids_from_usernames(db, usernames)

    # Get all tweets
    tweets = await twitter_client.get_all_follower_tweets(
        db=db,
        agent_name=agent_profile.name,
        user_id_mapping=user_id_mapping,
        since_time=bot_start_time,
    )

    # Generate and post responses to each tweet
    await twitter_client.reply_to_followers(db=db, agent_profile=agent_profile, tweets=tweets)
