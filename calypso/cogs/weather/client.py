import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel

from calypso.utils.httpclient import BaseClient
from .city import LatLon


# ==== response models ====
class _WeatherDetail(BaseModel):
    id: int
    main: str
    description: str
    icon: str


class _WeatherMain(BaseModel):
    temp: float
    pressure: int
    humidity: int
    temp_min: float
    temp_max: float


class _WeatherWind(BaseModel):
    speed: float
    deg: int


class _WeatherSystemInfo(BaseModel):
    country: str
    sunrise: datetime.datetime
    sunset: datetime.datetime
    type: Optional[int] = None
    id: Optional[int] = None
    message: Optional[Any] = None


class CurrentWeather(BaseModel):
    coord: LatLon
    weather: List[_WeatherDetail]
    base: str
    main: _WeatherMain
    visibility: Optional[int] = None
    wind: _WeatherWind
    clouds: Dict[str, int]
    dt: datetime.datetime
    sys: _WeatherSystemInfo
    id: int
    name: str
    cod: int


# ==== weather codes ====
# https://openweathermap.org/weather-conditions
WEATHER_DESC = {
    200: "It's thundering, with light rain.",
    201: "It's thundering, with rain.",
    202: "It's thundering, with rain pouring down.",
    210: "There's the occasional rumble of thunder.",
    211: "It's thundering.",
    212: "Lightning is striking multiple times each minute.",
    221: "There's a ragged thunderstorm.",
    230: "It's thundering, with rain sprinkling down.",
    231: "It's thundering, with rain.",
    232: "It's thundering, with the occasional downpour.",
    300: "It's gently drizzling.",
    301: "It's drizzling.",
    302: "It's drizzling, with the occasional downpour.",
    310: "It's gently drizzling.",
    311: "It's drizzling.",
    312: "It's drizzling, with the occasional downpour.",
    313: "It's showering, with the occasional reprieve.",
    314: "It's pouring, with the occasional reprieve.",
    321: "It's raining.",
    500: "It's showering.",
    501: "It's raining.",
    502: "It's raining quite heavily.",
    503: "It's pouring.",
    504: "It's raining harder than it's ever rained before.",
    511: "It's raining sheets of freezing water.",
    520: "It's drizzling, with the occasional downpour.",
    521: "It's showering, with the occasional reprieve.",
    522: "It's pouring, with the occasional reprieve.",
    531: "It's pouring, with the occasional reprieve.",
    600: "A light dusting of snowflakes is falling from the sky.",
    601: "A dusting of snowflakes is falling.",
    602: "It's snowing heavily.",
    611: "A sheet of freezing rain is falling.",
    612: "It's drizzling freezing rain.",
    613: "It's showering freezing rain.",
    615: "It's showering freezing rain.",
    616: "A sheet of freezing rain is falling.",
    621: "It's showering freezing rain.",
    622: "A sheet of freezing rain is falling.",
    701: "It's misty.",
    711: "It's smoky.",
    721: "It's hazy.",
    731: "It's dusty.",
    741: "It's foggy.",
    751: "It's sandy.",
    761: "It's dusty.",
    762: "Ash from a volcanic eruption is clouding the air.",
    771: "Violent gusts of wind and rain whip through the area.",
    781: "There's a tornado.",
    800: "There's a clear sky.",
    801: "There are a few clouds in the sky.",
    802: "There are a handful of scattered clouds in the sky.",
    803: "There are a good number of clouds in the sky.",
    804: "It's overcast.",
}


# ==== client ===
class WeatherClient(BaseClient):
    SERVICE_BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, http: aiohttp.ClientSession, api_key: str):
        super().__init__(http)
        self.api_key = api_key

    async def get_current_weather_by_city_id(self, city_id: int) -> CurrentWeather:
        data = await self.get("/weather", params={"id": city_id, "appid": self.api_key})
        return CurrentWeather.parse_obj(data)
