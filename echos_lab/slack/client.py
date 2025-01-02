from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.slack import handlers


class SlackClient:
    """
    Singleton client used to read and post slack messages
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs) -> "SlackClient":
        # Creates a new instance if one does not already exist
        if cls._instance is None:
            cls._instance = super(SlackClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, handlers: list[str] | None = None):
        # Prevent re-initialization if a client has already been created
        if self._initialized:
            return

        self.channel_id = get_env_or_raise(envs.SLACK_CHANNEL_ID)
        self.bot_token = get_env_or_raise(envs.SLACK_BOT_TOKEN)  # for posting
        self.app_token = get_env_or_raise(envs.SLACK_APP_TOKEN)  # for listening

        self.app = AsyncApp(token=self.bot_token)
        self.handler = AsyncSocketModeHandler(self.app, app_token=self.app_token)
        self._register_handlers(handlers)

        self._initialized = True

    def _register_handlers(self, handler_names: list[str] | None):
        """Setup all message handlers"""
        # If no handler names were passed in, register them all
        # Otherwise, only register those specified
        for handler in handlers.get_all_handlers():
            if not handler_names or handler.name in handler_names:
                handler.register_handler(self.app, self.channel_id)

    async def start_listener(self):
        """Starts the socket mode handler"""
        await self.handler.start_async()

    async def stop(self):
        """Cleanup to properly close socket connection"""
        if self.handler:
            await self.handler.close_async()
