from collections import namedtuple

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from calypso import models

ContributionLeaderboardEntry = namedtuple("ContributionLeaderboardEntry", "user_id total_cp")


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
    return await _get_cg(session, stmt, load_contributions)


async def get_cg_by_slug(session, cg_slug: str, load_contributions=False) -> models.CommunityGoal:
    stmt = select(models.CommunityGoal).where(models.CommunityGoal.slug == cg_slug)
    return await _get_cg(session, stmt, load_contributions)


async def get_cg_contributions(session, cg_id: int) -> list[models.CommunityGoalContribution]:
    stmt = select(models.CommunityGoalContribution).where(models.CommunityGoalContribution.goal_id == cg_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_cg_contribution_leaderboard(session, cg_id: int) -> list[ContributionLeaderboardEntry]:
    query = """
    SELECT user_id, SUM(amount_cp) AS total
    FROM cg_contributions
        WHERE goal_id = :goal_id
    GROUP BY user_id
    ORDER BY total DESC
    """
    result = await session.execute(text(query).bindparams(goal_id=cg_id))
    return [ContributionLeaderboardEntry(*row) for row in result]


async def get_cg_contribution_leaderboard_all(session) -> list[ContributionLeaderboardEntry]:
    query = """
    SELECT user_id, SUM(amount_cp) AS total
    FROM cg_contributions
    GROUP BY user_id
    ORDER BY total DESC
    """
    result = await session.execute(text(query))
    return [ContributionLeaderboardEntry(*row) for row in result]


async def _get_cg(session, stmt, load_contributions) -> models.CommunityGoal:
    if load_contributions:
        stmt = stmt.options(selectinload(models.CommunityGoal.contributions))
    result = await session.execute(stmt)
    cg = result.scalar()
    if cg is None:
        raise ValueError("This goal does not exist")
    return cg
