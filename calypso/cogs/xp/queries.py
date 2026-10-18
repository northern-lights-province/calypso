from sqlalchemy import select

from calypso import models


async def get_player_xp(session, guild_id: int, member_id: int) -> models.XPPlayer | None:
    """Get a player's XP object."""
    stmt = select(models.XPPlayer).where(
        (models.XPPlayer.member_id == member_id) & (models.XPPlayer.guild_id == guild_id)
    )
    return (await session.execute(stmt)).scalar()


async def get_channel_config(session, channel_id: int) -> models.XPChannelConfig | None:
    stmt = select(models.XPChannelConfig).where(models.XPChannelConfig.channel_id == channel_id)
    return (await session.execute(stmt)).scalar()


async def get_channel_configs(session, guild_id: int) -> list[models.XPChannelConfig]:
    stmt = select(models.XPChannelConfig).where(models.XPChannelConfig.guild_id == guild_id)
    return (await session.execute(stmt)).scalars().all()


async def get_channel_config_from_hierarchy(
    session, guild_id: int, channel_id: int, category_id: int | None = None, thread_id: int | None = None
) -> models.XPChannelConfig:
    """Get a channel's XP config, taking into account the channel hierarchy (specific beats general), or empty default
    if one does not exist."""
    result = None
    # thread
    if thread_id is not None:
        stmt = select(models.XPChannelConfig).where(models.XPChannelConfig.channel_id == thread_id)
        result = (await session.execute(stmt)).scalar()

    # channel
    if result is None:
        stmt = select(models.XPChannelConfig).where(models.XPChannelConfig.channel_id == channel_id)
        result = (await session.execute(stmt)).scalar()

    # category
    if result is None and category_id is not None:
        stmt = select(models.XPChannelConfig).where(models.XPChannelConfig.channel_id == category_id)
        result = (await session.execute(stmt)).scalar()

    # default
    if result is None:
        result = models.XPChannelConfig(guild_id=guild_id, channel_id=channel_id, xp_multiplier=1.0)

    return result
