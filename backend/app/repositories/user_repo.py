from sqlalchemy.orm import Session

from app.models.user import User

from app.schemas.user import UserRead, UserUpdate

def get_by_email(db: Session, email: str) -> User | None:
    #lookup helper used to check whether a user already exists for the given email
    return db.query(User).filter(User.email == email).first()


def create(db: Session, user_data: dict[str, str]) -> User:
    # persist a new user record using already-prepared values
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user