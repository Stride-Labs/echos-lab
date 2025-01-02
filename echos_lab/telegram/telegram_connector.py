import os
import re
import traceback
from functools import partial
from typing import List

from telegram import Update
from telegram.ext import Application, CallbackContext, ExtBot, MessageHandler, filters

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.common.logger import logger
from echos_lab.db import db_connector, db_setup, models
from echos_lab.engines import full_agent
from echos_lab.engines.personalities import profiles
from echos_lab.twitter import twitter_helpers

PARSE_MODE = "Markdown"
QUOTE_TWEET_MARKER = "QUOTE TWEET"
REPLY_TWEET_MARKER = "REPLY TO"
TWEET_MARKER = "TWEET"


# Module level singleton to store the telegram app
_app: Application | None = None


def get_telegram_app():
    """
    Singleton to get or create the telegram app
    """
    telegram_token = get_env_or_raise(envs.TELEGRAM_TOKEN)
    global _app
    if not _app:
        _app = Application.builder().token(telegram_token).build()
    return _app


def escape_markdown(text):
    """
    Escapes special markdown characters in text for telegram messages,
    to prevent messages from showing up as markdown
    """
    return re.sub(
        r'(?<!\[TWEET\]\()([_*[\]`])(?!.*\))',  # match markdown characters not in "[TWEET](...)" pattern
        r'\\\1',
        text,
    )


async def get_bot_username(bot: ExtBot) -> str:
    """
    Gets the telegram bot username by checking the info
    Errors if not found
    """
    bot_info = await bot.get_me()
    if not bot_info:
        raise ValueError(f"Bot info not found for {bot}!")
    if not bot_info.username:
        raise ValueError(f"Bot username not found for {bot}!")
    return bot_info.username


def get_posted_tweet_message(agent_username: str, tweet_id: int | None, tweet_text: str) -> str:
    """
    Builds a message to send in the telegram channel with the details of
    a tweet that was just posted.

    Successful message is of the form:
        Here is my tweet
        TWEETED (https://twitter.com/link/to/tweet)

    Failed message is of the form:
        Here is my tweet
        TWEET COULD NOT BE POSTED

    Args:
        agent_username: The twitter username of the agent
        tweet_id: The ID of the tweet (or None if the tweet failed)
        tweet_text: The tweet contents
    """
    if not tweet_id:
        return f"{tweet_text}\nTWEET COULD NOT BE POSTED"

    tweet_url = twitter_helpers.get_tweet_url(username=agent_username, tweet_id=tweet_id)
    return f"{tweet_text}\n[TWEETED]({tweet_url})\n"


def get_reply_tweet_message(agent_tweet_message: str, reply_to_tweet_url: str) -> str:
    """
    Builds a message to send in the telegram channel with details of a reply tweet

    Successful message is of the form:
        REPLY TWEET (https://twitter.com/link/to/tweet)
        Here is my tweet
        TWEETED (https://twitter.com/link/to/tweet)

    Failed message is of the form:
        REPLY TWEET (https://twitter.com/link/to/tweet)
        Here is my tweet
        TWEET COULD NOT BE POSTED

    Args:
        agent_tweet_message: String that includes the agent's tweet contents, and link
          (bottom two lines in example above)
        reply_to_tweet_url: URL of the tweet that's being replied to
    """
    original_tweet_header = f"[{REPLY_TWEET_MARKER}]({reply_to_tweet_url})"
    return f"{original_tweet_header}\n{agent_tweet_message}"


def get_quote_tweet_message(agent_tweet_message: str, quote_tweet_url: str) -> str:
    """
    Builds a message to send in the telegram channel with details of a quote tweet

    Successful message is of the form:
        QUOTE TWEET (https://twitter.com/link/to/tweet)
        Here is my tweet
        TWEETED (https://twitter.com/link/to/tweet)

    Failed message is of the form:
        QUOTE TWEET (https://twitter.com/link/to/tweet)
        Here is my tweet
        TWEET COULD NOT BE POSTED

    Args:
        agent_tweet_message: String that includes the agent's tweet contents, and link
          (bottom two lines in example above)
        quote_tweet_url: URL of the tweet that's being replied to
    """
    original_tweet_header = f"[{QUOTE_TWEET_MARKER}]({quote_tweet_url})"
    return f"{original_tweet_header}\n{agent_tweet_message}"


def get_username_from_update(update: Update) -> str:
    """
    Gets the telegram username from the update message
    If there's no username, returns their first name,
    and if there's no first name, returns "Unknown"
    """
    username = update.message.from_user.username  # type: ignore
    if username is None:
        username = update.message.from_user.first_name  # type: ignore
    if username is None:
        username = "Unknown"
    return username


def validate_message_update(update: Update, target_chat_id: int) -> str | None:
    """
    Validates an incoming telegram update and responds with a bool as to
    whether it can be ignored, based on the following critiera:
      - The update is empty
      - The updated chat ID doesn't match the target ID
      - There's no message in the update

    Returns the message text or None if the message should be ignored
    """
    if not update.effective_chat:
        logger.info("No chat found in update")
        return None

    if update.effective_chat.id != target_chat_id:
        logger.info("Update chat ID does not match target ID")
        return None

    if not update.message:
        return None

    logger.debug(f"Update: {update}")
    logger.debug(f"New message: {update.message.text}\n\n{update.message}")

    message_text = update.message.text
    if message_text.lower().strip().startswith("ignorethis"):  # type: ignore
        return None

    return message_text


def get_telegram_messages(target_chat_id: int, num_messages: int = 30) -> list[models.TelegramMessage]:
    """
    Reads recent telegram messages from the database
    """
    with db_setup.get_db() as db:
        return list(db_connector.get_telegram_messages(db, target_chat_id, num_messages))


