from echos_lab.db.models import User
from echos_lab.db.db_setup import SessionLocal
from dotenv import load_dotenv
import os

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")


def seed_database():
    db = SessionLocal()

    # Create users if they don't exist
    existing_users = db.query(User).all()
    print(f"Existing users: {existing_users}")
    if not existing_users:
        users = [User(username="echo_in_void", email="testecho@airmail.cc")]
        db.add_all(users)
        db.commit()

    db.close()


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
