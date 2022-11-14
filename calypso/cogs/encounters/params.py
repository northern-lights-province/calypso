import disnake
from disnake.ext import commands
from rapidfuzz import fuzz, process

from .client import EncounterRepository


async def biome_autocomplete(_: disnake.ApplicationCommandInteraction, arg: str):
    tiers = EncounterRepository.tiers
    biome_names = set(t.biome for t in tiers)

    if not arg:
        return list(biome_names)[:10]
    results = process.extract(arg, biome_names, scorer=fuzz.partial_ratio)
    return [name for name, score, idx in results]


def biome_param(default=..., **kwargs) -> commands.Param:
    return commands.Param(default, autocomplete=biome_autocomplete, **kwargs)
