import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.db.models import QueryType, TwitterQueryCheckpoint, TwitterUser
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.twitter import twitter_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_JSON_FILES_DIR = Path(__file__).parent.parent.parent / "db"
JSON_FILES_DIR = Path(os.getenv("REPLYGUY_DB_DIRECTORY", DEFAULT_JSON_FILES_DIR))


class MigrationError(Exception):
    """Custom exception for migration errors."""

    pass


class MigrationConfig:
    """Migration configuration that can be overridden in tests."""

    files_dir = JSON_FILES_DIR


async def get_agent_id(db: Session, profile_name: str, dry_run: bool = False) -> int:
    """Get agent ID from profile"""
    # Load agent profile.
    agent_profile = AgentProfile.from_yaml(profile_name)
    agent_username = agent_profile.twitter_handle

    # First check DB
    user = db.query(TwitterUser).filter_by(username=agent_username).first()
    if user:
        return user.user_id

    # If not found in DB, fetch from Twitter API
    agent_id = await twitter_client.get_user_id_from_username(agent_username)
    if not agent_id:
        raise MigrationError(f"Could not get the ID not found for agent @{agent_username}")

    if dry_run:
        logger.info(f"Would create user: {agent_username} (ID: {agent_id})")
        return agent_id

    # Save to DB
    user = TwitterUser(
        username=agent_username,
        user_id=agent_id,
    )
    db.add(user)
    db.commit()

    return agent_id


def backup_json_files(json_dir: Path) -> Path:
    """Create backup of JSON files before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = json_dir.parent / f"backup_{timestamp}"
    shutil.copytree(json_dir, backup_dir)
    return backup_dir


def migrate_user_ids(db: Session, data: dict, dry_run: bool = False):
    """Migrate user IDs from reply_guy_user_ids.json to TwitterUser table."""
    print(f"Migrating users with data: {data}")
    for username, user_id in data.items():
        print(f"Processing user: {username} with ID: {user_id}")
        if dry_run:
            continue

        user = TwitterUser(user_id=user_id, username=username)
        print(f"Created user object: {user.username} ({user.user_id})")
        db.merge(user)

    if not dry_run:
        print("Committing changes...")
        db.commit()
        print("Changes committed")

        # Verify data was persisted
        users = db.query(TwitterUser).all()
        print(f"Users after commit: {[u.username for u in users]}")


def migrate_mentions_checkpoint(db: Session, data: dict, agent_name: str, agent_id: int, dry_run: bool = False) -> None:
    """Migrate mentions checkpoint from reply_guy_user_ids.json to TwitterQueryCheckpoint table."""
    if 'mentions' not in data:
        print("No mentions checkpoint found")
        return

    last_tweet_id = data['mentions']

    if dry_run:
        logger.info(f"Would create mentions checkpoint: {last_tweet_id} for agent: {agent_id}")
        return

    checkpoint = TwitterQueryCheckpoint(
        agent_name=agent_name,
        user_id=agent_id,
        query_type=QueryType.USER_MENTIONS,
        last_tweet_id=last_tweet_id,
    )
    db.merge(checkpoint)
    db.commit()


def migrate_followers_checkpoints(db: Session, data: dict, agent_name, dry_run: bool = False) -> None:
    """Migrate follower checkpoints from reply_guy_followers_last_tweet_id.json."""
    for username, last_tweet_id in data.items():
        if dry_run:
            logger.info(f"Would create follower checkpoint for {username}: {last_tweet_id}")
            continue

        # Only check user existence if not in dry run mode
        user = db.query(TwitterUser).filter_by(username=username).first()
        if not user:
            raise MigrationError(f"User {username} not found in users table")

        checkpoint = TwitterQueryCheckpoint(
            agent_name=agent_name,
            user_id=user.user_id,
            query_type=QueryType.USER_TWEETS,
            last_tweet_id=last_tweet_id,
        )
        db.merge(checkpoint)

    if not dry_run:
        db.commit()


async def migrate(
    db: Session,
    dry_run: bool = False,
    backup: bool = True,
    profile_name: str = "vito",
    files_dir: Path | None = None,
):
    """
    Migrate data from JSON files to PostgresSQL database.

    Args:
        db: Database session
        dry_run: If True, only show what would be migrated without making changes.
        backup: If True, create a backup of JSON files before migration.
        profile_name: Name of the agent profile to use (default: "vito")
        files_dir: Override default JSON files directory (used in tests)
    """
    json_dir = files_dir or MigrationConfig.files_dir

    if backup:
        backup_dir = backup_json_files(json_dir)
        logger.info(f"Backup created at {backup_dir}")

    if dry_run:
        logger.info("DRY RUN - no changes will be made.")

    # Migration logic
    agent_id = await get_agent_id(db, profile_name, dry_run=dry_run)
    agent_name = get_env_or_raise(envs.AGENT_NAME)

    # 1. First migrate user IDs as other migrations depend on them
    user_ids_file = json_dir / "reply_guy_user_ids.json"
    if user_ids_file.exists():
        user_data = json.loads(user_ids_file.read_text())
        migrate_user_ids(db, user_data, dry_run=dry_run)
        logger.info("User IDs migrated successfully.")

    # 2. Migrate mentions checkpoint
    mentions_checkpoints_file = json_dir / "reply_guy_mentions_last_tweet_id.json"
    if mentions_checkpoints_file.exists():
        mentions_data = json.loads(mentions_checkpoints_file.read_text())
        migrate_mentions_checkpoint(db, mentions_data, agent_name, agent_id, dry_run=dry_run)
        logger.info("Mentions checkpoint migrated successfully.")

    # 3. Migrate follower checkpoints
    follower_checkpoints_file = json_dir / "reply_guy_followers_last_tweet_id.json"
    if follower_checkpoints_file.exists():
        follower_data = json.loads(follower_checkpoints_file.read_text())
        migrate_followers_checkpoints(db, follower_data, agent_name, dry_run=dry_run)
        logger.info("Follower checkpoints migrated successfully.")
