# we use telethon to create a group chat, as bots can't create groups
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.types import ChatBannedRights

from dotenv import load_dotenv
import os

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

# the TG API IDs are used for the telethon client, to create group chats
TG_API_ID = os.getenv("TG_API_ID")
if not TG_API_ID:
    raise ValueError("TG_API_ID not found in .env file")
TG_API_HASH = os.getenv("TG_API_HASH")
if not TG_API_HASH:
    raise ValueError("TG_API_HASH not found in .env file")

client = TelegramClient("create_chat_session", api_id=int(TG_API_ID), api_hash=TG_API_HASH)


def initialize_telegram_client():
    client.start()


async def create_group_with_admins(
    client: TelegramClient,
    group_name: str,
    group_description: str,
    user_ids: list[str],
) -> int:
    """
    Creates a Telegram megagroup with specified users, sets a description, and assigns admin rights.
    """
    # Step 1: Create the megagroup
    result = await client(
        CreateChannelRequest(title=group_name, about=group_description, megagroup=True)  # This makes it a megagroup
    )
    # Get the channel ID
    channel = result.chats[0]  # type: ignore
    channel_id = channel.id
    print(f"Megagroup '{group_name}' created successfully!")

    # Step 2: Add users to the channel (since we can't add them during creation)
    for user_id in user_ids:
        try:
            await client.edit_admin(
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
            print(f"User {user_id} added as admin.")
        except Exception as e:
            print(f"Failed to add {user_id} as admin: {e}")

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

    await client(EditChatDefaultBannedRightsRequest(peer=channel_id, banned_rights=default_rights))
    print("Group permissions set successfully!")

    # add -100 because this is a megagroup
    return int("-100" + str(channel_id))
