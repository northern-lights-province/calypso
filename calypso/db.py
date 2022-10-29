import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/calypso.db")

engine = create_async_engine(f"sqlite+aiosqlite:///{DATA_PATH}", echo=False)
async_session = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=AsyncSession
)

Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
