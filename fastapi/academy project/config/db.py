import os

from dotenv import load_dotenv
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


load_dotenv()

DATABASE_URL = os.environ["database_url"]

_ASYNC_URL = make_url(DATABASE_URL).set(drivername="postgresql+psycopg")

engine = create_async_engine(_ASYNC_URL, pool_pre_ping=True, future=True)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
	async with SessionLocal() as session:
		yield session
