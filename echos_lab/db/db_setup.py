from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env
from echos_lab.db.models import Base

# Database configuration
POSTGRES_DATABASE_URL = get_env(envs.POSTGRES_DATABASE_URL)

if POSTGRES_DATABASE_URL:
    # Using Postgres
    engine = create_engine(POSTGRES_DATABASE_URL)
else:
    # Fallback to SQLite
    default_path = str(Path(__file__).parent / "data" / "agents.db")
    db_path = Path(get_env(envs.SQLITE_DB_PATH, default_path))
    db_path.parent.mkdir(exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})  # SQLite specific

# Create SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get DB session using context manager for automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database and create all tables if needed."""
    Base.metadata.create_all(bind=engine)
