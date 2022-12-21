import disnake
from disnake.ext import commands
from rapidfuzz import fuzz, process

from calypso import db, models
from . import queries


async def cg_autocomplete(_: disnake.ApplicationCommandInteraction, arg: str, key=lambda b: b.name):
    async with db.async_session() as session:
        cgs = await queries.get_active_cgs(session)

    if not arg:
        results = cgs[:25]
    else:
        names = [key(d) for d in cgs]
        fuzzy_map = {key(d): d for d in cgs}
        results = process.extract(arg, names, scorer=fuzz.partial_ratio)
        results = [fuzzy_map[name] for name, score in results]
    return {b.name: b.id for b in results}


async def cg_converter(_: disnake.ApplicationCommandInteraction, arg: str) -> models.CommunityGoal:
    try:
        cg_id = int(arg)
    except ValueError as e:
        raise ValueError("Invalid goal selection") from e
    async with db.async_session() as session:
        cg = await queries.get_cg_by_id(session, cg_id)
    return cg


def cg_param(default=..., **kwargs) -> commands.Param:
    return commands.Param(default, autocomplete=cg_autocomplete, converter=cg_converter, **kwargs)
