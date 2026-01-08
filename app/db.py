from collections.abc import AsyncGenerator
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID #use to store users
from sqlalchemy.orm import relationship
from fastapi import Depends
DATABASE_URL = "sqlite+aiosqlite:///./test.db"


class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    posts= relationship("Post" , back_populates="user") #
class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    caption = Column(Text)
    url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="posts")

engine = create_async_engine(DATABASE_URL) ##connection to the DB
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():  # here we are creating the table for all classes in the Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) #It Gonna find all of the classes that inherit from declarative base and its gonna create inside the DB


async def get_async_session() -> AsyncGenerator[AsyncSession, None]: # accessing the created table
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
     yield SQLAlchemyUserDatabase(session, User)