def save_telegram_messages(username: str, message_contents: str, chat_id: int):
    """
    Saves sent telegram messages to the database
    """
    with db_setup.get_db() as db:
        db_connector.add_telegram_message(db, username, message_contents, chat_id)


def get_interacted_tweets() -> List[str]:
    """
    Gets a list of all the tweets that the bot has already interacted with
    This is to prevent re-engaging with the same tweet
    """
    # Gets the most recent 200 TG messages
    individual_chat_id = int(get_env_or_raise(envs.TELEGRAM_INDIVIDUAL_CHAT_ID))
    most_recent_messages_raw = get_telegram_messages(individual_chat_id, 200)

    # filter only to messages where msg.user_id == "You"
    most_recent_messages = [msg.content for msg in most_recent_messages_raw if msg.user_id == "You"]

    # Build a list of all the tweets IDs that were interacted with already
    interacted_tweets = []
    for message in most_recent_messages:
        if "https://twitter.com/" in message:
            try:
                tweet_id = message.split("https://twitter.com/")[1].split("/")[2].split(")")[0]
                interacted_tweets.append(tweet_id)
            except Exception:
                continue
    return list(set(interacted_tweets))


async def send_message(msg_contents: str, chat_id: int):
    """
    Asynchronously sends a telegram message to the specified chat
    Returns True since it's used as the last operation in most of the tools,
    which require returning a bool upon success
    """
    app = get_telegram_app()

    msg_contents = msg_contents.replace("@", "")
    logger.info(f"Sending message: {msg_contents}, to chat_id: {chat_id}, with parse_mode: {PARSE_MODE}")

    if (QUOTE_TWEET_MARKER in msg_contents) or (REPLY_TWEET_MARKER in msg_contents):
        first_line, rest = msg_contents.split("\n", 1)
        rest = escape_markdown(rest)
        msg_contents = f"{first_line}\n{rest}"
    else:
        msg_contents = escape_markdown(msg_contents)

    save_telegram_messages("You", msg_contents, chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=msg_contents,
        reply_markup=None,
        parse_mode=PARSE_MODE,
    )

    return True


async def individual_chat_message_handler(
    individual_chat_id: int,
    update: Update,
    context: CallbackContext,
):
    """
    This function triggers a callback when the bot receives a message in the target chat
    This is meant for bot-specific chats
    """
    message_text = validate_message_update(update, individual_chat_id)
    if not message_text:
        return

    try:
        # add message to history
        username = get_username_from_update(update)
        save_telegram_messages(username, message_text, individual_chat_id)

        # send typing symbol
        await context.bot.send_chat_action(chat_id=individual_chat_id, action="typing")

        # generate a new response
        await full_agent.respond_in_telegram_individual_flow(username, message_text, individual_chat_id)

    except Exception:
        traceback.print_exc()


def should_respond_to_groupchat_message(bot_name: str, message_text: str) -> bool:
    """
    Evaluates if the bot should respond to a message in the group chat.

    Currently, the bot will respond if the previous message contains the bot's name.
    """
    # filter to alphanumeric characters, without regex
    alphanum_message = "".join([c for c in message_text.lower() if c.isalnum()]).split()
    return bot_name.lower() in alphanum_message


async def group_chat_message_handler(
    bot_name: str,
    group_chat_id: int,
    update: Update,
    context: CallbackContext,
):
    """
    This function triggers a callback when the bot receives a message in a group chat
    (e.g. the community chat)
    """
    message_text = validate_message_update(update, group_chat_id)
    if not message_text:
        return

    try:
        # add message to history
        username = get_username_from_update(update)
        save_telegram_messages(username, message_text, group_chat_id)

        # evaluate if we should respond
        if not should_respond_to_groupchat_message(bot_name, message_text):
            return

        # send typing symbol
        await context.bot.send_chat_action(chat_id=group_chat_id, action="typing")

        # generate a new response
        await full_agent.respond_in_telegram_groupchat_flow(username, message_text, group_chat_id=group_chat_id)

    except Exception:
        traceback.print_exc()


async def start_telegram_listener() -> Application:
    """
    Configures and starts the telegram application with specific listeners/handlers:
        1. An echo-specific chat handler (e.g. the echo's TG chat)
        2. (Optionally) An echo *group* chat handler (e.g. the echo community chat)
        3. An emoji handler which listens to tweet buttons

    The app will poll for all messages and react based on each handler accordingly
    """
    # Get the agent profile
    agent_profile = profiles.get_legacy_agent_profile()
    bot_name = agent_profile.bot_name

    # Create a new telegram listening app
    app = get_telegram_app()
    individual_chat_id = int(get_env_or_raise(envs.TELEGRAM_INDIVIDUAL_CHAT_ID))
    group_chat_id = int(os.environ[envs.TELEGRAM_GROUP_CHAT_ID]) if envs.TELEGRAM_GROUP_CHAT_ID in os.environ else None

    # Listen to messages in the target chat
    in_individual_chat = filters.TEXT & filters.Chat(individual_chat_id)
    individual_chat_handler = partial(individual_chat_message_handler, individual_chat_id)
    app.add_handler(MessageHandler(in_individual_chat, individual_chat_handler))

    # If configured, listen to messages in the group chat
    if group_chat_id:
        logger.info(f"LISTENING TO GROUPCHAT: {group_chat_id}")
        in_group_chat = filters.TEXT & filters.Chat(group_chat_id)
        group_chat_handler = partial(group_chat_message_handler, bot_name, group_chat_id)
        app.add_handler(MessageHandler(in_group_chat, group_chat_handler))

    # Initailize the listener app
    await app.initialize()
    await app.start()

    # Start polling for new messages (that match the above handlers)
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)  # type: ignore
    return app
