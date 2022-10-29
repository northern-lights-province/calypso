import disnake
from disnake.ext import commands
from rapidfuzz import fuzz, process

from calypso import db, models
from . import utils
from .city import City, CityRepository


# ==== city ====
async def city_autocomplete(_: disnake.ApplicationCommandInteraction, arg: str, key=lambda c: f"{c.name}, {c.state}"):
    if not arg:
        city_results = CityRepository.cities[:5]
    else:
        names = [key(d) for d in CityRepository.cities]
        results = process.extract(arg, names, scorer=fuzz.partial_ratio)
        city_results = [CityRepository.cities[idx] for name, score, idx in results]
    return [f"{c.name}, {c.state} - {c.id}" for c in city_results]


def city_converter(_: disnake.ApplicationCommandInteraction, arg: str) -> City:
    try:
        _, city_id = arg.rsplit("- ", 1)
        city_id = int(city_id)
    except ValueError as e:
        raise ValueError("Invalid city selection") from e
    city = CityRepository.get_city(city_id)
    if city is None:
        raise ValueError("That city doesn't exist")
    return city


def city_param(default=..., **kwargs) -> commands.Param:
    return commands.Param(default, autocomplete=city_autocomplete, converter=city_converter, **kwargs)


# ==== biome ====
async def biome_autocomplete(inter: disnake.ApplicationCommandInteraction, arg: str, key=lambda b: b.name):
    async with db.async_session() as session:
        available_biomes = await utils.get_biomes_by_guild(session, inter.guild_id)

    if not arg:
        biome_results = available_biomes[:5]
    else:
        names = [key(d) for d in available_biomes]
        fuzzy_map = {key(d): d for d in available_biomes}
        results = process.extract(arg, names, scorer=fuzz.partial_ratio)
        biome_results = [fuzzy_map[name] for name, score in results]
    return [f"{b.name} - {b.id}" for b in biome_results]


async def biome_converter(_: disnake.ApplicationCommandInteraction, arg: str) -> models.WeatherBiome:
    try:
        _, biome_id = arg.rsplit("- ", 1)
        biome_id = int(biome_id)
    except ValueError as e:
        raise ValueError("Invalid biome selection") from e
    async with db.async_session() as session:
        biome = await utils.get_biome_by_id(session, biome_id)
    return biome


def biome_param(default=..., **kwargs) -> commands.Param:
    return commands.Param(default, autocomplete=biome_autocomplete, converter=biome_converter, **kwargs)
