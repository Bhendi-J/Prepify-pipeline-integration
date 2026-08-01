from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.core.security import decode_access_token
from app.database import db_session
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login") #bearer token extractor used by protected routes and tokenUrl is the endpoint where clients can obtain a token by providing their credentials


def get_current_user(db: db_session, token: str = Depends(oauth2_scheme)) -> User:
    #resolve the current authenticated user from the access token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        if user_id is None:
            raise ValueError("Missing user id in token")

        user = db.get(User, int(user_id))
        if user is None:
            raise ValueError("User not found")
        return user
    except (ValueError, TypeError, InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )