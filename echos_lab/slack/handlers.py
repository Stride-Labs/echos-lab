import re

from slack_bolt.context.say.async_say import AsyncSay
from sqlalchemy.orm import Session

from echos_lab import main
from echos_lab.common.logger import logger
from echos_lab.engines import profiles
from echos_lab.slack.types import SlackHandler, SlackMessage
from echos_lab.twitter import twitter_workflows


async def _reply_to_tweet_callback(db: Session, message: SlackMessage, say: AsyncSay):
    """
    Callback handler for replying forcing a reply to a tweet

    Usage:       !{agent-name} {tweet-link}
    Ex:          !vito reply https://x.com/someuser/status/12345
    Raw Message: !vito reply <https://x.com/someuser/status/12345>
    """
    agent_name = profiles.get_agent_name()
    help_command = "```\n!{agent-name} reply {tweet-link}\nEx: !vito reply https://x.com/someuser/status/12345\n```\n"

    # Confirm the message was sent with a valid format
    pattern = re.compile(rf"^!{agent_name} reply <https://x\.com/[a-zA-Z0-9_]+/status/(\d+)>")
    match = re.match(pattern, message.text)
    if match is None:
        response = f"Invalid `reply` command, should be format:\n{help_command}"
        await say(response, thread_ts=message.id)
        return

    # Extract the agent name and tweet ID
    (tweet_id,) = match.groups()  # type: ignore

    # Grab link from back half of message
    tweet_link = message.text.split(" ")[-1].replace("<", "").replace(">", "")
    logger.info(f"Forcing twitter reply to {tweet_link} from slack")

    # Generate the reply
    agent_profile = profiles.get_agent_profile()
    response_tweet_id = await twitter_workflows.reply_to_tweet(agent_profile=agent_profile, tweet_id=int(tweet_id))
    if not response_tweet_id:
        await say("Failed to post response. This is likely because the rating was too low", thread_ts=message.id)
        return

    response_link = f"<https://x.com/{agent_profile.twitter_handle}/status/{response_tweet_id}>"
    await say(response_link, thread_ts=message.id)


async def _subtweet_callback(db: Session, message: SlackMessage, say: AsyncSay):
    """
    Callback handler for sending a subtweet based on a given topic

    Usage:       !{agent-name} subtweet [--dry-run] {topic}

    Options:
        --dry-run    Preview the tweet without posting it to Twitter

    Examples:
        !vito subtweet There is beef going on right now between X and Y
        !vito subtweet --dry-run Let me test this tweet first
    """
    agent_name = profiles.get_agent_name()
    help_command = (
        "```\n"
        "!{agent-name} subtweet [--dry-run] {topic}\n\n"
        "Options:\n"
        "  --dry-run    Preview the tweet without posting it to Twitter\n\n"
        "Examples:\n"
        "  !vito subtweet There is beef going on right now between X and Y\n"
        "  !vito subtweet --dry-run Let me test this tweet first\n"
        "```\n"
    )

    # Confirm the message was sent with a valid format
    pattern = re.compile(rf"^!{agent_name} subtweet( --dry-run |\s)(.*)")
    match = re.match(pattern, message.text)
    if match is None:
        response = f"Invalid `subtweet` command, should be format:\n{help_command}"
        await say(response, thread_ts=message.id)
        return

    # Extract the agent name and subtweet topic
    dry_run_flag, topic = match.groups()
    dry_run = dry_run_flag.strip() == "--dry-run"

    # Generate and post the subtweet
    subtweet_text, subtweet_id = await main.subtweet(topic, dry_run=dry_run)

    # If this was a dry run, just respond with the tweet text
    if dry_run:
        await say(subtweet_text, thread_ts=message.id)
        return

    # If this was not a dry-run, respond with the tweet link
    agent_profile = profiles.get_agent_profile()
    response_link = f"<https://x.com/{agent_profile.twitter_handle}/status/{subtweet_id}>"
    await say(response_link, thread_ts=message.id)
    return


def get_all_handlers() -> list[SlackHandler]:
    """Returns all SlackHandler instances defined in this module"""
    return [
        SlackHandler(name="reply", command="reply", handler=_reply_to_tweet_callback),
        SlackHandler(name="subtweet", command="subtweet", handler=_subtweet_callback),
    ]
