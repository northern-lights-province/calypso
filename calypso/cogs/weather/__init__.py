from .cog import Weather
from .city import CityRepository
from . import utils


def setup(bot):
    CityRepository.reload_cities(city_filter=lambda c: c.country == "US")
    weather = Weather(bot)
    bot.add_cog(weather)
