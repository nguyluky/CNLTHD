from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models.user import User
from app.schemas.user import UserCreate


def create_user(db: Session, data: UserCreate) -> User:
    logger.info(f"Creating user with email: {data.email}")
    user = User(name=data.name, email=data.email)
    db.add(user)
    try:
        db.commit()
        logger.info(f"User created successfully. ID: {user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user {data.email}: {str(e)}", exc_info=True)
        raise
    db.refresh(user)
    return user
