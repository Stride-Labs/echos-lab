import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from echos_lab.db.models import Base

# get path of _this_ file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database URL
DB_PATH = os.getenv("SQLITE_DB_PATH", f"{BASE_DIR}/data/agents.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Create SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_database():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


class DBSession:
    def __enter__(self):
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()


def get_db():
    """Get DB session as a context manager."""
    return DBSession()


def get_db_session():
    """Get a direct DB session. Note: Remember to close the session manually."""
    return SessionLocal()


if __name__ == "__main__":
    create_database()
    print("Database and tables created successfully.")
