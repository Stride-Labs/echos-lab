import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from echos_lab.db.migrations import json_to_postgres
from echos_lab.db.models import QueryType, TwitterQueryCheckpoint, TwitterUser
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.twitter import twitter_client

# Path constants
JSON_FILES_DIR = Path(__file__).parent.parent / "fixtures" / "legacy_json_db"
PROFILES_DIR = Path(__file__).parent.parent.parent / "echos_lab/engines/personalities/profiles"
MOCKED_PROFILE_PATH = Path(__file__).parent.parent / "fixtures/test_profile.yaml"


@pytest.fixture
def mock_profile_path(monkeypatch):
    def mock_get_path(agent_name: str) -> str:
        path = str(PROFILES_DIR / f"{agent_name}.yaml")
        print(f"\nMocked profile path: {path}")
        return path

    monkeypatch.setattr(AgentProfile, '_get_profile_path', mock_get_path)


@pytest.fixture
def mock_twitter_api(monkeypatch):
    """Mock Twitter API calls"""

    async def mock_get_user_id(*args, **kwargs):
        # Return a dummy user ID for testing
        return 11111

    monkeypatch.setattr(twitter_client, 'get_user_id_from_username', mock_get_user_id)


@pytest.fixture
def reset_db(db: Session):
    """Clean up database before each test"""
    db.query(TwitterQueryCheckpoint).delete()
    db.query(TwitterUser).delete()
    db.commit()
    yield


@pytest.fixture
def clean_backups():
    """Remove any existing backups before tests."""
    for backup_dir in JSON_FILES_DIR.parent.glob("backup_*"):
        shutil.rmtree(backup_dir)
    yield


@pytest.fixture
def setup_test_files():
    """Setup test profile for integration tests."""
    # Create profiles directory if needed
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # Copy mock profile to where the code expects to find it
    if not MOCKED_PROFILE_PATH.exists():
        raise FileNotFoundError(f"Mock profile not found at {MOCKED_PROFILE_PATH}")
    shutil.copy(MOCKED_PROFILE_PATH, PROFILES_DIR / "test.yaml")

    yield

    # Cleanup: remove mock profile
    if (PROFILES_DIR / "test.yaml").exists():
        (PROFILES_DIR / "test.yaml").unlink()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_profile_path", "mock_twitter_api", "reset_db", "setup_test_files", "clean_backups")
class TestDBMigration:
    @pytest.fixture(autouse=True)
    def setup_test_db(self, db: Session):
        """Reset database before each test"""
        db.query(TwitterQueryCheckpoint).delete()
        db.query(TwitterUser).delete()
        db.commit()

    async def test_full_migration(self, db: Session):
        """Test the full migration process."""
        # Debugging the JSON files
        print(f"\nJSON_FILES_DIR: {JSON_FILES_DIR}")
        users_file = JSON_FILES_DIR / "reply_guy_user_ids.json"
        print(f"Users file exists: {users_file.exists()}")
        if users_file.exists():
            with open(users_file) as f:
                print(f"Users file content: {f.read()}")

        await json_to_postgres.migrate(
            db=db,
            dry_run=False,
            backup=False,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )

        # Verify users were migrated
        users = db.query(TwitterUser).all()
        print(f"Users in DB after migration: {[u.username for u in users]}")
        user_map = {u.username: u.user_id for u in users}
        assert "test_user" in user_map
        print(">>>> DONE <<<<")
        # Verify users were migrated
        users = db.query(TwitterUser).all()
        user_map = {u.username: u.user_id for u in users}
        assert "test_user" in user_map
        assert "test_follower" in user_map
        assert user_map["test_user"] == 12345

        # Verify mentions checkpoint
        mentions_checkpoint = (
            db.query(TwitterQueryCheckpoint)
            .filter_by(user_id=11111, query_type=QueryType.USER_MENTIONS)  # test_agent id
            .first()
        )
        assert mentions_checkpoint is not None
        assert mentions_checkpoint.last_tweet_id == 999888777

        # Verify follower checkpoint
        follower_checkpoint = (
            db.query(TwitterQueryCheckpoint)
            .filter_by(user_id=67890, query_type=QueryType.USER_TWEETS)  # test_follower id
            .first()
        )
        assert follower_checkpoint is not None
        assert follower_checkpoint.last_tweet_id == 444555666

    async def test_dry_run(self, db: Session):
        """Test dry run doesn't modify database."""
        # Run migration in dry run mode
        await json_to_postgres.migrate(
            db=db,
            dry_run=True,
            backup=False,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )

        # Verify no data was written
        assert db.query(TwitterUser).count() == 0
        assert db.query(TwitterQueryCheckpoint).count() == 0

    async def test_backup_creation(self, db: Session):
        """Test backup functionality."""
        await json_to_postgres.migrate(
            db=db,
            dry_run=False,
            backup=True,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )

        # Check that backup dir exists and contains files
        backup_dirs = list(JSON_FILES_DIR.parent.glob("backup_*"))
        assert len(backup_dirs) == 1
        backup_dir = backup_dirs[0]

        # Verify backup files
        assert (backup_dir / "reply_guy_user_ids.json").exists()
        assert (backup_dir / "reply_guy_mentions_last_tweet_id.json").exists()
        assert (backup_dir / "reply_guy_followers_last_tweet_id.json").exists()

    async def test_full_migration_with_real_data(self, db: Session):
        """Test migration with production-like data structure."""
        await json_to_postgres.migrate(
            db=db,
            dry_run=False,
            backup=False,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )

        # Test data integrity
        users = db.query(TwitterUser).all()
        assert len(users) == 3  # All users migrated

        # Test relationships are preserved
        checkpoints = db.query(TwitterQueryCheckpoint).all()
        assert len(checkpoints) == 2  # 1 mention + 1 follower checkpoint

        # Test specific data points
        followers = db.query(TwitterUser).filter(TwitterUser.username.in_(["test_user", "test_follower"])).all()
        assert len(followers) == 2

    async def test_idempotent_migration(self, db: Session):
        """Test that running migration multiple times is safe."""
        # Run migration twice
        await json_to_postgres.migrate(
            db=db,
            dry_run=False,
            backup=False,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )
        await json_to_postgres.migrate(
            db=db,
            dry_run=False,
            backup=False,
            profile_name="test",
            files_dir=JSON_FILES_DIR,
        )

        # Should have same data as single migration
        users = db.query(TwitterUser).all()
        assert len(users) == 3

    async def test_failed_migration_recovery(self, db: Session):
        """Test backup restoration works if migration fails."""
        # Intentionally cause failure mid-migration
        with patch('json.loads') as mock_loads:
            mock_loads.side_effect = Exception("Simulated failure")
            with pytest.raises(Exception):
                await json_to_postgres.migrate(
                    db=db,
                    backup=True,
                    profile_name="test",
                    files_dir=JSON_FILES_DIR,
                )

        # Verify backup exists
        backup_dirs = list(JSON_FILES_DIR.parent.glob("backup_*"))
        assert len(backup_dirs) == 1
