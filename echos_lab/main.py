import os
from echos_lab.db import db_setup, db_seed
from echos_lab.engines import full_agent, context_store
from echos_lab.telegram_lib import telegram_connector
from echos_lab.crypto_lib import crypto_connector
from dotenv import load_dotenv
import threading
import schedule
import asyncio
import nest_asyncio
from multiprocessing import freeze_support


load_dotenv()

LOOP_FREQUENCY = 60  # minutes

nest_asyncio.apply()

context_store.set_env_var("chat_id", telegram_connector.TARGET_CHAT_ID)


def seed_db_if_not_exists():
    # Check if the database file exists
    if not os.path.exists(db_setup.DB_PATH):
        print("Creating database...")
        db_setup.create_database()
        print("Seeding database...")
        db_seed.seed_database()
    else:
        print("Database already exists. Skipping creation and seeding.")


def create_onchain_account_if_not_exists():
    crypto_connector.get_account()


async def run_scheduler_async():
    while True:
        schedule.run_pending()
        await asyncio.sleep(5)


async def general_flow_async():
    return await asyncio.to_thread(full_agent.general_flow)


async def reply_flow_async():
    return await asyncio.to_thread(full_agent.reply_to_tweet_notifications_flow)


def start_scheduler():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # schedule the task to run every 30 minutes
    schedule.every(LOOP_FREQUENCY).minutes.do(lambda: asyncio.run_coroutine_threadsafe(general_flow_async(), loop))

    loop.run_until_complete(run_scheduler_async())


def main():
    freeze_support()

    seed_db_if_not_exists()
    create_onchain_account_if_not_exists()

    # run Twitter agent every 5 minutes
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Telegram listener (this will block the main thread)
    telegram_connector.start_listening_to_tg_messages()


def test_main():
    freeze_support()
    seed_db_if_not_exists()
    full_agent.reply_to_tweet_notifications_flow()


if __name__ == "__main__":
    main()
