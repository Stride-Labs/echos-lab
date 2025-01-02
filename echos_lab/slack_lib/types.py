import datetime
import re
import traceback
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from cachetools import TTLCache
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.say.async_say import AsyncSay
from sqlalchemy.orm import Session

from echos_lab.db import db_setup


@dataclass
class SlackMessage:
    id: str
    timestamp: datetime.datetime
    timestamp_id: str
    channel: str
    sender: str
    text: str
    thread_ts: str | None

    @property
    def cache_key(self) -> str:
        return f"{self.channel}:{self.id}"

    @classmethod
    def from_dict(cls, message: dict) -> "SlackMessage":
        return cls(
            id=message["ts"],
            timestamp=datetime.datetime.fromtimestamp(float(message["ts"])),
            timestamp_id=message["ts"],
            channel=message["channel"],
            sender=message["user"],
            text=message["text"],
            thread_ts=message.get("thread_ts"),
        )


@dataclass
class SlackHandler:
    # The name of the handler
    name: str
    # The command to invoke the handler (e.g. "/do-something")
    command: str
    # The callback function when the command is invoked
    handler: Callable[[Session, SlackMessage, AsyncSay], Awaitable[None]]

    # Local cache of seen messages to prevent dupe
    # Without this, slack will try to reprocess the same message multiple times
    _message_cache: TTLCache = field(default_factory=lambda: TTLCache(maxsize=1000, ttl=300))

    def register_handler(self, app: AsyncApp, channel_id: str):
        """
        Wraps and registers the handler to take care of common functionality:
          - Casts the message JSON to a dataclass
          - Enforces the message is from the specified channel
          - Enforces the handler is only called on messages with the specified command
          - Prevents duplicate message processing
        """

        # Message must start with with either: "!{command}" or "! {command}"
        message_regex = re.compile(rf"^!\s?{re.escape(self.command)}")

        @app.message(message_regex)  # filters for messages that match the above regex
        async def wrapped_handler(message: dict, say: AsyncSay):
            """
            Actual slack handler that matches on the message type, verifies the channel
            and calls the business logic in the callback
            When the decorator (@app.message) is evaluated, the handler is registered
            """
            slack_message = SlackMessage.from_dict(message)

            # Ignore messages that not in the specified channel
            if slack_message.channel != channel_id:
                return

            # Ignore messages that were already processed
            if self._message_cache.get(slack_message.cache_key) is not None:
                return
            self._message_cache[slack_message.cache_key] = True

            # Call the user-specified handler
            try:
                with db_setup.get_db() as db:
                    await self.handler(db, slack_message, say)
            except Exception:
                await say(f"Failed to post tweet:\n```\n{traceback.format_exc()}\n```\n", thread_ts=slack_message.id)
