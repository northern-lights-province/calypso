from sqlalchemy import select
from sqlalchemy.orm import selectinload

from calypso import models


async def get_all_cgs(session, load_contributions=False) -> list[models.CommunityGoal]:
    stmt = select(models.CommunityGoal)
    if load_contributions:
        stmt = stmt.options(selectinload(models.CommunityGoal.contributions))
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_active_cgs(session, load_contributions=False) -> list[models.CommunityGoal]:
    """Returns a list of all active CGs."""
    stmt = select(models.CommunityGoal).where(models.CommunityGoal.funded_cp < models.CommunityGoal.cost_cp)
    if load_contributions:
        stmt = stmt.options(selectinload(models.CommunityGoal.contributions))
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_cg_by_id(session, cg_id: int, load_contributions=False) -> models.CommunityGoal:
    stmt = select(models.CommunityGoal).where(models.CommunityGoal.id == cg_id)
    if load_contributions:
        stmt = stmt.options(selectinload(models.CommunityGoal.contributions))
    result = await session.execute(stmt)
    cg = result.scalar()
    if cg is None:
        raise ValueError("This goal does not exist")
    return cg
