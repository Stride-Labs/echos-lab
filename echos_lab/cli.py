import asyncio

import click

from echos_lab import main
from echos_lab.crypto_lib import crypto_connector
from echos_lab.db import db_setup
from echos_lab.db.migrations import json_to_postgres
from echos_lab.telegram import telegram_groups
from echos_lab.testing import scratch as scratchpad
from echos_lab.testing import twitter_replies as testing_twitter_replies
from echos_lab.twitter import auth, twitter_connector, twitter_helpers


@click.group()
def cli():
    """Echos Lab CLI"""
    pass


@cli.group()
def testing():
    """Commands for testing"""
    pass


@cli.group()
def db():
    """Database commands"""
    pass


@cli.command("login")
@click.option("--no-headless", is_flag=True, default=False, help="Run driver in visible mode instead of headless")
def twitter_login(no_headless: bool):
    """Login to twitter if cookies are nonexistent or stale"""
    twitter_connector.login_to_twitter(headless=not no_headless)


@cli.command("clear-cookies")
def clear_cookies():
    """Deletes twitter cookies"""
    if click.confirm("Are you sure you want to clear Twitter cookies?", abort=True):
        twitter_helpers.delete_cookies()


@cli.command("create-telegram-group")
def create_telegram_group():
    """Create a telegram group for testing"""
    asyncio.run(telegram_groups.create_test_group())


@cli.command("balances")
def balances():
    """Displays the bot's address and balances"""
    crypto_connector.display_account_balances()


@cli.command("twitter")
@click.option("--login", is_flag=True, default=False, help="Login to twitter before scraping posts")
def twitter(login: bool):
    """Run twitter flow

    Read tweets from the bots timeline and create a new tweet
    """
    asyncio.run(main.run_twitter_flow(login))


@cli.command("telegram")
def telegram():
    """Start the telegram flow

    Listens for telegram messages and respond in the chats
    """
    asyncio.run(main.run_telegram_flow())


@cli.command("slack")
@click.option(
    '--handlers',
    help='Comma-separated list of handler names to enable (default: all handlers)',
    default='',
    type=str,
)
def slack(handlers: str):
    """Starts the slack listener

    Listens for new messages and responds with custom handlers
    The listener will pick up messages from all channels where the bot is present
    """
    handler_list = [h.strip() for h in handlers.split(',') if h.strip()] or None
    asyncio.run(main.start_slack_listener(handler_list))


@cli.command("reply-guy")
@click.option("--mentions-only", is_flag=True, default=False, help="Only reply to mentions")
@click.option("--followers-only", is_flag=True, default=False, help="Only reply to posts from followers")
@click.option("--disable-slack", is_flag=True, default=False, help="Disable the slack listener")
@click.option(
    '--slack-handlers',
    help='Comma-separated list of slack handler names to enable (default: all handlers)',
    default='',
    type=str,
)
def reply_guy(mentions_only: bool, followers_only: bool, disable_slack: bool, slack_handlers: str):
    """Starts the "reply guy" twitter flow

    Polls for mentions and new tweets from followers on twitter
    Generates and posts a responses for each
    """
    slack_handler_list = [h.strip() for h in slack_handlers.split(',') if h.strip()] or None
    assert not (mentions_only and followers_only), "--mentions-only and --followers-only cannot both be specified"
    assert not (disable_slack and slack_handlers), "Cannot disable handlers while specifying the list of handlers"
    asyncio.run(main.start_twitter_reply_guy(mentions_only, followers_only, disable_slack, slack_handler_list))


@cli.command("subtweet")
@click.argument("topic")
@click.option("--dry_run", is_flag=True, help="Don't post the subtweet, just print it")
def subtweet(topic: str, dry_run: bool = False):
    """Generates and posts a subtweet from the reply-guy

    Specify the topic as a string, ideally in reference to a trending topic
    The agent will use it's configured agent context as background

    e.g.
    >>> echos subtweet "personA and personB are beefing on twitter right now"
    """
    asyncio.run(main.subtweet(topic, dry_run))


@cli.command("start")
@click.option("--login", is_flag=True, help="Login to twitter before starting bot")
def start(login: bool):
    """Starts the echo lab bot

    Scrapes twitter, create tweets, and respond to telegram chats
    """
    asyncio.run(main.start_bot(login))


@cli.command("oauth1")
def oauth1():
    """Starts the oauth1 flow to get the twitter access tokens

    The process generates a link, which the user must visit to authorize the app.
    Then, they must send the PIN back to the script to get the access tokens.
    """
    auth.get_twitter_access_tokens()


@testing.command("generate-examples")
@click.argument("links_file", type=click.Path(exists=True), default="tweet_links.txt")
@click.argument("tweets_file", type=click.Path(), default="tweets.json")
def generate_test_examples(links_file, tweets_file):
    """Generates a list of example tweets to test prompting

    This command reads from the specified links file,
    extracts the contents and threads from each link, and writes the
    output to the specified tweets file.
    """
    asyncio.run(testing_twitter_replies.generate_tweet_examples(links_file, tweets_file))


@testing.command("generate-responses")
@click.argument("input_file", type=click.Path(exists=True), default="tweets.json")
def generate_test_responses(input_file):
    """Generates an LLM response to each of the prompt examples

    This command reads from the specified input file
    and writes the output to `echos_lab/testing/output/{current_time}.txt`
    """
    asyncio.run(testing_twitter_replies.generate_tweet_responses(input_file))


@testing.command("scratch")
def scratch():
    """Runs scratch testing scripts"""
    asyncio.run(scratchpad.main())


@db.command("init")
def init_db():
    """Initializes the database and creates the tables"""
    db_setup.init_db()


@db.command("migrate")
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without making changes.")
@click.option("--backup", is_flag=True, default=True, help="Backup JSON files before migration")
@click.option("--profile", required=True, help="Name of the agent profile to use for migration")
def migrate_db(dry_run: bool, backup: bool, profile: str):
    """Migrate data from JSON files to PostgreSQl database."""
    with db_setup.get_db() as db:
        asyncio.run(json_to_postgres.migrate(db=db, dry_run=dry_run, backup=backup, profile_name=profile))
