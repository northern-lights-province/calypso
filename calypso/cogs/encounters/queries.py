from sqlalchemy import delete, select

from calypso import models


async def get_encounter_channel(session, channel_id: int) -> models.EncounterChannel | None:
    stmt = select(models.EncounterChannel).where(models.EncounterChannel.channel_id == channel_id)
    result = await session.execute(stmt)
    return result.scalar()


async def get_all_encounter_channels(session) -> list[models.EncounterChannel]:
    stmt = select(models.EncounterChannel)
    result = await session.execute(stmt)
    return result.scalars().all()


async def delete_encounter_channel(session, channel_id: int):
    await session.execute(delete(models.EncounterChannel).where(models.EncounterChannel.channel_id == channel_id))


# ==== ai ====
async def get_summary_by_id(session, summary_id: int) -> models.EncounterAISummary:
    stmt = select(models.EncounterAISummary).where(models.EncounterAISummary.id == summary_id)
    result = await session.execute(stmt)
    summary = result.scalar()
    if summary is None:
        raise ValueError("That summary does not exist")
    return summary
