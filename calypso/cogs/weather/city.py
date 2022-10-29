import json
import os
from typing import Dict, List, Optional

from pydantic import BaseModel


# ==== models ====
class LatLon(BaseModel):
    lat: float
    lon: float


class City(BaseModel):
    id: int
    name: str
    state: str
    country: str
    coord: LatLon


# ==== repository ====
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "city.list.min.json")


class CityRepository:
    """Singleton class to hold all the cities"""

    cities: List[City] = []
    cities_by_id: Dict[int, City] = {}
    cities_by_name: Dict[str, City] = {}

    @classmethod
    def reload_cities(cls, data_path=DEFAULT_DATA_PATH, city_filter=lambda city: True):
        with open(data_path, "r") as f:
            raw_cities = json.load(f)
        parsed_cities = []
        for c in raw_cities:
            parsed_city = City.parse_obj(c)
            if city_filter(parsed_city):
                parsed_cities.append(parsed_city)
        city_id_map = {c.id: c for c in parsed_cities}
        city_name_map = {c.name: c for c in parsed_cities}

        cls.cities = parsed_cities
        cls.cities_by_id = city_id_map
        cls.cities_by_name = city_name_map

    @classmethod
    def get_city(cls, city_id: int) -> Optional[City]:
        return cls.cities_by_id.get(city_id)

    @classmethod
    def get_city_by_name(cls, city_name: str) -> Optional[City]:
        return cls.cities_by_name.get(city_name)
