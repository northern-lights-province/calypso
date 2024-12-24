from typing import List, Optional

import disnake
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from calypso import models
from . import extreme_weather
from .client import CurrentWeather, WEATHER_DESC


async def get_biome_by_id(session, biome_id: int, guild_id: int = None) -> models.WeatherBiome:
    """
    Gets a biome by ID. If the biome is not found or the guild ID is supplied and it doesn't match, raises a ValueError
    """
    result = await session.execute(select(models.WeatherBiome).where(models.WeatherBiome.id == biome_id))
    biome = result.scalar()
    # check: must exist and be on the right server
    if biome is None or (guild_id is not None and biome.guild_id != guild_id):
        raise ValueError("This biome does not exist")
    return biome


async def get_biomes_by_guild(session, guild_id: int, load_channel_links=False) -> List[models.WeatherBiome]:
    """Returns a list of all biomes in a guild."""
    stmt = select(models.WeatherBiome).where(models.WeatherBiome.guild_id == guild_id)
    if load_channel_links:
        stmt = stmt.options(selectinload(models.WeatherBiome.channels))
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_channel_map_by_id(session, channel_id: int, load_biome=False) -> Optional[models.WeatherChannelMap]:
    """Returns the channel's channel map, or None"""
    stmt = select(models.WeatherChannelMap).where(models.WeatherChannelMap.channel_id == channel_id)
    if load_biome:
        stmt = stmt.options(selectinload(models.WeatherChannelMap.biome))
    result = await session.execute(stmt)
    return result.scalar()


async def get_weather_biome_by_channel(session, channel) -> Optional[models.WeatherBiome]:
    """Gets the weather biome in this channel, or None if the channel is not linked."""
    if isinstance(channel, disnake.Thread):
        channel_id = channel.parent_id
    else:
        channel_id = channel.id

    channel_link = await get_channel_map_by_id(session, channel_id, load_biome=True)
    if channel_link is None:
        return None
    return channel_link.biome


def k_to_f(deg_k: float):
    """Kelvin to Fahrenheit"""
    return deg_k * 1.8 - 459.67


def k_to_c(deg_k: float):
    """Kelvin to Celsius"""
    return deg_k - 273.15


def ms_to_mph(ms: float):
    """m/s to mph"""
    return ms * 2.237


def m_to_ft(meters: float):
    return meters * 3.281


def weather_temp(biome: models.WeatherBiome, weather: CurrentWeather) -> float:
    """Given the weather, return the temperature in Kelvin, taking into account the biome mod."""
    return weather.main.temp + (biome.temp_mod or 0) / 1.8


def weather_desc(weather: CurrentWeather) -> str:
    # wind
    if weather.wind.speed < 0.2:
        wind_desc = "calm"
    elif weather.wind.speed < 4.4:
        wind_desc = "light"
    elif weather.wind.speed < 6:
        wind_desc = "moderate"
    elif weather.wind.speed < 8:
        wind_desc = "blustery"
    elif weather.wind.speed < 10:
        wind_desc = "gusty"
    elif weather.wind.speed < 14:
        wind_desc = "strong"
    elif weather.wind.speed < 20:
        wind_desc = "a gale"
    elif weather.wind.speed < 32:
        wind_desc = "violent"
    else:
        wind_desc = "hurricane-like"

    if 0 <= weather.wind.deg < 45:
        wind_direction = "north"
    elif 45 <= weather.wind.deg < 90:
        wind_direction = "northeast"
    elif 90 <= weather.wind.deg < 135:
        wind_direction = "east"
    elif 135 <= weather.wind.deg < 180:
        wind_direction = "southeast"
    elif 180 <= weather.wind.deg < 225:
        wind_direction = "south"
    elif 225 <= weather.wind.deg < 270:
        wind_direction = "southwest"
    elif 270 <= weather.wind.deg < 315:
        wind_direction = "west"
    else:
        wind_direction = "northwest"

    if not weather.visibility:
        return (
            f"The wind is {wind_desc}, at {int(ms_to_mph(weather.wind.speed))} mph towards the {wind_direction}. "
            f"The humiditity is {weather.main.humidity}%."
        )

    # visibility
    visibility_ft = m_to_ft(weather.visibility)
    if visibility_ft > 5280:
        visibility_detail = f"{round(visibility_ft / 5280)} mi."
    else:
        visibility_detail = f"{int(visibility_ft)} ft."

    if weather.visibility > 2000:
        visibility_desc = "good"
    elif weather.visibility > 500:
        visibility_desc = "fair"
    else:
        visibility_desc = "poor"

    return (
        f"The wind is {wind_desc}, at {int(ms_to_mph(weather.wind.speed))} mph towards the {wind_direction}. "
        f"Visibility is {visibility_desc} ({visibility_detail}) with a humidity of {weather.main.humidity}%."
    )


class WeatherDescFull(BaseModel):
    desc: str
    fields: list[tuple[str, str]]


def weather_desc_full(biome: models.WeatherBiome, weather: CurrentWeather) -> WeatherDescFull:
    temp = weather_temp(biome, weather)
    degrees_f = int(k_to_f(temp))

    desc = f"It's currently {degrees_f}\u00b0F ({int(k_to_c(temp))}\u00b0C) in {biome.name}. {weather_desc(weather)}"

    is_heavy_precipitation = False
    is_lightly_obscured = False
    fields = []
    for weather_detail in weather.weather:
        fields.append((weather_detail.main, WEATHER_DESC.get(weather_detail.id, weather_detail.description)))
        is_heavy_precipitation = is_heavy_precipitation or extreme_weather.is_heavy_precipitation(weather_detail.id)
        is_lightly_obscured = is_lightly_obscured or extreme_weather.is_lightly_obscured(weather_detail.id)

    # extreme weather
    if degrees_f <= 0:
        fields.append(("Extreme Cold", extreme_weather.EXTREME_COLD))
    if degrees_f >= 100:
        fields.append(("Extreme Heat", extreme_weather.EXTREME_HEAT))
    if weather.wind.speed >= 10:
        fields.append(("Strong Wind", extreme_weather.STRONG_WIND))
    if is_heavy_precipitation:
        fields.append(("Heavy Precipitation", extreme_weather.HEAVY_PRECIPITATION))
    elif is_lightly_obscured:
        fields.append(("Lightly Obscured", extreme_weather.LIGHTLY_OBSCURED))
    return WeatherDescFull(desc=desc, fields=fields)


def weather_embed(biome: models.WeatherBiome, weather: CurrentWeather) -> disnake.Embed:
    embed = disnake.Embed()
    embed.title = f"Current Weather in {biome.name}"
    embed.colour = disnake.Color.random()
    embed.set_author(
        icon_url=f"http://openweathermap.org/img/wn/{weather.weather[0].icon}@2x.png", name=weather.weather[0].main
    )

    if biome.image_url:
        embed.set_thumbnail(url=biome.image_url)

    desc = weather_desc_full(biome, weather)
    embed.description = desc.desc
    for name, value in desc.fields:
        embed.add_field(name=name, value=value, inline=False)

    return embed
