import asyncio
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.common.logger import logger
from echos_lab.crypto_lib import crypto_connector
from echos_lab.db import db_connector, db_setup
from echos_lab.engines import full_agent, image_creator, post_maker
from echos_lab.engines.personalities import profiles
from echos_lab.engines.personalities.profiles import AgentProfile, LegacyAgentProfile
from echos_lab.slack_lib.client import SlackClient
from echos_lab.telegram_lib import telegram_connector
from echos_lab.twitter_lib import (
    twitter_client,
    twitter_connector,
    twitter_pipeline,
    twitter_workflows,
)

TWITTER_FLOW_LOOP_FREQUENCY = 120  # minutes
REPLY_GUY_LOOP_FREQUENCY = 1  # minutes


async def setup_legacy_app() -> LegacyAgentProfile:
    """
    Common setup functionality including initalizing the database and
    setting up the crypto account
    """
    agent_profile = profiles.get_legacy_agent_profile()

    db_setup.init_db()
    crypto_connector.get_account()
    image_creator.validate_image_envs()

    # Ensure the agent's username is stored in the database
    with db_setup.get_db() as db:
        agent_user_id = await twitter_pipeline.require_user_id_from_username(db, agent_profile.twitter_handle)
        db_connector.add_twitter_user(db, user_id=agent_user_id, username=agent_profile.twitter_handle)

    return agent_profile


async def setup_app() -> AgentProfile:
    """
    Common setup functionality including initalizing the database
    """
    agent_profile = profiles.get_agent_profile()

    db_setup.init_db()

    # Ensure the agent's username is stored in the database
    with db_setup.get_db() as db:
        agent_user_id = await twitter_pipeline.require_user_id_from_username(db, agent_profile.twitter_handle)
        db_connector.add_twitter_user(db, user_id=agent_user_id, username=agent_profile.twitter_handle)

    return agent_profile


async def run_twitter_flow(login: bool):
    """
    Testing helper to run through only the twitter flow, which will read
    timelines and create tweets
    This runs through the flow once and then exits
    """
    agent_profile = await setup_legacy_app()

    if login:
        twitter_connector.login_to_twitter()

    individual_telegram_chat_id = int(get_env_or_raise(envs.TELEGRAM_INDIVIDUAL_CHAT_ID))
    await full_agent.twitter_flow(agent_profile.twitter_handle, individual_telegram_chat_id)


async def run_telegram_flow():
    """
    Testing helper to run through only the telegram flow, which will
    listen to the telegram chat and respond
    """
    await setup_legacy_app()

    app = await telegram_connector.start_telegram_listener()
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await app.stop()


async def subtweet(tweet_topic: str, dry_run: bool = False) -> tuple[str, int | None]:
    """
    Generates and posts a subtweet using the agent's background context
    to set the stage, while focusing the material on tweet_topic
    Currently setup to only work with the reply-guy

    Returns:
        The subtweet text and tweet ID (or None if this was a dry run)
    """
    # Generate the subtweet
    agent_profile = await setup_app()
    agent_username = agent_profile.twitter_handle
    response_data = await post_maker.generate_subtweet(agent_profile, tweet_topic)

    if dry_run:
        logger.info("[DRYRUN] Did not post subtweet because --dryrun flag was set.")
        return response_data.subtweet, None

    # Post the subtweet
    response_tweet_id = await twitter_client.post_tweet(agent_username=agent_username, text=response_data.subtweet)

    return response_data.subtweet, response_tweet_id


async def start_twitter_reply_guy(
    mentions_only: bool,
    followers_only: bool,
    disable_slack: bool,
    slack_handlers: list[str] | None,
):
    """
    Starts the "reply-guy" scheduler which polls for twitter mentions
    and generates and posts responses

    Arg:
        mentions_only: bool indicating if we should only reply to mentions
        followers_only: bool indicating if we should only reply to followers
        disable_slack: bool indicating whether to turn off the slack listener
    """
    # Get the reply guy agent profile
    agent_profile = await setup_app()

    # Get the current time in RFC 3339
    current_time = datetime.now()
    lagged_time = datetime.now() + timedelta(seconds=30)  # offset from mention job
    current_time_string = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # used as twitter search filter

    # If an "only" flow is configured, start that job right away
    # Otherwise lag the followers job
    mentions_start_time = current_time
    followers_start_time = current_time if followers_only else lagged_time

    # Create a new scheduler to run the reply flows
    scheduler = AsyncIOScheduler()

    # Add the mentions job (if applicable)
    if not followers_only:
        scheduler.add_job(
            twitter_workflows.run_reply_guy_mentions_cycle,
            args=[agent_profile, current_time_string],
            trigger=IntervalTrigger(minutes=REPLY_GUY_LOOP_FREQUENCY),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None,
            name="reply-guy-mentions",
            next_run_time=mentions_start_time,
        )

    # Add the mentions job (if applicable)
    if not mentions_only:
        scheduler.add_job(
            twitter_workflows.run_reply_guy_followers_cycle,
            args=[agent_profile, current_time_string],
            trigger=IntervalTrigger(minutes=REPLY_GUY_LOOP_FREQUENCY),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None,
            name="reply-guy-followers",
            next_run_time=followers_start_time,
        )

    # Start the scheduler and wait cleanup gracefully during interruption
    scheduler.start()
    slack_client = None
    try:
        # If slack is enabled, we can use that listener as the main one that will keep the app active
        # If it's disabled, we have to explicitly wait
        if not disable_slack:
            slack_client = SlackClient(handlers=slack_handlers)
            await slack_client.start_listener()
        else:
            await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        scheduler.shutdown()
        if slack_client is not None:
            await slack_client.stop()


async def start_bot(login: bool):
    """
    Main entrypoint for the bot - spins up two processes:
     1. A background scheduled job to check twitter and respond to tweets
     2. A telegram listener to respond to messages in the respective chats
    """
    # Login to twitter if specified
    if login:
        twitter_connector.login_to_twitter()

    # Initialize database and accounts
    agent_profile = await setup_legacy_app()
    individual_telegram_chat_id = int(get_env_or_raise(envs.TELEGRAM_INDIVIDUAL_CHAT_ID))

    # Kick off the background scheduler to create tweets
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        full_agent.twitter_flow,
        args=[agent_profile.twitter_handle, individual_telegram_chat_id],
        trigger=IntervalTrigger(minutes=TWITTER_FLOW_LOOP_FREQUENCY),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=None,
        name="twitter-flow",
    )
    scheduler.start()

    # Start listening to telegram messages
    app = await telegram_connector.start_telegram_listener()

    # Keep process running indefinitely, and gracefully shut down
    # the telegram app and scheduler when the thread is killed
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await app.stop()
        scheduler.shutdown()


async def start_slack_listener(handlers: list[str] | None):
    """
    Starts the slack listener to listen for messages and respond with custom handlers
    """
    await setup_app()
    client = SlackClient(handlers=handlers)

    try:
        await client.start_listener()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await client.stop()
