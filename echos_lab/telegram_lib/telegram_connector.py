from telegram.ext import Application, ExtBot, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.constants import MessageEntityType

from dotenv import load_dotenv
import os
import re
from echos_lab.twitter_lib import twitter_connector
from echos_lab.engines import full_agent, agent_interests
from echos_lab.db import db_setup, db_connector
import asyncio
import time
from typing import List
import argparse
import traceback

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

# the TG Token is used for the bot
TG_TOKEN = os.getenv("TG_TOKEN", "")
if TG_TOKEN == "":
    raise ValueError("TG_TOKEN not found in .env file")

TARGET_CHAT_ID = os.getenv("CHAT_ID", "")
if TARGET_CHAT_ID == "":
    raise ValueError("CHAT_ID not found in .env file")
TARGET_CHAT_ID = int(TARGET_CHAT_ID)

# get TG admin
TG_ADMIN_HANDLE = os.getenv("TG_ADMIN_HANDLE", "")
if TG_ADMIN_HANDLE == "":
    raise ValueError("TG_ADMIN_HANDLE not found in .env file")

lower_bot_name = agent_interests.BOT_NAME.lower()

GROUPCHAT_TARGET_ID = os.getenv("GROUPCHAT_ID", "0")
GROUPCHAT_TARGET_ID = int(GROUPCHAT_TARGET_ID)
if GROUPCHAT_TARGET_ID == 0:
    IS_IN_GROUPCHAT = False

PARSE_MODE = "Markdown"

QUOTE_TWEET_MARKER = "QUOTE TWEET"
REPLY_TWEET_MARKER = "REPLY TO"
TWEET_MARKER = "TWEET"

app = Application.builder().token(TG_TOKEN).build()
bot = app.bot

ACCOUNT = twitter_connector.get_twitter_account()

DB = db_setup.get_db_session()


async def get_bot_username(bot: ExtBot) -> str:
    bot_info = await bot.get_me()
    if not bot_info:
        raise ValueError(f"Bot info not found for {bot}!")
    if not bot_info.username:
        raise ValueError(f"Bot username not found for {bot}!")
    return bot_info.username


def escape_markdown(text):
    return re.sub(r'([_*[\]`])', r'\\\1', text)


def get_most_recent_messages(target_chat_id=TARGET_CHAT_ID) -> List[tuple[str, str]]:
    # grab most recent messages
    most_recent_messages_raw = db_connector.get_tg_messages(DB, target_chat_id, 30)
    most_recent_messages = [(msg.user_id, msg.content) for msg in most_recent_messages_raw][::-1]
    return most_recent_messages  # type: ignore


def get_interacted_tweets(target_chat_id=TARGET_CHAT_ID) -> List[str]:
    most_recent_messages_raw = db_connector.get_tg_messages(DB, target_chat_id, 30)
    # filter only to messages where msg.user_id == "You"
    most_recent_messages = [msg.content for msg in most_recent_messages_raw if msg.user_id == "You"]  # type: ignore
    interacted_tweets = []
    for message in most_recent_messages:
        if "https://twitter.com/" in message:
            try:
                tweet_id = message.split("https://twitter.com/")[1].split("/")[2].split(")")[0]
                interacted_tweets.append(tweet_id)
            except Exception:
                continue
    return list(set(interacted_tweets))


async def create_test_group():
    from echos_lab.telegram_lib import create_telegram_group

    bot_username = await get_bot_username(bot)

    usernames = [TG_ADMIN_HANDLE] + [bot_username]
    bot_name = agent_interests.BOT_NAME
    description = f"Chat with {bot_name} - an Echo"
    create_telegram_group.initialize_telegram_client()
    async with create_telegram_group.client:
        chat_id = await create_telegram_group.create_group_with_admins(
            create_telegram_group.client,
            bot_name + " - Echo",
            description,
            usernames,
        )

    # Await the async function
    print(f"Created group with chat_id: {chat_id}")


