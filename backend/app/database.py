from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True, # This option enables the connection pool to check if a connection is still alive before using it, which helps prevent errors due to stale or closed connections.
)

SessionLocal = sessionmaker(
    bind=engine, #binding the sessionmaker to the engine, which allows it to create sessions that are connected to the specified database engine
    autoflush=False, #This option disables the automatic flushing of changes to the database before certain operations, giving you more control over when changes are persisted.
    autocommit=False, #This option disables the automatic committing of transactions after each operation, allowing you to manage transactions manually and control when changes are committed to the database.
    class_=Session, #specifying the class to be used for creating session instances, which in this case is the SQLAlchemy Session class
)


class Base(DeclarativeBase): #defining a base class for all database models
    pass



def get_db():
    with SessionLocal() as session: #creating a new database session using the SessionLocal factory 
        yield session #yielding the session to be used within the context of the "async with" statement, allowing for proper resource management and cleanup after use

db_session = Annotated[Session, Depends(get_db)]    # Dependency injection for database session management, 
                                #     allowing FastAPI to automatically provide a database session to route handlers that require it.nnnv