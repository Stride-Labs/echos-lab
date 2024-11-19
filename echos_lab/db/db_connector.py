from sqlalchemy.orm import Session
from echos_lab.db.models import TGMessage


def add_tg_message(db: Session, username: str, message: str, chat_id: str | int):
    new_tg_message = TGMessage(user_id=username, content=message, chat_id=chat_id)
    db.add(new_tg_message)
    db.commit()


def get_tg_messages(db: Session, chat_id: int, history: int = 100):
    return (
        db.query(TGMessage)
        .filter(TGMessage.chat_id == chat_id)
        .order_by(TGMessage.created_at.desc())
        .limit(history)
        .all()
    )
