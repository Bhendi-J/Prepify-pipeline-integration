from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import db_session
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import create as create_user
from app.repositories.user_repo import get_by_email
from app.schemas.user import Token, UserCreate, UserRead


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: db_session) -> UserRead:
    #reject duplicate registrations before creating a new account
    existing_user = get_by_email(db, user_in.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = create_user(
        db,
        {
            "email": user_in.email,
            "hashed_password": hash_password(user_in.password),
        },
    )
    return user


@router.post("/login", response_model=Token)
def login(db: db_session, form_data: OAuth2PasswordRequestForm = Depends()) -> Token: # Depends() has no default value, so FastAPI will automatically extract the form data from the request body and pass it to the function. The form data is expected to be in the format of an OAuth2 password grant request, which includes a username and password.
    #authenticate with the email stored in the OAuth username field
    user = get_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=30),
    )
    return Token(access_token=access_token)