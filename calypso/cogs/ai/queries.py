from sqlalchemy import select

from calypso import models


async def get_chat_thread(session, thread_id: int) -> models.AIOpenEndedChat | None:
    stmt = select(models.AIOpenEndedChat).where(models.AIOpenEndedChat.thread_id == thread_id)
    result = await session.execute(stmt)
    return result.scalar()


async def get_chat_messages(session, chat_id: int) -> list[models.AIChatMessageRaw]:
    stmt = (
        select(models.AIChatMessageRaw)
        .where(models.AIChatMessageRaw.chat_id == chat_id)
        .order_by(models.AIChatMessageRaw.id)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