async def send_message(msg_contents, chat_id=TARGET_CHAT_ID):
    if chat_id == TARGET_CHAT_ID:
        # define emoji buttons
        keyboard = [[InlineKeyboardButton("Tweet 🐦", callback_data="tweet")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = None

    msg_contents = msg_contents.replace("@", "")
    print(f"Sending message: {msg_contents}, to chat_id: {chat_id}, with parse_mode: {PARSE_MODE}")

    if (QUOTE_TWEET_MARKER in msg_contents) or (REPLY_TWEET_MARKER in msg_contents):
        first_line, rest = msg_contents.split("\n", 1)
        rest = escape_markdown(rest)
        msg_contents = f"{first_line}\n{rest}"
    else:
        msg_contents = escape_markdown(msg_contents)

    db_connector.add_tg_message(DB, "You", msg_contents, chat_id)

    await bot.send_message(
        chat_id=chat_id,
        text=msg_contents,
        reply_markup=reply_markup,
        parse_mode=PARSE_MODE,
    )


def send_message_sync(msg_contents, chat_id=TARGET_CHAT_ID):
    # try to send message 5 times
    for i in range(5):
        try:
            try:
                # Check if there's a running event loop
                loop = asyncio.get_running_loop()
                # If there is, create a task to send the message
                asyncio.create_task(send_message(msg_contents, chat_id))
            except Exception:
                # If no running event loop, create one and run the message
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # asyncio.create_task(send_message(msg_contents))
                loop.run_until_complete(send_message(msg_contents, chat_id))
        except Exception:
            print(f"ERROR SENDING MESSAGE {msg_contents} - TRY {i+1}")
            traceback.print_exc()
            time.sleep(3)
            continue
        break


async def message_handler(update: Update, context: CallbackContext, target_chat_id: int = TARGET_CHAT_ID):
    '''
    This function triggers a callback when the bot receives a message in the target chat.
    '''
    if not update.effective_chat:
        print("No chat found in update")
        return
    chat_id = update.effective_chat.id

    try:
        if chat_id == target_chat_id:
            if update.message:
                print(f"New message: {update.message.text}\n\n{update.message}")
                message_text = update.message.text
                if message_text.lower().strip().startswith("ignorethis"):  # type: ignore
                    return
                # add message to history
                username = update.message.from_user.username  # type: ignore
                if username is None:
                    username = update.message.from_user.first_name  # type: ignore
                if username is None:
                    username = "Unknown"
                db_connector.add_tg_message(DB, username, message_text, chat_id)  # type: ignore
                # send typing symbol
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                # generate a new response
                full_agent.respond_in_telegram_flow(username, message_text)
    except Exception:
        traceback.print_exc()


def evalute_if_should_respond_to_message(message_text: str, message_sender: str) -> bool:
    print("SENDER", message_sender)
    words = message_text.lower().split()
    start_sentence = " ".join(words[:3])
    if lower_bot_name in start_sentence:
        return True
    return False


async def groupchat_message_handler(
    update: Update, context: CallbackContext, target_chat_id: int = GROUPCHAT_TARGET_ID
):
    '''
    This function triggers a callback when the bot receives a message in the target chat.
    '''
    if not update.effective_chat:
        print("No chat found in update")
        return
    print("UPDATE")
    print(update)
    try:
        chat_id = update.effective_chat.id
        if chat_id == target_chat_id:
            if update.message:
                print(f"New message: {update.message.text}\n\n{update.message}")
                message_text = update.message.text
                if message_text.lower().strip().startswith("ignorethis"):  # type: ignore
                    return
                # add message to history
                username = update.message.from_user.username  # type: ignore
                if username is None:
                    username = update.message.from_user.first_name  # type: ignore
                if username is None:
                    username = "Unknown"
                db_connector.add_tg_message(DB, username, message_text, chat_id)  # type: ignore
                if not evalute_if_should_respond_to_message(message_text, username):  # type: ignore
                    return
                # send typing symbol
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                print(get_most_recent_messages(target_chat_id))
                # generate a new response
                full_agent.respond_in_telegram_groupchat_flow(username, message_text, chat_id=chat_id)
    except Exception:
        traceback.print_exc()


def initiate_tweet(msg: str) -> str:
    quote_marker = f"[{QUOTE_TWEET_MARKER}]"
    reply_marker = f"[{REPLY_TWEET_MARKER}]"

    if msg.startswith(quote_marker):
        msg_contents = msg.split("\n", 1)[1].strip()
        quote_tweet_id = msg.split("(", 1)[1].split(")")[0].split("/")[-1]
        tweet_result = twitter_connector.post_tweet(msg_contents, quote_tweet_id=quote_tweet_id)
    elif msg.startswith(reply_marker):
        msg_contents = msg.split("\n", 1)[1].strip()
        reply_tweet_id = msg.split("(", 1)[1].split(")")[0].split("/")[-1]
        tweet_result = twitter_connector.post_tweet(msg_contents, reply_tweet_id=reply_tweet_id)
    elif msg.startswith(TWEET_MARKER):
        tweet_content = msg.split("\n", 1)[1].strip()
        tweet_result = twitter_connector.post_tweet(tweet_content)
    else:
        tweet_result = twitter_connector.post_tweet(msg)
    return tweet_result


async def emoji_reaction_handler(update: Update, context: CallbackContext):
    '''
    This function handles when users react to the bot's emoji buttons.
    '''
    query = update.callback_query
    if not query:
        print("No query found in update")
        return
    if not query.from_user:
        print("No user found in query")
        return
    user_id = query.from_user.id

    # fetch the user's status in the chat
    chat_member = await context.bot.get_chat_member(TARGET_CHAT_ID, user_id)
    is_admin = chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]

    if is_admin:
        # acknowledge the button press if the user is an admin
        await query.answer()

        # handle reaction based on callback data
        reaction = query.data
        current_text = query.message.text  # type: ignore
        entities = query.message.entities  # type: ignore
        # find and insert hyperlinks
        for entity in entities:
            if entity.type == MessageEntityType.TEXT_LINK:
                offset_text = current_text[entity.offset : entity.offset + entity.length]  # noqa: E203
                current_text = (
                    current_text[: entity.offset]
                    + f"[{offset_text}]({entity.url})"
                    + current_text[entity.offset + entity.length :]  # noqa: E203
                )

        if reaction == "tweet":
            tweet_result = initiate_tweet(current_text)
            if tweet_result != "":
                new_text = current_text + f"\n\nThis message was approved by {query.from_user.username}"
                new_text += f", [tweeted]({tweet_result}) 🐦"
                await query.edit_message_text(text=new_text, parse_mode=PARSE_MODE)


def start_listening_to_tg_messages():
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(TARGET_CHAT_ID), message_handler))  # type: ignore
    if IS_IN_GROUPCHAT:
        print(f"LISTENING TO GROUPCHAT: {GROUPCHAT_TARGET_ID}")
        app.add_handler(
            MessageHandler(
                filters.TEXT & filters.Chat(GROUPCHAT_TARGET_ID),  # type: ignore
                groupchat_message_handler,
            )
        )
    app.add_handler(CallbackQueryHandler(emoji_reaction_handler))

    print("starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Telegram bot runner')
    parser.add_argument('--create-chat', action='store_true', help='Create a new test chat group')
    args = parser.parse_args()

    if args.create_chat:
        asyncio.run(create_test_group())
    else:
        start_listening_to_tg_messages()
