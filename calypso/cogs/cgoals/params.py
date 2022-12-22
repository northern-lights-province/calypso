import functools

import disnake
from disnake.ext import commands
from rapidfuzz import fuzz, process

from calypso import db, models
from . import queries


async def cg_autocomplete(
    _: disnake.ApplicationCommandInteraction, arg: str, key=lambda b: b.name, include_complete=False
):
    async with db.async_session() as session:
        if include_complete:
            cgs = await queries.get_all_cgs(session)
        else:
            cgs = await queries.get_active_cgs(session)

    if not arg:
        results = cgs[:25]
    else:
        names = [key(d) for d in cgs]
        results = process.extract(arg, names, scorer=fuzz.partial_ratio)
        results = [cgs[idx] for name, score, idx in results]
    return {g.name: str(g.id) for g in results}


async def cg_converter(_: disnake.ApplicationCommandInteraction, arg: str) -> models.CommunityGoal:
    try:
        cg_id = int(arg)
    except ValueError as e:
        raise ValueError("Invalid goal selection") from e
    async with db.async_session() as session:
        cg = await queries.get_cg_by_id(session, cg_id)
    return cg


def cg_param(default=..., include_complete=True, **kwargs) -> commands.Param:
    # noinspection PyTypeChecker
    return commands.Param(
        default,
        autocomplete=functools.partial(cg_autocomplete, include_complete=include_complete),
        converter=cg_converter,
        **kwargs
    )
