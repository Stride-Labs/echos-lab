import logging

# Silence Telethon's libssl info log
logging.getLogger("telethon").setLevel(logging.WARNING)

from telethon import TelegramClient  # noqa: E402
from telethon.tl.functions.channels import CreateChannelRequest  # noqa: E402
from telethon.tl.functions.messages import (  # noqa: E402
    EditChatDefaultBannedRightsRequest,
)
from telethon.tl.types import ChatBannedRights  # noqa: E402

from echos_lab.common.env import EnvironmentVariables as envs  # noqa: E402
from echos_lab.common.env import get_env_or_raise  # noqa: E402
from echos_lab.common.logger import logger  # noqa: E402
from echos_lab.telegram import telegram_client  # noqa: E402


async def create_group_with_admins(
    telethon_client: TelegramClient,
    group_name: str,
    group_description: str,
    user_ids: list[str],
) -> int:
    """
    Creates a Telegram megagroup with specified users, sets a description, and assigns admin rights.
    """
    # Step 1: Create the megagroup
    result = await telethon_client(
        CreateChannelRequest(title=group_name, about=group_description, megagroup=True)  # This makes it a megagroup
    )
    # Get the channel ID
    channel = result.chats[0]  # type: ignore
    channel_id = channel.id
    logger.info(f"Megagroup '{group_name}' created successfully!")

    # Step 2: Add users to the channel (since we can't add them during creation)
    for user_id in user_ids:
        try:
            await telethon_client.edit_admin(
                channel_id,
                user_id,
                is_admin=True,
                title="Admin",
                add_admins=True,
                invite_users=True,
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                pin_messages=True,
                manage_call=True,
                anonymous=False,
            )
            logger.info(f"User {user_id} added as admin.")
        except Exception as e:
            logger.error(f"Failed to add {user_id} as admin: {e}")

    # Set default permissions (optional, adjust as needed)
    default_rights = ChatBannedRights(
        until_date=None,
        send_messages=True,
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True,
        invite_users=False,
        pin_messages=True,
        change_info=True,
        view_messages=False,
    )

    await telethon_client(EditChatDefaultBannedRightsRequest(peer=channel_id, banned_rights=default_rights))
    logger.info("Group permissions set successfully!")

    # add -100 because this is a megagroup
    return int("-100" + str(channel_id))


async def create_test_group():
    """
    Creates a personal telegram group for testing

    Telethon is used to create groups since bots can't create groups
    """
    # Create telegram app
    app = telegram_client.get_telegram_app()
    admin_username = get_env_or_raise(envs.TELEGRAM_ADMIN_HANDLE)
    bot_username = await telegram_client.get_bot_username(app.bot)
    bot_name = get_env_or_raise(envs.LEGACY_AGENT_NAME).capitalize()

    # Create and start telethon client (since )
    api_id = int(get_env_or_raise(envs.TELEGRAM_API_ID))
    api_hash = get_env_or_raise(envs.TELEGRAM_API_HASH)
    telethon_client = TelegramClient("create_chat_session", api_id=api_id, api_hash=api_hash)
    telethon_client.start()

    usernames = [admin_username, bot_username]
    description = f"Chat with {bot_name} - an Echo"

    async with telethon_client:
        chat_id = await create_group_with_admins(
            telethon_client,
            bot_name + " - Echo",
            description,
            usernames,
        )

    logger.info(f"Created group with chat_id: {chat_id}")
